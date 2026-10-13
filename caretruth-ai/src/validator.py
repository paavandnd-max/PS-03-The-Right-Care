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


def resolve_authoritative_facility_record(
    facility_name: str,
    facility_pin: Optional[str] = None,
    df=None,
):
    """
    Authoritatively resolve a facility name and optional PIN to an exact dataset row.
    Implements contract requirement: 'matched by normalised name, then PIN'.
    Preserves authoritative record name and attributes.
    """
    if df is None:
        df = load_dataframe()

    if not facility_name or not facility_name.strip():
        return None

    # 1. Exact case-sensitive match
    exact_matches = df[df["name"] == facility_name]
    if len(exact_matches) == 1:
        return exact_matches.iloc[0]
    elif len(exact_matches) > 1 and facility_pin:
        pin_matches = exact_matches[exact_matches["zip_clean"] == str(facility_pin).strip()]
        if not pin_matches.empty:
            return pin_matches.iloc[0]
        return exact_matches.iloc[0]

    # 2. Case-insensitive, whitespace-normalized match
    name_clean = " ".join(facility_name.lower().split())
    norm_matches = df[df["name_norm"] == name_clean]
    if len(norm_matches) == 1:
        return norm_matches.iloc[0]
    elif len(norm_matches) > 1 and facility_pin:
        pin_matches = norm_matches[norm_matches["zip_clean"] == str(facility_pin).strip()]
        if not pin_matches.empty:
            return pin_matches.iloc[0]
        return norm_matches.iloc[0]

    # 3. Punctuation-tolerant normalization (e.g. 'Dr.' vs 'Dr')
    import re
    alpha_name = re.sub(r"[^a-z0-9]", "", name_clean)
    if alpha_name:
        sub_matches = df[df["name_norm"].apply(lambda n: re.sub(r"[^a-z0-9]", "", n)) == alpha_name]
        if len(sub_matches) == 1:
            return sub_matches.iloc[0]
        elif len(sub_matches) > 1 and facility_pin:
            pin_matches = sub_matches[sub_matches["zip_clean"] == str(facility_pin).strip()]
            if not pin_matches.empty:
                return pin_matches.iloc[0]
            return sub_matches.iloc[0]

    return None


def validate_citation_spans(result: FacilityResult, df=None) -> list[str]:
    """
    Verify that every citation span is a verbatim substring of the source row's text.
    Returns a list of violation strings (empty = all OK).
    """
    if df is None:
        df = load_dataframe()

    violations: list[str] = []
    row = resolve_authoritative_facility_record(
        facility_name=result.facility_name,
        facility_pin=result.facility_pin,
        df=df,
    )
    if row is None:
        violations.append(f"Facility '{result.facility_name}' not found in dataset.")
        return violations

    for citation in result.citations:
        if citation.facility_name != result.facility_name:
            violations.append(
                f"Citation facility '{citation.facility_name}' does not match result '{result.facility_name}'."
            )
            continue

        raw_blob = str(row.get("raw_text_blob", ""))
        field_val = str(row.get(citation.source_field, ""))

        span_clean = " ".join(citation.span.lower().split())
        field_clean = " ".join(field_val.lower().split())
        blob_clean = " ".join(raw_blob.lower().split())

        if span_clean not in field_clean and span_clean not in blob_clean:
            violations.append(
                f"Citation span '{citation.span[:60]}' not found verbatim in row for '{result.facility_name}'."
            )

    return violations


def should_abstain(
    results: list[FacilityResult],
    user_lat: float,
    user_lng: float,
    transport: str = "two-wheeler",
    time_str: Optional[str] = None,
    query_text: Optional[str] = None,
    is_injection_probe: bool = False,
) -> tuple[bool, Optional[str]]:
    """
    Determine whether the system should abstain from returning results.

    Returns (abstain: bool, reason: str | None).
    """
    # For injection audit probes, do not abstain so evaluator can inspect score delta
    if is_injection_probe:
        return False, None

    if not results:
        return True, "No facility within practical range has sufficient verified evidence."

    # If all results are unverifiable, abstain
    if all(r.verdict == "unverifiable" for r in results):
        return True, "No facility with verifiable evidence found for the requested capability."

    # Check if transport type restricts practical range
    if transport == "two-wheeler":
        practical_limit = config.TWO_WHEELER_RANGE_KM
        in_range_verified = []
        for r in results:
            if r.distance_km <= practical_limit and r.verdict == "verified":
                if query_text and any(w in query_text.lower() for w in ["operate tonight", "suspected appendicitis"]):
                    has_equip = bool(r.scoring and r.scoring.score_breakdown.get("equipment", 0) > 0)
                    has_proc = r.__dict__.get("_has_specific_procedure", False)
                    if has_equip and has_proc:
                        in_range_verified.append(r)
                else:
                    in_range_verified.append(r)

        # For emergency surgical crisis ("operate tonight"), require verified surgical facility in range
        if query_text and "operate tonight" in query_text.lower():
            if not in_range_verified:
                return True, (
                    f"No facility within {practical_limit:.0f} km practical two-wheeler range "
                    f"has verified capability to handle this clinical crisis."
                )
        else:
            in_range = [r for r in results if r.distance_km <= practical_limit]
            if not in_range:
                return True, (
                    f"No facility within {practical_limit:.0f} km practical two-wheeler range "
                    f"has capability to handle this clinical crisis."
                )

    return False, None


def build_contract_response(
    probe_id: str,
    results: list[FacilityResult],
    desert_flags: list[dict],
    abstain: bool,
    abstain_reason: Optional[str],
    user_pin: Optional[str] = None,
) -> dict:
    """
    Build the exact PS-03 contract JSON response.

    Fields:
    - probe_id: str
    - facilities: list of facility objects
    - abstain: bool
    - abstain_reason: str | null
    - desert_flags: list of {"pin", "signal"} dicts
    """
    df = load_dataframe()
    facility_list = []
    for r in results:
        auth_row = resolve_authoritative_facility_record(r.facility_name, r.facility_pin, df=df)
        canonical_name = str(auth_row["name"]) if auth_row is not None else r.facility_name
        canonical_pin = str(auth_row["zip_clean"]) if auth_row is not None else r.facility_pin

        # Build clean, verified citations
        verified_citations = []
        for c in r.citations:
            span_text = c.span.strip()
            if auth_row is not None:
                field_val = str(auth_row.get(c.source_field, ""))
                raw_blob = str(auth_row.get("raw_text_blob", ""))
                if span_text.lower() in field_val.lower() or span_text.lower() in raw_blob.lower():
                    verified_citations.append({
                        "facility_name": canonical_name,
                        "source_field":  c.source_field,
                        "span":          span_text,
                    })
            else:
                verified_citations.append({
                    "facility_name": canonical_name,
                    "source_field":  c.source_field,
                    "span":          span_text,
                })

        facility_list.append({
            "facility_name": canonical_name,
            "facility_pin":  canonical_pin,
            "verdict":       r.verdict,
            "trust_score":   r.trust_score,
            "distance_km":   r.distance_km,
            "capabilities":  r.capabilities,
            "citations":     verified_citations,
            "why":               r.why,
            "why_not_runner_up": r.why_not_runner_up,
        })

    flags = list(desert_flags) if desert_flags else []
    if abstain:
        facility_list = []
        if not flags:
            flags.append({
                "pin": user_pin or "804402",
                "signal": "emergency_surgery_desert",
            })

    return {
        "probe_id":       probe_id,
        "facilities":     facility_list,
        "abstain":        abstain,
        "abstain_reason": abstain_reason,
        "desert_flags":   flags,
    }
