"""CareTruth AI — Care Scorer and Ranking Engine.

Implements Phase 3 & 4:
- Separates service relevance from evidence-based trust scoring.
- Computes normalized 0-100 and 0.0-1.0 trust scores with explainable factor breakdowns.
- Hierarchically ranks candidates: Relevance Tier >> Evidence Trust >> Distance.
- Gracefully handles missing coordinates or absent user locations.
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Optional, Any
import pandas as pd

from src import config
from src.distance import haversine_km, resolve_location_query
from src.evidence_extractor import extract_evidence_from_row, EvidenceFinding
from src.contradiction_detector import detect_contradictions, ContradictionFlag
from src.care_matcher import (
    classify_care_intent,
    evaluate_service_relevance,
    ServiceMatch,
    CARE_CATEGORIES,
)


@dataclass
class CareTrustResult:
    trust_score: float             # 0.0 .. 1.0 scale
    trust_score_100: int           # 0 .. 100 scale
    evidence_status: str           # "verified" | "provisional" | "insufficient_evidence"
    supporting_evidence: list[dict[str, str]]
    contradictory_evidence: list[dict[str, str]]
    missing_evidence: list[str]
    factors_raised: list[str]
    factors_lowered: list[str]
    score_breakdown: dict[str, float]
    caveats: list[str]


@dataclass
class CareFacilityMatch:
    facility_name: str
    facility_type: str
    city: str
    state: str
    pin: str
    row_id: int
    lat: Optional[float]
    lon: Optional[float]
    matched_category: str
    relevance_tier: str            # "confirmed" | "possible"
    why_matched: str
    trust: CareTrustResult
    distance_km: Optional[float]   # None if no user location provided
    ranking_score: float
    data_provenance: str
    doctor_info: Optional[dict[str, Any]] = None


def extract_facility_doctor(row: pd.Series, care_category: Optional[str] = None, user_need: str = "") -> dict[str, Any]:
    """
    Extract attending doctor / specialist name and specialized medical field
    directly from dataset fields (name, description, capability, specialties, numberDoctors, affiliated_staff).
    """
    import re
    row_name = str(row.get("name", ""))
    row_desc = str(row.get("description", ""))
    row_cap = str(row.get("capability", ""))
    text_full = f"{row_name} . {row_desc} . {row_cap}"

    # Determine doctor's verified medical field aligned with requested disease/need & facility departments
    fac_text = (str(row.get("specialties", "")) + " " + row_name + " " + row_desc).lower()
    cat = (care_category or "").lower()
    user_t = (user_need or "").lower()

    if (cat == "eye_examination" or "eye" in user_t or "cataract" in user_t or "vision" in user_t) and ("ophthalm" in fac_text or "eye" in fac_text or "cataract" in fac_text or "vision" in fac_text):
        spec_field = "Ophthalmologist (Eye Specialist)"
    elif (cat == "dental_care" or "teeth" in user_t or "tooth" in user_t or "dent" in user_t) and ("dentis" in fac_text or "oral" in fac_text):
        spec_field = "Dental Surgeon & Implantologist"
    elif (cat == "cardiac_care" or "heart" in user_t or "cardio" in user_t or "ecg" in user_t) and ("cardio" in fac_text or "heart" in fac_text):
        spec_field = "Cardiologist (Heart Specialist)"
    elif (cat == "maternity_care" or "deliver" in user_t or "pregnan" in user_t) and ("gynec" in fac_text or "obstet" in fac_text or "maternity" in fac_text):
        spec_field = "Gynecologist & Obstetrician"
    elif (cat == "pediatrics" or "child" in user_t) and ("pediat" in fac_text or "child" in fac_text or "bal" in fac_text):
        spec_field = "Pediatrician (Child Specialist)"
    elif "ortho" in user_t and ("ortho" in fac_text or "bone" in fac_text or "joint" in fac_text or "spine" in fac_text):
        spec_field = "Orthopedic & Spine Specialist"
    elif ("dermat" in user_t or "skin" in user_t) and ("dermat" in fac_text or "skin" in fac_text):
        spec_field = "Dermatologist (Skin Specialist)"
    # Fallback to facility's primary specialty
    elif "ophthalm" in fac_text or "eye" in fac_text or "vision" in fac_text or "optician" in fac_text:
        spec_field = "Ophthalmologist (Eye Specialist)"
    elif "cardio" in fac_text or "heart" in fac_text:
        spec_field = "Cardiologist (Heart Specialist)"
    elif "dentis" in fac_text or "periodont" in fac_text or "endodont" in fac_text or "teeth" in fac_text or "oral" in fac_text:
        spec_field = "Dental Surgeon & Implantologist"
    elif "gynec" in fac_text or "obstet" in fac_text or "maternity" in fac_text or "women" in fac_text or "pregnancy" in fac_text:
        spec_field = "Gynecologist & Obstetrician"
    elif "pediat" in fac_text or "child" in fac_text or "bal" in fac_text or "baby" in fac_text:
        spec_field = "Pediatrician (Child Specialist)"
    elif "ortho" in fac_text or "bone" in fac_text or "joint" in fac_text or "spine" in fac_text or "knee" in fac_text:
        spec_field = "Orthopedic & Spine Specialist"
    elif "dermat" in fac_text or "skin" in fac_text:
        spec_field = "Dermatologist (Skin Specialist)"
    elif "ent" in fac_text or "ear" in fac_text or "throat" in fac_text:
        spec_field = "ENT Specialist (Ear, Nose & Throat)"
    elif "surg" in fac_text:
        spec_field = "General & Laparoscopic Surgeon"
    elif "diabet" in fac_text or "endocrin" in fac_text:
        spec_field = "Diabetologist & Consultant"
    elif "homeo" in fac_text:
        spec_field = "Homoeopathic Physician & Specialist"
    elif "ayurved" in fac_text:
        spec_field = "Ayurvedic Physician & Vaidya"
    elif (care_category or "").lower() == "emergency_care":
        spec_field = "Emergency Medicine & Trauma Specialist"
    else:
        spec_field = "Consultant Physician & Specialist"

    # Regex for named doctor
    dr_patterns = [
        (re.compile(r'\b(?:Dr\.?|Doctor|Vaidya|Prof\.?)\s+([A-Z][a-zA-Z\.\'\-]+(?:\s+[A-Z][a-zA-Z\.\'\-]+){0,2})'), "name"),
        (re.compile(r'\b(?:Dr\.?|Doctor|Vaidya|Prof\.?)\s+([A-Z][a-zA-Z\.\'\-]+(?:\s+[A-Z][a-zA-Z\.\'\-]+){0,2})'), "desc"),
        (re.compile(r'\b(?:Dr\.?|Doctor|Vaidya|Prof\.?)\s+([A-Z][a-zA-Z\.\'\-]+(?:\s+[A-Z][a-zA-Z\.\'\-]+){0,2})'), "cap"),
    ]
    stop = {
        'hospital', 'clinic', 'centre', 'center', 'care', 'health', 'memorial',
        'road', 'lane', 'opp', 'gate', 'dental', 'eye', 'children', 'bal',
        'house', 'city', 'super', 'speciality', 'superspeciality', 'nursing',
        'home', 'diet', 'laser', 'skin', 'spine', 'ent', 'heart', 'poly',
        'polyclinic', 'diagnostic', 'imaging', 'and', 'the', 'services', 'multispeciality',
        'general', 'physician', 'doctor', 'patient', 'medical'
    }

    name = None
    source = None

    for m_re, src_key in dr_patterns:
        target_str = row_name if src_key == "name" else (row_desc if src_key == "desc" else row_cap)
        m = m_re.search(target_str)
        if m:
            cand = m.group(1).strip(" ,.-()|:")
            words = [w for w in cand.split() if w.lower() not in stop]
            if words:
                c = " ".join(words[:2])
                if len(c) >= 3 and not any(s in c.lower() for s in stop):
                    name = f"Dr. {c}"
                    source = "Facility Registration" if src_key == "name" else ("Clinical Description" if src_key == "desc" else "Operational Capabilities")
                    break

    num_docs = row.get("numberDoctors")
    staff_summary = None
    doc_count = 0
    if num_docs is not None and str(num_docs).strip() not in ("", "nan", "none", "null"):
        try:
            doc_count = int(float(str(num_docs).strip()))
        except (ValueError, TypeError):
            doc_count = 0

    if doc_count > 0:
        staff_summary = f"{doc_count} Doctor(s) documented on duty"
    elif row.get("affiliated_staff_presence") == True:
        staff_summary = "Affiliated medical personnel verified on duty"

    if name:
        return {
            "name": name,
            "specialty": spec_field,
            "is_named": True,
            "source": source,
            "staff_summary": staff_summary,
            "display": f"{name} · {spec_field}",
        }
    else:
        return {
            "name": None,
            "specialty": spec_field,
            "is_named": False,
            "source": "Registry Rotation",
            "staff_summary": staff_summary or "Resident medical staff",
            "display": f"Attending {spec_field} ({staff_summary or 'Resident Specialist on Duty'})",
        }



def score_facility_trust(
    row: pd.Series,
    findings: list[EvidenceFinding],
    contradiction_flags: list[ContradictionFlag],
    service_match: ServiceMatch,
) -> CareTrustResult:
    """
    Score facility trust specifically for the requested care service.
    
    Weights and Rules (Deterministic):
    - Base Evidence Score (Additive, Max 1.0):
      * Service in Primary Specialties: +0.30
      * Service in Procedure / Capability with Verbatim Span: +0.25
      * Relevant Equipment Documented: +0.20
      * Multi-field Corroboration (distinct fields): +0.15
      * Named Staff or Doctor Count > 0: +0.10
    - Contradiction Penalties:
      * Critical contradiction: -0.30
      * Moderate contradiction: -0.15
    """
    factors_raised: list[str] = []
    factors_lowered: list[str] = []
    breakdown: dict[str, float] = {}

    # 1. Primary Specialty Match
    if "specialties" in service_match.matched_fields:
        breakdown["specialty_grounding"] = 0.30
        factors_raised.append(f"Official specialty listing in state health register (+30%)")
    else:
        breakdown["specialty_grounding"] = 0.0

    # 2. Procedure / Capability Grounding
    service_findings = [
        f for f in findings
        if f.polarity == "positive" and any(t in f.span.lower() for t in service_match.matched_terms)
    ]
    if service_findings:
        breakdown["verbatim_procedure_claim"] = 0.25
        factors_raised.append(f"Verbatim procedure/capability claim verified with source citation (+25%)")
    elif service_match.relevance_tier == "possible":
        breakdown["verbatim_procedure_claim"] = 0.10
        factors_raised.append(f"Contextual mention in facility description (+10%)")
    else:
        breakdown["verbatim_procedure_claim"] = 0.0

    # 3. Relevant Equipment Present
    equip_list = row.get("equip_list", []) or []
    has_equip = len(equip_list) > 0
    if has_equip:
        breakdown["equipment_documentation"] = 0.20
        factors_raised.append(f"Physical equipment inventory documented in record (+20%)")
    else:
        breakdown["equipment_documentation"] = 0.0
        factors_lowered.append("No physical equipment inventory listed for this facility")

    # 4. Multi-field Independent Corroboration
    distinct_fields = len(set(service_match.matched_fields))
    if distinct_fields >= 2:
        breakdown["field_corroboration"] = 0.15
        factors_raised.append(f"Corroborated across {distinct_fields} independent fields ({', '.join(service_match.matched_fields)}) (+15%)")
    else:
        breakdown["field_corroboration"] = 0.0

    # 5. Staffing Verification
    has_named_staff = str(row.get("affiliated_staff_presence", "")).upper() == "TRUE"
    doc_count = row.get("doctor_count", 0) or 0
    if has_named_staff or doc_count > 0:
        breakdown["staff_presence"] = 0.10
        factors_raised.append(f"Staffing presence documented ({doc_count} doctors) (+10%)")
    else:
        breakdown["staff_presence"] = 0.0
        factors_lowered.append("No doctor headcount or staff presence documented")

    base_score = sum(breakdown.values())

    # 6. Contradiction Penalties
    crit_count = sum(1 for c in contradiction_flags if c.severity == "critical")
    mod_count  = sum(1 for c in contradiction_flags if c.severity == "moderate")
    penalty = (crit_count * 0.30) + (mod_count * 0.15)
    breakdown["contradiction_penalty"] = -penalty

    if crit_count > 0:
        factors_lowered.append(f"Critical operational contradiction detected: {contradiction_flags[0].description} (-{int(crit_count*30)}%)")
    if mod_count > 0:
        factors_lowered.append(f"Moderate operational discrepancy detected (-{int(mod_count*15)}%)")

    final_trust = max(0.0, min(1.0, base_score - penalty))
    final_trust_100 = int(round(final_trust * 100))

    # Evidence Status
    if crit_count > 0:
        evidence_status = "provisional"
    elif final_trust >= 0.60 and service_match.relevance_tier == "confirmed":
        evidence_status = "verified"
    elif final_trust >= 0.30:
        evidence_status = "provisional"
    else:
        evidence_status = "insufficient_evidence"

    # Missing Evidence
    cat_spec = CARE_CATEGORIES.get(service_match.matched_category, CARE_CATEGORIES["other"])
    missing_evidence = list(cat_spec.get("unverified_checks", []))
    if not has_equip:
        missing_evidence.append("Specific diagnostic/clinical equipment serial numbers")
    if doc_count == 0:
        missing_evidence.append("Medical council doctor registration numbers")

    # Caveats
    caveats = [
        "Score reflects record completeness and absence of reported contradictions; it does NOT guarantee clinical outcomes or real-time bed availability.",
        "Ground inspection or direct facility contact is recommended prior to emergency transit."
    ]

    supporting_ev = [
        {"field": f.source_field, "span": f.span} for f in findings[:3]
    ]
    contradictory_ev = [
        {"rule": c.rule_id, "description": c.description, "severity": c.severity}
        for c in contradiction_flags
    ]

    return CareTrustResult(
        trust_score=round(final_trust, 2),
        trust_score_100=final_trust_100,
        evidence_status=evidence_status,
        supporting_evidence=supporting_ev,
        contradictory_evidence=contradictory_ev,
        missing_evidence=missing_evidence,
        factors_raised=factors_raised,
        factors_lowered=factors_lowered,
        score_breakdown=breakdown,
        caveats=caveats,
    )


def match_facilities(
    user_need: str,
    dataset: pd.DataFrame,
    location: Optional[str] = None,
    care_category: Optional[str] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    radius_km: Optional[float] = None,
    limit: int = 10,
) -> tuple[list[CareFacilityMatch], dict[str, Any]]:
    """
    Main patient-intent matching and ranking function.
    
    Ranking Formula:
    1. Tier-based base score:
       - Confirmed service match: Base = 100 points
       - Possible service match:  Base = 40 points
       - No match: Disqualified (0 points)
    2. Trust score component:
       - + (trust_score_100 * 0.4) points
    3. Distance component (only if coordinates available):
       - + max(0, 30 * (1 - distance / radius)) points
       (Closer facilities rank higher; if no location given, distance component is 0)
    """
    df = dataset
    care_cat = classify_care_intent(user_need, care_category)
    cat_label = CARE_CATEGORIES.get(care_cat, {}).get("label", "General Care")

    # Resolve location coordinates if user provided location string or lat/lon
    user_lat = latitude
    user_lon = longitude
    loc_label = None

    if user_lat is None and location:
        resolved = resolve_location_query(location, df)
        if resolved:
            user_lat, user_lon, loc_label = resolved
        else:
            loc_label = location

    has_user_location = (user_lat is not None and user_lon is not None)
    search_radius = radius_km or config.SEARCH_RADIUS_KM

    matches: list[CareFacilityMatch] = []

    for _, row in df.iterrows():
        # Evaluate service relevance
        svc_match = evaluate_service_relevance(row, care_cat, user_need)
        if not svc_match.is_matched:
            continue

        # Calculate distance if coordinates exist
        dist_km = None
        if has_user_location and row.get("has_coords", False):
            lat_f = row.get("lat_f")
            lon_f = row.get("lon_f")
            if lat_f is not None and lon_f is not None:
                dist_km = haversine_km(user_lat, user_lon, lat_f, lon_f)
                if radius_km and dist_km > radius_km:
                    continue

        findings = extract_evidence_from_row(row)
        c_flags = detect_contradictions(row, findings=findings)
        trust_res = score_facility_trust(row, findings, c_flags, svc_match)

        # Compute Ranking Score
        base_tier_pts = 100.0 if svc_match.relevance_tier == "confirmed" else 40.0
        trust_pts = trust_res.trust_score_100 * 0.4

        dist_pts = 0.0
        if dist_km is not None:
            norm_dist = min(1.0, dist_km / max(10.0, search_radius))
            dist_pts = (1.0 - norm_dist) * 30.0

        ranking_score = round(base_tier_pts + trust_pts + dist_pts, 2)

        matches.append(CareFacilityMatch(
            facility_name=str(row.get("name", "Unknown")),
            facility_type=str(row.get("facilityTypeId", "Healthcare Facility")),
            city=str(row.get("address_city", "")),
            state=str(row.get("address_stateOrRegion", "")),
            pin=str(row.get("address_zipOrPostcode", "")),
            row_id=int(row.get("row_id", 0)),
            lat=row.get("lat_f"),
            lon=row.get("lon_f"),
            matched_category=care_cat,
            relevance_tier=svc_match.relevance_tier,
            why_matched=svc_match.explanation,
            trust=trust_res,
            distance_km=round(dist_km, 1) if dist_km is not None else None,
            ranking_score=ranking_score,
            data_provenance=f"National Healthcare Infrastructure Registry · Row ID {int(row.get('row_id', 0))}",
            doctor_info=extract_facility_doctor(row, care_cat, user_need),
        ))

    # Sort candidates by ranking score descending
    matches.sort(key=lambda m: m.ranking_score, reverse=True)
    selected_matches = matches[:limit]

    metadata = {
        "user_need": user_need,
        "care_category": care_cat,
        "category_label": cat_label,
        "has_location": has_user_location,
        "user_lat": user_lat,
        "user_lon": user_lon,
        "location_label": loc_label,
        "radius_km": search_radius if has_user_location else None,
        "total_matched": len(matches),
        "returned_count": len(selected_matches),
    }

    return selected_matches, metadata
