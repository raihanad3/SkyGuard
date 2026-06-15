"""
SkyGuard — Asian Airspace Configuration
==============================================
Zones, airports, restricted areas, and coordinate helpers.
Single source of truth — used by all components.
"""

from math import radians, sin, cos, sqrt, atan2

# ============================================================
# Asian Airspace Boundaries (Bounding Box)
# ============================================================
ASIA_AIRSPACE_BBOX = {
    "lat_min": -11.0,
    "lat_max": 55.0,
    "lon_min": 60.0,
    "lon_max": 150.0,
}

# ============================================================
# Restricted / Sensitive Zones
# ============================================================
RESTRICTED_ZONES = {
    "jakarta_presidential": {
        "name": "Jakarta Presidential Palace Area",
        "center": [-6.1701, 106.8229],
        "radius_km": 5,
        "risk_multiplier": 2.0,
    },
    "beijing_forbidden_city": {
        "name": "Beijing Forbidden City",
        "center": [39.9163, 116.3971],
        "radius_km": 10,
        "risk_multiplier": 2.0,
    },
    "taiwan_strait": {
        "name": "Taiwan Strait Median Line",
        "center": [24.0, 119.5],
        "radius_km": 50,
        "risk_multiplier": 1.8,
    },
    "dmz_korea": {
        "name": "Korean DMZ",
        "center": [38.0, 126.5],
        "radius_km": 20,
        "risk_multiplier": 2.0,
    },
}

# ============================================================
# Major Asian Airports
# ============================================================
MAJOR_AIRPORTS = {
    "CGK": {"name": "Soekarno-Hatta (Jakarta)", "lat": -6.1256, "lon": 106.6560},
    "SIN": {"name": "Changi (Singapore)", "lat": 1.3644, "lon": 103.9915},
    "HND": {"name": "Haneda (Tokyo)", "lat": 35.5494, "lon": 139.7798},
    "PEK": {"name": "Capital (Beijing)", "lat": 40.0799, "lon": 116.6031},
    "HKG": {"name": "Hong Kong International", "lat": 22.3080, "lon": 113.9185},
    "DEL": {"name": "Indira Gandhi (Delhi)", "lat": 28.5562, "lon": 77.1000},
    "DXB": {"name": "Dubai International", "lat": 25.2532, "lon": 55.3657},
}

# ============================================================
# Asian Airspace Coordinate Database (for news geolocation)
# ============================================================
ASIA_AIR_COORDINATES = {
    # Countries/Regions
    "indonesia": "-2.5489, 118.0149",
    "singapore": "1.3521, 103.8198",
    "malaysia": "4.2105, 101.9758",
    "japan": "36.2048, 138.2529",
    "china": "35.8617, 104.1954",
    "india": "20.5937, 78.9629",
    "korea": "35.9078, 127.7669",
    "taiwan": "23.6978, 120.9605",
    # Major cities
    "jakarta": "-6.2088, 106.8456",
    "tokyo": "35.6895, 139.6917",
    "beijing": "39.9042, 116.4074",
    "delhi": "28.6139, 77.2090",
    "seoul": "37.5665, 126.9780",
}

# ============================================================
# Helper Functions
# ============================================================
def calculate_distance_km(lat1, lon1, lat2, lon2):
    R = 6371  # Earth radius in km
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c

def is_near_airport(lat, lon, threshold_km=30):
    for code, airport in MAJOR_AIRPORTS.items():
        distance = calculate_distance_km(lat, lon, airport["lat"], airport["lon"])
        if distance <= threshold_km:
            return True, code, airport["name"]
    return False, None, None

def is_in_restricted_zone(lat, lon):
    for zone_id, zone in RESTRICTED_ZONES.items():
        center_lat, center_lon = zone["center"]
        distance = calculate_distance_km(lat, lon, center_lat, center_lon)
        if distance <= zone["radius_km"]:
            return True, zone_id, zone["name"], zone["risk_multiplier"]
    return False, None, None, 1.0
