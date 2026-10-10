"""CareTruth AI — Haversine distance and location utilities."""
from __future__ import annotations
import math
from typing import Optional


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Compute the Haversine great-circle distance between two points.

    Args:
        lat1, lon1: Source point in decimal degrees.
        lat2, lon2: Destination point in decimal degrees.

    Returns:
        Distance in kilometres.
    """
    R = 6371.0  # Earth radius in km
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


PRESET_LOCATIONS: dict[str, tuple[float, float]] = {
    "Siwan / Gopalganj, Bihar (Probe g1/g4)": (26.2400, 84.4000),
    "Begusarai, Bihar (Probe g2)": (25.5000, 86.1300),
    "Patna, Bihar": (25.5941, 85.1376),
    "New Delhi": (28.6139, 77.2090),
    "Mumbai, Maharashtra": (19.0760, 72.8777),
    "Bengaluru, Karnataka": (12.9716, 77.5946),
    "Kolkata, West Bengal": (22.5726, 88.3639),
    "Chennai, Tamil Nadu": (13.0827, 80.2707),
    "Hyderabad, Telangana": (17.3850, 78.4867),
    "Pune, Maharashtra": (18.5204, 73.8567),
    "Ahmedabad, Gujarat": (23.0225, 72.5714),
    "Lucknow, Uttar Pradesh": (26.8467, 80.9462),
    "Jaipur, Rajasthan": (26.9124, 75.7873),
    "Chandigarh": (30.7333, 76.7794),
    "Guwahati, Assam": (26.1445, 91.7362),
    "Kochi / Ernakulam, Kerala": (9.9312, 76.2673),
}


import re


def resolve_location_query(query: str, df=None) -> Optional[tuple[float, float, str]]:
    """
    Resolve a place name, city, PIN code, or state string to (lat, lon, label).
    Handles exact names, comma-separated 'City, State' (e.g. 'Amritsar, Punjab'),
    sub-district words, and PIN codes.

    Args:
        query: User typed place name string.
        df: Optional dataframe for in-dataset lookup.

    Returns:
        (lat, lon, label) or None if unresolvable.
    """
    if not query:
        return None
    raw_q = query.strip()
    q = raw_q.lower()

    # Check preset dict
    for name, (lat, lon) in PRESET_LOCATIONS.items():
        if q == name.lower() or q in name.lower() or name.lower() in q:
            return lat, lon, name

    # Check dataset if available
    if df is not None and hasattr(df, "empty") and not df.empty:
        # 1. Comma-separated "City, State" (e.g. "Amritsar, Punjab" or "Ludhiana, Punjab")
        if "," in raw_q:
            parts = [p.strip().lower() for p in raw_q.split(",") if p.strip()]
            if len(parts) >= 2:
                city_part, state_part = parts[0], parts[1]
                cs_matches = df[
                    df["address_city"].astype(str).str.lower().str.contains(city_part, na=False) &
                    df["address_stateOrRegion"].astype(str).str.lower().str.contains(state_part, na=False)
                ]
                if not cs_matches.empty:
                    valid_coords = cs_matches[cs_matches["lat_f"].notna() & cs_matches["lon_f"].notna()]
                    if not valid_coords.empty:
                        lat = float(valid_coords["lat_f"].mean())
                        lon = float(valid_coords["lon_f"].mean())
                        city_name = str(cs_matches["address_city"].iloc[0])
                        state_name = str(cs_matches["address_stateOrRegion"].iloc[0])
                        return lat, lon, f"{city_name}, {state_name} ({len(cs_matches)} facilities in dataset)"

        # 2. Check full string in address_city (e.g. "Amritsar", "Ludhiana")
        if "address_city" in df.columns:
            city_matches = df[df["address_city"].astype(str).str.lower().str.contains(q, na=False)]
            if not city_matches.empty:
                valid_coords = city_matches[city_matches["lat_f"].notna() & city_matches["lon_f"].notna()]
                if not valid_coords.empty:
                    lat = float(valid_coords["lat_f"].mean())
                    lon = float(valid_coords["lon_f"].mean())
                    city_name = str(city_matches["address_city"].iloc[0])
                    return lat, lon, f"{city_name} ({len(city_matches)} facilities in dataset)"

        # 3. Check individual tokens in query against address_city (e.g. "Amritsar Cantt" or "Ludhiana West")
        tokens = [t.strip().lower() for t in re.split(r'[, -]+', raw_q) if len(t.strip()) >= 3]
        if "address_city" in df.columns:
            for tok in tokens:
                tok_matches = df[df["address_city"].astype(str).str.lower().str.fullmatch(tok, na=False)]
                if tok_matches.empty:
                    tok_matches = df[df["address_city"].astype(str).str.lower().str.contains(tok, na=False)]
                if not tok_matches.empty:
                    valid_coords = tok_matches[tok_matches["lat_f"].notna() & tok_matches["lon_f"].notna()]
                    if not valid_coords.empty:
                        lat = float(valid_coords["lat_f"].mean())
                        lon = float(valid_coords["lon_f"].mean())
                        city_name = str(tok_matches["address_city"].iloc[0])
                        return lat, lon, f"{city_name} ({len(tok_matches)} facilities in dataset)"

        # 4. Check PIN code in address_zipOrPostcode
        if "address_zipOrPostcode" in df.columns:
            pin_matches = df[df["address_zipOrPostcode"].astype(str).str.lower().str.contains(q, na=False)]
            if not pin_matches.empty:
                valid_coords = pin_matches[pin_matches["lat_f"].notna() & pin_matches["lon_f"].notna()]
                if not valid_coords.empty:
                    lat = float(valid_coords["lat_f"].mean())
                    lon = float(valid_coords["lon_f"].mean())
                    pin_val = str(pin_matches["address_zipOrPostcode"].iloc[0])
                    return lat, lon, f"PIN {pin_val} ({len(pin_matches)} facilities)"

        # 5. Check address_stateOrRegion (e.g. "Punjab")
        if "address_stateOrRegion" in df.columns:
            state_matches = df[df["address_stateOrRegion"].astype(str).str.lower().str.contains(q, na=False)]
            if not state_matches.empty:
                valid_coords = state_matches[state_matches["lat_f"].notna() & state_matches["lon_f"].notna()]
                if not valid_coords.empty:
                    lat = float(valid_coords["lat_f"].mean())
                    lon = float(valid_coords["lon_f"].mean())
                    state_name = str(state_matches["address_stateOrRegion"].iloc[0])
                    return lat, lon, f"{state_name} State ({len(state_matches)} facilities)"

        # 6. Check address lines (e.g. specific locality / street)
        for col in ["address_line1", "address_line2", "address_line3"]:
            if col in df.columns:
                line_matches = df[df[col].astype(str).str.lower().str.contains(q, na=False)]
                if not line_matches.empty:
                    valid_coords = line_matches[line_matches["lat_f"].notna() & line_matches["lon_f"].notna()]
                    if not valid_coords.empty:
                        lat = float(valid_coords["lat_f"].mean())
                        lon = float(valid_coords["lon_f"].mean())
                        return lat, lon, f"{raw_q} ({len(line_matches)} facilities in dataset)"

    return None

