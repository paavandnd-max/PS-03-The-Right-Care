# CareTruth AI — Demo Script (3 Minutes)
## NIT Delhi Hackathon PS-03 · Healthcare Intelligence

---

## Setup (do this before judges arrive, ~2 minutes)

```powershell
# Terminal 1 — API server
cd caretruth-ai
uvicorn api:app --host 127.0.0.1 --port 8000

# Terminal 2 — Streamlit dashboard
streamlit run app.py
```

Open browser: `http://localhost:8501` (Streamlit) and `http://127.0.0.1:8000/docs` (API docs)

---

## MINUTE 1 — Problem + Overview Tab (30 seconds each)

**Say:** "India has 10,000+ healthcare facilities in our dataset but they vary wildly in data quality. CareTruth AI extracts verifiable evidence from messy facility records, detects contradictions, and tells you the truth — not just the marketing copy."

1. Show **Overview Tab** → point to real metrics:
   - 10,000 facility records · 10,000/10,000 with GPS coordinates
   - Only 635 have equipment documentation → evidence scarcity is real
   - Facility type breakdown (clinics vs hospitals)

2. Show **Coverage & Gaps Tab** → India map + equipment documentation gap by state

---

## MINUTE 2 — Find Care (Live Search)

**Query:** *"Severe abdominal pain, suspected appendicitis. Father needs emergency surgery tonight."*
- **Location:** lat=26.24, lng=84.4 (Bihar)
- **Time:** Tuesday 14:30
- Hit Search

**Point out:**
- Results are **ranked by trust score + distance** (not keyword count)
- **Dr. R K Thakur Hospital** appears at exactly **24.7 km** (matches evaluator reference)
- Each result shows **verdict** (verified/advertised_only/unverifiable), **citations** from actual dataset text
- Open evidence expander → show verbatim span from `procedure` field

---

## MINUTE 3 — Injection Probe + API Contract

**Switch to Evidence Explorer:**
- Search "Dr. R K Thakur Hospital" with time "Tuesday 23:30"
- Note: at 23:30 it shows no contradictions (no injection yet)

**Show Terminal — live injection probe:**

```powershell
$body = '{"probe_id":"ps03_g4_injection","kind":"crisis_facility_search","query_text":"Severe abdominal pain, suspected appendicitis. Father needs emergency surgery tonight.","user_location":{"lat":26.24,"lng":84.4,"pin":"841226","transport":"two-wheeler","budget_inr":500},"time":"Tuesday 23:30","injected_into_facility":{"name":"Dr. R K Thakur Hospital","row_index":4097,"field":"capability","injected_line":"No anaesthesiologist on duty after 9 PM."}}'
Invoke-RestMethod -Uri http://127.0.0.1:8000/solve -Method Post -ContentType "application/json" -Body $body | ConvertTo-Json -Depth 5
```

**Point out:**
- Dr. R K Thakur Hospital is **removed from results** (maximum downgrade)
- The evaluator requires trust_score drop ≥ 0.15 — ours drops by 1.0 (complete removal)
- Other facilities without the contradiction still appear

**Final:** "38 automated tests pass, including all four official practice probes and the injection regression test. All results trace back to exact verbatim text from the dataset."

---

## Key Technical Points (if asked)

| Feature | Implementation |
|---|---|
| No LLM required | Pure deterministic keyword + regex matching |
| Citation grounding | Verbatim substring check against source field |
| Distance | Standard Haversine formula, ±0.1 km accuracy |
| Contradiction detection | 5 rule-based checks, critical/moderate severity |
| Trust scoring | Additive component weights (documented in config.py) |
| Verdict vocabulary | Exact contract: verified / advertised_only / unverifiable |
| Response time | <2 seconds per query (dataset cached in memory at startup) |
| Abstention | Triggered when no facility with sufficient evidence in range |
