# opensky collector - fetch real flight data
import asyncio
import aiohttp
import logging
from datetime import datetime
from core.config import (
    OPENSKY_API_URL,
    OPENSKY_UPDATE_INTERVAL,
    INDONESIA_AIRSPACE_BBOX
)

logger = logging.getLogger("skyguard")


class OpenSkyCollector:
    def __init__(self, database, anomaly_detector, alert_system, socketio=None):
        self.db = database
        self.detector = anomaly_detector
        self.alert_system = alert_system
        self.socketio = socketio
        
        self.running = False
        self.session = None
    
    async def start_streaming(self):
        # mulai streaming dari opensky
        self.running = True
        
        logger.info("🚀 Starting OpenSky Network collector...")
        logger.info(f"📡 Update interval: {OPENSKY_UPDATE_INTERVAL} seconds")
        logger.info(f"📍 Monitoring Indonesian airspace:")
        logger.info(f"   Lat: {INDONESIA_AIRSPACE_BBOX['lat_min']} to {INDONESIA_AIRSPACE_BBOX['lat_max']}")
        logger.info(f"   Lon: {INDONESIA_AIRSPACE_BBOX['lon_min']} to {INDONESIA_AIRSPACE_BBOX['lon_max']}")
        logger.info("")
        
        self.session = aiohttp.ClientSession()
        
        fetch_count = 0
        
        try:
            while self.running:
                try:
                    # fetch flights
                    flights = await self._fetch_flights()
                    
                    fetch_count += 1
                    
                    if flights:
                        logger.info(f"✈️  Received {len(flights)} flights (fetch #{fetch_count})")
                        
                        # process tiap flight
                        for flight_data in flights:
                            # save ke db
                            self.db.insert_flight_position(flight_data)
                            self.db.upsert_flight_info({
                                "icao24": flight_data["icao24"],
                                "callsign": flight_data.get("callsign"),
                                "origin_country": flight_data.get("origin_country")
                            })
                            
                            # anomaly detection
                            analysis = self.detector.analyze(flight_data)
                            
                            # process alert
                            self.alert_system.process_alert(analysis)
                            
                            # push ke dashboard
                            if self.socketio:
                                try:
                                    self.socketio.emit("flight_update", {
                                        "icao24": flight_data["icao24"],
                                        "callsign": flight_data.get("callsign", "N/A"),
                                        "latitude": flight_data["latitude"],
                                        "longitude": flight_data["longitude"],
                                        "altitude": flight_data.get("baro_altitude", 0),
                                        "speed": flight_data.get("velocity", 0),
                                        "heading": flight_data.get("true_track", 0),
                                        "origin_country": flight_data.get("origin_country", "Unknown"),
                                        "alert_level": analysis["alert_level"],
                                        "anomaly_score": analysis["anomaly_score"]
                                    })
                                except Exception as e:
                                    logger.debug(f"SocketIO emit error: {e}")
                    else:
                        logger.warning(f"⚠️  No flights in Indonesian airspace (fetch #{fetch_count})")
                    
                    # tunggu next update
                    await asyncio.sleep(OPENSKY_UPDATE_INTERVAL)
                
                except Exception as e:
                    logger.error(f"❌ Fetch error: {type(e).__name__}: {e}")
                    await asyncio.sleep(30)
        
        finally:
            if self.session:
                await self.session.close()
    
    async def _fetch_flights(self):
        """Fetch flights from OpenSky API in Indonesian airspace."""
        bbox = INDONESIA_AIRSPACE_BBOX
        
        # OpenSky API parameters
        params = {
            "lamin": bbox["lat_min"],
            "lamax": bbox["lat_max"],
            "lomin": bbox["lon_min"],
            "lomax": bbox["lon_max"]
        }
        
        try:
            async with self.session.get(OPENSKY_API_URL, params=params, timeout=30) as response:
                if response.status != 200:
                    logger.warning(f"OpenSky API returned status {response.status}")
                    return []
                
                data = await response.json()
                
                # Parse OpenSky response
                # Format: {"time": timestamp, "states": [[icao24, callsign, ...], ...]}
                if not data or "states" not in data or not data["states"]:
                    return []
                
                flights = []
                
                for state in data["states"]:
                    try:
                        # OpenSky state vector format:
                        # 0: icao24, 1: callsign, 2: origin_country, 3: time_position,
                        # 4: last_contact, 5: longitude, 6: latitude, 7: baro_altitude,
                        # 8: on_ground, 9: velocity, 10: true_track, 11: vertical_rate,
                        # 12: sensors, 13: geo_altitude, 14: squawk, 15: spi, 16: position_source
                        
                        if state[5] is None or state[6] is None:
                            continue  # No position data
                        
                        flight = {
                            "icao24": state[0],
                            "callsign": (state[1] or "").strip(),
                            "origin_country": state[2],
                            "time_position": state[3],
                            "last_contact": state[4],
                            "longitude": state[5],
                            "latitude": state[6],
                            "baro_altitude": state[7],
                            "on_ground": state[8],
                            "velocity": state[9],
                            "true_track": state[10],
                            "vertical_rate": state[11],
                            "sensors": str(state[12]) if state[12] else None,
                            "geo_altitude": state[13],
                            "squawk": state[14],
                            "spi": state[15],
                            "position_source": state[16],
                            "timestamp": datetime.utcnow().isoformat()
                        }
                        
                        flights.append(flight)
                    
                    except (IndexError, TypeError) as e:
                        logger.debug(f"Parse error for state: {e}")
                        continue
                
                return flights
        
        except asyncio.TimeoutError:
            logger.warning("⏱️  OpenSky API timeout")
        except aiohttp.ClientError as e:
            logger.warning(f"🔌 Connection error: {e}")
        except Exception as e:
            logger.error(f"❌ Unexpected error: {type(e).__name__}: {e}")
        
        return []
    
    def stop(self):
        """Stop collector."""
        logger.info("🛑 Stopping OpenSky collector...")
        self.running = False
