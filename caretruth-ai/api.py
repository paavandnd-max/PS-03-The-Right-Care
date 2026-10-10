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

from src.data_loader import load_dataframe
from src.search_engine import search
from src.validator import should_abstain, build_contract_response
from src import config


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


# ── Endpoints ──────────────────────────────────────────────────────────────────
@app.get("/health")
def health() -> dict:
    """Health check — always returns 200 with {ok: true}."""
    return {"ok": True}


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
