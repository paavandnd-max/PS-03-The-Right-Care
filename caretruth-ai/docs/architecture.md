# CareTruth AI — Architecture Overview

CareTruth AI is an evidence-backed healthcare facility intelligence system built for **NIT Delhi Hackathon PS-03**.

## System Architecture Diagram

```
                              ┌─────────────────────────┐
                              │  Streamlit Dashboard UI │
                              │    (Port 8501 / 8502)   │
                              └────────────┬────────────┘
                                           │
                                           ▼
┌─────────────────────────┐   ┌─────────────────────────┐
│     FastAPI Server      │   │  Search & Scorer Engine │
│      (POST /solve)      │◄──┤    (Haversine + Rules)  │
└────────────┬────────────┘   └────────────┬────────────┘
             │                             │
             ▼                             ▼
┌─────────────────────────┐   ┌─────────────────────────┐
│ Contradiction Detector  │   │   Evidence Extractor    │
│  (Operational Rules)    │   │  (Verbatim Citations)   │
└────────────┬────────────┘   └────────────┬────────────┘
             │                             │
             └─────────────┬───────────────┘
                           │
                           ▼
              ┌─────────────────────────┐
              │ Normalized Data Cache   │
              │ (10,000 Facility Rows)  │
              └─────────────────────────┘
```

## Core Components

1. **`src/data_loader.py`**: Loads and normalizes 10,000 facility records into memory. Extracts structured arrays (`capability`, `procedure`, `equipment`, `specialties`) and normalizes numeric/coordinate fields.
2. **`src/evidence_extractor.py`**: Performs exact string matching and keyword scanning against raw facility blobs to return exact `source_row` indices and verbatim `citation_span` strings.
3. **`src/contradiction_detector.py`**: Applies 5 core rule checks:
   - **Night-time Anaesthesiologist Probe**: Checks emergency/ICU/surgery requests after 21:00 against explicit negative availability notes.
   - **Type-Capability Mismatch**: Flags primary care clinics claiming complex tertiary surgeries (e.g. CABG).
   - **Missing Equipment for Procedure**: Ensures required surgical tools exist for claimed surgeries.
   - **Doctor Count Deficit**: Ensures staff headcount matches high-demand service claims.
   - **Negative Operational Notes**: Detects explicitly stated unavailability in raw text.
4. **`src/trust_scorer.py`**: Computes deterministic trust scores in $[0.0, 1.0]$ based on evidence completeness, verified staff/equipment, and contradiction penalties (dropping score $\ge 0.15$ on severe contradictions).
5. **`src/distance.py`**: Computes geographical distance using the Haversine formula within $\pm 2\text{ km}$ accuracy.
6. **`src/search_engine.py`**: Filters, ranks, and returns candidate facilities matching spatial, capability, and time constraints.
7. **`api.py`**: Implements the official PS-03 contract (`POST /solve`, `GET /health`) with response formatting, exact citation spans, and fallback candidate generation.
8. **`app.py`**: Streamlit interactive dashboard providing Search, Facility Inspector, Contradiction Engine view, and Regional Intelligence Analytics.
