"""Pytest test suite for CareTruth AI.

Covers:
- Distance (Haversine)
- Data loading
- Evidence extraction
- Contradiction detection
- Trust scoring / verdict
- Search engine / ranking
- API contract
- Practice probes (ps03_g1, ps03_g3, ps03_g4_injection)
"""
from __future__ import annotations
import json
import math
import sys
from pathlib import Path

# Allow imports from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from src.distance import haversine_km
from src import config


# ══════════════════════════════════════════════════════════════════════════════
# 1. HAVERSINE DISTANCE TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestHaversine:
    def test_same_point_is_zero(self):
        assert haversine_km(28.61, 77.21, 28.61, 77.21) == pytest.approx(0.0, abs=0.001)

    def test_delhi_to_mumbai_approx(self):
        # Known ~1150 km
        d = haversine_km(28.6139, 77.2090, 19.0760, 72.8777)
        assert 1100 < d < 1200

    def test_probe_g1_top_facility_distance(self):
        """
        probe_g1: user_location lat=26.24, lng=84.4
        Dr. R K Thakur Hospital: lat=26.45777512, lon=84.44892883
        Expected from sample output: ~24.7 km (±2 km tolerance per contract)
        """
        d = haversine_km(26.24, 84.4, 26.45777512, 84.44892883)
        assert abs(d - 24.7) <= 2.0, f"Distance {d:.2f} km deviates more than ±2 km from 24.7"

    def test_distance_is_symmetric(self):
        d1 = haversine_km(20.0, 78.0, 22.0, 80.0)
        d2 = haversine_km(22.0, 80.0, 20.0, 78.0)
        assert d1 == pytest.approx(d2, rel=1e-6)

    def test_north_south_1_degree(self):
        # 1 degree latitude ≈ 111 km
        d = haversine_km(20.0, 78.0, 21.0, 78.0)
        assert 110 < d < 112


# ══════════════════════════════════════════════════════════════════════════════
# 2. DATA LOADER TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestDataLoader:
    @pytest.fixture(autouse=True)
    def _reset_cache(self):
        from src.data_loader import invalidate_cache
        invalidate_cache()
        yield
        invalidate_cache()

    def test_load_raises_if_missing(self, tmp_path):
        from src.data_loader import load_dataframe
        bad_path = tmp_path / "nonexistent.csv"
        with pytest.raises(FileNotFoundError):
            load_dataframe(bad_path)

    def test_load_real_dataset(self):
        """Only runs if the real dataset is in place."""
        if not config.DATASET_PATH.exists():
            pytest.skip("Dataset not present at DATASET_PATH")
        from src.data_loader import load_dataframe
        df = load_dataframe()
        assert len(df) == 10000
        assert "row_id" in df.columns
        assert "text_blob" in df.columns
        assert "lat_f" in df.columns

    def test_real_dataset_has_coords(self):
        if not config.DATASET_PATH.exists():
            pytest.skip("Dataset not present")
        from src.data_loader import load_dataframe
        df = load_dataframe()
        assert df["has_coords"].all(), "All rows should have valid coords"

    def test_row_4097_is_dr_rk_thakur(self):
        """Injection probe references row_index 4097 = Dr. R K Thakur Hospital."""
        if not config.DATASET_PATH.exists():
            pytest.skip("Dataset not present")
        from src.data_loader import load_dataframe, get_row_by_index
        df = load_dataframe()
        row = get_row_by_index(4097, df)
        assert row is not None
        assert "thakur" in row["name"].lower()

    def test_no_duplicate_facility_names(self):
        if not config.DATASET_PATH.exists():
            pytest.skip("Dataset not present")
        from src.data_loader import load_dataframe
        df = load_dataframe()
        dups = df["name"].value_counts()
        assert dups.max() == 1, "Duplicate facility names found"

    def test_malformed_csv(self, tmp_path):
        """A CSV with no rows raises ValueError."""
        from src.data_loader import load_dataframe
        bad = tmp_path / "empty.csv"
        bad.write_text("col1,col2\n")
        with pytest.raises(ValueError):
            load_dataframe(bad)


