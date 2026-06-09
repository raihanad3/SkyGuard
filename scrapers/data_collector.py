"""
Data Collector — Koneksi WebSocket ke AISstream.io
untuk streaming data AIS kapal secara real-time.
Filter: hanya kapal di wilayah Indonesia.
"""

import asyncio
import json
import logging
import websockets
from datetime import datetime

from core.config import (
    AISSTREAM_API_KEY, AISSTREAM_WS_URL,
    INDONESIA_EEZ_BBOX, get_ship_type_name
)

logger = logging.getLogger("vessel_anomaly")


class DataCollector:
    """
    Real-time AIS data collector via WebSocket.
    Connects to AISstream.io and streams vessel data
    within Indonesian waters.
    """

    def __init__(self, db_manager, anomaly_detector, alert_system,
                 socketio=None):
        self.db = db_manager
        self.detector = anomaly_detector
        self.alert_system = alert_system
        self.socketio = socketio
        self.is_running = False
        self.stats = {
            "messages_received": 0,
            "vessels_tracked": set(),
            "alerts_generated": 0,
            "dark_vessels_detected": 0,  # NEW
            "connection_time": None,
            "last_message_time": None
        }
        self.last_dark_vessel_check = datetime.utcnow()

    async def start_streaming(self):
        """Mulai streaming data AIS dari AISstream.io."""
        self.is_running = True
        logger.info("🚀 Starting AIS data collector...")

        while self.is_running:
            try:
                await self._connect_and_stream()
            except websockets.exceptions.ConnectionClosed as e:
                logger.warning("🔌 WebSocket connection closed: %s", e)
                if self.is_running:
                    logger.info("🔄 Reconnecting in 5 seconds...")
                    await asyncio.sleep(5)
            except Exception as e:
                logger.error("❌ Connection error: %s", e)
                if self.is_running:
                    logger.info("🔄 Reconnecting in 10 seconds...")
                    await asyncio.sleep(10)

    async def _connect_and_stream(self):
        """Establish WebSocket connection and process messages."""
        logger.info("🔗 Connecting to AISstream.io...")

        async with websockets.connect(AISSTREAM_WS_URL) as ws:
            # Subscribe dengan filter bounding box Indonesia
            subscribe_msg = {
                "APIKey": AISSTREAM_API_KEY,
                "BoundingBoxes": INDONESIA_EEZ_BBOX,
                "FilterMessageTypes": [
                    "PositionReport",
                    "ShipStaticData",
                    "StandardClassBCSPositionReport"
                ]
            }

            await ws.send(json.dumps(subscribe_msg))
            self.stats["connection_time"] = datetime.utcnow().isoformat()
            logger.info("✅ Connected! Streaming AIS data for Indonesian waters...")
            logger.info("📍 Bounding Box: %s", INDONESIA_EEZ_BBOX)

            async for raw_message in ws:
                if not self.is_running:
                    break

                try:
                    message = json.loads(raw_message)
                    await self._process_message(message)
                except json.JSONDecodeError:
                    logger.warning("Invalid JSON received")
                except Exception as e:
                    logger.error("Message processing error: %s", e)

    async def _process_message(self, message: dict):
        """Process a single AIS message."""
        msg_type = message.get("MessageType", "")
        meta = message.get("MetaData", {})

        self.stats["messages_received"] += 1
        self.stats["last_message_time"] = datetime.utcnow().isoformat()

        if msg_type == "PositionReport":
            await self._handle_position_report(message, meta)
        elif msg_type == "StandardClassBCSPositionReport":
            await self._handle_position_report(message, meta)
        elif msg_type == "ShipStaticData":
            await self._handle_static_data(message, meta)

        # Log progress setiap 100 pesan
        if self.stats["messages_received"] % 100 == 0:
            logger.info(
                "📊 Stats: %d messages | %d vessels tracked | %d alerts | %d dark vessels",
                self.stats["messages_received"],
                len(self.stats["vessels_tracked"]),
                self.stats["alerts_generated"],
                self.stats["dark_vessels_detected"]
            )

        # 🆕 Periodic Dark Vessel Check (setiap 3 menit untuk lebih responsif)
        now = datetime.utcnow()
        if (now - self.last_dark_vessel_check).total_seconds() > 180:  # 180 detik = 3 menit
            await self._check_for_dark_vessels()
            self.last_dark_vessel_check = now

    async def _handle_position_report(self, message: dict, meta: dict):
        """Process position report message."""
        msg_data = message.get("Message", {})

        # Handle nested structure
        position_report = (
            msg_data.get("PositionReport") or
            msg_data.get("StandardClassBCSPositionReport") or
            {}
        )

        mmsi = str(meta.get("MMSI", ""))
        if not mmsi:
            return

        # Extract data
        vessel_data = {
            "mmsi": mmsi,
            "latitude": meta.get("latitude", 0),
            "longitude": meta.get("longitude", 0),
            "speed": position_report.get("Sog", 0),
            "course": position_report.get("Cog", 0),
            "heading": position_report.get("TrueHeading", 0),
            "timestamp": meta.get("time_utc",
                                  datetime.utcnow().isoformat()),
            "ship_name": meta.get("ShipName", "").strip(),
            "ship_type": meta.get("ShipType"),
            "flag_country": meta.get("country_iso", "UNKNOWN"),
            "destination": None,
            "raw_data": message
        }

        # Track vessel
        self.stats["vessels_tracked"].add(mmsi)

        # Save to database
        self.db.insert_position(vessel_data)

        # Update vessel info
        self.db.upsert_vessel_info({
            "mmsi": mmsi,
            "ship_name": vessel_data["ship_name"],
            "ship_type": vessel_data["ship_type"],
            "ship_type_name": get_ship_type_name(vessel_data["ship_type"]),
            "flag_country": vessel_data["flag_country"],
        })

        # Run anomaly detection
        analysis = self.detector.analyze(vessel_data)

        # Process alert if needed
        self.alert_system.process_alert(analysis)

        if analysis["alert_level"] != "NORMAL":
            self.stats["alerts_generated"] += 1

        # Push vessel position to dashboard
        if self.socketio:
            try:
                self.socketio.emit("vessel_update", {
                    "mmsi": mmsi,
                    "latitude": vessel_data["latitude"],
                    "longitude": vessel_data["longitude"],
                    "speed": vessel_data["speed"],
                    "course": vessel_data["course"],
                    "ship_name": vessel_data["ship_name"],
                    "flag_country": vessel_data["flag_country"],
                    "ship_type": get_ship_type_name(vessel_data["ship_type"]),
                    "alert_level": analysis["alert_level"],
                    "anomaly_score": analysis["anomaly_score"],
                })
            except Exception as e:
                logger.debug("SocketIO emit error: %s", e)

    async def _handle_static_data(self, message: dict, meta: dict):
        """Process ship static data message."""
        msg_data = message.get("Message", {})
        static_data = msg_data.get("ShipStaticData", {})

        mmsi = str(meta.get("MMSI", ""))
        if not mmsi:
            return

        # Extract detailed vessel info
        dimension = static_data.get("Dimension", {})
        vessel_info = {
            "mmsi": mmsi,
            "ship_name": static_data.get("Name", "").strip() or
                         meta.get("ShipName", "").strip(),
            "ship_type": static_data.get("Type", meta.get("ShipType")),
            "ship_type_name": get_ship_type_name(
                static_data.get("Type", meta.get("ShipType"))),
            "flag_country": meta.get("country_iso", "UNKNOWN"),
            "imo": str(static_data.get("ImoNumber", "")) or None,
            "callsign": static_data.get("CallSign", "").strip() or None,
            "length": (dimension.get("A", 0) + dimension.get("B", 0)) or None,
            "width": (dimension.get("C", 0) + dimension.get("D", 0)) or None,
            "draught": static_data.get("MaximumStaticDraught"),
            "destination": static_data.get("Destination", "").strip() or None,
            "eta": None,
        }

        # Parse ETA
        eta_data = static_data.get("Eta", {})
        if eta_data:
            try:
                vessel_info["eta"] = (
                    f"{eta_data.get('Month', 0):02d}-"
                    f"{eta_data.get('Day', 0):02d} "
                    f"{eta_data.get('Hour', 0):02d}:"
                    f"{eta_data.get('Minute', 0):02d}"
                )
            except (ValueError, TypeError):
                pass

        self.db.upsert_vessel_info(vessel_info)

    async def _check_for_dark_vessels(self):
        """
        🆕 DARK VESSEL SCANNER
        Periodik scan untuk detect kapal yang hilang setelah masuk Indonesia.
        """
        try:
            current_timestamp = datetime.utcnow().isoformat()
            
            # Get feature engine from detector
            feature_engine = self.detector.feature_engine
            
            # Check for disappeared vessels
            disappeared = feature_engine.check_for_disappeared_vessels(
                current_timestamp,
                gap_threshold_minutes=10  # 10 menit tidak ada sinyal = hilang (lebih sensitif)
            )
            
            if disappeared:
                logger.warning(
                    "🚨 DARK VESSEL ALERT: %d kapal hilang setelah masuk Indonesia!",
                    len(disappeared)
                )
                
                for vessel in disappeared:
                    self.stats["dark_vessels_detected"] += 1
                    
                    # Create high priority alert
                    alert_data = {
                        "mmsi": vessel["mmsi"],
                        "anomaly_score": 0.95,  # Very high score
                        "alert_level": vessel["threat_level"],
                        "reasons": [vessel["reason"]],
                        "features": {
                            "dark_vessel_score": 0.9,
                            "is_quick_disappearance": vessel["is_quick_disappearance"],
                            "time_since_entry_minutes": vessel["time_since_entry_minutes"],
                            "gap_minutes": vessel["gap_minutes"]
                        },
                        "flag_country": vessel["flag"],
                        "timestamp": current_timestamp,
                        "entry_timestamp": vessel["entry_timestamp"],
                        "last_seen": vessel["last_seen"]
                    }
                    
                    # Process alert
                    self.alert_system.process_alert(alert_data)
                    
                    # Push to dashboard
                    if self.socketio:
                        try:
                            self.socketio.emit("dark_vessel_alert", {
                                "mmsi": vessel["mmsi"],
                                "flag": vessel["flag"],
                                "threat_level": vessel["threat_level"],
                                "reason": vessel["reason"],
                                "entry_time": vessel["entry_timestamp"],
                                "last_seen": vessel["last_seen"],
                                "gap_minutes": vessel["gap_minutes"],
                                "is_quick_disappearance": vessel["is_quick_disappearance"]
                            })
                        except Exception as e:
                            logger.debug("SocketIO emit error: %s", e)
                    
                    logger.warning(
                        "  🎯 MMSI: %s | Flag: %s | Gap: %.0f min | Threat: %s",
                        vessel["mmsi"], vessel["flag"], 
                        vessel["gap_minutes"], vessel["threat_level"]
                    )
                    
        except Exception as e:
            logger.error("Error in dark vessel check: %s", e)

    def stop(self):
        """Stop streaming."""
        self.is_running = False
        logger.info("🛑 Data collector stopping...")

    def get_stats(self) -> dict:
        """Get collector statistics."""
        return {
            "messages_received": self.stats["messages_received"],
            "vessels_tracked": len(self.stats["vessels_tracked"]),
            "alerts_generated": self.stats["alerts_generated"],
            "dark_vessels_detected": self.stats["dark_vessels_detected"],  # NEW
            "connection_time": self.stats["connection_time"],
            "last_message_time": self.stats["last_message_time"]
        }
