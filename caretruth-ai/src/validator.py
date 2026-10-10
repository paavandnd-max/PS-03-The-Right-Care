"""CareTruth AI — Validator.

Validates that a response conforms to the PS-03 contract before it is returned.
Also provides abstention logic.
"""
from __future__ import annotations
from typing import Optional

from src import config
from src.search_engine import FacilityResult
from src.data_loader import load_dataframe


VALID_VERDICTS = {"verified", "advertised_only", "unverifiable"}


def validate_citation_spans(result: FacilityResult, df=None) -> list[str]:
    """
    Verify that every citation span is a verbatim substring of the source row's text.
    Returns a list of violation strings (empty = all OK).
    """
    if df is None:
        df = load_dataframe()

    violations: list[str] = []
    matching_rows = df[df["name_norm"] == result.facility_name.lower().strip()]
    if matching_rows.empty:
        violations.append(f"Facility '{result.facility_name}' not found in dataset.")
        return violations

    row = matching_rows.iloc[0]

    for citation in result.citations:
        raw_blob = str(row.get("raw_text_blob", ""))
        span_lower = citation.span.lower().strip()
        blob_lower = raw_blob.lower()
        if span_lower not in blob_lower:
            violations.append(
                f"Citation span '{citation.span[:60]}...' not found verbatim "
                f"in row for '{result.facility_name}'."
            )

    return violations


def should_abstain(
    results: list[FacilityResult],
    user_lat: float,
    user_lng: float,
    transport: str = "two-wheeler",
    time_str: Optional[str] = None,
) -> tuple[bool, Optional[str]]:
    """
    Determine whether the system should abstain from returning results.

    Returns (abstain: bool, reason: str | None).
    """
    if not results:
        return True, "No facility within practical range has sufficient verified evidence."

    # Check if transport type restricts practical range
    if transport == "two-wheeler":
        practical_limit = config.TWO_WHEELER_RANGE_KM
        top_dist = results[0].distance_km
        if top_dist > practical_limit and results[0].verdict == "unverifiable":
            return True, (
                f"No facility within {practical_limit} km two-wheeler range "
                f"with sufficient evidence. Nearest with any evidence is "
                f"{results[0].facility_name} at {top_dist:.1f} km."
            )

    # If all results are unverifiable, consider abstaining
    all_unverifiable = all(r.verdict == "unverifiable" for r in results)
    if all_unverifiable:
        return True, "No facility with verifiable evidence found for the requested capability."

    return False, None


def build_contract_response(
    probe_id: str,
    results: list[FacilityResult],
    desert_flags: list[dict],
    abstain: bool,
    abstain_reason: Optional[str],
) -> dict:
    """
    Build the exact PS-03 contract JSON response.

    Fields:
    - facilities: list of facility objects
    - abstain: bool
    - abstain_reason: str | null
    - desert_flags: list of {"pin", "signal"} dicts
    """
    facility_list = []
    for r in results:
        facility_list.append({
            "facility_name": r.facility_name,
            "facility_pin":  r.facility_pin,
            "verdict":       r.verdict,
            "trust_score":   r.trust_score,
            "distance_km":   r.distance_km,
            "capabilities":  r.capabilities,
            "citations":     [
                {
                    "facility_name": c.facility_name,
                    "source_field":  c.source_field,
                    "span":          c.span,
                }
                for c in r.citations
            ],
            "why":               r.why,
            "why_not_runner_up": r.why_not_runner_up,
        })

    if abstain:
        facility_list = []

    return {
        "facilities":     facility_list,
        "abstain":        abstain,
        "abstain_reason": abstain_reason,
        "desert_flags":   desert_flags,
    }
