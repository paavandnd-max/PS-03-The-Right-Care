# CareTruth AI — AGENTS.md
## NIT Delhi Hackathon · Problem Statement PS-03: Healthcare Intelligence

---

## Project Overview
CareTruth AI is an evidence-backed healthcare facility intelligence system that:
- Extracts capabilities from 10,000 real Indian facility records
- Detects contradictions between claimed services and operational notes
- Ranks facilities for a user query using grounded evidence + Haversine distance
- Implements the official PS-03 POST /solve evaluation contract exactly

## Dataset
- **File**: `Hackathon_Dataset_India_Larg.csv` (10,000 rows, 41 columns)
- **Path at runtime**: configured in `src/config.py` via `DATASET_PATH` env var
- **Key columns**: name, description, capability (JSON list), procedure (JSON list),
  specialties (JSON list), equipment (JSON list), latitude, longitude,
  address_zipOrPostcode, address_stateOrRegion, address_city, facilityTypeId,
  numberDoctors, capacity, affiliated_staff_presence
- **Row index**: 0-based position in CSV (used as source_row_id)
- **Duplicate names**: None found in dataset (verified)
- **Coordinate coverage**: 10,000/10,000 rows have valid lat/lon

## Official PS-03 Contract (source of truth)
See `reference/participant_eval_kit/participant_eval_kit/contracts/ps03_contract.md`

### Endpoint
```
POST /solve          — main evaluation endpoint
GET  /health         — returns {"ok": true}
Timeout: 8 seconds
```

### Input Schema
```json
{
  "probe_id": "ps03_g1_ananya",
  "kind": "crisis_facility_search",
  "query_text": "...",
  "user_location": {"lat": 26.24, "lng": 84.4, "pin": "841226",
                    "transport": "two-wheeler", "budget_inr": 500},
  "time": "Tuesday 14:30",
  "injected_into_facility": {           // OPTIONAL — injection probe only
    "name": "Dr. R K Thakur Hospital",
    "row_index": 4097,
    "field": "capability",
    "injected_line": "No anaesthesiologist on duty after 9 PM."
  }
}
```

### Output Schema
```json
{
  "facilities": [
    {
      "facility_name": "Dr. R K Thakur Hospital",
      "facility_pin":  "841428",
      "verdict":       "verified",          // verified|advertised_only|unverifiable
      "trust_score":   0.82,               // float 0..1
      "distance_km":   24.7,
      "capabilities":  ["generalSurgery", "emergencyMedicine"],
      "citations":     [
        {"facility_name": "Dr. R K Thakur Hospital",
         "source_field":  "procedure",
         "span":          "Performs general surgery for appendicitis"}
      ],
      "why":             "...",
      "why_not_runner_up": "..."
    }
  ],
  "abstain":       false,
  "abstain_reason": null,
  "desert_flags":  []
}
```

### Verdict Rules
- `verified`: Equipment OR named staff OR explicit 24/7 claim present
- `advertised_only`: Capability/specialty listed but no equipment, no named staff
- `unverifiable`: Insufficient evidence to assess

### Contract Enforcement (checked by evaluator)
1. `facility_name` must match a real dataset row (normalised name + PIN)
2. Every `citations[].span` must be a verbatim substring of that row's text fields
3. `distance_km` (top result) must match Haversine ± 2 km
4. Injection probe: trust_score drops ≥ 0.15 OR verdict downgrades when
   "No anaesthesiologist on duty after 9 PM." is in capability AND time > 21:00
5. Abstain when no facility within range has sufficient evidence

---

## Architecture
```
Dataset (CSV)
  -> DataLoader      (src/data_loader.py)   — reads, caches, row-indexes
  -> Normalizer      (src/normalizer.py)    — parses JSON fields, cleans nulls
  -> EvidenceExtractor (src/evidence_extractor.py) — per-row capability evidence
  -> ContradictionDetector (src/contradiction_detector.py) — flags conflicts
  -> TrustScorer     (src/trust_scorer.py)  — 0..1 score + verdict assignment
  -> SearchEngine    (src/search_engine.py) — query->candidates->ranked results
  -> Validator       (src/validator.py)     — abstention logic, citation grounding
  -> Analytics       (src/analytics.py)    — coverage/gap metrics for dashboard
  -> api.py          — FastAPI POST /solve + GET /health
  -> app.py          — Streamlit dashboard (uses same src/ modules)
```

## Module Interfaces (agreed before parallel work)

### DataLoader.get_df() -> pd.DataFrame
Returns normalized dataframe with added columns:
- `row_id` (0-based int)
- `text_blob` (concatenated searchable text)
- `cap_list`, `proc_list`, `equip_list`, `spec_list` (parsed lists)
- `lat_f`, `lon_f` (float coordinates)

### SearchEngine.search(query_text, user_lat, user_lng, time_str, injected=None)
Returns list of FacilityResult dataclasses

### FacilityResult fields:
facility_name, facility_pin, verdict, trust_score, distance_km,
capabilities, citations, why, why_not_runner_up

---

## Coding Conventions
- Python 3.11, type hints throughout
- No LLM API calls required for core logic
- Deterministic — same input always produces same output
- All thresholds documented and configurable via src/config.py
- No hardcoded fake statistics
- Evidence only from actual dataset rows
- Citations: verbatim substrings of source field text only

## Commands
```powershell
# Install
cd caretruth-ai
pip install -r requirements.txt

# Copy dataset (do not move original)
copy "C:\Users\Paavan Sharma\OneDrive\Desktop\Hackathon_Dataset_India_Larg.csv" data\raw\

# Run Streamlit dashboard
streamlit run app.py

# Run API (separate terminal)
uvicorn api:app --host 127.0.0.1 --port 8000

# Run tests
pytest tests/ -v

# Test health endpoint
Invoke-RestMethod http://127.0.0.1:8000/health

# Test solve endpoint
$body = '{"probe_id":"ps03_g1_ananya","kind":"crisis_facility_search","query_text":"Severe abdominal pain, suspected appendicitis. Father needs emergency surgery tonight.","user_location":{"lat":26.24,"lng":84.4,"pin":"841226","transport":"two-wheeler","budget_inr":500},"time":"Tuesday 14:30"}'
Invoke-RestMethod -Uri http://127.0.0.1:8000/solve -Method Post -ContentType "application/json" -Body $body
```

## Data Handling Rules
- Never modify the source CSV
- Never fabricate a facility, capability, or citation
- Never attach evidence from one row to another
- Citations must be exact substrings (case/whitespace-insensitive matching)
- Row 4097 = "Dr. R K Thakur Hospital" — the injection probe target
- Injection probe fires at time > 21:00; injected_line goes into capability field

## Known Limitations
- No real-time bed availability (dataset is static)
- Trust scoring uses heuristic weights, not calibrated probabilities
- Geographic filtering limited to coordinate proximity; admin boundaries not enforced
- No OCR or PDF parsing
