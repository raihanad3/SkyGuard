"""
SkyGuard — Anomaly Detector (Computer 3)
==========================================
Rule-based anomaly detection on preprocessed flight features.
Migrated from modules/anomaly_model.py.
Structure is ready for ML model integration.
"""

import logging
from computer3_inference.config.settings import ANOMALY_CONFIG, ALERT_THRESHOLDS

logger = logging.getLogger("skyguard.inference")


class AnomalyDetector:
    """Detect anomalous flight behavior from preprocessed features."""

    def __init__(self):
        self.config = ANOMALY_CONFIG

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

        # --- Rule 4: Rapid climb / descent ---
        climb_rate = features.get("climb_rate_fpm", 0) or 0
        if abs(climb_rate) > self.config["rapid_climb_rate"]:
            score += 0.25
            direction = "climb" if climb_rate > 0 else "descent"
            reasons.append(
                f"Rapid {direction}: {int(abs(climb_rate))} ft/min"
            )

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
            "timestamp": features.get("raw_timestamp"),
        }
