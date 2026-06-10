"""
Alert System untuk Flight Monitoring
Process dan dispatch alerts untuk suspicious flights.
"""

import logging
import json
from datetime import datetime, timedelta
from core.config import ALERT_COOLDOWN_MINUTES, ALERT_LOG_FILE

logger = logging.getLogger("skyguard")


class AlertSystem:
    """Manage flight alerts."""
    
    def __init__(self, database, socketio=None):
        self.db = database
        self.socketio = socketio
        self.recent_alerts = {}  # Track recent alerts untuk cooldown
        
        # Setup alert logger
        self.alert_logger = logging.getLogger("alerts")
        handler = logging.FileHandler(ALERT_LOG_FILE, encoding="utf-8")
        handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s"
        ))
        self.alert_logger.addHandler(handler)
        self.alert_logger.setLevel(logging.INFO)
    
    def process_alert(self, analysis):
        """Process analysis result dan create alert jika perlu."""
        alert_level = analysis["alert_level"]
        
        # Only alert for LOW, MEDIUM, HIGH (not NORMAL)
        if alert_level == "NORMAL":
            return
        
        icao24 = analysis["icao24"]
        
        # Check cooldown
        if self._is_in_cooldown(icao24, alert_level):
            return
        
        # Log alert
        self._log_alert(analysis)
        
        # Save to database
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
            "reasons": json.dumps(analysis["reasons"]),
            "zone_name": analysis.get("zone_name", ""),
            "created_at": datetime.utcnow().isoformat()
        }
        
        alert_id = self.db.insert_alert(alert_data)
        
        if alert_id:
            # Update cooldown
            self._update_cooldown(icao24, alert_level)
            
            # Broadcast via SocketIO
            if self.socketio:
                try:
                    self.socketio.emit("new_alert", alert_data)
                except Exception as e:
                    logger.debug(f"SocketIO emit error: {e}")
    
    def _is_in_cooldown(self, icao24, alert_level):
        """Check if flight is in cooldown period."""
        key = f"{icao24}_{alert_level}"
        
        if key in self.recent_alerts:
            last_alert_time = self.recent_alerts[key]
            elapsed = (datetime.utcnow() - last_alert_time).total_seconds() / 60
            
            if elapsed < ALERT_COOLDOWN_MINUTES:
                return True
        
        return False
    
    def _update_cooldown(self, icao24, alert_level):
        """Update cooldown timestamp."""
        key = f"{icao24}_{alert_level}"
        self.recent_alerts[key] = datetime.utcnow()
        
        # Cleanup old entries (older than 1 hour)
        cutoff = datetime.utcnow() - timedelta(hours=1)
        self.recent_alerts = {
            k: v for k, v in self.recent_alerts.items()
            if v > cutoff
        }
    
    def _log_alert(self, analysis):
        """Log alert to file and console."""
        alert_level = analysis["alert_level"]
        icao24 = analysis["icao24"]
        callsign = analysis["callsign"]
        score = analysis["anomaly_score"]
        reasons = ", ".join(analysis["reasons"])
        
        emoji = "🔴" if alert_level == "HIGH" else "🟡" if alert_level == "MEDIUM" else "🔵"
        
        msg = f"{emoji} {alert_level} ALERT: {callsign} ({icao24}) | Score: {score:.0%} | {reasons}"
        
        if alert_level == "HIGH":
            self.alert_logger.critical(msg)
            logger.critical(msg)
        elif alert_level == "MEDIUM":
            self.alert_logger.warning(msg)
            logger.warning(msg)
        else:
            self.alert_logger.info(msg)
            logger.info(msg)
