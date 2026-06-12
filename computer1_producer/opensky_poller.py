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
        self.session = aiohttp.ClientSession()

        logger.info("🚀 OpenSky poller started")
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
                        logger.warning("⚠️  Fetch #%d — No flights detected", fetch_count)

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
                for state in data["states"]:
                    try:
                        # Skip records without position
                        if state[5] is None or state[6] is None:
                            continue

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
                            "timestamp": datetime.utcnow().isoformat(),
                        }
                        flights.append(flight)

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
