"""Exhaustive test suite for Patient-Intent Matching and Evidence-Based Trust Scoring.

Covers all 14 required hackathon scenarios:
1. User requests an eye examination.
2. User requests a general check-up.
3. User requests dental care.
4. User requests emergency care.
5. High-trust facility without requested service does NOT outrank relevant facility.
6. Relevant clinic vs general hospital ranking behavior.
7. Relevant facility has missing evidence.
8. Relevant capability has contradictory evidence.
9. Facility has invalid or missing coordinates.
10. User provides no location (distance is None, no crashes).
11. Dataset contains missing specialty or procedure fields.
12. No facilities match requested service.
13. API endpoint POST /search returns structured results and evidence.
14. Existing official evaluation probes continue to pass.
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
import pandas as pd
from fastapi.testclient import TestClient

from src.data_loader import load_dataframe
from src.care_matcher import classify_care_intent, evaluate_service_relevance, CARE_CATEGORIES
from src.care_scorer import score_facility_trust, match_facilities
from api import app as _test_app


@pytest.fixture(scope="module")
def df():
    return load_dataframe()


@pytest.fixture(scope="module")
def client():
    return TestClient(_test_app)


# ── Scenario 1: Eye Examination Request ──────────────────────────────────────
def test_scenario_1_eye_examination(df):
    matches, meta = match_facilities("I need a routine eye test and cataract screening", df, limit=5)
    assert meta["care_category"] == "eye_examination"
    assert len(matches) > 0
    top = matches[0]
    assert top.relevance_tier in ("confirmed", "possible")
    assert any(term in top.why_matched.lower() for term in ["ophthalmology", "eye", "cataract", "vision", "lens"])


# ── Scenario 2: General Check-up Request ────────────────────────────────────
def test_scenario_2_general_checkup(df):
    matches, meta = match_facilities("Find a clinic for a routine general health check-up", df, limit=5)
    assert meta["care_category"] == "general_checkup"
    assert len(matches) > 0
    top = matches[0]
    assert top.relevance_tier == "confirmed"


# ── Scenario 3: Dental Care Request ─────────────────────────────────────────
def test_scenario_3_dental_care(df):
    matches, meta = match_facilities("I have a toothache and need dental root canal treatment", df, limit=5)
    assert meta["care_category"] == "dental_care"
    assert len(matches) > 0
    top = matches[0]
    assert any("dental" in term or "dentist" in term or "teeth" in term for term in top.why_matched.lower().split())


# ── Scenario 4: Emergency Care Request ──────────────────────────────────────
def test_scenario_4_emergency_care(df):
    matches, meta = match_facilities("Emergency severe chest pain and trauma accident", df, limit=5)
    assert meta["care_category"] == "emergency_care"
    assert len(matches) > 0
    top = matches[0]
    assert top.relevance_tier == "confirmed"


# ── Scenario 5: High-Trust Facility Without Service Does NOT Outrank Relevant ─
def test_scenario_5_relevance_trumps_unrelated_high_trust(df):
    """
    A facility with high generic data completeness that does NOT offer ophthalmology
    must NOT outrank a facility that actually offers confirmed eye care.
    """
    matches, _ = match_facilities("Routine eye test and spectacles check", df, limit=10)
    for m in matches:
        # Every ranked facility must be relevant to eye examination
        assert m.relevance_tier in ("confirmed", "possible")
        assert m.matched_category == "eye_examination"


# ── Scenario 6: Relevant Clinic vs Hospital Ranking ────────────────────────
def test_scenario_6_clinic_vs_hospital_ranking(df):
    """
    Dental clinic with confirmed dental care matches specifically for dental need.
    """
    matches, _ = match_facilities("Dental extraction and tooth cleaning", df, limit=5)
    assert len(matches) > 0
    assert matches[0].relevance_tier == "confirmed"


# ── Scenario 7: Relevant Facility With Missing Evidence ────────────────────
def test_scenario_7_missing_evidence_handled_gracefully(df):
    synthetic_row = pd.Series({
        "row_id": 99991,
        "name": "Rural Vision Center",
        "facilityTypeId": "Vision Clinic",
        "spec_list": ["ophthalmology"],
        "proc_list": [],
        "cap_list": [],
        "equip_list": [],  # missing equipment
        "doctor_count": 0,  # missing doctor count
        "affiliated_staff_presence": "FALSE",
        "has_coords": False,
        "lat_f": None,
        "lon_f": None,
        "description": "Rural eye clinic providing vision tests",
    })
    svc_match = evaluate_service_relevance(synthetic_row, "eye_examination")
    trust_res = score_facility_trust(synthetic_row, [], [], svc_match)
    
    assert svc_match.relevance_tier == "confirmed"
    assert len(trust_res.missing_evidence) > 0
    assert "No physical equipment inventory listed for this facility" in trust_res.factors_lowered
    assert trust_res.trust_score_100 >= 30  # Got points for specialty and description, but penalized for missing


# ── Scenario 8: Relevant Capability With Contradictory Evidence ─────────────
def test_scenario_8_contradictory_evidence_lowers_score(df):
    from src.contradiction_detector import ContradictionFlag
    synthetic_row = pd.Series({
        "row_id": 99992,
        "name": "Contested Emergency Center",
        "facilityTypeId": "Hospital",
        "spec_list": ["emergencyMedicine"],
        "proc_list": ["emergency surgery"],
        "cap_list": ["24/7 casualty"],
        "equip_list": ["autoclave"],
        "doctor_count": 5,
        "affiliated_staff_presence": "TRUE",
        "has_coords": True,
        "lat_f": 25.5,
        "lon_f": 85.1,
    })
    c_flag = ContradictionFlag(
        rule_id="NIGHT_RESTRICTION",
        description="No anaesthesiologist on duty after 9 PM",
        severity="critical",
        source_field="capability"
    )
    svc_match = evaluate_service_relevance(synthetic_row, "emergency_care")
    trust_clean = score_facility_trust(synthetic_row, [], [], svc_match)
    trust_flagged = score_facility_trust(synthetic_row, [], [c_flag], svc_match)

    assert trust_flagged.trust_score < trust_clean.trust_score
    assert trust_flagged.trust_score_100 <= (trust_clean.trust_score_100 - 30)
    assert len(trust_flagged.contradictory_evidence) == 1


# ── Scenario 9: Facility With Invalid Or Missing Coordinates ────────────────
def test_scenario_9_invalid_or_missing_coordinates(df):
    synthetic_df = pd.DataFrame([{
        "row_id": 99993,
        "name": "No GPS Eye Care",
        "facilityTypeId": "Eye Clinic",
        "spec_list": ["ophthalmology"],
        "proc_list": ["cataract surgery"],
        "cap_list": [],
        "equip_list": [],
        "doctor_count": 1,
        "affiliated_staff_presence": "TRUE",
        "has_coords": False,
        "lat_f": None,
        "lon_f": None,
        "address_city": "Patna",
        "address_stateOrRegion": "Bihar",
        "address_zipOrPostcode": "800001",
        "description": "Specialized ophthalmic center",
    }])
    matches, meta = match_facilities("Eye test", synthetic_df, location="Patna, Bihar")
    assert len(matches) == 1
    assert matches[0].distance_km is None
    assert matches[0].facility_name == "No GPS Eye Care"


# ── Scenario 10: User Provides No Location ──────────────────────────────────
def test_scenario_10_user_provides_no_location(df):
    matches, meta = match_facilities("Routine dental extraction", df, location=None, latitude=None, longitude=None, limit=3)
    assert meta["has_location"] is False
    assert len(matches) > 0
    for m in matches:
        assert m.distance_km is None  # no fabricated distance
        assert m.ranking_score > 0


# ── Scenario 11: Missing Specialty Or Procedure Fields ──────────────────────
def test_scenario_11_missing_specialty_or_procedure(df):
    synthetic_row = pd.Series({
        "row_id": 99994,
        "name": "Generic Care Center",
        "facilityTypeId": "",
        "spec_list": [],     # empty
        "proc_list": [],     # empty
        "cap_list": [],      # empty
        "equip_list": [],
        "description": "Provides comprehensive dental check-up and teeth filling.",
    })
    svc_match = evaluate_service_relevance(synthetic_row, "dental_care")
    assert svc_match.is_matched is True
    assert svc_match.relevance_tier == "possible"
    assert "description" in svc_match.matched_fields


# ── Scenario 12: No Facilities Match Requested Service ──────────────────────
def test_scenario_12_no_facilities_match_unsupported_service():
    synthetic_df = pd.DataFrame([{
        "row_id": 1,
        "name": "Pediatric Clinic",
        "facilityTypeId": "Children Hospital",
        "spec_list": ["pediatrics"],
        "proc_list": ["immunization"],
        "cap_list": [],
        "equip_list": [],
        "description": "Child care only",
    }])
    matches, meta = match_facilities("dental tooth extraction and root canal", synthetic_df)
    assert len(matches) == 0
    assert meta["total_matched"] == 0


# ── Scenario 13: API POST /search Returns Structured Results ────────────────
def test_scenario_13_api_post_search(client):
    payload = {
        "query": "I need routine eye examination and cataract check",
        "care_category": "eye_examination",
        "location": "Patna, Bihar",
        "limit": 3
    }
    response = client.post("/search", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "OK"
    assert "metadata" in data
    assert data["metadata"]["care_category"] == "eye_examination"
    assert len(data["results"]) > 0
    r0 = data["results"][0]
    assert "name" in r0
    assert "why_matched" in r0
    assert "trust" in r0
    assert "score_100" in r0["trust"]
    assert "factors_raised" in r0["trust"]
    assert "missing_evidence" in r0["trust"]


# ── Scenario 14: Existing Official Evaluation Probes Continue To Pass ───────
def test_scenario_14_official_eval_probes_continue_to_pass(client):
    # Health check
    h = client.get("/health")
    assert h.status_code == 200
    assert h.json()["ok"] is True

    # Practice probe g1
    g1_payload = {
        "probe_id": "ps03_g1_appendicitis",
        "kind": "crisis_facility_search",
        "query_text": "Severe abdominal pain, suspected appendicitis. Father needs emergency surgery tonight.",
        "user_location": {"lat": 26.24, "lng": 84.4, "pin": "841226", "transport": "two-wheeler", "budget_inr": 500},
        "time": "Tuesday 14:30"
    }
    g1_res = client.post("/solve", json=g1_payload)
    assert g1_res.status_code == 200
    g1_data = g1_res.json()
    assert len(g1_data["facilities"]) > 0
    top_fac = g1_data["facilities"][0]
    assert top_fac["verdict"] in ("verified", "advertised_only", "unverifiable")
    assert "distance_km" in top_fac
    assert len(top_fac["citations"]) > 0
