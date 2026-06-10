# feature engineering dari raw ADS-B data
import logging
from datetime import datetime, timedelta
from core.config import (
    ANOMALY_CONFIG,
    is_near_airport,
    is_in_restricted_zone,
    calculate_distance_km
)

logger = logging.getLogger("skyguard")


class FeatureEngine:
    def __init__(self, database):
        self.db = database
        self.flight_history = {}  # simpan history flight buat pattern detection
    
    def extract_features(self, flight_data):
        # extract features dari raw data
        icao24 = flight_data.get("icao24")
        
        features = {
            # data dasar
            "icao24": icao24,
            "callsign": flight_data.get("callsign", "N/A"),
            "origin_country": flight_data.get("origin_country", "Unknown"),
            "latitude": flight_data.get("latitude", 0),
            "longitude": flight_data.get("longitude", 0),
            "altitude": flight_data.get("baro_altitude", 0),
            "speed": flight_data.get("velocity", 0),
            "heading": flight_data.get("true_track", 0),
            "vertical_rate": flight_data.get("vertical_rate", 0),
            "on_ground": flight_data.get("on_ground", False),
            "timestamp": flight_data.get("timestamp"),
            
            # converted features
            "speed_knots": flight_data.get("velocity", 0) * 1.94384 if flight_data.get("velocity") else 0,
            "altitude_feet": flight_data.get("baro_altitude", 0),
            "climb_rate_fpm": flight_data.get("vertical_rate", 0) * 196.85 if flight_data.get("vertical_rate") else 0,
        }
        
        # cek deket bandara ga
        near_airport, airport_code, airport_name = is_near_airport(
            features["latitude"],
            features["longitude"]
        )
        features["near_airport"] = near_airport
        features["airport_code"] = airport_code
        features["airport_name"] = airport_name
        
        # cek di restricted zone ga
        in_zone, zone_id, zone_name, risk_mult = is_in_restricted_zone(
            features["latitude"],
            features["longitude"]
        )
        features["in_restricted_zone"] = in_zone
        features["restricted_zone_id"] = zone_id
        features["restricted_zone_name"] = zone_name
        features["zone_risk_multiplier"] = risk_mult
        
        # track history
        if icao24 not in self.flight_history:
            self.flight_history[icao24] = []
        
        self.flight_history[icao24].append({
            "lat": features["latitude"],
            "lon": features["longitude"],
            "alt": features["altitude"],
            "speed": features["speed_knots"],
            "heading": features["heading"],
            "timestamp": features["timestamp"]
        })
        
        # Keep only last 100 positions
        if len(self.flight_history[icao24]) > 100:
            self.flight_history[icao24] = self.flight_history[icao24][-100:]
        
        # Calculate behavior features
        if len(self.flight_history[icao24]) >= 2:
            prev = self.flight_history[icao24][-2]
            curr = self.flight_history[icao24][-1]
            
            # Altitude change rate (handle None)
            if prev["alt"] is not None and curr["alt"] is not None:
                features["altitude_change"] = curr["alt"] - prev["alt"]
            else:
                features["altitude_change"] = 0
            
            # Heading change (handle None)
            if prev["heading"] is not None and curr["heading"] is not None:
                heading_diff = abs(curr["heading"] - prev["heading"])
                if heading_diff > 180:
                    heading_diff = 360 - heading_diff
                features["heading_change"] = heading_diff
            else:
                features["heading_change"] = 0
            
            # Distance traveled (handle None)
            if (prev["lat"] is not None and prev["lon"] is not None and
                curr["lat"] is not None and curr["lon"] is not None):
                features["distance_traveled_km"] = calculate_distance_km(
                    prev["lat"], prev["lon"],
                    curr["lat"], curr["lon"]
                )
            else:
                features["distance_traveled_km"] = 0
        else:
            features["altitude_change"] = 0
            features["heading_change"] = 0
            features["distance_traveled_km"] = 0
        
        return features
    
    def get_flight_history(self, icao24, limit=10):
        """Get recent history untuk specific flight."""
        if icao24 in self.flight_history:
            return self.flight_history[icao24][-limit:]
        return []
