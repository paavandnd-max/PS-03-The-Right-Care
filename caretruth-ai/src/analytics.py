"""CareTruth AI — Analytics module.

Computes coverage and gap metrics from the dataset for the Streamlit dashboard.
All numbers come directly from the loaded DataFrame — never hardcoded.
"""
from __future__ import annotations
from typing import Optional

import pandas as pd

from src.data_loader import load_dataframe, dataset_summary


def coverage_by_state(df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    """Return per-state facility counts and data completeness metrics."""
    if df is None:
        df = load_dataframe()

    agg = df.groupby("address_stateOrRegion").agg(
        total_facilities=("row_id", "count"),
        with_description=("has_description", "sum"),
        with_equipment=("has_equipment", "sum"),
        with_named_staff=("has_named_staff", "sum"),
        with_coords=("has_coords", "sum"),
    ).reset_index()
    agg.columns.name = None
    agg = agg.rename(columns={"address_stateOrRegion": "state"})
    agg["description_pct"] = (agg["with_description"] / agg["total_facilities"] * 100).round(1)
    agg["equipment_pct"]   = (agg["with_equipment"]   / agg["total_facilities"] * 100).round(1)
    return agg.sort_values("total_facilities", ascending=False)


def coverage_by_city(df: Optional[pd.DataFrame] = None, top_n: int = 20) -> pd.DataFrame:
    """Return per-city facility counts (top N cities)."""
    if df is None:
        df = load_dataframe()

    agg = df.groupby("address_city").agg(
        total_facilities=("row_id", "count"),
        with_equipment=("has_equipment", "sum"),
        with_named_staff=("has_named_staff", "sum"),
    ).reset_index()
    agg.columns.name = None
    agg = agg.rename(columns={"address_city": "city"})
    return agg.nlargest(top_n, "total_facilities")


def equipment_gap_analysis(df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    """Identify states where equipment documentation is lowest."""
    if df is None:
        df = load_dataframe()

    agg = coverage_by_state(df)
    agg["equipment_gap"] = 100 - agg["equipment_pct"]
    return agg[["state", "total_facilities", "equipment_pct", "equipment_gap"]].sort_values(
        "equipment_gap", ascending=False
    )


def facility_type_breakdown(df: Optional[pd.DataFrame] = None) -> dict[str, int]:
    """Return counts by facility type."""
    if df is None:
        df = load_dataframe()
    return df["facilityTypeId"].value_counts().to_dict()


def pin_code_summary(df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    """Return facility count per PIN code (top 50 PINs)."""
    if df is None:
        df = load_dataframe()
    agg = df.groupby("zip_clean").agg(
        count=("row_id", "count"),
        state=("address_stateOrRegion", "first"),
        city=("address_city", "first"),
    ).reset_index().rename(columns={"zip_clean": "pin"})
    return agg.nlargest(50, "count")