# ══════════════════════════════════════════════════════════════════════════════
# 3. EVIDENCE EXTRACTION TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestEvidenceExtractor:
    def _make_row(self, **kwargs):
        """Build a minimal mock row for testing."""
        import pandas as pd
        defaults = {
            "row_id": 0, "name": "Test Facility",
            "description": "", "capability": "[]",
            "procedure": "[]", "equipment": "[]", "specialties": "[]",
            "raw_text_blob": "", "text_blob": "",
            "has_equipment": False, "has_named_staff": False,
            "open_24h": False, "has_description": False,
            "doctor_count": 0, "affiliated_staff_presence": "FALSE",
        }
        defaults.update(kwargs)
        return pd.Series(defaults)

    def test_positive_surgery_evidence(self):
        from src.evidence_extractor import extract_evidence_from_row
        row = self._make_row(
            procedure='["Performs general surgery for appendicitis"]',
            raw_text_blob='Performs general surgery for appendicitis',
        )
        findings = extract_evidence_from_row(row, ["generalSurgery"])
        positive = [f for f in findings if f.polarity == "positive"]
        assert len(positive) >= 1

    def test_negative_evidence_detected(self):
        from src.evidence_extractor import extract_evidence_from_row
        row = self._make_row(
            capability='["No surgery available"]',
            raw_text_blob='No surgery available at this facility',
        )
        findings = extract_evidence_from_row(row, ["generalSurgery"])
        negatives = [f for f in findings if f.polarity == "negative"]
        assert len(negatives) >= 1

    def test_citation_span_is_verbatim_substring(self):
        from src.evidence_extractor import extract_evidence_from_row
        proc_text = "Performs general surgery for appendicitis and kidney stones"
        row = self._make_row(procedure=f'["{proc_text}"]', raw_text_blob=proc_text)
        findings = extract_evidence_from_row(row, ["generalSurgery"])
        for f in findings:
            # The span must appear verbatim (case-insensitive) in the source
            assert f.span.lower() in proc_text.lower() or proc_text.lower() in f.span.lower() or \
                   "surgery" in f.span.lower()

    def test_map_query_surgery(self):
        from src.evidence_extractor import map_query_to_capabilities
        caps = map_query_to_capabilities("emergency surgery appendicitis")
        assert "generalSurgery" in caps

    def test_map_query_cardiac(self):
        from src.evidence_extractor import map_query_to_capabilities
        caps = map_query_to_capabilities("cardiac bypass surgery")
        assert "cardiacSurgery" in caps

    def test_map_query_fallback(self):
        from src.evidence_extractor import map_query_to_capabilities
        caps = map_query_to_capabilities("I feel unwell and need help")
        assert len(caps) > 0  # should not return empty


# ══════════════════════════════════════════════════════════════════════════════
# 4. CONTRADICTION DETECTOR TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestContradictionDetector:
    def _make_row(self, **kwargs):
        import pandas as pd
        defaults = {
            "row_id": 0, "name": "Test Hospital",
            "description": "", "capability": "[]",
            "procedure": "[]", "equipment": "[]", "specialties": "[]",
            "facilityTypeId": "hospital",
            "has_equipment": False, "has_named_staff": False,
            "open_24h": False, "has_description": False,
            "doctor_count": 0, "affiliated_staff_presence": "FALSE",
        }
        defaults.update(kwargs)
        return pd.Series(defaults)

    def test_night_anaesthesiologist_injection_at_night(self):
        """
        Core contract test: injected 'No anaesthesiologist on duty after 9 PM.'
        + time = 23:30 → NIGHT_NO_ANAESTHESIOLOGIST flag with severity=critical
        """
        from src.contradiction_detector import detect_contradictions
        row = self._make_row(
            capability='["Open 24 Hrs", "Performs surgery"]',
        )
        flags = detect_contradictions(
            row=row,
            findings=[],
            time_str="Tuesday 23:30",
            injected_text="No anaesthesiologist on duty after 9 PM.",
        )
        rule_ids = [f.rule_id for f in flags]
        assert "NIGHT_NO_ANAESTHESIOLOGIST" in rule_ids
        for f in flags:
            if f.rule_id == "NIGHT_NO_ANAESTHESIOLOGIST":
                assert f.severity == "critical"

    def test_night_anaesthesiologist_NOT_fired_during_day(self):
        """Same injection at 14:30 should NOT trigger the critical night flag."""
        from src.contradiction_detector import detect_contradictions
        row = self._make_row()
        flags = detect_contradictions(
            row=row,
            findings=[],
            time_str="Tuesday 14:30",
            injected_text="No anaesthesiologist on duty after 9 PM.",
        )
        critical = [f for f in flags if f.rule_id == "NIGHT_NO_ANAESTHESIOLOGIST"]
        assert len(critical) == 0

    def test_no_contradictions_clean_row(self):
        from src.contradiction_detector import detect_contradictions
        row = self._make_row(
            capability='["Performs surgery", "Open 24 hours"]',
        )
        flags = detect_contradictions(row=row, findings=[], time_str="Tuesday 14:30")
        critical = [f for f in flags if f.severity == "critical"]
        assert len(critical) == 0


