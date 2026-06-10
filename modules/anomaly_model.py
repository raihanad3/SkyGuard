"""
Anomaly Detection Model untuk Flight Monitoring
Rule-based detection untuk suspicious flight behavior.
"""

import logging
import json
from core.config import ANOMALY_CONFIG, ALERT_THRESHOLDS

logger = logging.getLogger("skyguard")


class AnomalyDetector:
    """Detect anomalous flight behavior."""
    
    def __init__(self, feature_engine):
        self.feature_engine = feature_engine
        self.config = ANOMALY_CONFIG
    
    def analyze(self, flight_data):
        """Analyze flight untuk detect anomalies."""
        # Extract features
        features = self.feature_engine.extract_features(flight_data)
        
        # Calculate anomaly score
        score = 0.0
        reasons = []
        
        # Rule 1: Restricted Zone Entry
        if features.get("in_restricted_zone"):
            score += 0.4
            reasons.append(f"Entered restricted zone: {features.get('restricted_zone_name')}")
        
        # Rule 2: Suspicious Altitude
        altitude = features.get("altitude_feet", 0)
        near_airport = features.get("near_airport", False)
        
        if altitude and not near_airport:
            if altitude < self.config["min_safe_altitude"]:
                score += 0.3
                reasons.append(f"Very low altitude: {int(altitude)} ft (not near airport)")
            elif altitude > self.config["max_normal_altitude"]:
                score += 0.2
                reasons.append(f"Unusually high altitude: {int(altitude)} ft")
        
        # Rule 3: Unusual Speed
        speed = features.get("speed_knots", 0)
        on_ground = features.get("on_ground", False)
        
        if not on_ground and speed:
            if speed < self.config["min_cruise_speed"]:
                score += 0.2
                reasons.append(f"Unusually slow: {int(speed)} knots")
            elif speed > self.config["max_normal_speed"]:
                score += 0.25
                reasons.append(f"Very high speed: {int(speed)} knots")
        
        # Rule 4: Rapid Altitude Change
        climb_rate = features.get("climb_rate_fpm", 0)
        if abs(climb_rate) > self.config["rapid_climb_rate"]:
            score += 0.25
            reasons.append(f"Rapid {'climb' if climb_rate > 0 else 'descent'}: {int(abs(climb_rate))} ft/min")
        
        # Rule 5: Erratic Course Change
        heading_change = features.get("heading_change", 0)
        if heading_change > self.config["erratic_course_change"]:
            score += 0.2
            reasons.append(f"Sudden course change: {int(heading_change)}°")
        
        # Rule 6: Squawk Emergency Codes
        squawk = flight_data.get("squawk")
        if squawk:
            if squawk == "7500":  # Hijack
                score += 1.0
                reasons.append("EMERGENCY: Hijack code (7500)")
            elif squawk == "7600":  # Radio failure
                score += 0.6
                reasons.append("EMERGENCY: Radio failure (7600)")
            elif squawk == "7700":  # General emergency
                score += 0.8
                reasons.append("EMERGENCY: General emergency (7700)")
        
        # Apply zone risk multiplier
        if features.get("in_restricted_zone"):
            score *= features.get("zone_risk_multiplier", 1.0)
        
        # Cap score at 1.0
        score = min(score, 1.0)
        
        # Determine alert level
        alert_level = "NORMAL"
        if score >= ALERT_THRESHOLDS["HIGH"]:
            alert_level = "HIGH"
        elif score >= ALERT_THRESHOLDS["MEDIUM"]:
            alert_level = "MEDIUM"
        elif score >= ALERT_THRESHOLDS["LOW"]:
            alert_level = "LOW"
        
        return {
            "icao24": features["icao24"],
            "callsign": features["callsign"],
            "origin_country": features["origin_country"],
            "latitude": features["latitude"],
            "longitude": features["longitude"],
            "altitude": features["altitude_feet"],
            "speed": features["speed_knots"],
            "heading": features["heading"],
            "anomaly_score": round(score, 3),
            "alert_level": alert_level,
            "reasons": reasons,
            "zone_name": features.get("restricted_zone_name", ""),
            "timestamp": features["timestamp"]
        }
