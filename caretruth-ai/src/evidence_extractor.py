"""CareTruth AI — Evidence Extractor.

Extracts structured evidence findings from a facility record.
Every finding retains:
  - source_row_id   : 0-based row index
  - facility_name   : exact name from dataset
  - source_field    : column name
  - span            : verbatim substring (for citation grounding)
  - capability      : normalised capability label
  - polarity        : "positive" | "negative" | "uncertain" | "conditional"
  - constraint      : time/availability constraint if any
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from src import config


@dataclass
class EvidenceFinding:
    source_row_id:  int
    facility_name:  str
    source_field:   str
    span:           str          # verbatim original text (for citation)
    capability:     str          # normalised capability label
    polarity:       str          # positive | negative | uncertain | conditional
    constraint:     Optional[str] = None   # e.g. "not after 9 PM"


import ast
import json

# ── Keyword -> capability mapping ────────────────────────────────────────────
#   Each entry: (capability_label, keyword_patterns, negation_invert=False)
CAPABILITY_PATTERNS: list[tuple[str, list[str]]] = [
    ("generalSurgery",    config.SURGERY_KEYWORDS),
    ("cardiacSurgery",    config.CARDIAC_KEYWORDS),
    ("emergencyMedicine", config.EMERGENCY_KEYWORDS),
    ("anaesthesia",       config.ANAESTHESIA_KEYWORDS),
    ("radiology",         ["x-ray", "xray", "radiology", "mri", "ct scan", "ultrasound", "imaging"]),
    ("pathology",         ["pathology", "lab", "laboratory", "blood test", "diagnostic"]),
    ("icu",               ["icu", "intensive care", "critical care", "ventilator"]),
    ("orthopaedics",      ["ortho", "fracture", "bone", "joint replacement", "knee", "hip replacement"]),
    ("gynaecology",       ["gynaecolog", "gynecolog", "obstetric", "maternity", "delivery", "neonatal"]),
    ("paediatrics",       ["paediatric", "pediatric", "children", "neonatal", "infant"]),
    ("ophthalmology",     ["eye", "cataract", "lasik", "retina", "ophthalmol", "vision"]),
    ("dentistry",         ["dental", "dentist", "teeth", "tooth", "orthodont", "root canal"]),
    ("neurology",         ["neuro", "brain", "stroke", "epilepsy", "spine"]),
    ("dialysis",          ["dialysis", "kidney", "renal", "nephrology"]),
    ("physiotherapy",     ["physiotherapy", "physiotherapist", "rehabilitation", "rehab"]),
    ("pharmacy",          ["pharmacy", "pharmacist", "medicine", "drug store"]),
]

CAPABILITY_SPECIALTIES_MAP: dict[str, set[str]] = {
    "generalSurgery": {
        "generalsurgery", "laparoscopicsurgery", "advancelaproscopicsurgery",
        "laparoscopicsurgeon", "burngeneralsurgery", "uppergiandforegutsurgery",
        "colorectalsurgery", "traumasurgery"
    },
    "cardiacSurgery": {
        "cardiacsurgery", "cardiothoracicsurgery", "cardiovascularthoracicsurgery",
        "cardiologist"
    },
    "emergencyMedicine": {
        "emergencymedicine", "criticalcaremedicine", "traumacare"
    },
    "anaesthesia": {
        "anesthesia", "anaesthesia", "anaesthesiology", "anesthesiology"
    },
    "radiology": {
        "radiology", "diagnosticradiology", "interventionalradiology"
    },
    "pathology": {
        "pathology", "biochemistry", "hematology"
    },
    "icu": {
        "criticalcaremedicine", "intensivecare"
    },
    "orthopaedics": {
        "orthopedicsurgery", "arthroscopicsurgery", "jointreplacementsurgery",
        "orthopedicspinesurgery", "orthopedictraumaandfracturesurgery",
        "paediatricorthopaedicsurgery", "pediatricorthopedicsurgery",
        "footandankleorthopedicsurgery", "shoulderandelboworthopedicsurgery"
    },
    "gynaecology": {
        "gynecologyandobstetrics", "gynecologicalsurgery", "obstetricsandmaternitycare",
        "urogynecologyandreconstructivepelvissurgery"
    },
    "paediatrics": {
        "pediatrics", "paediatrics", "pediatricsurgery", "paediatricorthopaedicsurgery"
    },
    "ophthalmology": {
        "ophthalmology", "cataractandanteriorsegmentsurgery", "refractivesurgeryophthalmology",
        "vitreo-retinalsurgery", "squinteyesurgery"
    },
    "dentistry": {
        "dentistry", "oralsurgery", "oralandmaxillofacialsurgery",
        "dentoalveolarsurgery", "endodontics"
    },
    "neurology": {
        "neurology", "neurosurgery", "pediatricneurosurgery", "spineneurosurgery"
    },
    "dialysis": {
        "nephrology", "dialysis"
    },
    "physiotherapy": {
        "physiotherapy", "rehabilitation"
    },
    "pharmacy": {
        "pharmacy", "pharmacology"
    },
}

_NEGATION_RE = re.compile(
    r"\b(no|not|without|lack|unable|does not|cannot|no longer|"
    r"temporarily closed|closed|unavailable|not available)\b",
    re.IGNORECASE,
)

_TIME_CONSTRAINT_RE = re.compile(
    r"(after\s+\d{1,2}(?::\d{2})?\s*(?:AM|PM)?|"
    r"before\s+\d{1,2}(?::\d{2})?\s*(?:AM|PM)?|"
    r"not\s+(?:available\s+)?after\s+\d{1,2}(?:\s*(?:PM|AM))?|"
    r"\d{1,2}\s*(?:PM|AM)\s+only|"
    r"night(?:time)?|daytime only|weekdays only)",
    re.IGNORECASE,
)


def _parse_items(text: str) -> list[str]:
    """Parse text as JSON list if possible; else fallback to raw or comma-split."""
    t = text.strip()
    if not t or t.lower() in ("null", "[]", "none"):
        return []
    if t.startswith("[") and t.endswith("]"):
        try:
            parsed = json.loads(t)
            if isinstance(parsed, list):
                return [str(x).strip() for x in parsed if str(x).strip()]
        except Exception:
            try:
                parsed = ast.literal_eval(t)
                if isinstance(parsed, list):
                    return [str(x).strip() for x in parsed if str(x).strip()]
            except Exception:
                pass
    return [t]


def _matches_specialty(item: str, cap_label: str) -> bool:
    """Check if a specialty item matches the target capability label."""
    allowed = CAPABILITY_SPECIALTIES_MAP.get(cap_label)
    if not allowed:
        return False
    norm = re.sub(r"[^a-zA-Z0-9]", "", item.lower())
    return norm in allowed


def _sentence_context(text: str, match_start: int, match_end: int, window: int = 120) -> str:
    """Return surrounding text context for a match, stopping at sentence boundaries."""
    start = max(0, match_start - window)
    end   = min(len(text), match_end + window)
    snippet = text[start:end]
    # Find sentence boundaries within the snippet
    dot_before = snippet.rfind(".", 0, match_start - start)
    dot_after  = snippet.find(".", match_end - start)
    if dot_before >= 0:
        snippet = snippet[dot_before + 1:]
    if dot_after >= 0:
        snippet = snippet[:dot_after + 1]
    return snippet.strip().strip('"').strip("'")


def _has_negation_before(text: str, match_start: int, look_back: int = 60) -> bool:
    """Check if a negation word appears within look_back chars before match_start."""
    preceding = text[max(0, match_start - look_back):match_start]
    return bool(_NEGATION_RE.search(preceding))


def _extract_time_constraint(text: str, match_start: int, look_around: int = 120) -> Optional[str]:
    """Return a time constraint string if one appears near the match."""
    region = text[max(0, match_start - look_around): match_start + look_around]
    m = _TIME_CONSTRAINT_RE.search(region)
    return m.group(0).strip() if m else None


def extract_evidence_from_row(
    row: pd.Series,
    target_capabilities: Optional[list[str]] = None,
) -> list[EvidenceFinding]:
    """
    Extract all evidence findings from a single facility row.

    Args:
        row: A normalized DataFrame row (from data_loader.load_dataframe).
        target_capabilities: If provided, only extract for these capability labels.
                             If None, extract all.

    Returns:
        List of EvidenceFinding instances. All spans are verbatim from source fields.
    """
    findings: list[EvidenceFinding] = []
    row_id        = int(row["row_id"])
    facility_name = str(row["name"])

    # Fields to search with their original-case text
    text_fields = {
        "description": str(row.get("description", "")),
        "capability":  str(row.get("capability", "")),
        "procedure":   str(row.get("procedure", "")),
        "equipment":   str(row.get("equipment", "")),
        "specialties": str(row.get("specialties", "")),
    }

    for cap_label, keywords in CAPABILITY_PATTERNS:
        if target_capabilities and cap_label not in target_capabilities:
            continue

        for field_name, field_text in text_fields.items():
            if not field_text or field_text.strip().lower() in ("null", "[]", ""):
                continue

            # Case A: specialties field — strict specialty mapping
            if field_name == "specialties":
                items = _parse_items(field_text)
                for item in items:
                    if _matches_specialty(item, cap_label):
                        # Ensure item is a clean verbatim substring
                        if item in field_text:
                            already = any(
                                f.capability == cap_label
                                and f.source_field == field_name
                                and f.span == item
                                for f in findings
                            )
                            if not already:
                                findings.append(EvidenceFinding(
                                    source_row_id=row_id,
                                    facility_name=facility_name,
                                    source_field=field_name,
                                    span=item,
                                    capability=cap_label,
                                    polarity="positive",
                                    constraint=None,
                                ))
                continue

            # Case B: JSON list fields (procedure, capability, equipment)
            if field_name in ("procedure", "capability", "equipment"):
                items = _parse_items(field_text)
                for item in items:
                    item_lower = item.lower()
                    for kw in keywords:
                        kw_lower = kw.lower()
                        # Avoid false positives for generic surgery in non-surgical domains
                        if cap_label == "generalSurgery" and kw_lower in ("surgery", "surgical", "operation"):
                            non_general = ["dental", "teeth", "tooth", "eye", "cataract", "ortho", "bone", "cosmetic", "joint"]
                            if any(ng in item_lower for ng in non_general) and not any(g in item_lower for g in ["general", "appendix", "laparoscopic"]):
                                continue

                        if kw_lower in item_lower:
                            # Verbatim check: item must appear as a substring in the field_text
                            span = item
                            negated = bool(_NEGATION_RE.search(item_lower))
                            time_con = _extract_time_constraint(item_lower, item_lower.find(kw_lower))

                            if negated:
                                polarity = "negative"
                            elif time_con:
                                polarity = "conditional"
                            else:
                                polarity = "positive"

                            already = any(
                                f.capability == cap_label
                                and f.source_field == field_name
                                and f.span == span
                                for f in findings
                            )
                            if not already and span in field_text:
                                findings.append(EvidenceFinding(
                                    source_row_id=row_id,
                                    facility_name=facility_name,
                                    source_field=field_name,
                                    span=span,
                                    capability=cap_label,
                                    polarity=polarity,
                                    constraint=time_con,
                                ))
                            break  # one keyword match per item is enough
                continue

            # Case C: Free text fields (description)
            field_lower = field_text.lower()
            for kw in keywords:
                kw_lower = kw.lower()
                pos = field_lower.find(kw_lower)
                if pos != -1:
                    span = _sentence_context(field_text, pos, pos + len(kw))
                    if not span:
                        span = field_text[max(0, pos - 30): pos + len(kw) + 30].strip()

                    negated  = _has_negation_before(field_lower, pos)
                    time_con = _extract_time_constraint(field_lower, pos)

                    if negated:
                        polarity = "negative"
                    elif time_con:
                        polarity = "conditional"
                    else:
                        polarity = "positive"

                    # Verify that span is an exact verbatim substring
                    if span in field_text:
                        already = any(
                            f.capability == cap_label
                            and f.source_field == field_name
                            and f.span == span
                            for f in findings
                        )
                        if not already:
                            findings.append(EvidenceFinding(
                                source_row_id=row_id,
                                facility_name=facility_name,
                                source_field=field_name,
                                span=span,
                                capability=cap_label,
                                polarity=polarity,
                                constraint=time_con,
                            ))
                    break

    return findings


def extract_evidence_for_query(
    df: pd.DataFrame,
    target_capabilities: list[str],
    row_indices: Optional[list[int]] = None,
) -> dict[int, list[EvidenceFinding]]:
    """
    Extract evidence for a list of target capabilities across multiple rows.

    Args:
        df: Full normalized DataFrame.
        target_capabilities: Capability labels to look for.
        row_indices: Subset of row IDs to check. If None, check all rows.

    Returns:
        dict mapping row_id -> list of EvidenceFinding
    """
    result: dict[int, list[EvidenceFinding]] = {}
    subset = df if row_indices is None else df[df["row_id"].isin(row_indices)]

    for _, row in subset.iterrows():
        findings = extract_evidence_from_row(row, target_capabilities)
        if findings:
            result[int(row["row_id"])] = findings

    return result


def map_query_to_capabilities(query_text: str) -> list[str]:
    """
    Map a free-text query to a list of capability labels to search for.
    Deterministic keyword matching — no LLM required.
    """
    qt = query_text.lower()
    matched: list[str] = []

    # If cardiac query, prioritize cardiacSurgery and avoid generalSurgery collision
    is_cardiac = any(w in qt for w in ["cardiac", "bypass", "cabg", "heart surgery"])

    for cap_label, keywords in CAPABILITY_PATTERNS:
        if is_cardiac and cap_label == "generalSurgery":
            continue
        for kw in keywords:
            if kw.lower() in qt:
                if cap_label not in matched:
                    matched.append(cap_label)
                break

    # Fallback: if nothing matched, search for common emergency terms
    if not matched:
        if any(w in qt for w in ["emergency", "urgent", "critical", "severe"]):
            matched = ["emergencyMedicine", "generalSurgery"]
        else:
            matched = ["emergencyMedicine"]

    return matched
