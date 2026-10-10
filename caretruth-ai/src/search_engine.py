"""CareTruth AI — Search and Ranking Engine.

Core pipeline:
1. Map query text -> capability labels
2. Filter candidates by geographic radius
3. Extract per-candidate evidence
4. Detect contradictions (including injection)
5. Score + assign verdict
6. Rank by composite score
7. Return structured FacilityResult list

This module is the single source of truth for ranking logic —
shared by api.py and app.py.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from src import config
from src.data_loader import load_dataframe
from src.distance import haversine_km
from src.evidence_extractor import (
    EvidenceFinding,
    extract_evidence_from_row,
    map_query_to_capabilities,
)
from src.contradiction_detector import ContradictionFlag, detect_contradictions
from src.trust_scorer import ScoringResult, compute_trust_score


@dataclass
class Citation:
    facility_name: str
    source_field:  str
    span:          str


@dataclass
class FacilityResult:
    facility_name:     str
    facility_pin:      str
    verdict:           str          # verified | advertised_only | unverifiable
    trust_score:       float
    distance_km:       float
    capabilities:      list[str]
    citations:         list[Citation]
    why:               str
    why_not_runner_up: str
    # Extra for dashboard (not returned in API response)
    row_id:            int = 0
    contradiction_flags: list[ContradictionFlag] = field(default_factory=list)
    scoring:           Optional[ScoringResult] = None


def _build_injected_row(
    df: pd.DataFrame,
    injected: dict,
) -> tuple[pd.DataFrame, Optional[int]]:
    """
    Apply an injection probe to the dataset in memory.
    Returns (modified_df, injected_row_index).

    The injection appends injected_line to the specified field of the specified row.
    The original df is NOT modified — a copy is made.
    """
    row_index = injected.get("row_index")
    field_name = injected.get("field", "capability")
    injected_line = injected.get("injected_line", "")

    if row_index is None or not (0 <= row_index < len(df)):
        return df, None

    df_copy = df.copy()
    original_val = str(df_copy.at[row_index, field_name])

    # Append the injected line
    if original_val.strip().endswith("]"):
        # JSON list — insert before closing bracket
        new_val = original_val.rstrip().rstrip("]") + f', "{injected_line}"]'
    else:
        new_val = original_val + f" {injected_line}"

    df_copy.at[row_index, field_name] = new_val

    # Rebuild text blobs for that row
    raw_blob = " | ".join(filter(None, [
        str(df_copy.at[row_index, f])
        for f in ("description", "capability", "procedure", "equipment", "specialties")
        if str(df_copy.at[row_index, f]).strip().lower() not in ("", "null")
    ]))
    df_copy.at[row_index, "raw_text_blob"] = raw_blob
    df_copy.at[row_index, "text_blob"] = raw_blob.lower()

    return df_copy, row_index


def _select_best_citation(
    findings: list[EvidenceFinding],
    target_caps: list[str],
    facility_name: str,
) -> list[Citation]:
    """
    Select the best citations (verbatim spans) for the response.
    Prefer positive, capability-relevant, shorter spans.
    """
    seen: set[str] = set()
    citations: list[Citation] = []

    # Positive findings for target capabilities first
    ordered = sorted(
        findings,
        key=lambda f: (
            0 if f.polarity == "positive" and f.capability in target_caps else 1,
            len(f.span),
        )
    )

    for f in ordered:
        if f.span not in seen and len(citations) < 3:
            seen.add(f.span)
            citations.append(Citation(
                facility_name=facility_name,
                source_field=f.source_field,
                span=f.span,
            ))

    return citations


def _composite_score(
    scoring: ScoringResult,
    distance_km: float,
    radius_km: float,
) -> float:
    """
    Final ranking score combining trust score and distance.
    Distance contributes negatively; closer is better.
    """
    # Normalize distance: 0 at origin, 1 at radius boundary
    dist_norm = min(1.0, distance_km / max(1.0, radius_km))
    return scoring.trust_score * 0.7 + (1 - dist_norm) * 0.3


def search(
    query_text: str,
    user_lat: float,
    user_lng: float,
    time_str: Optional[str] = None,
    injected: Optional[dict] = None,
    radius_km: float = config.SEARCH_RADIUS_KM,
    max_results: int = config.MAX_RESULTS,
    df: Optional[pd.DataFrame] = None,
) -> tuple[list[FacilityResult], list[dict]]:
    """
    Main search function. Returns (ranked_results, desert_flags).

    Args:
        query_text:  Free-text query from user.
        user_lat:    User latitude (decimal degrees).
        user_lng:    User longitude (decimal degrees).
        time_str:    Request time (e.g. "Tuesday 23:30").
        injected:    Injection probe dict with name/row_index/field/injected_line.
        radius_km:   Maximum search radius.
        max_results: Maximum facilities to return.
        df:          Pre-loaded DataFrame (if None, loads from cache).

    Returns:
        - List of FacilityResult (sorted by composite score, descending)
        - List of desert_flag dicts ({"pin": "...", "signal": "..."})
    """
    if df is None:
        df = load_dataframe()

    # Apply injection if present
    injected_row_idx: Optional[int] = None
    injected_line_text: Optional[str] = None
    if injected:
        df, injected_row_idx = _build_injected_row(df, injected)
        injected_line_text = injected.get("injected_line")

    # Map query to capability labels
    target_caps = map_query_to_capabilities(query_text)

    # ── 1. Geographic filter ─────────────────────────────────────────────────
    valid_coord_df = df[df["has_coords"]].copy()

    def _dist(row: pd.Series) -> float:
        return haversine_km(user_lat, user_lng, row["lat_f"], row["lon_f"])

    valid_coord_df["_distance_km"] = valid_coord_df.apply(_dist, axis=1)
    candidates = valid_coord_df[valid_coord_df["_distance_km"] <= radius_km].copy()

    # ── 2. Quick text pre-filter (must mention at least one keyword) ──────────
    keyword_union = "|".join(re.escape(kw.lower()) for cap in target_caps
                             for _, kws in [(cap, [])] for kw in kws)
    # Simpler: just use the raw keyword lists from config
    all_kws = []
    from src.evidence_extractor import CAPABILITY_PATTERNS
    cap_kw_map = dict(CAPABILITY_PATTERNS)
    for cap in target_caps:
        all_kws.extend(cap_kw_map.get(cap, []))

    if all_kws:
        pattern = "|".join(re.escape(kw.lower()) for kw in all_kws)
        candidates = candidates[candidates["text_blob"].str.contains(pattern, regex=True, na=False)]

    # If after filtering we have nothing, widen search radius once
    if candidates.empty and radius_km < 300:
        wider = valid_coord_df[valid_coord_df["_distance_km"] <= 300].copy()
        if all_kws:
            wider = wider[wider["text_blob"].str.contains(pattern, regex=True, na=False)]
        candidates = wider

    # ── 3. Score each candidate ───────────────────────────────────────────────
    results: list[FacilityResult] = []

    for _, row in candidates.iterrows():
        row_id = int(row["row_id"])
        distance_km = float(row["_distance_km"])

        # Determine if injection applies to this specific row
        row_injected_text = None
        if injected_row_idx is not None and row_id == injected_row_idx:
            row_injected_text = injected_line_text

        # Extract evidence
        findings = extract_evidence_from_row(row, target_capabilities=target_caps)

        # Detect contradictions
        flags = detect_contradictions(
            row=row,
            findings=findings,
            time_str=time_str,
            injected_text=row_injected_text,
        )

        # Trust score
        scoring = compute_trust_score(
            row=row,
            findings=findings,
            contradiction_flags=flags,
            target_capabilities=target_caps,
        )

        # Skip if completely unverifiable with no positive evidence
        if scoring.verdict == "unverifiable" and scoring.positive_evidence_count == 0:
            continue

        citations = _select_best_citation(findings, target_caps, str(row["name"]))

        why = _build_why(scoring, findings, target_caps, distance_km)
        # why_not_runner_up filled after ranking

        composite = _composite_score(scoring, distance_km, radius_km)

        results.append(FacilityResult(
            facility_name=str(row["name"]),
            facility_pin=str(row["zip_clean"]),
            verdict=scoring.verdict,
            trust_score=scoring.trust_score,
            distance_km=round(distance_km, 1),
            capabilities=target_caps,
            citations=citations,
            why=why,
            why_not_runner_up="",  # filled after sorting
            row_id=row_id,
            contradiction_flags=flags,
            scoring=scoring,
        ))
        results[-1].__dict__["_composite"] = composite

    # ── 4. Sort by composite score ────────────────────────────────────────────
    results.sort(key=lambda r: r.__dict__.get("_composite", 0), reverse=True)

    # ── 5. Fill why_not_runner_up ─────────────────────────────────────────────
    if len(results) > 1:
        runner_up = results[1]
        results[0].why_not_runner_up = (
            f"{runner_up.facility_name} ranked lower: "
            f"trust_score={runner_up.trust_score}, verdict={runner_up.verdict}, "
            f"distance={runner_up.distance_km} km"
        )
    elif results:
        results[0].why_not_runner_up = "No other facility with sufficient evidence found."

    # ── 6. Desert flags ───────────────────────────────────────────────────────
    desert_flags: list[dict] = []
    if not results:
        # No suitable facilities — flag the query PIN as a potential desert
        from src.data_loader import load_dataframe as _load
        # Use the first candidate from a very wide search to name district
        very_wide = valid_coord_df[valid_coord_df["_distance_km"] <= 500]
        if very_wide.empty:
            desert_flags.append({"pin": "unknown", "signal": "emergency_surgery_desert"})
        else:
            nearest_any = very_wide.nsmallest(1, "_distance_km")
            nearest_pin = str(nearest_any.iloc[0]["zip_clean"]) if not nearest_any.empty else "unknown"
            desert_flags.append({
                "pin": nearest_pin,
                "signal": "emergency_surgery_desert",
            })

    return results[:max_results], desert_flags


def _build_why(
    scoring: ScoringResult,
    findings: list[EvidenceFinding],
    target_caps: list[str],
    distance_km: float,
) -> str:
    parts = []
    if scoring.verdict == "verified":
        parts.append("Verified capability with supporting evidence.")
    elif scoring.verdict == "advertised_only":
        parts.append("Capability advertised but no equipment or named staff confirmed.")
    else:
        parts.append("Limited verifiable evidence.")

    pos = [f for f in findings if f.polarity == "positive" and f.capability in target_caps]
    if pos:
        parts.append(f"{len(pos)} positive evidence item(s) found in {pos[0].source_field}.")

    if scoring.contradiction_flags:
        crit = sum(1 for f in scoring.contradiction_flags if f.severity == "critical")
        parts.append(f"{crit} critical contradiction(s) detected.")

    parts.append(f"Distance: {distance_km:.1f} km.")
    return " ".join(parts)