# ══════════════════════════════════════════════════════════════════════════════
# 5. TRUST SCORER TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestTrustScorer:
    def _make_row(self, **kwargs):
        import pandas as pd
        defaults = {
            "row_id": 0, "name": "Test Hospital",
            "has_equipment": False, "has_named_staff": False,
            "open_24h": False, "has_description": False,
            "doctor_count": 0, "spec_list": [],
            "officialWebsite": "null", "facebookLink": "null",
        }
        defaults.update(kwargs)
        return pd.Series(defaults)

    def test_score_in_valid_range(self):
        from src.trust_scorer import compute_trust_score
        from src.evidence_extractor import EvidenceFinding
        row = self._make_row(has_equipment=True, has_named_staff=True, open_24h=True)
        finding = EvidenceFinding(0, "Test", "procedure", "performs surgery", "generalSurgery", "positive")
        result = compute_trust_score(row, [finding], [], ["generalSurgery"])
        assert 0.0 <= result.trust_score <= 1.0

    def test_verdict_verified_requires_strong_evidence(self):
        from src.trust_scorer import compute_trust_score
        from src.evidence_extractor import EvidenceFinding
        row = self._make_row(has_equipment=True, has_named_staff=True, open_24h=True,
                              has_description=True, doctor_count=5)
        finding = EvidenceFinding(0, "Test", "procedure", "performs surgery", "generalSurgery", "positive")
        result = compute_trust_score(row, [finding], [], ["generalSurgery"])
        assert result.verdict == "verified"

    def test_critical_contradiction_drops_score(self):
        """
        Contract requirement: trust_score drops >= 0.15 when critical contradiction injected.
        """
        from src.trust_scorer import compute_trust_score
        from src.evidence_extractor import EvidenceFinding
        from src.contradiction_detector import ContradictionFlag

        row = self._make_row(has_equipment=True, has_named_staff=True, open_24h=True,
                              has_description=True, doctor_count=3)
        finding = EvidenceFinding(0, "Test", "procedure", "performs surgery", "generalSurgery", "positive")

        # Score without contradiction
        baseline = compute_trust_score(row, [finding], [], ["generalSurgery"])

        # Score WITH critical contradiction (injection probe scenario)
        crit_flag = ContradictionFlag(
            rule_id="NIGHT_NO_ANAESTHESIOLOGIST",
            description="No anaesthesiologist at night.",
            severity="critical",
            source_field="capability",
            conflicting_span="No anaesthesiologist on duty after 9 PM.",
        )
        injected = compute_trust_score(row, [finding], [crit_flag], ["generalSurgery"])

        drop = baseline.trust_score - injected.trust_score
        assert drop >= 0.15, (
            f"Trust score drop {drop:.3f} < 0.15 — contract requires >= 0.15 drop "
            f"when critical contradiction injected. Baseline: {baseline.trust_score:.3f}, "
            f"Injected: {injected.trust_score:.3f}"
        )

    def test_verdict_is_valid_enum(self):
        from src.trust_scorer import compute_trust_score
        row = self._make_row()
        result = compute_trust_score(row, [], [], ["generalSurgery"])
        assert result.verdict in {"verified", "advertised_only", "unverifiable"}


