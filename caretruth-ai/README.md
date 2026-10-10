# CareTruth AI — NIT Delhi Hackathon PS-03

Evidence-backed healthcare facility intelligence for India.

## Quick Start (Windows PowerShell)

```powershell
# 1. Go to project
cd caretruth-ai

# 2. Install dependencies
pip install -r requirements.txt

# 3. Place the dataset (copy — do NOT move the original)
copy "C:\Users\Paavan Sharma\OneDrive\Desktop\Hackathon_Dataset_India_Larg.csv" data\raw\

# 4. Start Streamlit dashboard (Terminal 1)
streamlit run app.py

# 5. Start evaluation API (Terminal 2)
uvicorn api:app --host 127.0.0.1 --port 8000

# 6. Test health
Invoke-RestMethod http://127.0.0.1:8000/health

# 7. Test solve (probe g1)
$body = Get-Content ..\reference\participant_eval_kit\participant_eval_kit\samples\ps03_practice_probes.jsonl | Select-Object -First 1 | ConvertFrom-Json
$input = ($body.input | ConvertTo-Json -Depth 10)
Invoke-RestMethod -Uri http://127.0.0.1:8000/solve -Method Post -ContentType "application/json" -Body $input

# 8. Run tests
pytest tests/ -v
```

## Environment Variables (optional)
Copy `.env.example` to `.env` and set:
```
DATASET_PATH=data/raw/Hackathon_Dataset_India_Larg.csv
MAX_RESULTS=5
SEARCH_RADIUS_KM=100
```

## Project Structure
```
caretruth-ai/
  app.py           — Streamlit dashboard
  api.py           — FastAPI POST /solve + GET /health
  src/
    config.py      — paths, thresholds
    data_loader.py — CSV load + cache
    normalizer.py  — field parsing
    evidence_extractor.py  — capability evidence per row
    contradiction_detector.py
    trust_scorer.py
    search_engine.py
    validator.py
    analytics.py
  tests/           — pytest suite
  data/raw/        — place CSV here
  docs/            — architecture, schema, demo script
```

## Official PS-03 Contract
- Endpoint: `POST /solve` (8-second timeout)
- Verdict values: `verified | advertised_only | unverifiable`
- Citations: verbatim substrings from dataset row fields
- Haversine distance, ±2 km tolerance for top result
- Injection probe: trust_score drops ≥ 0.15 when night-time anaesthesiologist contradiction detected

## Known Limitations
- Dataset is static (no real-time bed/staff availability)
- Trust scoring uses provisional heuristic weights
- No LLM — all evidence extraction is deterministic keyword/pattern matching
