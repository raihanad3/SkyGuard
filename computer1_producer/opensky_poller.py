"""
SkyGuard — OpenSky Network Poller
===================================
Polls the OpenSky Network REST API every N seconds for flights
within the Asian airspace bounding box, then produces
each flight record to Kafka.

Migrated from scrapers/opensky_collector.py — polling-only,
no processing or storage.
"""

import asyncio
import aiohttp
import logging
import os
import threading
from datetime import datetime

from shared.config.settings import OPENSKY_API_URL, OPENSKY_UPDATE_INTERVAL, KAFKA_TOPIC_RAW_FLIGHT
from shared.config.airspace import ASIA_AIRSPACE_BBOX

logger = logging.getLogger("skyguard.producer")


class OpenSkyPoller:
    """Fetch flight states from OpenSky Network API."""

    def __init__(self, kafka_producer):
        self.kafka_producer = kafka_producer
        self.running = False
        self.api = None

    async def start(self):
        """Start the polling loop."""
        self.running = True
        
        logger.info("🚀 OpenSky poller started")
        logger.warning("🔓 Unauthenticated OpenSky polling. Subject to strict rate limits.")
            
        logger.info("📡 Interval: %ds | Bbox: lat[%.1f, %.1f] lon[%.1f, %.1f]",
                     OPENSKY_UPDATE_INTERVAL,
                     ASIA_AIRSPACE_BBOX["lat_min"],
                     ASIA_AIRSPACE_BBOX["lat_max"],
                     ASIA_AIRSPACE_BBOX["lon_min"],
                     ASIA_AIRSPACE_BBOX["lon_max"])

        fetch_count = 0

        try:
            while self.running:
                try:
                    flights = await self._fetch_flights()
                    fetch_count += 1

                    if flights:
                        logger.info("✈️  Fetch #%d — %d flights in Asian airspace",
                                    fetch_count, len(flights))

                        # Produce each flight to Kafka
                        messages = [
                            (flight["icao24"], flight)
                            for flight in flights
                        ]
                        self.kafka_producer.send_batch(
                            KAFKA_TOPIC_RAW_FLIGHT, messages
                        )
                    else:
                        logger.warning("⚠️  Fetch #%d — No flights detected or rate limited (429)", fetch_count)

                    await asyncio.sleep(OPENSKY_UPDATE_INTERVAL)

                except Exception as e:
                    logger.error("❌ Polling error: %s: %s", type(e).__name__, e)
                    await asyncio.sleep(30)
        finally:
            self.running = False

    async def _fetch_flights(self):
        """Fetch flights from OpenSky API within Asian airspace using direct REST API."""
        bbox = ASIA_AIRSPACE_BBOX

        try:
            # Build OpenSky API URL with bbox parameters
            url = f"{OPENSKY_API_URL}?lamin={bbox['lat_min']}&lamax={bbox['lat_max']}&lomin={bbox['lon_min']}&lomax={bbox['lon_max']}"
            
            import socket
            connector = aiohttp.TCPConnector(family=socket.AF_INET)
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    if response.status != 200:
                        logger.warning("OpenSky API returned status %d", response.status)
                        return []
                    
                    data = await response.json()
                    
                    if not data or "states" not in data or not data["states"]:
                        return []
                    
                    # Parse OpenSky states
                    opensky_flights = []
                    for state in data["states"]:
                        # OpenSky state vector format:
                        # [0]=icao24, [1]=callsign, [2]=origin_country, [3]=time_position, [4]=last_contact,
                        # [5]=longitude, [6]=latitude, [7]=baro_altitude, [8]=on_ground, [9]=velocity,
                        # [10]=true_track, [11]=vertical_rate, [12]=sensors, [13]=geo_altitude, 
                        # [14]=squawk, [15]=spi, [16]=position_source
                        if state[5] is None or state[6] is None:  # longitude, latitude
                            continue
                        opensky_flights.append(state)
                    
                    if not opensky_flights:
                        return []
                    
                    # --- Airplanes.live Enrichment ---
                    hex_codes = [state[0].lower() for state in opensky_flights[:1000] if state[0]]
                    enrichment_map = {}
                    
                    try:
                        # Batch hex codes into chunks of 50
                        chunk_size = 50
                        for i in range(0, len(hex_codes), chunk_size):
                            chunk = hex_codes[i:i + chunk_size]
                            hex_str = ",".join(chunk)
                            
                            async with session.get(
                                f"https://api.airplanes.live/v2/hex/{hex_str}",
                                timeout=aiohttp.ClientTimeout(total=10)
                            ) as al_response:
                                if al_response.status == 200:
                                    al_data = await al_response.json()
                                    if "ac" in al_data:
                                        for ac in al_data["ac"]:
                                            hex_key = ac.get("hex", "").lower()
                                            if hex_key:
                                                enrichment_map[hex_key] = ac
                    except Exception as e:
                        logger.warning("Airplanes.live enrichment failed: %s", type(e).__name__)
                    
                    # --- Merge Data ---
                    flights = []
                    for state in opensky_flights:
                        try:
                            icao24 = state[0].lower() if state[0] else ""
                            al_info = enrichment_map.get(icao24, {})
                            
                            # Prefer Airplanes.live callsign if available
                            callsign = al_info.get("flight", "").strip()
                            if not callsign:
                                callsign = state[1].strip() if state[1] else ""
                            
                            # Prefer Airplanes.live squawk
                            squawk = al_info.get("squawk", "")
                            if not squawk:
                                squawk = state[14] if len(state) > 14 else ""
                            
                            flights.append({
                                "icao24": icao24,
                                "callsign": callsign,
                                "origin_country": state[2] if state[2] else "",
                                "time_position": state[3],
                                "last_contact": state[4],
                                "longitude": state[5],
                                "latitude": state[6],
                                "baro_altitude": state[7],
                                "on_ground": state[8] if state[8] is not None else False,
                                "velocity": state[9],
                                "true_track": state[10],
                                "vertical_rate": state[11],
                                "sensors": ",".join(map(str, state[12])) if len(state) > 12 and state[12] else "",
                                "geo_altitude": state[13] if len(state) > 13 else None,
                                "squawk": squawk,
                                "spi": state[15] if len(state) > 15 else False,
                                "position_source": state[16] if len(state) > 16 else 0,
                                "registration": al_info.get("r", ""),
                                "aircraft_type": al_info.get("t", ""),
                                "aircraft_desc": al_info.get("desc", ""),
                                "timestamp": datetime.utcnow().isoformat(),
                            })
                        except (IndexError, TypeError) as e:
                            logger.debug("Parse error: %s", e)
                            continue
                    
                    return flights

        except asyncio.TimeoutError:
            logger.warning("⏱️  OpenSky API timeout")
        except aiohttp.ClientError as e:
            logger.warning("🔌 Connection error: %s", e)
        except Exception as e:
            logger.error("❌ Unexpected: %s: %s", type(e).__name__, e)

        return []

    def stop(self):
        """Stop the polling loop."""
        logger.info("🛑 Stopping OpenSky poller...")
        self.running = False