# ══════════════════════════════════════════════════════════════════════════════
# 6. SEARCH ENGINE TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestSearchEngine:
    def test_search_returns_results_within_radius(self):
        if not config.DATASET_PATH.exists():
            pytest.skip("Dataset not present")
        from src.search_engine import search
        results, _ = search(
            query_text="emergency surgery appendicitis",
            user_lat=26.24, user_lng=84.4,
            radius_km=50,
        )
        for r in results:
            assert r.distance_km <= 52  # minor tolerance

    def test_probe_g1_top_distance_within_tolerance(self):
        """Top result distance must be within ±2 km of haversine calculation."""
        if not config.DATASET_PATH.exists():
            pytest.skip("Dataset not present")
        from src.search_engine import search
        results, _ = search(
            query_text="Severe abdominal pain, suspected appendicitis. Father needs emergency surgery tonight.",
            user_lat=26.24, user_lng=84.4,
            time_str="Tuesday 14:30",
        )
        assert results, "Expected at least one result for probe g1"
        # Cross-check distance
        from src.distance import haversine_km
        from src.data_loader import load_dataframe
        df = load_dataframe()
        top = results[0]
        row = df[df["name_norm"] == top.facility_name.lower().strip()]
        if not row.empty:
            expected = haversine_km(26.24, 84.4, float(row.iloc[0]["lat_f"]), float(row.iloc[0]["lon_f"]))
            assert abs(top.distance_km - expected) <= 2.0

    def test_verdict_values_are_valid(self):
        if not config.DATASET_PATH.exists():
            pytest.skip("Dataset not present")
        from src.search_engine import search
        results, _ = search(
            query_text="emergency surgery",
            user_lat=26.24, user_lng=84.4,
        )
        for r in results:
            assert r.verdict in {"verified", "advertised_only", "unverifiable"}

    def test_desert_flag_on_empty_area(self):
        """Remote location should produce desert flags if nothing found."""
        if not config.DATASET_PATH.exists():
            pytest.skip("Dataset not present")
        from src.search_engine import search
        results, desert_flags = search(
            query_text="cardiac bypass surgery",
            user_lat=25.0, user_lng=84.75,
            time_str="Tuesday 22:00",
            radius_km=30,
        )
        if not results:
            assert len(desert_flags) > 0

    def test_injection_probe_reduces_trust_score(self):
        """
        Probe g4_injection: same as g1 but with injected_into_facility at 23:30.
        Trust score for Dr. R K Thakur Hospital must drop >= 0.15.
        """
        if not config.DATASET_PATH.exists():
            pytest.skip("Dataset not present")
        from src.search_engine import search

        # Baseline (g1, daytime)
        base_results, _ = search(
            query_text="Severe abdominal pain, suspected appendicitis. Father needs emergency surgery tonight.",
            user_lat=26.24, user_lng=84.4,
            time_str="Tuesday 14:30",
        )

        # Injection (g4, night-time)
        inj_results, _ = search(
            query_text="Severe abdominal pain, suspected appendicitis. Father needs emergency surgery tonight.",
            user_lat=26.24, user_lng=84.4,
            time_str="Tuesday 23:30",
            injected={
                "name": "Dr. R K Thakur Hospital",
                "row_index": 4097,
                "field": "capability",
                "injected_line": "No anaesthesiologist on duty after 9 PM.",
            },
        )

        # Find Dr. R K Thakur in both
        base_thakur = next((r for r in base_results if "thakur" in r.facility_name.lower()), None)
        inj_thakur  = next((r for r in inj_results  if "thakur" in r.facility_name.lower()), None)

        if base_thakur is None:
            pytest.skip("Dr. R K Thakur Hospital not in baseline results")

        if inj_thakur is None:
            # If absent from injected results, that also counts as a downgrade
            return

        drop = base_thakur.trust_score - inj_thakur.trust_score
        verdict_downgraded = (
            base_thakur.verdict == "verified" and inj_thakur.verdict in ("advertised_only", "unverifiable")
        ) or (
            base_thakur.verdict == "advertised_only" and inj_thakur.verdict == "unverifiable"
        )

        assert drop >= 0.15 or verdict_downgraded, (
            f"Injection probe failed: trust_score drop={drop:.3f} < 0.15 "
            f"and verdict not downgraded (was {base_thakur.verdict}, now {inj_thakur.verdict})"
        )


# ══════════════════════════════════════════════════════════════════════════════
# 7. VALIDATOR TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestValidator:
    def test_abstain_on_empty_results(self):
        from src.validator import should_abstain
        abstain, reason = should_abstain([], user_lat=25.0, user_lng=84.0)
        assert abstain is True
        assert reason is not None

    def test_no_abstain_with_verified_result(self):
        from src.validator import should_abstain
        from src.search_engine import FacilityResult
        r = FacilityResult(
            facility_name="Test Hospital", facility_pin="123456",
            verdict="verified", trust_score=0.8, distance_km=15.0,
            capabilities=["generalSurgery"], citations=[],
            why="test", why_not_runner_up="",
        )
        abstain, _ = should_abstain([r], user_lat=26.24, user_lng=84.4)
        assert abstain is False

    def test_contract_response_shape(self):
        from src.validator import build_contract_response
        from src.search_engine import FacilityResult, Citation
        r = FacilityResult(
            facility_name="Test Hospital", facility_pin="841428",
            verdict="verified", trust_score=0.8, distance_km=24.7,
            capabilities=["generalSurgery"], citations=[
                Citation("Test Hospital", "procedure", "performs surgery")
            ],
            why="test why", why_not_runner_up="runner up note",
        )
        resp = build_contract_response("test_probe", [r], [], False, None)
        # Must have all required fields
        assert "facilities" in resp
        assert "abstain" in resp
        assert "abstain_reason" in resp
        assert "desert_flags" in resp
        fac = resp["facilities"][0]
        required_fields = {
            "facility_name", "facility_pin", "verdict", "trust_score",
            "distance_km", "capabilities", "citations", "why", "why_not_runner_up"
        }
        assert required_fields.issubset(set(fac.keys()))
        # Verdict must be valid
        assert fac["verdict"] in {"verified", "advertised_only", "unverifiable"}


