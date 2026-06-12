"""
SkyGuard — Anomaly Detector (Computer 3)
==========================================
Rule-based anomaly detection on preprocessed flight features.
Migrated from modules/anomaly_model.py.
Structure is ready for ML model integration.
"""

import math
import time
import logging
from computer3_inference.config.settings import ANOMALY_CONFIG, ALERT_THRESHOLDS

logger = logging.getLogger("skyguard.inference")

def haversine(lat1, lon1, lat2, lon2):
    R = 3440.065 # Radius of earth in Nautical Miles
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    return R * c


class AnomalyDetector:
    """Detect anomalous flight behavior from preprocessed features."""

    def __init__(self):
        self.config = ANOMALY_CONFIG

    def detect_conflicts(self, batch):
        conflicts = {}
        for i in range(len(batch)):
            f1 = batch[i]
            if f1.get('on_ground') or not f1.get('latitude') or not f1.get('longitude') or not f1.get('altitude_feet'): continue
            for j in range(i+1, len(batch)):
                f2 = batch[j]
                if f2.get('on_ground') or not f2.get('latitude') or not f2.get('longitude') or not f2.get('altitude_feet'): continue
                
                alt_diff = abs(f1['altitude_feet'] - f2['altitude_feet'])
                if alt_diff < 1000: # 1000 ft vertical separation
                    dist_nm = haversine(f1['latitude'], f1['longitude'], f2['latitude'], f2['longitude'])
                    if dist_nm < 5.0: # 5 NM horizontal separation
                        conflicts.setdefault(f1['icao24'], []).append(f2['callsign'] or f2['icao24'])
                        conflicts.setdefault(f2['icao24'], []).append(f1['callsign'] or f1['icao24'])
        return conflicts

    def analyze(self, features):
        """
        Run anomaly detection on preprocessed flight features.

        Args:
            features: dict with preprocessed fields
                (icao24, altitude_feet, speed_knots, heading,
                 in_restricted_zone, near_airport, squawk, etc.)

        Returns:
            dict with anomaly_score, alert_level, reasons
        """
        score = 0.0
        reasons = []

        # --- Rule 1: Restricted zone entry ---
        if features.get("in_restricted_zone"):
            score += 0.4
            reasons.append(
                f"Entered restricted zone: {features.get('restricted_zone_name')}"
            )

        # --- Rule 2: Suspicious altitude ---
        altitude = features.get("altitude_feet", 0) or 0
        near_airport = features.get("near_airport", False)

        if altitude and not near_airport:
            if altitude < self.config["min_safe_altitude"]:
                score += 0.3
                reasons.append(
                    f"Very low altitude: {int(altitude)} ft (not near airport)"
                )
            elif altitude > self.config["max_normal_altitude"]:
                score += 0.2
                reasons.append(f"Unusually high altitude: {int(altitude)} ft")

        # --- Rule 3: Abnormal speed ---
        speed = features.get("speed_knots", 0) or 0
        on_ground = features.get("on_ground", False)

        if not on_ground and speed:
            if speed < self.config["min_cruise_speed"]:
                score += 0.2
                reasons.append(f"Unusually slow: {int(speed)} knots")
            elif speed > self.config["max_normal_speed"]:
                score += 0.25
                reasons.append(f"Very high speed: {int(speed)} knots")

        # --- Rule 4: Rapid climb / descent & MSAW ---
        climb_rate = features.get("climb_rate_fpm", 0) or 0
        if abs(climb_rate) > self.config["rapid_climb_rate"]:
            score += 0.25
            direction = "climb" if climb_rate > 0 else "descent"
            reasons.append(f"Rapid {direction}: {int(abs(climb_rate))} ft/min")
            
            # MSAW (Minimum Safe Altitude Warning)
            if climb_rate < -1000 and altitude < 5000 and not near_airport and not on_ground:
                score += 0.8
                reasons.append("MSAW: Rapid descent at low altitude")

        # --- Rule 5: Sudden course change ---
        heading_change = features.get("heading_change", 0) or 0
        if heading_change > self.config["erratic_course_change"]:
            score += 0.2
            reasons.append(f"Sudden course change: {int(heading_change)}°")

        # --- Rule 6: Emergency squawk codes ---
        squawk = features.get("squawk")
        if squawk:
            if squawk == "7500":  # hijack
                score += 1.0
                reasons.append("EMERGENCY: Hijack code (7500)")
            elif squawk == "7600":  # radio failure
                score += 0.6
                reasons.append("EMERGENCY: Radio failure (7600)")
            elif squawk == "7700":  # general emergency
                score += 0.8
                reasons.append("EMERGENCY: General emergency (7700)")

        # --- Rule 7: Loss of Communication ---
        last_contact = features.get("last_contact")
        if last_contact:
            # Assuming last_contact is epoch seconds
            age = time.time() - last_contact
            if age > 300: # 5 minutes
                score += 0.4
                reasons.append(f"Loss of Comms: >{int(age/60)} mins")

        # --- Rule 8: STCA (Short Term Conflict Alert) ---
        stca_conflicts = features.get("stca_conflicts")
        if stca_conflicts:
            score += 0.9
            reasons.append(f"STCA: Conflict with {', '.join(stca_conflicts)}")

        # Apply restricted zone multiplier
        if features.get("in_restricted_zone"):
            score *= features.get("zone_risk_multiplier", 1.0)

        # Cap at 1.0
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
            "icao24": features.get("icao24"),
            "callsign": features.get("callsign"),
            "origin_country": features.get("origin_country"),
            "latitude": features.get("latitude"),
            "longitude": features.get("longitude"),
            "altitude": features.get("altitude_feet", 0),
            "speed": features.get("speed_knots", 0),
            "heading": features.get("heading", 0),
            "anomaly_score": round(score, 3),
            "alert_level": alert_level,
            "reasons": reasons,
            "zone_name": features.get("restricted_zone_name", ""),
            "squawk": squawk,
            "last_contact": last_contact,
            "vertical_rate": features.get("vertical_rate"),
            "timestamp": features.get("raw_timestamp"),
        }
