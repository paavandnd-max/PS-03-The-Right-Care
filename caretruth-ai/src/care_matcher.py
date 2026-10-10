"""CareTruth AI — Patient Care Intent Matcher.

Understands user healthcare requests, maps them to clinical categories,
and identifies relevant facilities with explainable match rationales.

Supported care categories:
- eye_examination
- general_checkup
- dental_care
- emergency_care
- specialist_consultation
- diagnostic_tests
- pharmacy
- other
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Optional, Any
import pandas as pd

from src.distance import haversine_km, resolve_location_query
from src.evidence_extractor import extract_evidence_from_row, EvidenceFinding
from src.contradiction_detector import detect_contradictions, ContradictionFlag


@dataclass
class ServiceMatch:
    is_matched: bool
    relevance_tier: str       # "confirmed" | "possible" | "none"
    matched_category: str     # e.g. "eye_examination"
    matched_terms: list[str]  # e.g. ["cataract", "ophthalmology"]
    matched_fields: list[str] # e.g. ["specialties", "procedure"]
    explanation: str          # Why this facility matched


# ── Category Taxonomy & Lexicons ─────────────────────────────────────────────
CARE_CATEGORIES: dict[str, dict[str, Any]] = {
    "eye_examination": {
        "label": "Eye examination",
        "primary_specialties": [
            "ophthalmology", "optometry", "eye", "cornea", "retina", "glaucoma", "cataract"
        ],
        "keywords": [
            "eye", "vision", "ophthalm", "optomet", "cataract", "lasik", "retina",
            "glaucoma", "spectacles", "refraction", "cornea", "ocular", "lens"
        ],
        "facility_types": ["eye hospital", "ophthalmic clinic", "eye centre", "vision care"],
        "unverified_checks": [
            "Slit lamp bio-microscopy", "Auto-refractometer calibration", "Ophthalmic surgeon roster"
        ]
    },
    "general_checkup": {
        "label": "General check-up",
        "primary_specialties": [
            "general medicine", "internal medicine", "family medicine", "preventive medicine", "general practice"
        ],
        "keywords": [
            "checkup", "check-up", "routine check", "health check", "general medicine",
            "internal medicine", "physician", "opd", "consultation", "preventive",
            "vital signs", "family doctor", "wellness", "primary care"
        ],
        "facility_types": ["primary health centre", "phc", "community health centre", "chc", "general hospital", "clinic"],
        "unverified_checks": [
            "General physician OPD schedule", "Routine blood pressure / glucometer kit", "Preventive screening protocols"
        ]
    },
    "dental_care": {
        "label": "Dental care",
        "primary_specialties": [
            "dentistry", "dental", "orthodontics", "endodontics", "periodontics", "oral surgery"
        ],
        "keywords": [
            "dental", "dentist", "tooth", "teeth", "root canal", "scaling",
            "extraction", "orthodont", "caries", "cavity", "gums", "implant", "denture"
        ],
        "facility_types": ["dental clinic", "dental hospital", "dental care centre"],
        "unverified_checks": [
            "Dental chair autoclave sterilization", "Dental X-ray / RVG status", "Registered BDS/MDS roster"
        ]
    },
    "emergency_care": {
        "label": "Emergency care",
        "primary_specialties": [
            "emergency medicine", "trauma", "critical care", "intensive care", "casualty"
        ],
        "keywords": [
            "emergency", "urgent", "casualty", "24/7", "24 hours", "24 hr",
            "trauma", "acute", "ambulance", "triage", "icu", "critical care", "accident"
        ],
        "facility_types": ["hospital", "multispeciality hospital", "district hospital", "chc", "trauma centre"],
        "unverified_checks": [
            "Night-time Anaesthesiologist active roster", "Defibrillator & central O2 manifold", "Emergency blood storage unit"
        ]
    },
    "specialist_consultation": {
        "label": "Specialist consultation",
        "primary_specialties": [
            "cardiology", "neurology", "orthopedics", "oncology", "gastroenterology",
            "nephrology", "pulmonology", "pediatrics", "gynecology", "dermatology"
        ],
        "keywords": [
            "specialist", "consultant", "cardiolog", "neurolog", "orthoped", "oncolog",
            "gastro", "nephrol", "pulmon", "pediatric", "gynecolog", "dermatol", "super speciality"
        ],
        "facility_types": ["super speciality hospital", "speciality clinic", "multispeciality hospital"],
        "unverified_checks": [
            "Visiting super-specialist schedule", "Advanced diagnostic equipment", "Specialist registration certificates"
        ]
    },
    "diagnostic_tests": {
        "label": "Diagnostic tests",
        "primary_specialties": [
            "pathology", "radiology", "diagnostics", "biochemistry", "microbiology"
        ],
        "keywords": [
            "diagnostic", "pathology", "blood test", "x-ray", "xray", "ultrasound",
            "mri", "ct scan", "ecg", "laboratory", "lab test", "cbc", "lipid profile", "scan"
        ],
        "facility_types": ["diagnostic centre", "pathology lab", "imaging centre", "laboratory"],
        "unverified_checks": [
            "NABL accreditation certificate", "Reagent cold-chain maintenance log", "Pathologist verification stamp"
        ]
    },
    "pharmacy": {
        "label": "Pharmacy",
        "primary_specialties": [
            "pharmacy", "pharmacology", "dispensary"
        ],
        "keywords": [
            "pharmacy", "chemist", "druggist", "dispensary", "medicine shop",
            "medicines", "drug store", "jan aushadhi", "medical store"
        ],
        "facility_types": ["pharmacy", "medical store", "dispensary", "chemist"],
        "unverified_checks": [
            "Form 20/21 Drug Controller License", "Registered pharmacist on premises", "Vaccine/Insulin refrigerator log"
        ]
    },
    "other": {
        "label": "Other / custom request",
        "primary_specialties": [],
        "keywords": [],
        "facility_types": [],
        "unverified_checks": ["General registration on National Health Portal", "Standard operational hours"]
    }
}


def normalize_query_text(text: str) -> str:
    """Normalize whitespace, punctuation, and case."""
    if not text:
        return ""
    cleaned = re.sub(r"[^\w\s\-/]", " ", text.lower())
    return " ".join(cleaned.split())


def classify_care_intent(user_query: str, explicit_category: Optional[str] = None) -> str:
    """
    Determine the primary care category from user query or explicit category.
    Deterministic regex matching.
    """
    if explicit_category and explicit_category in CARE_CATEGORIES and explicit_category != "other":
        return explicit_category

    normalized = normalize_query_text(user_query)
    if not normalized:
        return "general_checkup"

    # Score categories by keyword matches
    scores: dict[str, int] = {}
    for cat_key, cat_data in CARE_CATEGORIES.items():
        if cat_key == "other":
            continue
        score = 0
        for kw in cat_data["keywords"]:
            pattern = r"\b" + re.escape(kw) + r"\b" if len(kw) <= 4 else re.escape(kw)
            if re.search(pattern, normalized):
                score += 2 if len(kw) > 4 else 1
        for spec in cat_data["primary_specialties"]:
            if spec in normalized:
                score += 3
        if score > 0:
            scores[cat_key] = score

    if scores:
        best_cat = max(scores, key=lambda k: scores[k])
        return best_cat

    # Emergency fallback check
    if any(w in normalized for w in ["emergency", "urgent", "critical", "severe", "accident", "dying"]):
        return "emergency_care"

    return "other"


def evaluate_service_relevance(row: pd.Series, care_category: str, custom_query: str = "") -> ServiceMatch:
    """
    Evaluate whether a facility offers the requested service based on real dataset fields:
    - specialties (list)
    - procedure (list)
    - capability (list)
    - equipment (list)
    - facilityTypeId (str)
    - description (str)
    - name (str)

    Returns ServiceMatch with relevance tier ('confirmed' | 'possible' | 'none').
    """
    cat_info = CARE_CATEGORIES.get(care_category, CARE_CATEGORIES["other"])
    keywords = cat_info["keywords"]
    primary_specs = cat_info["primary_specialties"]
    facility_types = cat_info["facility_types"]

    # Gather facility fields
    spec_list = [str(s).lower() for s in (row.get("spec_list", []) or [])]
    proc_list = [str(p).lower() for p in (row.get("proc_list", []) or [])]
    cap_list  = [str(c).lower() for c in (row.get("cap_list", []) or [])]
    equip_list = [str(e).lower() for e in (row.get("equip_list", []) or [])]
    
    fac_type = str(row.get("facilityTypeId", "")).lower()
    fac_name = str(row.get("name", "")).lower()
    fac_desc = str(row.get("description", "")).lower()

    matched_terms: list[str] = []
    matched_fields: list[str] = []
    relevance_tier = "none"

    # ── Check 1: Primary Specialties & Procedures (CONFIRMED) ───────────────
    # If the facility officially lists the specialty or procedure
    for spec in primary_specs:
        if any(spec in s or s in spec for s in spec_list):
            matched_terms.append(spec)
            if "specialties" not in matched_fields:
                matched_fields.append("specialties")
            relevance_tier = "confirmed"

    for kw in keywords:
        for proc in proc_list:
            if kw in proc:
                matched_terms.append(kw)
                if "procedure" not in matched_fields:
                    matched_fields.append("procedure")
                relevance_tier = "confirmed"
        for cap in cap_list:
            if kw in cap:
                matched_terms.append(kw)
                if "capability" not in matched_fields:
                    matched_fields.append("capability")
                relevance_tier = "confirmed"

    # Facility Type Match (e.g. Eye Hospital or Dental Clinic)
    for ft in facility_types:
        if ft in fac_type or ft in fac_name:
            matched_terms.append(ft)
            if "facilityTypeId" not in matched_fields:
                matched_fields.append("facilityTypeId")
            relevance_tier = "confirmed"

    # ── Check 2: Equipment confirmation ─────────────────────────────────────
    for kw in keywords:
        for eq in equip_list:
            if kw in eq:
                matched_terms.append(kw)
                if "equipment" not in matched_fields:
                    matched_fields.append("equipment")
                relevance_tier = "confirmed"

    # ── Check 3: Description mentions (POSSIBLE if not already confirmed) ──
    if relevance_tier == "none":
        for kw in keywords:
            pattern = r"\b" + re.escape(kw) + r"\b" if len(kw) <= 4 else re.escape(kw)
            if re.search(pattern, fac_desc):
                matched_terms.append(kw)
                if "description" not in matched_fields:
                    matched_fields.append("description")
                relevance_tier = "possible"

    # ── Custom Query Matching (for 'other' or specific user queries) ────────
    if custom_query:
        cq_norm = normalize_query_text(custom_query)
        cq_words = [w for w in cq_norm.split() if len(w) > 3 and w not in ["need", "find", "care", "clinic", "hospital", "near", "want", "please"]]
        cq_matches = []
        for w in cq_words:
            in_spec = any(w in s for s in spec_list)
            in_proc = any(w in p for p in proc_list)
            in_cap  = any(w in c for c in cap_list)
            in_eq   = any(w in e for e in equip_list)
            in_desc = w in fac_desc
            in_name = w in fac_name

            if in_spec or in_proc or in_cap or in_eq:
                cq_matches.append(w)
                relevance_tier = "confirmed"
            elif in_desc or in_name:
                cq_matches.append(w)
                if relevance_tier == "none":
                    relevance_tier = "possible"

        if cq_matches:
            matched_terms.extend(cq_matches)

    # De-duplicate terms
    matched_terms = list(dict.fromkeys(matched_terms))

    # Build human-readable explanation
    if relevance_tier == "confirmed":
        field_str = ", ".join(matched_fields) if matched_fields else "records"
        terms_str = ", ".join(matched_terms[:3])
        explanation = f"Confirmed {cat_info['label']} service supported via explicit {field_str} listing ('{terms_str}')."
    elif relevance_tier == "possible":
        terms_str = ", ".join(matched_terms[:3])
        explanation = f"Possible {cat_info['label']} service identified from facility description ('{terms_str}'). Not listed in primary specialty register."
    else:
        explanation = f"No verified evidence found for {cat_info['label']} in specialties, procedures, or equipment."

    return ServiceMatch(
        is_matched=(relevance_tier != "none"),
        relevance_tier=relevance_tier,
        matched_category=care_category,
        matched_terms=matched_terms,
        matched_fields=matched_fields,
        explanation=explanation,
    )
