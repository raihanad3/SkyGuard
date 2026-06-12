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
from datetime import datetime

from computer1_producer.config.settings import OPENSKY_API_URL, OPENSKY_UPDATE_INTERVAL, KAFKA_TOPIC_RAW_FLIGHT
from computer1_producer.config.airspace import ASIA_AIRSPACE_BBOX

logger = logging.getLogger("skyguard.producer")


class OpenSkyPoller:
    """Fetch flight states from OpenSky Network API."""

    def __init__(self, kafka_producer):
        self.kafka_producer = kafka_producer
        self.running = False
        self.session = None

    async def start(self):
        """Start the polling loop."""
        self.running = True
        
        # Check for OpenSky authentication
        username = os.getenv("OPENSKY_USERNAME", "").strip()
        password = os.getenv("OPENSKY_PASSWORD", "").strip()
        auth = aiohttp.BasicAuth(username, password) if username and password else None
        
        self.session = aiohttp.ClientSession(auth=auth)

        logger.info("🚀 OpenSky poller started")
        if auth:
            logger.info("🔒 Authenticated with OpenSky as '%s'", username)
        else:
            logger.warning("🔓 Unauthenticated OpenSky polling. Subject to strict rate limits (400 req/day).")
            
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
            if self.session:
                await self.session.close()

    async def _fetch_flights(self):
        """Fetch flights from OpenSky API within Asian airspace."""
        bbox = ASIA_AIRSPACE_BBOX
        params = {
            "lamin": bbox["lat_min"],
            "lamax": bbox["lat_max"],
            "lomin": bbox["lon_min"],
            "lomax": bbox["lon_max"],
        }

        try:
            async with self.session.get(
                OPENSKY_API_URL, params=params, timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status != 200:
                    logger.warning("OpenSky API status %d", response.status)
                    return []

                data = await response.json()

                if not data or "states" not in data or not data["states"]:
                    return []

                flights = []
                for s in data["states"]:
                    try:
                        # Skip records without position
                        if s[5] is None or s[6] is None:
                            continue

                        flights.append({
                            "icao24": s[0],
                            "callsign": s[1].strip() if s[1] else "",
                            "origin_country": s[2],
                            "time_position": s[3],
                            "last_contact": s[4],
                            "longitude": s[5],
                            "latitude": s[6],
                            "baro_altitude": s[7],
                            "on_ground": s[8],
                            "velocity": s[9],
                            "true_track": s[10],
                            "vertical_rate": s[11],
                            "sensors": ",".join(map(str, s[12])) if s[12] else "",
                            "geo_altitude": s[13],
                            "squawk": s[14],
                            "spi": s[15],
                            "position_source": s[16],
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
