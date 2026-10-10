"""CareTruth AI — Data Loader.

Reads the CSV once, normalizes it, and caches the result in memory.
Subsequent calls return the cached DataFrame immediately.

The source CSV is NEVER modified.
Row index (0-based) is the authoritative facility identifier.
"""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path
from typing import Optional

import pandas as pd

from src.config import DATASET_PATH


# ── Module-level cache ────────────────────────────────────────────────────────
_df_cache: Optional[pd.DataFrame] = None


def _parse_json_list(value: str) -> list[str]:
    """Parse a JSON array string into a Python list, return [] on failure."""
    if not value or value.strip().lower() in ("null", "none", "[]", ""):
        return []
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return [str(x).strip() for x in parsed if str(x).strip()]
        return [str(parsed).strip()]
    except (json.JSONDecodeError, ValueError):
        # Fall back: split by comma after stripping brackets
        cleaned = re.sub(r'[\[\]"]', "", value)
        return [x.strip() for x in cleaned.split(",") if x.strip()]


def _safe_float(value: str) -> Optional[float]:
    """Parse float, return None if invalid."""
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _is_null(value: str) -> bool:
    """True if the cell value represents a missing/null value."""
    return not value or value.strip().lower() in ("null", "none", "nan", "")


def load_dataframe(dataset_path: Path = DATASET_PATH) -> pd.DataFrame:
    """
    Load and normalize the facility CSV. Results are cached in memory.

    Returns a DataFrame with additional computed columns:
    - row_id         : 0-based integer row index (source record identifier)
    - cap_list       : parsed list from 'capability'
    - proc_list      : parsed list from 'procedure'
    - equip_list     : parsed list from 'equipment'
    - spec_list      : parsed list from 'specialties'
    - phone_list     : parsed list from 'phone_numbers'
    - lat_f          : float latitude  (None if missing/invalid)
    - lon_f          : float longitude (None if missing/invalid)
    - has_coords     : bool — both lat_f and lon_f are valid
    - text_blob      : concatenated searchable text (lower-cased)
    - raw_text_blob  : original-case concatenated text (for citation extraction)
    - name_norm      : lower-cased, stripped facility name
    - zip_clean      : stripped zip/postcode
    - has_description: bool
    - has_equipment  : bool — equip_list is non-empty
    - has_named_staff: bool — affiliated_staff_presence == TRUE
    - open_24h       : bool — "24" appears in text_blob
    - doctor_count   : int (0 if missing)

    Raises:
        FileNotFoundError — dataset file not found at configured path
        ValueError        — file exists but is empty or unreadable
    """
    global _df_cache
    if _df_cache is not None:
        return _df_cache

    path = Path(dataset_path)
    if not path.exists():
        raise FileNotFoundError(
            f"Dataset not found at {path}.\n"
            f"Copy the CSV to that location:\n"
            f"  copy \"<source>\\Hackathon_Dataset_India_Larg.csv\" \"{path}\""
        )

    try:
        df = pd.read_csv(path, encoding="utf-8", low_memory=False, dtype=str)
    except Exception as exc:
        raise ValueError(f"Could not read dataset at {path}: {exc}") from exc

    if df.empty:
        raise ValueError(f"Dataset at {path} is empty.")

    # Fill NaN (from pandas) with empty string so str operations work uniformly
    df = df.fillna("")

    # ── Row identifier ────────────────────────────────────────────────────────
    df["row_id"] = range(len(df))

    # ── Parse JSON list fields ────────────────────────────────────────────────
    df["cap_list"]   = df["capability"].apply(_parse_json_list)
    df["proc_list"]  = df["procedure"].apply(_parse_json_list)
    df["equip_list"] = df["equipment"].apply(_parse_json_list)
    df["spec_list"]  = df["specialties"].apply(_parse_json_list)
    df["phone_list"] = df["phone_numbers"].apply(_parse_json_list)

    # ── Coordinates ───────────────────────────────────────────────────────────
    df["lat_f"] = df["latitude"].apply(_safe_float)
    df["lon_f"] = df["longitude"].apply(_safe_float)
    df["has_coords"] = df["lat_f"].notna() & df["lon_f"].notna()

    # ── Derived boolean flags ─────────────────────────────────────────────────
    df["has_description"] = df["description"].apply(
        lambda x: not _is_null(x) and len(x.strip()) > 10
    )
    df["has_equipment"] = df["equip_list"].apply(len) > 0
    df["has_named_staff"] = df["affiliated_staff_presence"].str.upper().str.strip() == "TRUE"

    def _doctor_count(v: str) -> int:
        try:
            n = int(float(v))
            return max(0, n)
        except (ValueError, TypeError):
            return 0

    df["doctor_count"] = df["numberDoctors"].apply(_doctor_count)

    # ── Text blobs for search and citation ────────────────────────────────────
    def _build_raw_blob(row: pd.Series) -> str:
        parts = []
        for field in ("description", "capability", "procedure", "equipment", "specialties"):
            val = row.get(field, "")
            if not _is_null(val):
                parts.append(val)
        # Also include name and address for location matching
        for field in ("name", "address_city", "address_stateOrRegion"):
            val = row.get(field, "")
            if not _is_null(val):
                parts.append(val)
        return " | ".join(parts)

    df["raw_text_blob"] = df.apply(_build_raw_blob, axis=1)
    df["text_blob"]     = df["raw_text_blob"].str.lower()

    df["open_24h"] = df["text_blob"].str.contains(
        r"24\s*(?:/\s*7|hours?|hrs?)\b|open\s+24|round.the.clock", regex=True
    )

    # ── Name and ZIP normalization ────────────────────────────────────────────
    df["name_norm"] = df["name"].str.lower().str.strip()
    df["zip_clean"] = df["address_zipOrPostcode"].str.strip()

    _df_cache = df
    return df


def invalidate_cache() -> None:
    """Force reload on next call to load_dataframe(). Useful for tests."""
    global _df_cache
    _df_cache = None


def get_row_by_index(row_index: int, df: Optional[pd.DataFrame] = None) -> Optional[pd.Series]:
    """Return the DataFrame row at 0-based row_index, or None."""
    if df is None:
        df = load_dataframe()
    if 0 <= row_index < len(df):
        return df.iloc[row_index]
    return None


def get_rows_by_name(name: str, df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    """Return all rows whose normalized name matches the given name (case-insensitive)."""
    if df is None:
        df = load_dataframe()
    name_norm = name.lower().strip()
    return df[df["name_norm"] == name_norm]


def dataset_summary(df: Optional[pd.DataFrame] = None) -> dict:
    """Return high-level summary stats for the Overview dashboard panel."""
    if df is None:
        df = load_dataframe()
    total = len(df)
    with_coords = int(df["has_coords"].sum())
    with_description = int(df["has_description"].sum())
    with_equipment = int(df["has_equipment"].sum())
    with_staff = int(df["has_named_staff"].sum())
    with_procedures = int(df["proc_list"].apply(len).gt(0).sum())
    by_type = df["facilityTypeId"].value_counts().to_dict()
    by_state = df["address_stateOrRegion"].value_counts().head(15).to_dict()

    return {
        "total_records": total,
        "with_coords": with_coords,
        "with_description": with_description,
        "with_equipment": with_equipment,
        "with_named_staff": with_staff,
        "with_procedures": with_procedures,
        "by_facility_type": by_type,
        "by_state": by_state,
    }
