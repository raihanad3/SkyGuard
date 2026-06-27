"""
SkyGuard — Airspace Configuration
==================================
Airport locations, restricted zones, and geographic utilities for Asia region.
"""

import math

# ============================================================
# ASIA GEOGRAPHIC BOUNDING BOX
# ============================================================
# Coverage: Southeast Asia, East Asia, South Asia
ASIA_AIRSPACE_BBOX = {
    "lat_min": -11.0,   # Indonesia (south)
    "lat_max": 55.0,    # Russia (north)
    "lon_min": 92.0,    # India (west)
    "lon_max": 141.0,   # Japan (east)
}

# Coordinates for news scraping focus (major aviation hubs)
ASIA_AIR_COORDINATES = [
    (-6.125, 106.655),   # Jakarta (CGK)
    (-7.788, 110.438),   # Yogyakarta (JOG)
    (-8.748, 115.167),   # Bali (DPS)
    (3.139, 101.687),    # Kuala Lumpur (KUL)
    (1.350, 103.994),    # Singapore (SIN)
    (13.681, 100.747),   # Bangkok (BKK)
    (22.309, 113.915),   # Hong Kong (HKG)
    (35.765, 140.386),   # Tokyo Narita (NRT)
]

# ============================================================
# MAJOR AIRPORTS IN ASIA
# ============================================================
# Format: (latitude, longitude, IATA_code, name, radius_km)
AIRPORTS = [
    # Indonesia
    (-6.125, 106.655, "CGK", "Soekarno-Hatta International Airport", 15),
    (-7.380, 112.787, "SUB", "Juanda International Airport", 12),
    (-8.748, 115.167, "DPS", "Ngurah Rai International Airport", 10),
    (-7.788, 110.438, "JOG", "Adisucipto International Airport", 10),
    (3.642, 98.885, "KNO", "Kualanamu International Airport", 12),
    (-5.062, 119.554, "UPG", "Sultan Hasanuddin International Airport", 10),
    (-1.268, 116.894, "BPN", "Sultan Aji Muhammad Sulaiman Airport", 10),
    (-6.971, 110.374, "SRG", "Achmad Yani International Airport", 10),
    (1.121, 104.119, "BTH", "Hang Nadim International Airport", 10),
    (-0.873, 100.352, "PDG", "Minangkabau International Airport", 10),
    
    # Southeast Asia
    (1.350, 103.994, "SIN", "Singapore Changi Airport", 15),
    (3.139, 101.687, "KUL", "Kuala Lumpur International Airport", 15),
    (13.681, 100.747, "BKK", "Suvarnabhumi Airport", 15),
    (10.819, 106.652, "SGN", "Tan Son Nhat International Airport", 12),
    (21.221, 105.807, "HAN", "Noi Bai International Airport", 12),
    (14.509, 121.020, "MNL", "Ninoy Aquino International Airport", 12),
    
    # East Asia
    (22.309, 113.915, "HKG", "Hong Kong International Airport", 15),
    (25.077, 121.233, "TPE", "Taiwan Taoyuan International Airport", 15),
    (35.765, 140.386, "NRT", "Narita International Airport", 15),
    (34.434, 135.244, "KIX", "Kansai International Airport", 15),
    (37.469, 126.451, "ICN", "Incheon International Airport", 15),
    
    # South Asia
    (28.566, 77.103, "DEL", "Indira Gandhi International Airport", 15),
    (19.089, 72.868, "BOM", "Chhatrapati Shivaji Maharaj International Airport", 15),
    (12.990, 77.593, "BLR", "Kempegowda International Airport", 15),
]

# ============================================================
# RESTRICTED ZONES (Simplified - Real zones would be polygons)
# ============================================================
# Format: {"id": str, "name": str, "center": (lat, lon), "radius_km": float, "risk_multiplier": float}
RESTRICTED_ZONES = [
    {
        "id": "ZONE_NATUNA",
        "name": "Natuna Military Zone",
        "center": (3.5, 108.2),
        "radius_km": 50,
        "risk_multiplier": 1.5,
    },
    {
        "id": "ZONE_PAPUA",
        "name": "Papua Border Restricted Zone",
        "center": (-3.5, 140.5),
        "radius_km": 40,
        "risk_multiplier": 1.3,
    },
    {
        "id": "ZONE_DMZ_KOREA",
        "name": "Korean DMZ Airspace",
        "center": (38.0, 127.0),
        "radius_km": 30,
        "risk_multiplier": 2.0,
    },
]

# ============================================================
# UTILITY FUNCTIONS
# ============================================================

def calculate_distance_km(lat1, lon1, lat2, lon2):
    """
    Calculate distance between two coordinates using Haversine formula.
    
    Args:
        lat1, lon1: First coordinate (degrees)
        lat2, lon2: Second coordinate (degrees)
    
    Returns:
        float: Distance in kilometers
    """
    if None in [lat1, lon1, lat2, lon2]:
        return 0.0
    
    R = 6371  # Earth radius in kilometers
    
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)
    
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    
    a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    
    return R * c


def is_near_airport(lat, lon, proximity_km=None):
    """
    Check if coordinates are near any major airport.
    
    Args:
        lat, lon: Coordinates to check (degrees)
        proximity_km: Override default proximity threshold
    
    Returns:
        tuple: (is_near: bool, airport_code: str, airport_name: str)
    """
    if lat is None or lon is None:
        return (False, None, None)
    
    for airport in AIRPORTS:
        airport_lat, airport_lon, code, name, radius = airport
        
        distance = calculate_distance_km(lat, lon, airport_lat, airport_lon)
        threshold = proximity_km if proximity_km else radius
        
        if distance <= threshold:
            return (True, code, name)
    
    return (False, None, None)


def is_in_restricted_zone(lat, lon):
    """
    Check if coordinates are in a restricted zone.
    
    Args:
        lat, lon: Coordinates to check (degrees)
    
    Returns:
        tuple: (in_zone: bool, zone_id: str, zone_name: str, risk_multiplier: float)
    """
    if lat is None or lon is None:
        return (False, None, None, 1.0)
    
    for zone in RESTRICTED_ZONES:
        center_lat, center_lon = zone["center"]
        radius = zone["radius_km"]
        
        distance = calculate_distance_km(lat, lon, center_lat, center_lon)
        
        if distance <= radius:
            return (
                True,
                zone["id"],
                zone["name"],
                zone["risk_multiplier"]
            )
    
    return (False, None, None, 1.0)


def get_airport_by_code(iata_code):
    """
    Retrieve airport details by IATA code.
    
    Args:
        iata_code: 3-letter IATA code (e.g., "CGK")
    
    Returns:
        dict or None: Airport details if found
    """
    for airport in AIRPORTS:
        lat, lon, code, name, radius = airport
        if code == iata_code:
            return {
                "latitude": lat,
                "longitude": lon,
                "code": code,
                "name": name,
                "radius_km": radius,
            }
    return None


def is_in_asia_bbox(lat, lon):
    """
    Check if coordinates are within Asia bounding box.
    
    Args:
        lat, lon: Coordinates to check
    
    Returns:
        bool: True if within ASIA_AIRSPACE_BBOX
    """
    if lat is None or lon is None:
        return False
    
    bbox = ASIA_AIRSPACE_BBOX
    return (bbox["lat_min"] <= lat <= bbox["lat_max"] and 
            bbox["lon_min"] <= lon <= bbox["lon_max"])
