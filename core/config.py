"""
SkyGuard Configuration
======================
Konfigurasi sistem monitoring penerbangan Indonesia.
"""

import os

# ============================================================
# OpenSky Network API Configuration
# ============================================================
OPENSKY_API_URL = "https://opensky-network.org/api/states/all"
OPENSKY_UPDATE_INTERVAL = 10  # seconds (API updates every 10s)

# ============================================================
# Indonesian Airspace Boundaries
# ============================================================
# Indonesia FIR (Flight Information Region) bounding box
INDONESIA_AIRSPACE_BBOX = {
    "lat_min": -11.0,
    "lat_max": 6.0,
    "lon_min": 95.0,
    "lon_max": 141.0
}

# ============================================================
# Restricted/Sensitive Zones
# ============================================================
RESTRICTED_ZONES = {
    "jakarta_presidential": {
        "name": "Jakarta Presidential Palace Area",
        "center": [-6.1701, 106.8229],
        "radius_km": 5,
        "risk_multiplier": 2.0
    },
    "halim_military": {
        "name": "Halim Perdanakusuma Military Base",
        "center": [-6.2667, 106.8911],
        "radius_km": 3,
        "risk_multiplier": 1.8
    },
    "bali_ngurah_rai": {
        "name": "Ngurah Rai Restricted Area",
        "center": [-8.7467, 115.1671],
        "radius_km": 2,
        "risk_multiplier": 1.5
    },
    "surabaya_juanda": {
        "name": "Juanda Military Zone",
        "center": [-7.3798, 112.7868],
        "radius_km": 3,
        "risk_multiplier": 1.6
    },
    "natuna_border": {
        "name": "Natuna Border Area",
        "center": [3.9731, 108.2426],
        "radius_km": 50,
        "risk_multiplier": 1.4
    }
}

# ============================================================
# Anomaly Detection Parameters
# ============================================================
ANOMALY_CONFIG = {
    # Altitude thresholds (feet)
    "min_safe_altitude": 1000,      # Below this = suspicious (unless near airport)
    "max_normal_altitude": 45000,   # Above this = unusual
    "rapid_climb_rate": 2000,       # ft/min - rapid altitude change
    
    # Speed thresholds (knots)
    "min_cruise_speed": 100,        # Below this at cruise = suspicious
    "max_normal_speed": 600,        # Above this = unusual (commercial)
    "max_military_speed": 1200,     # Military jets can go faster
    
    # Course change
    "erratic_course_change": 90,    # Degrees - sudden turn
    
    # Transponder off
    "transponder_timeout": 300,     # Seconds (5 min) - no update = off
    
    # Ground proximity
    "airport_buffer_km": 20,        # Within 20km of airport = OK to be low
}

# ============================================================
# Major Indonesian Airports (for altitude exception)
# ============================================================
MAJOR_AIRPORTS = {
    "CGK": {"name": "Soekarno-Hatta", "lat": -6.1256, "lon": 106.6560},
    "DPS": {"name": "Ngurah Rai", "lat": -8.7467, "lon": 115.1671},
    "SUB": {"name": "Juanda", "lat": -7.3798, "lon": 112.7868},
    "BTH": {"name": "Hang Nadim", "lat": 1.1210, "lon": 104.1196},
    "UPG": {"name": "Hasanuddin", "lat": -5.0616, "lon": 119.5540},
    "KNO": {"name": "Kualanamu", "lat": 3.6422, "lon": 98.8853},
}

# ============================================================
# Alert Thresholds
# ============================================================
ALERT_THRESHOLDS = {
    "HIGH": 0.7,       # Score >= 0.7 → HIGH ALERT
    "MEDIUM": 0.5,     # Score >= 0.5 → MEDIUM
    "LOW": 0.3,        # Score >= 0.3 → LOW
}

ALERT_COOLDOWN_MINUTES = 10  # Prevent alert spam

# ============================================================
# Database Configuration
# ============================================================
DATABASE_PATH = os.path.join(os.path.dirname(__file__), "data", "skyguard.db")

# ============================================================
# Logging Configuration
# ============================================================
LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
LOG_FILE = os.path.join(LOG_DIR, "skyguard.log")
ALERT_LOG_FILE = os.path.join(LOG_DIR, "alerts.log")

# ============================================================
# Dashboard Configuration
# ============================================================
DASHBOARD_HOST = "0.0.0.0"
DASHBOARD_PORT = 5000

# ============================================================
# Model Save Path
# ============================================================
MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")
MODEL_PATH = os.path.join(MODEL_DIR, "flight_anomaly.pkl")

# ============================================================
# Helper Functions
# ============================================================
def calculate_distance_km(lat1, lon1, lat2, lon2):
    """Calculate distance between two coordinates in km."""
    from math import radians, sin, cos, sqrt, atan2
    
    R = 6371  # Earth radius in km
    
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    
    return R * c

def is_near_airport(lat, lon, threshold_km=20):
    """Check if coordinate is near major airport."""
    for code, airport in MAJOR_AIRPORTS.items():
        distance = calculate_distance_km(lat, lon, airport["lat"], airport["lon"])
        if distance <= threshold_km:
            return True, code, airport["name"]
    return False, None, None

def is_in_restricted_zone(lat, lon):
    """Check if coordinate is in restricted zone."""
    for zone_id, zone in RESTRICTED_ZONES.items():
        center_lat, center_lon = zone["center"]
        distance = calculate_distance_km(lat, lon, center_lat, center_lon)
        if distance <= zone["radius_km"]:
            return True, zone_id, zone["name"], zone["risk_multiplier"]
    return False, None, None, 1.0
