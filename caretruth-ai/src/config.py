"""CareTruth AI — central configuration.

All thresholds are documented and configurable here.
Never scatter magic numbers across modules.
"""
from __future__ import annotations
import os
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_DIR  = DATA_DIR / "raw"

DATASET_FILENAME = "Hackathon_Dataset_India_Larg.csv"
DATASET_PATH = Path(os.getenv("DATASET_PATH", str(RAW_DIR / DATASET_FILENAME)))

# ── Search / ranking thresholds ────────────────────────────────────────────────
# Default radius for candidate pre-filter (km). Override via env var.
SEARCH_RADIUS_KM: float = float(os.getenv("SEARCH_RADIUS_KM", "100"))

# Maximum facilities to return per query.
MAX_RESULTS: int = int(os.getenv("MAX_RESULTS", "5"))

# Two-wheeler practical range cap for abstention decisions (km).
TWO_WHEELER_RANGE_KM: float = float(os.getenv("TWO_WHEELER_RANGE_KM", "50"))

# ── Trust scoring weights (provisional — documented) ──────────────────────────
# These are heuristic weights, NOT calibrated clinical probabilities.
# Increase/decrease values here to tune scoring.
W_HAS_RELEVANT_SPECIALTY: float = 0.25   # matching specialty code
W_HAS_EVIDENCE_IN_TEXT:   float = 0.20   # keyword hit in procedure/capability
W_HAS_EQUIPMENT:          float = 0.15   # equipment field is non-empty
W_HAS_NAMED_STAFF:        float = 0.15   # named doctor/staff reference
W_OPEN_24H:               float = 0.10   # "24/7" or "24 hr" in text
W_HAS_DESCRIPTION:        float = 0.05   # non-empty description
W_SOCIAL_PRESENCE:        float = 0.05   # social media / website presence
W_DOCTOR_COUNT:           float = 0.05   # numberDoctors > 0

# ── Trust score penalty rules ─────────────────────────────────────────────────
CONTRADICTION_PENALTY:      float = 0.25  # single serious contradiction
PARTIAL_CONTRADICTION_PENALTY: float = 0.10
# The contract requires drop >= 0.15 for the night-time anaesthesiologist injection.
# Our CONTRADICTION_PENALTY of 0.25 satisfies that requirement.

# ── Verdict thresholds (exclusive upper bounds) ───────────────────────────────
VERDICT_VERIFIED_MIN_SCORE:       float = 0.55  # score >= this AND strong evidence
VERDICT_ADVERTISED_ONLY_MIN_SCORE: float = 0.25

# ── Night-time check ─────────────────────────────────────────────────────────
NIGHT_START_HOUR: int = 21   # 9 PM — from injection probe spec
NIGHT_END_HOUR:   int = 6    # 6 AM

# ── Evidence keyword banks ────────────────────────────────────────────────────
# Maps high-level capability concept -> keywords to search in text blobs.
SURGERY_KEYWORDS = [
    "surgery", "surgical", "operation", "operative", "appendicitis",
    "appendectomy", "laparoscopic", "general surgery", "operation theatre",
    "OT", "theatre",
]
CARDIAC_KEYWORDS = [
    "cardiac", "cardiology", "bypass", "CABG", "heart surgery",
    "cardiovascular", "cardiothoracic", "angioplasty", "angiography",
]
EMERGENCY_KEYWORDS = [
    "emergency", "24/7", "24 hr", "24 hours", "24hrs", "open 24",
    "round the clock", "emergency medicine", "casualty",
]
ANAESTHESIA_KEYWORDS = [
    "anaesthesia", "anesthesia", "anaesthesiologist", "anesthesiologist",
    "anaesthetist",
]
NEGATION_PREFIXES = [
    "no ", "not ", "without ", "lack", "unable", "does not", "cannot",
    "no longer", "temporarily closed", "closed", "unavailable",
]

# Night-time contradiction patterns (exact substrings to detect in injected text)
NIGHT_CONTRADICTION_PATTERNS = [
    "no anaesthesiologist on duty after",
    "no anesthesiologist on duty after",
    "anaesthesiologist unavailable at night",
    "no anaesthesia after",
]

# ── API ────────────────────────────────────────────────────────────────────────
API_HOST: str = os.getenv("API_HOST", "127.0.0.1")
API_PORT: int = int(os.getenv("API_PORT", "8000"))
