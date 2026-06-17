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
        from opensky_api import OpenSkyApi, TokenManager

        self.running = True
        
        # Check for OpenSky authentication using credentials.json
        cred_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "credentials.json")
        tm = None
        if os.path.exists(cred_path):
            try:
                tm = TokenManager.from_json_file(cred_path)
            except Exception as e:
                logger.error("Failed to load OpenSky TokenManager from %s: %s", cred_path, e)
        else:
            logger.warning("No credentials.json found at %s. Unauthenticated access.", cred_path)
            
        self.api = OpenSkyApi(token_manager=tm) if tm else OpenSkyApi()

        logger.info("🚀 OpenSky poller started")
        if tm:
            logger.info("🔒 Authenticated with OpenSky TokenManager")
        else:
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
        """Fetch flights from OpenSky API within Asian airspace."""
        bbox = ASIA_AIRSPACE_BBOX

        try:
            # Run the synchronous API call in a thread
            loop = asyncio.get_running_loop()
            def fetch_states():
                # bbox tuple format: (minLatitude, maxLatitude, minLongitude, maxLongitude)
                return self.api.get_states(bbox=(bbox["lat_min"], bbox["lat_max"], bbox["lon_min"], bbox["lon_max"]))

            opensky_data = await loop.run_in_executor(None, fetch_states)

            if opensky_data is None:
                logger.error("DEBUG: opensky_data is None. The API rate limiter or HTTP request blocked it.")
                return []
            if not opensky_data.states:
                logger.warning("DEBUG: opensky_data.states is empty.")
                return []

            # Extract all valid flights with positions
            opensky_flights = []
            for s in opensky_data.states:
                if s.longitude is None or s.latitude is None:
                    continue
                opensky_flights.append(s)

            if not opensky_flights:
                return []

            # --- Airplanes.live Enrichment ---
            hex_codes = [s.icao24.lower() for s in opensky_flights[:1000] if s.icao24]
            enrichment_map = {}

            # Fetch al_response asynchronously (using IPv4 to avoid Tailscale timeout issues)
            import socket
            connector = aiohttp.TCPConnector(family=socket.AF_INET)
            async with aiohttp.ClientSession(connector=connector) as session:
                try:
                    # Batch hex codes into chunks of 50 to prevent URI Too Long (414)
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
            for s in opensky_flights:
                try:
                    icao24 = s.icao24.lower()
                    al_info = enrichment_map.get(icao24, {})
                    
                    # Prefer Airplanes.live callsign if available, else OpenSky
                    callsign = al_info.get("flight", "").strip()
                    if not callsign:
                        callsign = s.callsign.strip() if s.callsign else ""
                        
                    # Prefer Airplanes.live squawk
                    squawk = al_info.get("squawk", "")
                    if not squawk:
                        squawk = s.squawk

                    flights.append({
                        "icao24": icao24,
                        "callsign": callsign,
                        "origin_country": s.origin_country,
                        "time_position": s.time_position,
                        "last_contact": s.last_contact,
                        "longitude": s.longitude,
                        "latitude": s.latitude,
                        "baro_altitude": s.baro_altitude,
                        "on_ground": s.on_ground,
                        "velocity": s.velocity,
                        "true_track": s.true_track,
                        "vertical_rate": s.vertical_rate,
                        "sensors": ",".join(map(str, s.sensors)) if s.sensors else "",
                        "geo_altitude": s.geo_altitude,
                        "squawk": squawk,
                        "spi": s.spi,
                        "position_source": s.position_source,
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
