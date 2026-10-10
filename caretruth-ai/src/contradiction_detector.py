"""CareTruth AI — Contradiction Detector.

Detects logical conflicts within a single facility record.
Returns structured ContradictionFlag objects for use by TrustScorer.

Rules implemented:
1. Positive claim + negative statement in same record for same capability
2. Night-time restriction injected into capability (injection probe)
3. Equipment listed as non-functional
4. Staff availability restricted by time
5. Facility type vs. claimed specialty mismatch
"""
from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Optional

import pandas as pd

from src import config
from src.evidence_extractor import EvidenceFinding


@dataclass
class ContradictionFlag:
    rule_id:          str           # short identifier for the rule
    description:      str           # human-readable explanation
    severity:         str           # "critical" | "moderate" | "minor"
    source_field:     str           # field where contradiction found
    conflicting_span: Optional[str] = None  # verbatim text that causes conflict
    time_condition:   Optional[str] = None  # "after 21:00" etc.


def _text_contains(text: str, patterns: list[str]) -> bool:
    return any(p.lower() in text.lower() for p in patterns)


def _night_hour(time_str: Optional[str]) -> bool:
    """
    Return True if the time string falls in the night window (after 21:00 or before 06:00).
    Accepts formats like 'Tuesday 23:30', '22:00', '9 PM'.
    """
    if not time_str:
        return False
    t = time_str.lower()
    # Match HH:MM
    m = re.search(r"(\d{1,2}):(\d{2})", t)
    if m:
        hour = int(m.group(1))
        return hour >= config.NIGHT_START_HOUR or hour < config.NIGHT_END_HOUR
    # Match "9 PM" style
    m2 = re.search(r"(\d{1,2})\s*(am|pm)", t)
    if m2:
        hour = int(m2.group(1))
        period = m2.group(2)
        if period == "pm" and hour != 12:
            hour += 12
        elif period == "am" and hour == 12:
            hour = 0
        return hour >= config.NIGHT_START_HOUR or hour < config.NIGHT_END_HOUR
    return False


def _extract_night_contradiction_span(text: str) -> Optional[str]:
    """
    Return the first matching night-time contradiction substring, or None.
    Used to find the injected anaesthesiologist restriction.
    """
    t_lower = text.lower()
    for pattern in config.NIGHT_CONTRADICTION_PATTERNS:
        idx = t_lower.find(pattern)
        if idx >= 0:
            end = min(len(text), idx + len(pattern) + 60)
            return text[idx:end].strip().rstrip(".")
    return None


def detect_contradictions(
    row: pd.Series,
    findings: Optional[list[EvidenceFinding]] = None,
    time_str: Optional[str] = None,
    injected_text: Optional[str] = None,
) -> list[ContradictionFlag]:
    """
    Detect contradictions in a facility row.

    Args:
        row:           Normalized DataFrame row.
        findings:      Evidence findings already extracted for this row (optional).
        time_str:      Query time string (e.g. "Tuesday 23:30").
        injected_text: Injected capability line (from injection probe).

    Returns:
        List of ContradictionFlag objects.
    """
    flags: list[ContradictionFlag] = []

    if findings is None:
        from src.evidence_extractor import extract_evidence_from_row
        findings = extract_evidence_from_row(row)

    # Combine all text fields for searching
    all_text = " ".join([
        str(row.get("description", "")),
        str(row.get("capability", "")),
        str(row.get("procedure", "")),
        str(row.get("equipment", "")),
    ])
    if injected_text:
        all_text = all_text + " " + injected_text

    # ── Rule 1: Positive capability + explicit negation in same record ─────────
    positive_caps = {f.capability for f in findings if f.polarity == "positive"}
    negative_caps = {f.capability for f in findings if f.polarity == "negative"}
    for cap in positive_caps & negative_caps:
        neg_finding = next(f for f in findings if f.capability == cap and f.polarity == "negative")
        flags.append(ContradictionFlag(
            rule_id="POSITIVE_NEGATIVE_CONFLICT",
            description=f"Positive claim for '{cap}' contradicted by negative statement in same record.",
            severity="critical",
            source_field=neg_finding.source_field,
            conflicting_span=neg_finding.span,
        ))

    # ── Rule 2: Night-time anaesthesiologist restriction (injection probe) ────
    is_night = _night_hour(time_str)
    anaes_span = _extract_night_contradiction_span(all_text)
    if anaes_span and is_night:
        flags.append(ContradictionFlag(
            rule_id="NIGHT_NO_ANAESTHESIOLOGIST",
            description=(
                "No anaesthesiologist available during night hours — "
                "emergency surgery cannot proceed safely at this time."
            ),
            severity="critical",
            source_field="capability",
            conflicting_span=anaes_span,
            time_condition=f"Time is night ({time_str}); restriction applies.",
        ))
    elif anaes_span and not is_night:
        # The restriction exists but doesn't apply right now — flag as moderate
        flags.append(ContradictionFlag(
            rule_id="CONDITIONAL_NO_ANAESTHESIOLOGIST",
            description="Night-time anaesthesiologist restriction present (not currently active).",
            severity="moderate",
            source_field="capability",
            conflicting_span=anaes_span,
            time_condition="Restriction applies after 21:00.",
        ))

    # ── Rule 3: Equipment claimed as non-functional ───────────────────────────
    equip_negation_patterns = [
        "equipment not available", "equipment out of service",
        "machine not working", "scanner unavailable", "x-ray not functional",
        "mri not available", "ct not available",
    ]
    for pattern in equip_negation_patterns:
        if pattern in all_text.lower():
            idx = all_text.lower().find(pattern)
            span = all_text[max(0, idx - 20): idx + len(pattern) + 20].strip()
            flags.append(ContradictionFlag(
                rule_id="EQUIPMENT_NON_FUNCTIONAL",
                description="Equipment listed as non-functional or unavailable.",
                severity="critical",
                source_field="equipment",
                conflicting_span=span,
            ))

    # ── Rule 4: Staff restricted by time ─────────────────────────────────────
    staff_restriction_patterns = [
        "doctor not available", "no doctor on duty", "no staff after",
        "specialist unavailable", "surgeon not available on",
    ]
    for pattern in staff_restriction_patterns:
        if pattern in all_text.lower():
            idx = all_text.lower().find(pattern)
            span = all_text[max(0, idx - 20): idx + len(pattern) + 40].strip()
            flags.append(ContradictionFlag(
                rule_id="STAFF_RESTRICTION",
                description="Staff availability restricted.",
                severity="moderate",
                source_field="capability",
                conflicting_span=span,
            ))

    # ── Rule 5: Facility type vs. claimed complex surgery ─────────────────────
    facility_type = str(row.get("facilityTypeId", "")).lower()
    if facility_type in ("clinic", "pharmacy", "farmacy", "dentist") and \
       any(k in all_text.lower() for k in ["cardiac bypass", "cabg", "open heart", "cardiothoracic"]):
        flags.append(ContradictionFlag(
            rule_id="TYPE_CAPABILITY_MISMATCH",
            description=(
                f"Facility type '{facility_type}' claims complex cardiac surgery — "
                "inconsistent with facility classification."
            ),
            severity="moderate",
            source_field="facilityTypeId",
            conflicting_span=None,
        ))

    return flags
