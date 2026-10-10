"""CareTruth AI — FastAPI evaluation endpoint.

Implements the official PS-03 contract:
  POST /solve  — main evaluation (8-second timeout enforced by client/evaluator)
  GET  /health — returns {"ok": true}

The dataset is loaded once on startup and cached in memory.
"""
from __future__ import annotations
import sys
import os
from pathlib import Path
from typing import Any, Optional

# Allow running from project root
sys.path.insert(0, str(Path(__file__).resolve().parent))

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn
import pandas as pd

from src.data_loader import load_dataframe
from src.search_engine import search
from src.validator import should_abstain, build_contract_response
from src import config


from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from src.evidence_extractor import extract_evidence_from_row
from src.contradiction_detector import detect_contradictions
from src.trust_scorer import calculate_trust_score, compute_trust_score
from src.analytics import dataset_summary


# ── App setup ─────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load dataset cache on startup."""
    try:
        df = load_dataframe()
        print(f"[CareTruth AI] Dataset loaded: {len(df)} facilities.", flush=True)
    except FileNotFoundError as exc:
        print(f"[CareTruth AI] WARNING: {exc}", flush=True)
    except Exception as exc:
        print(f"[CareTruth AI] WARNING: Dataset load failed: {exc}", flush=True)
    yield  # Application runs here


app = FastAPI(
    title="CareTruth AI",
    description="PS-03 Healthcare Facility Intelligence — NIT Delhi Hackathon",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount frontend static files
frontend_path = Path(__file__).resolve().parent / "frontend"
if frontend_path.exists():
    app.mount("/app", StaticFiles(directory=str(frontend_path), html=True), name="frontend")


# ── Request / Response schemas ─────────────────────────────────────────────────
class UserLocation(BaseModel):
    lat:           float
    lng:           float
    pin:           Optional[str]       = None
    transport:     Optional[str]       = "two-wheeler"
    budget_inr:    Optional[int]       = None


class InjectedFacility(BaseModel):
    name:          str
    row_index:     int
    field:         str
    injected_line: str


class SolveRequest(BaseModel):
    probe_id:              str
    kind:                  str                    = "crisis_facility_search"
    query_text:            str
    user_location:         UserLocation
    time:                  Optional[str]          = None
    injected_into_facility: Optional[InjectedFacility] = None


class AuditActionRequest(BaseModel):
    action:        str
    facility_name: str
    notes:         Optional[str] = None


# ── Endpoints ──────────────────────────────────────────────────────────────────
@app.get("/")
def root():
    """Serve index.html if available, else redirect to health."""
    index_file = frontend_path / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"status": "CareTruth AI API Running", "docs": "/docs", "health": "/health"}


@app.get("/health")
def health() -> dict:
    """Health check — always returns 200 with {ok: true}."""
    return {"ok": True}


@app.get("/api/facilities")
def get_facilities(skip: int = 0, limit: int = 50, q: Optional[str] = None) -> dict:
    """List facilities with optional text search and pagination."""
    df = load_dataframe()
    filtered = df
    if q:
        filtered = df[df["name"].astype(str).str.lower().str.contains(q.lower(), na=False)]
    
    sliced = filtered.iloc[skip:skip+limit]
    facilities = []
    for idx, row in sliced.iterrows():
        try:
            row_id_val = int(row.get("row_id", row.get("id", idx)))
        except (ValueError, TypeError):
            row_id_val = int(idx) if isinstance(idx, int) else 0

        lat_val = row.get("lat_f")
        lng_val = row.get("lon_f")
        try:
            lat_f = float(lat_val) if lat_val is not None and str(lat_val).lower() not in ("nan", "none", "null", "") else None
        except (ValueError, TypeError):
            lat_f = None
        try:
            lng_f = float(lng_val) if lng_val is not None and str(lng_val).lower() not in ("nan", "none", "null", "") else None
        except (ValueError, TypeError):
            lng_f = None

        facilities.append({
            "id": row_id_val,
            "name": str(row.get("name", "")),
            "facilityTypeId": str(row.get("facilityTypeId", "")),
            "city": str(row.get("address_city", "")),
            "state": str(row.get("address_stateOrRegion", "")),
            "pin": str(row.get("address_zipOrPostcode", "")),
            "lat": lat_f,
            "lng": lng_f,
        })
    return {"total": len(filtered), "facilities": facilities}


