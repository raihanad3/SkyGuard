"""
Realistic Vessel Generator for Indonesian Waters
==================================================
Generate realistic vessel movement patterns berdasarkan:
- Real shipping lanes di Indonesia
- Realistic vessel behavior (speed, course, type)
- Historical traffic patterns

NOT DEMO DATA - This is "simulated realistic data" for demonstration purposes.
"""

import random
import asyncio
import logging
from datetime import datetime
from core.config import CRITICAL_ZONES

logger = logging.getLogger("vessel_anomaly")


class RealisticVesselGenerator:
    """Generate realistic vessel movements in Indonesian waters."""
    
    def __init__(self):
        self.vessels = []
        self.vessel_count = 0
        
        # Shipping lanes in Indonesia (real routes)
        self.shipping_lanes = {
            # Malacca Strait (Singapore-Indonesia-Malaysia)
            "malacca_strait": {
                "start": [1.0, 98.5],
                "end": [4.0, 103.5],
                "direction": "northeast",
                "traffic": "very_high",
                "countries": ["SG", "MY", "CN", "JP", "KR", "TW", "PH"]
            },
            # Sunda Strait (Jakarta-Sumatra)
            "sunda_strait": {
                "start": [-6.5, 105.5],
                "end": [-5.5, 106.0],
                "direction": "north",
                "traffic": "high",
                "countries": ["ID", "SG", "MY", "CN", "JP"]
            },
            # Java Sea (Jakarta-Surabaya-Makassar)
            "java_sea": {
                "start": [-6.0, 107.0],
                "end": [-3.0, 115.0],
                "direction": "east",
                "traffic": "high",
                "countries": ["ID", "SG", "CN", "MY"]
            },
            # Natuna Sea (high risk - foreign fishing vessels)
            "natuna_sea": {
                "start": [2.0, 106.0],
                "end": [5.0, 110.0],
                "direction": "variable",
                "traffic": "medium",
                "countries": ["CN", "VN", "ID", "MY", "UNKNOWN"]  # High risk flags
            },
            # Makassar Strait (Kalimantan-Sulawesi)
            "makassar_strait": {
                "start": [-5.0, 117.5],
                "end": [1.0, 118.5],
                "direction": "north",
                "traffic": "medium",
                "countries": ["ID", "MY", "PH", "CN"]
            },
            # Arafura Sea (Papua - Australia route)
            "arafura_sea": {
                "start": [-8.0, 138.0],
                "end": [-6.0, 140.0],
                "direction": "variable",
                "traffic": "low",
                "countries": ["ID", "PH", "CN", "TW", "UNKNOWN"]
            }
        }
        
        # Ship types with realistic distribution
        self.ship_types = {
            30: {"name": "Fishing", "speed_range": (2, 8), "weight": 25},  # Most common in ID waters
            70: {"name": "Cargo", "speed_range": (10, 18), "weight": 30},
            80: {"name": "Tanker", "speed_range": (8, 15), "weight": 20},
            60: {"name": "Passenger", "speed_range": (12, 22), "weight": 10},
            40: {"name": "High Speed Craft", "speed_range": (20, 35), "weight": 5},
            50: {"name": "Special Craft", "speed_range": (5, 12), "weight": 5},
            90: {"name": "Other", "speed_range": (5, 15), "weight": 5}
        }
    
    def generate_initial_vessels(self, count=30):
        """Generate initial fleet of vessels across Indonesian waters."""
        logger.info(f"🚢 Generating {count} realistic vessels for Indonesian waters...")
        
        for i in range(count):
            vessel = self._create_vessel(i + 1)
            self.vessels.append(vessel)
        
        self.vessel_count = count
        logger.info(f"✅ Generated {count} vessels across shipping lanes")
        return self.vessels
    
    def _create_vessel(self, vessel_id):
        """Create a single realistic vessel."""
        # Pick shipping lane based on traffic weight
        lane_name = random.choices(
            list(self.shipping_lanes.keys()),
            weights=[
                3 if lane["traffic"] == "very_high" else
                2 if lane["traffic"] == "high" else
                1 for lane in self.shipping_lanes.values()
            ]
        )[0]
        
        lane = self.shipping_lanes[lane_name]
        
        # Pick ship type based on weight
        ship_type = random.choices(
            list(self.ship_types.keys()),
            weights=[info["weight"] for info in self.ship_types.values()]
        )[0]
        
        ship_info = self.ship_types[ship_type]
        
        # Generate position along lane
        start_lat, start_lon = lane["start"]
        end_lat, end_lon = lane["end"]
        progress = random.random()
        
        lat = start_lat + (end_lat - start_lat) * progress
        lon = start_lon + (end_lon - start_lon) * progress
        
        # Add some randomness (vessels don't follow exact lines)
        lat += random.uniform(-0.3, 0.3)
        lon += random.uniform(-0.3, 0.3)
        
        # Calculate course based on lane direction
        if end_lat > start_lat and end_lon > start_lon:
            base_course = 45  # Northeast
        elif end_lat < start_lat and end_lon > start_lon:
            base_course = 135  # Southeast
        elif end_lat > start_lat and end_lon < start_lon:
            base_course = 315  # Northwest
        elif end_lat > start_lat:
            base_course = 0  # North
        elif end_lon > start_lon:
            base_course = 90  # East
        else:
            base_course = 180  # South
        
        course = (base_course + random.uniform(-20, 20)) % 360
        
        # Generate realistic MMSI (9 digits)
        mmsi_base = 525000000 if random.random() > 0.3 else random.randint(400000000, 600000000)
        mmsi = str(mmsi_base + vessel_id)
        
        # Pick flag country from lane
        flag = random.choice(lane["countries"])
        
        # Generate speed based on ship type
        speed = random.uniform(*ship_info["speed_range"])
        
        # Generate ship name
        prefixes = ["MV", "MT", "FV", "KM", "TB"]
        names = [
            "SINAR", "MUTIARA", "BAHAGIA", "SEJAHTERA", "JAYA",
            "OCEAN", "PACIFIC", "ASIA", "STAR", "GLORY",
            "FORTUNE", "MEGA", "INDO", "NUSANTARA", "SAMUDRA"
        ]
        ship_name = f"{random.choice(prefixes)} {random.choice(names)} {random.randint(1, 99)}"
        
        return {
            "mmsi": mmsi,
            "latitude": lat,
            "longitude": lon,
            "speed": speed,
            "course": course,
            "heading": course,
            "ship_name": ship_name,
            "ship_type": ship_type,
            "ship_type_name": ship_info["name"],
            "flag_country": flag,
            "timestamp": datetime.utcnow().isoformat(),
            "destination": "INDONESIA" if flag == "ID" else "VARIOUS",
            "source": "RealisticSimulation",
            "lane": lane_name
        }
    
    def update_vessel_positions(self):
        """Update all vessel positions (simulate movement)."""
        for vessel in self.vessels:
            # Move vessel based on speed and course
            # 1 knot = 1.852 km/h = 0.0005144 degrees per second (approx)
            speed_deg_per_sec = vessel["speed"] * 0.0005144 / 3600
            
            # Update position (30 second interval)
            time_step = 30  # seconds
            distance = speed_deg_per_sec * time_step
            
            # Calculate new position
            import math
            course_rad = math.radians(vessel["course"])
            vessel["latitude"] += distance * math.cos(course_rad)
            vessel["longitude"] += distance * math.sin(course_rad)
            
            # Add some randomness (currents, manual steering)
            vessel["course"] += random.uniform(-5, 5)
            vessel["course"] = vessel["course"] % 360
            vessel["heading"] = vessel["course"]
            
            # Small speed variation
            speed_change = random.uniform(-0.5, 0.5)
            vessel["speed"] = max(0, vessel["speed"] + speed_change)
            
            # Update timestamp
            vessel["timestamp"] = datetime.utcnow().isoformat()
            
            # Keep vessels in bounds (wrap around or turn back)
            if vessel["latitude"] < -14.0 or vessel["latitude"] > 8.0:
                vessel["course"] = (vessel["course"] + 180) % 360
            if vessel["longitude"] < 92.0 or vessel["longitude"] > 141.5:
                vessel["course"] = (vessel["course"] + 180) % 360
        
        return self.vessels
    
    def add_suspicious_vessel(self):
        """Add a suspicious/high-risk vessel (for testing alerts)."""
        # Create fishing vessel in Natuna Sea (high risk area)
        vessel = {
            "mmsi": str(412000000 + random.randint(1000, 9999)),  # Chinese MMSI
            "latitude": random.uniform(2.0, 6.0),
            "longitude": random.uniform(106.0, 110.0),
            "speed": random.uniform(3, 7),  # Slow fishing speed
            "course": random.uniform(0, 360),
            "heading": random.uniform(0, 360),
            "ship_name": f"FV LU RONG YU {random.randint(100, 999)}",
            "ship_type": 30,  # Fishing
            "ship_type_name": "Fishing",
            "flag_country": "CN",  # High risk flag
            "timestamp": datetime.utcnow().isoformat(),
            "destination": "FISHING GROUND",
            "source": "RealisticSimulation",
            "lane": "natuna_sea"
        }
        
        self.vessels.append(vessel)
        logger.info(f"⚠️ Added suspicious vessel: {vessel['ship_name']} in Natuna Sea")
        return vessel


# Singleton
generator = RealisticVesselGenerator()
