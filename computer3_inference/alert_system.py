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
import redis
from datetime import datetime, timedelta

from shared.config.settings import (
    ALERT_COOLDOWN_MINUTES, LOG_DIR, ALERT_LOG_FILE,
    REDIS_HOST, REDIS_PORT
)

logger = logging.getLogger("skyguard.inference")


class AlertSystem:
    """Process and manage flight anomaly alerts using Redis/Local Memory."""

    def __init__(self):
        self.recent_alerts = {}

        # Setup Redis Client
        try:
            self.redis_client = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                db=0,
                decode_responses=True,
                socket_timeout=2.0
            )
            self.redis_client.ping()
            logger.info(f"✅ Redis connected successfully at {REDIS_HOST}:{REDIS_PORT}")
        except Exception as e:
            logger.warning(f"⚠️ Redis connection failed: {e}. Falling back to in-memory cooldown.")
            self.redis_client = None

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
        icao24 = analysis["icao24"]

        # Cache latest vessel position state in Redis for fast dashboard/caching retrieval
        if self.redis_client and icao24:
            try:
                state_key = f"vessel:{icao24}:state"
                state_data = {
                    "icao24": icao24,
                    "callsign": analysis.get("callsign"),
                    "latitude": analysis.get("latitude"),
                    "longitude": analysis.get("longitude"),
                    "altitude": analysis.get("altitude"),
                    "speed": analysis.get("speed"),
                    "heading": analysis.get("heading"),
                    "anomaly_score": analysis.get("anomaly_score"),
                    "alert_level": alert_level,
                    "reasons": analysis.get("reasons", []),
                    "timestamp": datetime.utcnow().isoformat()
                }
                self.redis_client.setex(state_key, 1800, json.dumps(state_data))  # Expire in 30 minutes
            except Exception as e:
                logger.debug(f"Redis error writing vessel state: {e}")

        # Skip normal flights for DB alerting
        if alert_level == "NORMAL":
            return None

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
        """Check if this flight/level is still in cooldown using Redis or memory fallback."""
        if not icao24:
            return False
        key = f"cooldown:{icao24}:{alert_level}"
        if self.redis_client:
            try:
                return self.redis_client.exists(key) > 0
            except Exception as e:
                logger.error(f"Redis error in _is_in_cooldown: {e}")
        
        # Local memory fallback
        mem_key = f"{icao24}_{alert_level}"
        if mem_key in self.recent_alerts:
            elapsed = (datetime.utcnow() - self.recent_alerts[mem_key]).total_seconds() / 60
            if elapsed < ALERT_COOLDOWN_MINUTES:
                return True
        return False

    def _update_cooldown(self, icao24, alert_level):
        """Update cooldown timestamp in Redis or memory fallback."""
        if not icao24:
            return
        key = f"cooldown:{icao24}:{alert_level}"
        cooldown_seconds = int(ALERT_COOLDOWN_MINUTES * 60)
        
        if self.redis_client:
            try:
                self.redis_client.setex(key, cooldown_seconds, "1")
                return
            except Exception as e:
                logger.error(f"Redis error in _update_cooldown: {e}")
                
        # Local memory fallback
        mem_key = f"{icao24}_{alert_level}"
        self.recent_alerts[mem_key] = datetime.utcnow()

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