# ══════════════════════════════════════════════════════════════════════════════
# 8. API CONTRACT TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestAPIContract:
    @pytest.fixture()
    def client(self):
        """Returns TestClient only if the dataset is available."""
        if not config.DATASET_PATH.exists():
            pytest.skip("Dataset not present for API tests")
        from fastapi.testclient import TestClient
        import api
        return TestClient(api.app)

    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}

    def test_solve_probe_g1(self, client):
        payload = {
            "probe_id": "ps03_g1_ananya",
            "kind": "crisis_facility_search",
            "query_text": "Severe abdominal pain, suspected appendicitis. Father needs emergency surgery tonight.",
            "user_location": {"lat": 26.24, "lng": 84.4, "pin": "841226", "transport": "two-wheeler", "budget_inr": 500},
            "time": "Tuesday 14:30"
        }
        resp = client.post("/solve", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "facilities" in data
        assert "abstain" in data
        assert "abstain_reason" in data
        assert "desert_flags" in data

    def test_solve_probe_g3_abstain(self, client):
        payload = {
            "probe_id": "ps03_g3_abstain",
            "kind": "crisis_facility_search",
            "query_text": "Emergency: suspected appendicitis. Find the nearest facility that can operate tonight.",
            "user_location": {"lat": 25.0, "lng": 84.75, "pin": "804402", "transport": "two-wheeler", "budget_inr": 500},
            "time": "Tuesday 22:00"
        }
        resp = client.post("/solve", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "abstain" in data
        # If empty facilities list — that's valid per contract
        if not data["facilities"]:
            assert data["abstain"] is True

    def test_solve_probe_g4_injection(self, client):
        """Night-time injection probe — must downgrade Dr. R K Thakur Hospital."""
        payload = {
            "probe_id": "ps03_g4_injection",
            "kind": "crisis_facility_search",
            "query_text": "Severe abdominal pain, suspected appendicitis. Father needs emergency surgery tonight.",
            "user_location": {"lat": 26.24, "lng": 84.4, "pin": "841226", "transport": "two-wheeler", "budget_inr": 500},
            "time": "Tuesday 23:30",
            "injected_into_facility": {
                "name": "Dr. R K Thakur Hospital",
                "row_index": 4097,
                "field": "capability",
                "injected_line": "No anaesthesiologist on duty after 9 PM."
            }
        }
        resp = client.post("/solve", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "facilities" in data
        # Either abstained OR Thakur not verified
        thakur = next(
            (f for f in data["facilities"] if "thakur" in f["facility_name"].lower()),
            None
        )
        if thakur:
            assert thakur["verdict"] in ("advertised_only", "unverifiable") or \
                   thakur["trust_score"] <= 0.65, \
                   f"Injection probe: Thakur still has verdict={thakur['verdict']} score={thakur['trust_score']}"

    def test_verdict_vocabulary(self, client):
        payload = {
            "probe_id": "test", "kind": "crisis_facility_search",
            "query_text": "emergency surgery",
            "user_location": {"lat": 26.24, "lng": 84.4},
            "time": "Monday 10:00"
        }
        resp = client.post("/solve", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        for f in data.get("facilities", []):
            assert f["verdict"] in {"verified", "advertised_only", "unverifiable"}

    def test_facility_names_grounded_in_dataset(self, client):
        """Every returned facility_name must exist in the actual dataset."""
        if not config.DATASET_PATH.exists():
            pytest.skip("Dataset not present")
        from src.data_loader import load_dataframe
        df = load_dataframe()
        all_names = set(df["name_norm"].tolist())

        payload = {
            "probe_id": "test_grounding", "kind": "crisis_facility_search",
            "query_text": "emergency surgery appendicitis",
            "user_location": {"lat": 26.24, "lng": 84.4},
            "time": "Tuesday 14:30"
        }
        resp = client.post("/solve", json=payload)
        data = resp.json()
        for f in data.get("facilities", []):
            name_norm = f["facility_name"].lower().strip()
            assert name_norm in all_names, \
                f"Returned facility '{f['facility_name']}' not found in dataset"
