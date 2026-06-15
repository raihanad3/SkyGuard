"""
SkyGuard — Alert System (Computer 3)
======================================
Processes anomaly detection results, applies cooldown logic,
logs alerts, and stores them in PostgreSQL.
Migrated from modules/alert_system.py.
"""

import json
import logging
import os
from datetime import datetime, timedelta

from shared.config.settings import ALERT_COOLDOWN_MINUTES, LOG_DIR, ALERT_LOG_FILE

logger = logging.getLogger("skyguard.inference")


class AlertSystem:
    """Process and manage flight anomaly alerts."""

    def __init__(self):
        self.recent_alerts = {}

        # Setup dedicated alert file logger
        os.makedirs(LOG_DIR, exist_ok=True)
        self.alert_logger = logging.getLogger("skyguard.alerts")
        if not self.alert_logger.handlers:
            handler = logging.FileHandler(ALERT_LOG_FILE, encoding="utf-8")
            handler.setFormatter(logging.Formatter(
                "%(asctime)s [%(levelname)s] %(message)s"
            ))
            self.alert_logger.addHandler(handler)
            self.alert_logger.setLevel(logging.INFO)

    def process(self, analysis):
        """
        Process a single anomaly analysis result.

        Args:
            analysis: dict from AnomalyDetector.analyze()

        Returns:
            dict (alert_data) if alert was generated, None otherwise
        """
        alert_level = analysis["alert_level"]

        # Skip normal flights
        if alert_level == "NORMAL":
            return None

        icao24 = analysis["icao24"]

        # Check cooldown
        if self._is_in_cooldown(icao24, alert_level):
            return None

        # Log to console and file
        self._log_alert(analysis)

        # Build alert record
        alert_data = {
            "icao24": icao24,
            "callsign": analysis["callsign"],
            "alert_level": alert_level,
            "anomaly_score": analysis["anomaly_score"],
            "latitude": analysis["latitude"],
            "longitude": analysis["longitude"],
            "altitude": analysis["altitude"],
            "speed": analysis["speed"],
            "heading": analysis["heading"],
            "reasons": analysis["reasons"],
            "zone_name": analysis.get("zone_name", ""),
            "near_airport": analysis.get("near_airport", False),
            "airport_code": analysis.get("airport_code"),
            "airport_name": analysis.get("airport_name"),
            "created_at": datetime.utcnow().isoformat(),
        }

        # Update cooldown
        self._update_cooldown(icao24, alert_level)

        return alert_data

    def _is_in_cooldown(self, icao24, alert_level):
        """Check if this flight/level is still in cooldown."""
        key = f"{icao24}_{alert_level}"
        if key in self.recent_alerts:
            elapsed = (datetime.utcnow() - self.recent_alerts[key]).total_seconds() / 60
            if elapsed < ALERT_COOLDOWN_MINUTES:
                return True
        return False

    def _update_cooldown(self, icao24, alert_level):
        """Update cooldown timestamp and cleanup old entries."""
        key = f"{icao24}_{alert_level}"
        self.recent_alerts[key] = datetime.utcnow()

        # Cleanup entries older than 1 hour
        cutoff = datetime.utcnow() - timedelta(hours=1)
        self.recent_alerts = {
            k: v for k, v in self.recent_alerts.items() if v > cutoff
        }

    def _log_alert(self, analysis):
        """Log alert to console and file."""
        level = analysis["alert_level"]
        icao24 = analysis["icao24"]
        callsign = analysis["callsign"]
        score = analysis["anomaly_score"]
        reasons = ", ".join(analysis["reasons"])

        emoji = "🔴" if level == "HIGH" else "🟡" if level == "MEDIUM" else "🔵"
        msg = f"{emoji} {level} ALERT: {callsign} ({icao24}) | Score: {score:.0%} | {reasons}"

        if level == "HIGH":
            self.alert_logger.critical(msg)
            logger.critical(msg)
        elif level == "MEDIUM":
            self.alert_logger.warning(msg)
            logger.warning(msg)
        else:
            self.alert_logger.info(msg)
            logger.info(msg)