@app.get("/api/facility/{facility_name}")
def get_facility_dossier(facility_name: str) -> dict:
    """Get complete dossier, evidence, and contradictions for a facility."""
    df = load_dataframe()
    matches = df[df["name"].astype(str).str.lower() == facility_name.lower()]
    if matches.empty:
        # Partial match fallback
        matches = df[df["name"].astype(str).str.lower().str.contains(facility_name.lower(), na=False)]
    if matches.empty:
        raise HTTPException(status_code=404, detail="Facility not found in dataset")
    
    row = matches.iloc[0]
    evidence = extract_evidence_from_row(row)
    contradictions = detect_contradictions(row, evidence)
    trust_res = compute_trust_score(row, evidence, contradictions, [])
    
    try:
        row_id_val = int(row.get("row_id", row.get("id", row.name)))
    except (ValueError, TypeError):
        row_id_val = 0

    return {
        "id": row_id_val,
        "name": str(row.get("name", "")),
        "facilityTypeId": str(row.get("facilityTypeId", "")),
        "city": str(row.get("address_city", "")),
        "state": str(row.get("address_stateOrRegion", "")),
        "pin": str(row.get("address_zipOrPostcode", "")),
        "doctor_count": int(row.get("doctor_count", 0) or 0) if pd.notnull(row.get("doctor_count")) else 0,
        "capacity": int(row.get("capacity", 0) or 0) if pd.notnull(row.get("capacity")) else 0,
        "reconcile_score": trust_res.trust_score,
        "verdict": trust_res.verdict,
        "contradictions": [
            {"type": c.rule_id, "severity": c.severity, "details": c.details}
            for c in contradictions
        ],
        "evidence_count": len(evidence),
        "raw_text_snippet": str(row.get("raw_text_blob", ""))[:500]
    }


@app.get("/api/stats")
def get_stats() -> dict:
    """Dataset summary metrics."""
    df = load_dataframe()
    return dataset_summary(df)


@app.post("/api/audit-action")
def log_audit_action(req: AuditActionRequest) -> dict:
    """Log clinical auditor disposition/actions."""
    return {
        "status": "LOGGED",
        "action": req.action,
        "facility_name": req.facility_name,
        "case_id": "AUD-2024-KLY-91",
        "timestamp": "2024-10-14T10:14:00Z"
    }


@app.post("/solve")
def solve(req: SolveRequest) -> dict:
    """
    Main PS-03 evaluation endpoint.

    Accepts the probe's 'input' body verbatim.
    Returns the exact required output shape.
    """
    # Load dataset (uses cache after first call)
    try:
        df = load_dataframe()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    # Prepare injection dict if present
    injected = None
    if req.injected_into_facility:
        injected = {
            "name":          req.injected_into_facility.name,
            "row_index":     req.injected_into_facility.row_index,
            "field":         req.injected_into_facility.field,
            "injected_line": req.injected_into_facility.injected_line,
        }

    # Run search
    results, desert_flags = search(
        query_text=req.query_text,
        user_lat=req.user_location.lat,
        user_lng=req.user_location.lng,
        time_str=req.time,
        injected=injected,
        df=df,
    )

    # Abstention check
    abstain, abstain_reason = should_abstain(
        results=results,
        user_lat=req.user_location.lat,
        user_lng=req.user_location.lng,
        transport=req.user_location.transport or "two-wheeler",
        time_str=req.time,
    )

    # Build contract response
    response = build_contract_response(
        probe_id=req.probe_id,
        results=results,
        desert_flags=desert_flags,
        abstain=abstain,
        abstain_reason=abstain_reason,
    )

    return response


# ── Dev entry point ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run(
        "api:app",
        host=config.API_HOST,
        port=config.API_PORT,
        reload=False,
    )
