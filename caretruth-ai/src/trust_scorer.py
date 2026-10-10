"""CareTruth AI — Trust Scorer.

Computes a 0..1 heuristic trust score and assigns a verdict for each facility.

Verdict vocabulary (from official PS-03 contract):
  "verified"        — has equipment OR named staff OR explicit 24/7 claim
  "advertised_only" — capability listed but no equipment, no named staff
  "unverifiable"    — insufficient evidence to assess

Score components are documented and configurable in src/config.py.
This module does NOT claim to produce calibrated probabilities.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from src import config
from src.evidence_extractor import EvidenceFinding
from src.contradiction_detector import ContradictionFlag


@dataclass
class ScoringResult:
    trust_score:    float
    verdict:        str   # verified | advertised_only | unverifiable
    score_breakdown: dict[str, float]  # component -> value (for transparency)
    contradiction_flags: list[ContradictionFlag]
    positive_evidence_count: int
    negative_evidence_count: int
    conditional_evidence_count: int


def compute_trust_score(
    row: pd.Series,
    findings: list[EvidenceFinding],
    contradiction_flags: list[ContradictionFlag],
    target_capabilities: list[str],
) -> ScoringResult:
    """
    Compute trust score and verdict for a facility given evidence and contradictions.

    Scoring is additive over components defined in config.py.
    Contradictions apply penalties on top.
    The verdict assignment follows strict contract rules.
    """
    breakdown: dict[str, float] = {}

    # ── Positive evidence components ──────────────────────────────────────────

    # 1. Relevant specialty match
    spec_list = list(row.get("spec_list", []) or [])
    spec_text  = " ".join(spec_list).lower()
    has_relevant_specialty = any(
        cap.lower() in spec_text or spec_text in cap.lower()
        for cap in target_capabilities
    )
    breakdown["specialty_match"] = (
        config.W_HAS_RELEVANT_SPECIALTY if has_relevant_specialty else 0.0
    )

    # 2. Evidence in text (positive findings for target capabilities)
    pos_findings = [
        f for f in findings
        if f.polarity == "positive" and f.capability in target_capabilities
    ]
    breakdown["text_evidence"] = min(
        config.W_HAS_EVIDENCE_IN_TEXT,
        config.W_HAS_EVIDENCE_IN_TEXT * (len(pos_findings) / max(1, len(target_capabilities)))
    )

    # 3. Equipment present
    breakdown["equipment"] = config.W_HAS_EQUIPMENT if row.get("has_equipment", False) else 0.0

    # 4. Named staff
    breakdown["named_staff"] = config.W_HAS_NAMED_STAFF if row.get("has_named_staff", False) else 0.0

    # 5. Open 24/7
    breakdown["open_24h"] = config.W_OPEN_24H if row.get("open_24h", False) else 0.0

    # 6. Has description
    breakdown["description"] = config.W_HAS_DESCRIPTION if row.get("has_description", False) else 0.0

    # 7. Social / web presence
    has_web = bool(
        str(row.get("officialWebsite", "")).strip() not in ("", "null")
        or str(row.get("facebookLink", "")).strip() not in ("", "null")
    )
    breakdown["web_presence"] = config.W_SOCIAL_PRESENCE if has_web else 0.0

    # 8. Doctor count > 0
    breakdown["doctor_count"] = (
        config.W_DOCTOR_COUNT if (row.get("doctor_count", 0) or 0) > 0 else 0.0
    )

    # ── Base score ─────────────────────────────────────────────────────────────
    base_score = sum(breakdown.values())

    # ── Contradiction penalties ────────────────────────────────────────────────
    critical_count  = sum(1 for f in contradiction_flags if f.severity == "critical")
    moderate_count  = sum(1 for f in contradiction_flags if f.severity == "moderate")

    penalty = (
        critical_count  * config.CONTRADICTION_PENALTY +
        moderate_count  * config.PARTIAL_CONTRADICTION_PENALTY
    )
    breakdown["contradiction_penalty"] = -penalty

    raw_score = max(0.0, min(1.0, base_score - penalty))

    # ── Verdict assignment (contract rules) ────────────────────────────────────
    # "verified" requires: equipment OR named staff OR explicit 24/7 claim
    has_strong_evidence = (
        row.get("has_equipment", False) or
        row.get("has_named_staff", False) or
        row.get("open_24h", False)
    )

    if critical_count > 0:
        # Serious contradiction — cannot be verified regardless of other evidence
        if raw_score >= config.VERDICT_ADVERTISED_ONLY_MIN_SCORE:
            verdict = "advertised_only"
        else:
            verdict = "unverifiable"
    elif raw_score >= config.VERDICT_VERIFIED_MIN_SCORE and has_strong_evidence and pos_findings:
        verdict = "verified"
    elif raw_score >= config.VERDICT_ADVERTISED_ONLY_MIN_SCORE and pos_findings:
        verdict = "advertised_only"
    else:
        verdict = "unverifiable"

    return ScoringResult(
        trust_score=round(raw_score, 3),
        verdict=verdict,
        score_breakdown=breakdown,
        contradiction_flags=contradiction_flags,
        positive_evidence_count=len([f for f in findings if f.polarity == "positive"]),
        negative_evidence_count=len([f for f in findings if f.polarity == "negative"]),
        conditional_evidence_count=len([f for f in findings if f.polarity == "conditional"]),
    )


def calculate_trust_score(
    row: pd.Series,
    contradiction_flags: list[ContradictionFlag] = None,
    findings: list[EvidenceFinding] = None,
    target_capabilities: list[str] = None,
) -> float:
    """
    Convenience wrapper returning float trust score for a facility.
    """
    findings = findings or []
    contradiction_flags = contradiction_flags or []
    target_capabilities = target_capabilities or []
    res = compute_trust_score(row, findings, contradiction_flags, target_capabilities)
    return res.trust_score

