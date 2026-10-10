# VERITAS Health Intelligence & CareTruth AI — Integration Architecture

## 1. System Architecture & Component Mapping

The system integrates a high-fidelity **VERITAS Health Intelligence** clinical audit interface with the deterministic **CareTruth AI** healthcare facility analysis backend.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    VERITAS Clinical Audit Frontend                          │
│               (HTML5 / CSS3 / Vanilla JS & Streamlit Portal)                 │
└──────────────────────┬──────────────────────────────┬───────────────────────┘
                       │                              │
                       ▼                              ▼
┌──────────────────────────────┐              ┌──────────────────────────────┐
│     FastAPI REST Engine      │              │  Streamlit Executive Portal  │
│   (Port 8000: /solve, /api)  │              │    (Port 8501: Dashboard)    │
└──────────────┬───────────────┘              └──────────────┬───────────────┘
               │                                             │
               └──────────────────────┬──────────────────────┘
                                      │
                                      ▼
             ┌──────────────────────────────────────────────────┐
             │       CareTruth AI Deterministic Core Engine     │
             │  - Data Loader & Cache (data_loader.py)          │
             │  - Evidence Extractor (evidence_extractor.py)    │
             │  - Contradiction Detector (contradiction.py)     │
             │  - Trust Scorer & Verdict (trust_scorer.py)      │
             │  - Haversine Spatial Engine (distance.py)        │
             └────────────────────────┬─────────────────────────┘
                                      │
                                      ▼
             ┌──────────────────────────────────────────────────┐
             │   Indian Healthcare Facilities Dataset (10,000)  │
             │   (Hackathon_Dataset_India_Larg.csv)             │
             └──────────────────────────────────────────────────┘
```

## 2. API Endpoint Contracts

### A. Official PS-03 Competition Endpoint (`POST /solve`)
- **Route**: `POST /solve`
- **Request Body**:
  ```json
  {
    "user_requirements_text": "string",
    "user_lat": float,
    "user_lng": float,
    "current_time_str": "string (e.g. Tuesday 14:30)",
    "radius_km": float (optional, default 100)
  }
  ```
- **Response Contract**:
  - `results`: List of candidate facilities with `verdict`, `trust_score`, `distance_km`, `citations`, `why`.
  - `abstain`: Boolean flag.
  - `abstain_reason`: String explanation.
  - `desert_flags`: Optional list of healthcare desert signals.

### B. System Health (`GET /health`)
- **Route**: `GET /health`
- **Response**: `{"ok": true}`

### C. Additional REST API Endpoints for Frontend Integration
- **`GET /api/facilities`**: List facilities with search, filter, and pagination.
- **`GET /api/facility/{facility_id}`**: Retrieve detailed dossier, claims, telemetry, and detected contradictions for a specific facility.
- **`GET /api/stats`**: Retrieve global dataset statistics and state coverage breakdown.
- **`POST /api/audit-action`**: Log clinical auditor disposition actions (`Confirm Surgical Discrepancy`, `Request Field Re-Audit`, `Escalate HR Deficit`).

## 3. Data Integrity & Safety Commitments
- **No Fabricated Evidence**: Verbatim citation spans are extracted strictly from source row text.
- **Unavailable Fields**: Fields not present in raw CSV records are explicitly marked as *"Not available in source data"*.
- **Deterministic Evaluation**: Scoring, distance calculations, and contradiction penalties follow zero-hallucination rule sets.
