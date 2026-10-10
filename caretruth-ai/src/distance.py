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


def resolve_location_query(query: str, df=None) -> Optional[tuple[float, float, str]]:
    """
    Resolve a place name, city, PIN code, or state string to (lat, lon, label).

    Args:
        query: User typed place name string.
        df: Optional dataframe for in-dataset lookup.

    Returns:
        (lat, lon, label) or None if unresolvable.
    """
    if not query:
        return None
    q = query.strip().lower()

    # Check preset dict
    for name, (lat, lon) in PRESET_LOCATIONS.items():
        if q in name.lower():
            return lat, lon, name

    # Check dataset if available
    if df is not None and hasattr(df, "empty") and not df.empty:
        if "address_city" in df.columns:
            city_matches = df[df["address_city"].astype(str).str.lower().str.contains(q, na=False)]
            if not city_matches.empty:
                lat = float(city_matches["lat_f"].mean())
                lon = float(city_matches["lon_f"].mean())
                city_name = str(city_matches["address_city"].iloc[0])
                return lat, lon, f"{city_name} ({len(city_matches)} facilities in dataset)"

        if "address_zipOrPostcode" in df.columns:
            pin_matches = df[df["address_zipOrPostcode"].astype(str).str.lower().str.contains(q, na=False)]
            if not pin_matches.empty:
                lat = float(pin_matches["lat_f"].mean())
                lon = float(pin_matches["lon_f"].mean())
                pin_val = str(pin_matches["address_zipOrPostcode"].iloc[0])
                return lat, lon, f"PIN {pin_val} ({len(pin_matches)} facilities)"

        if "address_stateOrRegion" in df.columns:
            state_matches = df[df["address_stateOrRegion"].astype(str).str.lower().str.contains(q, na=False)]
            if not state_matches.empty:
                lat = float(state_matches["lat_f"].mean())
                lon = float(state_matches["lon_f"].mean())
                state_name = str(state_matches["address_stateOrRegion"].iloc[0])
                return lat, lon, f"{state_name} State ({len(state_matches)} facilities)"

    return None

