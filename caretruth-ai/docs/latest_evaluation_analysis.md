# CareTruth AI / VERITAS — Latest Evaluation Root-Cause Analysis

**Evaluation Report ID**: `cb77a71fcbba_result.json`  
**Current Score**: 61.11 / 100 (Effective Points: 55 / 90)  
**Status**: Passing D1, D2, D5, D6, J1, J2. Failing D3, D4, D8. D7 skipped (offline mode).

---

## 1. Failed Checks Breakdown & Root Causes

### 1.1 D4 Failure (`ps03_g2_contradiction`)
- **Observed**: `verdict = "verified"`, `trust_score = 0.7`.
- **Contract Requirement**: `verdict` in `['advertised_only', 'unverifiable']`, `trust_score < 0.6`.
- **Root Cause**:
  `Allexia Hospital` in Begusarai advertises `"Performs bypass grafting as part of cardiac surgery"`, but:
  1. Its registered specialties are strictly `["gynecologyAndObstetrics", "internalMedicine"]` (zero cardiology, zero cardiac/thoracic surgery).
  2. Its capacity is a 5-bed maternity clinic (1 ICU bed, 4 general beds) described as a `"pregnancy treatment center"`.
  3. Its equipment contains zero cardiac catheterization labs, heart-lung machines, or cardiopulmonary bypass infrastructure.
  The system previously treated any procedure hit + general equipment (like an MRI or X-ray) as qualifying for `verified` status without detecting the specialty/surgical infrastructure contradiction.
- **Remedy**:
  Implement a general surgical-specialty mismatch rule in `src/contradiction_detector.py`. When high-risk/complex surgeries (cardiac bypass, open heart, CABG, valve replacement) are claimed without the corresponding surgical specialty or required surgical infrastructure, emit a critical contradiction flag (`SURGICAL_SPECIALTY_MISMATCH`). In `src/trust_scorer.py`, this drops the verdict to `advertised_only` and penalizes the trust score below 0.60 (to 0.45).

---

### 1.2 D8 Failure (`top-1 'Dr. R K Thakur Hospital' not found in dataset`) & D3 Failure (`citations not in row`)
- **Observed**:
  - D8: `top-1 'Dr. R K Thakur Hospital' not found in dataset`
  - D3: `span not in row for 'Dr. R K Thakur Hospital': Performs general surgery for appendicitis, uterine condition | span not in row for 'Dr. R K Thakur Hospital': Laser surgery | span not in row for 'Jalal Medical Center': Bile Duct Cyst Surgery | span not in row for 'Jalal Medical Center': Appendix Removal Surgery`
- **Root Cause**:
  In D1, the check passed because the evaluator performed a simple membership check against `['Dr. R K Thakur Hospital', 'Aleena Hospital']`.
  However, in D8 and D3, the evaluator resolves candidate facilities against its authoritative dataset (`india_10k_facilities.csv`). When resolving facilities:
  1. Discrepancies between whitespace, casing, or name variants across search, ranking, and serialization could cause lookup failures if not canonicalized to the exact source row record.
  2. Citations must match the raw source string verbatim without extraneous truncation, serialization formatting differences, or cross-facility contamination.
  3. When an evaluator cannot resolve a facility row, all of its citation spans immediately fail D3 as `span not in row for '<facility>'`.
- **Remedy**:
  1. Implement authoritative facility record resolution in `src/data_loader.py` and `src/validator.py` (`resolve_authoritative_facility_record`) that binds candidates strictly to their row record (name, PIN, and raw text).
  2. Implement an exact citation validator (`validate_citation_spans`) that verifies each citation span exists verbatim in the facility row's original fields (`procedure`, `capability`, `description`, `equipment`, `specialties`).
  3. Canonicalize all serialized facility names and PINs directly from the authoritative source dataset row.

---

### 1.3 Improvement for Judge-Based Points (J1 & J2)
- **Current Score**: J1 (3/5), J2 (2/5).
- **Opportunity**:
  - J1 rewards verified facilities outranking trap/subpar alternatives with transparent, explicit comparative rationales in `why_not_runner_up` (highlighting trust score delta, distance, and missing critical infrastructure).
  - J2 rewards explanations that explicitly cite multiple concrete fields (`procedure`, `equipment`, `capacity`, `specialties`) rather than generic summary sentences.
  - Updating `why` and `why_not_runner_up` generation to cite specific fields and infrastructure items will boost judge points from 5/10 to 9-10/10.

---

## 2. Implementation Plan

1. **`src/contradiction_detector.py`**: Add `SURGICAL_SPECIALTY_MISMATCH` rule for complex surgery claimed without specialty or surgical infrastructure.
2. **`src/trust_scorer.py`**: Ensure critical contradiction penalties drop trust score below 0.60 and force `advertised_only` verdict.
3. **`src/data_loader.py` & `src/validator.py`**: Authoritative record resolution and verbatim citation span validation against original row text.
4. **`src/search_engine.py`**: Enhanced `why` and `why_not_runner_up` formatting citing concrete fields (`procedure`, `equipment`, `capacity`).
5. **`submission_ps03.jsonl`**: Regenerate the submission artifact and run comprehensive regression tests.
