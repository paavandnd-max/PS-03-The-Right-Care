# 🏥 CareTruth AI (VERITAS) — NIT Delhi Hackathon PS-03

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688.svg?logo=fastapi)](https://fastapi.tiangolo.com)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.28+-FF4B4B.svg?logo=streamlit)](https://streamlit.io)
[![Tests Passing](https://img.shields.io/badge/tests-38%2F38%20passing-brightgreen.svg)]()
[![Deterministic](https://img.shields.io/badge/LLM%20Calls-0%20(100%25%20Deterministic)-orange.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> **Evidence-backed, deterministic healthcare facility intelligence and clinical command center for 10,000+ Indian healthcare facilities.**  
> Built for **NIT Delhi Hackathon Problem Statement PS-03: The Right Care**.

---

## 🌟 Executive Summary

In emergency and critical care scenarios across India, healthcare seekers frequently encounter inaccurate hospital listings, inflated capability claims, and missing operational reality (e.g., lack of night-time anaesthesiologists or ICU equipment).

**CareTruth AI (VERITAS)** solves this crisis through a **strictly deterministic, zero-hallucination verification engine**:
- **100% Grounded Citations**: Every capability claim, procedure, equipment, and doctor credential returns verbatim quotation spans directly extracted from raw hospital record blobs.
- **5-Tier Contradiction Detection**: Flags operational incompatibilities—such as emergency surgeries claimed without night-time anaesthesiologists, primary health centers advertising complex cardiac procedures (CABG), or doctor headcount deficits.
- **Strict PS-03 Contract Compliance**: Implements the official `POST /solve` and `GET /health` API specs within `< 2s` response times (well under the 8s cutoff), passing all practice probes (`ps03_g1` through `ps03_g4`).
- **Dual Presentation Experience**:
  1. **VERITAS Clinical Command Center**: A pixel-perfect, dark-mode healthcare command interface with live audit queues, cold-chain telemetry, equipment timeline drawers, and verification actions.
  2. **CareTruth Streamlit Intelligence Dashboard**: Interactive geospatial GIS mapping, regional gap analysis, facility explorer, and live GitHub commit activity stream.

---

## 🏗️ System Architecture

```text
                               ┌────────────────────────────────────────────────────────┐
                               │                    Client Layer                        │
                               ├───────────────────────────┬────────────────────────────┤
                               │  VERITAS Command Center   │    Streamlit Dashboard     │
                               │  (FastAPI Static / UI)    │    (GIS & Analytics)       │
                               │     Port: 8000 (/)        │     Port: 8501             │
                               └─────────────┬─────────────┴─────────────┬──────────────┘
                                             │                           │
                                             ▼                           ▼
┌───────────────────────────────────────────────────────────────────────────────────────┐
│                                FastAPI Evaluation Engine                              │
│                GET /health   ·   POST /solve   ·   GET /api/facilities                │
└────────────────────────────────────────────┬──────────────────────────────────────────┘
                                             │
               ┌─────────────────────────────┼─────────────────────────────┐
               ▼                             ▼                             ▼
┌─────────────────────────────┐┌───────────────────────────┐┌───────────────────────────┐
│     Evidence Extractor      ││  Contradiction Detector   ││      Haversine Engine     │
│  • Verbatim substring match ││  • 5 Operational tiers    ││  • ±2 km tolerance        │
│  • Exact citation spans     ││  • Night anaesthesia check││  • Preset city mapping    │
│  • Zero LLM hallucinations  ││  • Type/procedure checks  ││  • Radius filtering       │
└──────────────┬──────────────┘└─────────────┬─────────────┘└─────────────┬─────────────┘
               │                             │                            │
               └─────────────────────────────┼────────────────────────────┘
                                             ▼
                               ┌───────────────────────────┐
                               │    Trust Scorer Engine    │
                               │  • Score ∈ [0.0, 1.0]     │
                               │  • Additive weights       │
                               │  • Contradiction penalty  │
                               │    (Δ ≥ 0.15 on mismatch) │
                               └─────────────┬─────────────┘
                                             ▼
                               ┌───────────────────────────┐
                               │   In-Memory Data Cache    │
                               │  10,000 Facility Records  │
                               └───────────────────────────┘
```

---

## 🚀 Key Features

### 1. 🛡️ Deterministic Contradiction Detection
- **Night-time Anaesthesiologist Probe**: Checks emergency surgery/ICU requests scheduled after 21:00 against facility capability records. If an explicit negative note exists (e.g., *"No anaesthesiologist on duty after 9 PM"*), the facility is flagged or disqualified, dropping trust score by $\ge 0.15$.
- **Type-Capability Mismatches**: Flags clinics or PHCs claiming high-complexity tertiary procedures (e.g., Open Heart Surgery / CABG).
- **Missing Equipment Requirements**: Cross-verifies claimed surgical capabilities against recorded diagnostic/surgical equipment rosters.
- **Staffing Capacity Deficits**: Flags specialized departments operating without verified specialist doctors.
- **Negative Operational Notes**: Scans raw text blobs for operational constraints (e.g., "radiology out of order", "temporary closure").

### 2. 📍 Precise Geospatial Matching
- Implements Haversine distance calculations verified against the official test harness ($\pm 2\text{ km}$ precision).
- Includes preset location resolution for Indian urban centers (Patna, Begusarai, Samastipur, Muzaffarpur, etc.).

### 3. 🎯 Official PS-03 Evaluation Contract
- **Endpoint**: `POST /solve`
- **Output Format**:
  ```json
  {
    "probe_id": "ps03_g1_appendicitis",
    "result": {
      "verdict": "verified",
      "trust_score": 0.85,
      "facilities": [
        {
          "name": "Dr. R K Thakur Hospital",
          "distance_km": 24.7,
          "verdict": "verified",
          "trust_score": 0.85,
          "citations": [
            {
              "source_row": 4097,
              "field": "capability",
              "citation_span": "emergency surgery"
            }
          ]
        }
      ]
    }
  }
  ```
- Complies with verdict vocabulary: `verified`, `advertised_only`, `unverifiable`.

---

## ⚡ Quick Start Guide

### Prerequisites
- Python 3.10, 3.11, or 3.12
- Git

### 1. Clone & Setup
```bash
git clone https://github.com/paavandnd-max/PS-03-The-Right-Care.git
cd PS-03-The-Right-Care/caretruth-ai
pip install -r requirements.txt
```

### 2. Dataset Placement
Place the dataset CSV in the `data/raw/` directory:
```powershell
# Windows PowerShell
copy "C:\path\to\Hackathon_Dataset_India_Larg.csv" data\raw\
```
*(A synthetic test dataset is automatically loaded for testing if the raw CSV is not present).*

### 3. Run the Services

#### Option A: FastAPI Backend & VERITAS Command Center (Port 8000)
```bash
python -m uvicorn api:app --host 127.0.0.1 --port 8000
```
- Open **VERITAS Clinical Command Center**: `http://localhost:8000`
- API Interactive Docs: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/health`

#### Option B: Streamlit Intelligence Dashboard (Port 8501)
```bash
python -m streamlit run app.py --server.port 8501
```
- Open **Streamlit Dashboard**: `http://localhost:8501`

---

## 🧪 Test Suite & Validation

The codebase includes an exhaustive test suite covering data ingestion, distance accuracy, evidence citation extraction, contradiction detection, and official probe contracts:

```bash
cd caretruth-ai
pytest tests/ -v
```

### Verification Results
```text
tests/test_all.py::test_dataset_loading PASSED                           [  2%]
tests/test_all.py::test_haversine_distance_accuracy PASSED               [  5%]
tests/test_all.py::test_verbatim_citation_extraction PASSED              [  7%]
tests/test_all.py::test_contradiction_night_anaesthesiologist PASSED     [ 10%]
tests/test_all.py::test_trust_score_range PASSED                         [ 13%]
tests/test_all.py::test_ps03_g1_appendicitis_probe PASSED                [ 15%]
tests/test_all.py::test_ps03_g2_obstetric_probe PASSED                   [ 18%]
tests/test_all.py::test_ps03_g3_cardiac_probe PASSED                     [ 21%]
tests/test_all.py::test_ps03_g4_injection_probe PASSED                   [ 23%]
...
============================= 38 passed, 1 warning in 8.12s =============================
```

---

## 📂 Repository Structure

```text
PS-03-The-Right-Care/
└── caretruth-ai/
    ├── api.py                     # FastAPI application (POST /solve, GET /health, REST API)
    ├── app.py                     # Streamlit multi-tab intelligence dashboard
    ├── requirements.txt           # Python dependencies
    ├── frontend/                  # VERITAS Clinical Auditor frontend
    │   ├── index.html             # Pixel-perfect VERITAS command center UI
    │   ├── app.js                 # Frontend interactions & audit API integration
    │   └── styles.css             # Supplementary custom styles
    ├── src/
    │   ├── config.py              # System thresholds, constants & weights
    │   ├── data_loader.py         # CSV ingestion, data normalization & in-memory caching
    │   ├── normalizer.py          # Field normalization & regex tokenizers
    │   ├── evidence_extractor.py  # Exact substring matching for verbatim citations
    │   ├── contradiction_detector.py # 5-tier operational contradiction engine
    │   ├── trust_scorer.py        # Multi-factor deterministic trust scoring
    │   ├── distance.py            # Haversine distance calculator & preset locations
    │   ├── search_engine.py       # Multi-criteria candidate search & ranking
    │   ├── validator.py           # Evaluation contract builder & abstention rules
    │   └── analytics.py           # Regional facility gap & equipment coverage metrics
    ├── tests/
    │   └── test_all.py            # Comprehensive 38-test verification suite
    ├── data/
    │   └── raw/                   # Dataset directory (Hackathon_Dataset_India_Larg.csv)
    └── docs/
        ├── architecture.md        # Technical architecture specification
        ├── dataset_schema.md      # Field definitions & data dictionary
        ├── demo_script.md         # 3-minute hackathon jury demonstration script
        └── frontend-backend-integration.md # VERITAS UI integration notes
```

---

## 👥 Hackathon Team & Credentials

- **Problem Statement**: NIT Delhi Hackathon — PS-03: The Right Care
- **Project Name**: CareTruth AI / VERITAS
- **GitHub Repository**: [paavandnd-max/PS-03-The-Right-Care](https://github.com/paavandnd-max/PS-03-The-Right-Care)
- **Core Principles**: Deterministic, 100% Grounded, Transparent Evidence, Zero Hallucinations.
