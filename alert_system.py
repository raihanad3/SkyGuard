"""
Alert System — Mengelola notifikasi alert untuk kapal anomali.
Console alerts, file logging, dan sound notification.
"""

import os
import logging
import json
from datetime import datetime
from colorama import Fore, Back, Style, init as colorama_init

from config import (
    LOG_DIR, LOG_FILE, ALERT_COOLDOWN_MINUTES,
    get_flag_emoji
)

# Initialize colorama for Windows
colorama_init(autoreset=True)

logger = logging.getLogger("vessel_anomaly")


class AlertSystem:
    """Sistem alert multi-channel untuk deteksi kapal anomali."""

    def __init__(self, db_manager, socketio=None):
        self.db = db_manager
        self.socketio = socketio  # Flask-SocketIO untuk push ke dashboard
        self._setup_logging()

    def _setup_logging(self):
        """Setup file logging untuk alerts."""
        os.makedirs(LOG_DIR, exist_ok=True)

        self.alert_logger = logging.getLogger("vessel_alerts")
        self.alert_logger.setLevel(logging.INFO)

        # Hindari duplicate handlers
        if not self.alert_logger.handlers:
            file_handler = logging.FileHandler(
                LOG_FILE, encoding="utf-8")
            file_handler.setLevel(logging.INFO)
            file_handler.setFormatter(logging.Formatter(
                "%(asctime)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            ))
            self.alert_logger.addHandler(file_handler)

    def process_alert(self, analysis_result: dict):
        """
        Memproses hasil analisis dan mengirim alert jika perlu.
        """
        alert_level = analysis_result.get("alert_level", "NORMAL")

        if alert_level == "NORMAL":
            return  # Tidak perlu alert

        mmsi = analysis_result.get("mmsi", "")

        # Cek cooldown (deduplication)
        if self.db.check_recent_alert(mmsi, ALERT_COOLDOWN_MINUTES):
            return  # Alert baru-baru ini sudah dikirim

        # Simpan ke database
        self.db.insert_alert({
            "mmsi": mmsi,
            "alert_level": alert_level,
            "anomaly_score": analysis_result.get("anomaly_score", 0),
            "latitude": analysis_result.get("latitude"),
            "longitude": analysis_result.get("longitude"),
            "speed": analysis_result.get("speed"),
            "ship_name": analysis_result.get("ship_name"),
            "flag_country": analysis_result.get("flag_country"),
            "reasons": analysis_result.get("reasons", []),
            "zone_name": analysis_result.get("zone_name"),
        })

        # Console alert
        self._console_alert(analysis_result)

        # File log
        self._log_alert(analysis_result)

        # Dashboard push (via SocketIO)
        self._push_to_dashboard(analysis_result)

        # Sound alert (untuk HIGH)
        if alert_level == "HIGH":
            self._sound_alert()

    def _console_alert(self, result: dict):
        """Print alert ke console dengan warna."""
        level = result.get("alert_level", "")
        score = result.get("anomaly_score", 0)
        mmsi = result.get("mmsi", "Unknown")
        ship_name = result.get("ship_name", "UNKNOWN VESSEL")
        flag = result.get("flag_country", "UNKNOWN")
        flag_emoji = get_flag_emoji(flag)
        lat = result.get("latitude", 0)
        lon = result.get("longitude", 0)
        speed = result.get("speed", 0)
        zone = result.get("zone_name", "Unknown")
        reasons = result.get("reasons", [])
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Color coding
        if level == "HIGH":
            color = Fore.RED + Style.BRIGHT
            icon = "🚨"
            bg = Back.RED + Fore.WHITE
        elif level == "MEDIUM":
            color = Fore.YELLOW + Style.BRIGHT
            icon = "⚠️"
            bg = Back.YELLOW + Fore.BLACK
        else:
            color = Fore.CYAN
            icon = "ℹ️"
            bg = Back.CYAN + Fore.BLACK

        print()
        print(f"{bg}{'=' * 60}{Style.RESET_ALL}")
        print(f"{color}{icon} [{level} ALERT] {now}{Style.RESET_ALL}")
        print(f"{bg}{'=' * 60}{Style.RESET_ALL}")
        print(f"  {Fore.WHITE}Vessel : {Style.BRIGHT}"
              f"{ship_name} (MMSI: {mmsi}){Style.RESET_ALL}")
        print(f"  {Fore.WHITE}Flag   : {flag_emoji} {flag}{Style.RESET_ALL}")
        print(f"  {Fore.WHITE}Position: {lat:.4f}, {lon:.4f} "
              f"({zone}){Style.RESET_ALL}")
        print(f"  {Fore.WHITE}Speed  : {speed:.1f} knots{Style.RESET_ALL}")
        print(f"  {color}Score  : {score:.3f}{Style.RESET_ALL}")

        if reasons:
            print(f"  {Fore.WHITE}Reasons:{Style.RESET_ALL}")
            for r in reasons:
                print(f"    {color}• {r}{Style.RESET_ALL}")

        print(f"{bg}{'=' * 60}{Style.RESET_ALL}")
        print()

    def _log_alert(self, result: dict):
        """Tulis alert ke file log."""
        level = result.get("alert_level", "")
        mmsi = result.get("mmsi", "Unknown")
        ship_name = result.get("ship_name", "UNKNOWN")
        flag = result.get("flag_country", "UNKNOWN")
        lat = result.get("latitude", 0)
        lon = result.get("longitude", 0)
        score = result.get("anomaly_score", 0)
        reasons = result.get("reasons", [])
        zone = result.get("zone_name", "Unknown")

        log_entry = (
            f"[{level}] MMSI={mmsi} | {ship_name} | Flag={flag} | "
            f"Pos=({lat:.4f},{lon:.4f}) | Zone={zone} | "
            f"Score={score:.3f} | "
            f"Reasons: {'; '.join(reasons)}"
        )
        self.alert_logger.info(log_entry)

    def _push_to_dashboard(self, result: dict):
        """Push alert ke web dashboard via SocketIO."""
        if self.socketio:
            try:
                self.socketio.emit("new_alert", {
                    "mmsi": result.get("mmsi"),
                    "alert_level": result.get("alert_level"),
                    "anomaly_score": result.get("anomaly_score"),
                    "latitude": result.get("latitude"),
                    "longitude": result.get("longitude"),
                    "speed": result.get("speed"),
                    "ship_name": result.get("ship_name"),
                    "flag_country": result.get("flag_country"),
                    "reasons": result.get("reasons", []),
                    "zone_name": result.get("zone_name"),
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
            except Exception as e:
                logger.error("Dashboard push error: %s", e)

    def _sound_alert(self):
        """Sound notification untuk HIGH alert."""
        try:
            # Windows beep
            import winsound
            winsound.Beep(1000, 500)  # 1000 Hz, 500ms
            winsound.Beep(1500, 300)
            winsound.Beep(1000, 500)
        except ImportError:
            # Non-Windows: print bell character
            print("\a\a\a")
        except Exception:
            print("\a")
