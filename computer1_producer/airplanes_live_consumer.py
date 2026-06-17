"""
SkyGuard — Airplanes.live Consumer
==================================
Polls airplanes.live API (1s interval).
Filters squawks 7700/7600/7500 and inserts into alerts table.
Enriches callsign via routes.dat and inserts into flight_routes.
"""

import asyncio
import aiohttp
import logging
import psycopg2
import os
import csv
from datetime import datetime

from shared.config.settings import (
    POSTGRES_HOST, POSTGRES_PORT,
    POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB,
    KAFKA_TOPIC_RAW_FLIGHT
)
from shared.config.airspace import ASIA_AIRSPACE_BBOX
from computer1_producer.kafka_producer import SkyGuardProducer

logger = logging.getLogger("skyguard.producer.airplanes_live")

# Cache for callsign routing
ROUTES_DATA = {}
AIRLINES_DATA = {}

def load_openflights_data():
    """Load routes.dat and airlines.dat to enrich callsigns."""
    base_dir = os.path.dirname(os.path.dirname(__file__))
    routes_path = os.path.join(base_dir, "shared", "data", "routes.dat")
    airlines_path = os.path.join(base_dir, "shared", "data", "airlines.dat")
    
    icao_to_airline = {}
    try:
        with open(airlines_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) > 4:
                    iata = row[3]
                    icao = row[4]
                    if icao and len(icao) == 3:
                        icao_to_airline[icao] = iata
    except Exception as e:
        logger.warning(f"Failed to load airlines.dat: {e}")

    try:
        with open(routes_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) > 4:
                    airline = row[0] # Usually IATA or ICAO
                    src = row[2]
                    dst = row[4]
                    
                    if airline not in ROUTES_DATA:
                        ROUTES_DATA[airline] = []
                    ROUTES_DATA[airline].append((src, dst))
        logger.info(f"Loaded {len(ROUTES_DATA)} airlines from routes.dat")
    except Exception as e:
        logger.warning(f"Failed to load routes.dat: {e}")
        
    return icao_to_airline

class AirplanesLiveConsumer:
    def __init__(self):
        self.conn = None
        self.polling = False
        self.icao_to_iata = load_openflights_data()
        self.kafka_producer = SkyGuardProducer()

    def _connect_db(self):
        if self.conn is None or self.conn.closed:
            self.conn = psycopg2.connect(
                host=POSTGRES_HOST,
                port=POSTGRES_PORT,
                user=POSTGRES_USER,
                password=POSTGRES_PASSWORD,
                dbname=POSTGRES_DB,
            )
            self.conn.autocommit = True

    def enrich_callsign(self, callsign):
        """Enrich callsign using routes.dat"""
        if not callsign or len(callsign) < 4:
            return None, None
            
        airline_icao = callsign[:3]
        airline_iata = self.icao_to_iata.get(airline_icao, airline_icao)
        
        # We just pick a known route for that airline as a proxy/example since routes.dat lacks full flight numbers
        routes = ROUTES_DATA.get(airline_iata) or ROUTES_DATA.get(airline_icao)
        if routes:
            return routes[0][0], routes[0][1]
        return None, None

    def insert_alert(self, ac):
        """Insert emergency squawk into alerts table"""
        self._connect_db()
        sql = """
            INSERT INTO alerts (icao24, callsign, alert_level, anomaly_score, latitude, longitude, altitude, speed, heading, reasons)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        squawk = str(ac.get("squawk", ""))
        reasons = f'["Squawk {squawk}"]'
        
        alert_level = "HIGH" if squawk in ["7700", "7500"] else "MEDIUM"
        
        try:
            with self.conn.cursor() as cur:
                cur.execute(sql, (
                    ac.get("hex", "UNKNOWN"),
                    ac.get("flight", "").strip()[:20],
                    alert_level,
                    1.0, # anomaly score max
                    ac.get("lat"),
                    ac.get("lon"),
                    ac.get("alt_baro"),
                    ac.get("gs"),
                    ac.get("track"),
                    reasons
                ))
            logger.warning(f"🚨 SQUAWK {squawk} ALERT for {ac.get('hex')} ({ac.get('flight')})")
        except Exception as e:
            logger.error(f"Error inserting alert: {e}")

    def insert_flight_route(self, callsign, origin, dest, ac):
        """Insert enriched route data into flight_routes"""
        self._connect_db()
        sql = """
            INSERT INTO flight_routes (callsign, origin_airport_icao, destination_airport_icao, registration, aircraft_type)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (callsign) DO UPDATE SET
                origin_airport_icao = EXCLUDED.origin_airport_icao,
                destination_airport_icao = EXCLUDED.destination_airport_icao,
                updated_at = NOW()
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute(sql, (
                    callsign[:20], origin[:10], dest[:10], str(ac.get("r"))[:20], str(ac.get("t"))[:20]
                ))
        except Exception as e:
            pass # Ignore conflicts or DB noise

    async def poll(self):
        """Poll airplanes.live every 1s"""
        self.polling = True
        url = "https://api.airplanes.live/v2/all"
        
        async with aiohttp.ClientSession() as session:
            while self.polling:
                try:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            aircrafts = data.get("ac", [])
                            
                            batch_messages = []
                            for ac in aircrafts:
                                lat = ac.get("lat")
                                lon = ac.get("lon")
                                if lat is None or lon is None:
                                    continue
                                    
                                # Filter by Asian Airspace
                                if not (ASIA_AIRSPACE_BBOX["lat_min"] <= lat <= ASIA_AIRSPACE_BBOX["lat_max"] and 
                                        ASIA_AIRSPACE_BBOX["lon_min"] <= lon <= ASIA_AIRSPACE_BBOX["lon_max"]):
                                    continue

                                squawk = str(ac.get("squawk", ""))
                                callsign = ac.get("flight", "").strip()
                                
                                # 1. Squawk Filter
                                if squawk in ["7700", "7600", "7500"]:
                                    self.insert_alert(ac)
                                
                                # 2. Enrich and Insert Route
                                if callsign:
                                    origin, dest = self.enrich_callsign(callsign)
                                    if origin and dest:
                                        self.insert_flight_route(callsign, origin, dest, ac)
                                        
                                # 3. Format for Kafka (Insert into flights table pipeline)
                                icao24 = ac.get("hex", "UNKNOWN").lower()
                                flight_data = {
                                    "icao24": icao24,
                                    "callsign": callsign,
                                    "origin_country": "Unknown",
                                    "time_position": int(datetime.utcnow().timestamp()),
                                    "last_contact": int(datetime.utcnow().timestamp()),
                                    "longitude": lon,
                                    "latitude": lat,
                                    "baro_altitude": ac.get("alt_baro"),
                                    "on_ground": bool(ac.get("gnd", False)),
                                    "velocity": ac.get("gs"),
                                    "true_track": ac.get("track"),
                                    "vertical_rate": ac.get("baro_rate"),
                                    "sensors": "",
                                    "geo_altitude": ac.get("alt_geom"),
                                    "squawk": squawk,
                                    "spi": False,
                                    "position_source": 0,
                                    "registration": ac.get("r", ""),
                                    "aircraft_type": ac.get("t", ""),
                                    "aircraft_desc": ac.get("desc", ""),
                                    "timestamp": datetime.utcnow().isoformat()
                                }
                                batch_messages.append((icao24, flight_data))
                                
                            # Send batch to Kafka
                            if batch_messages:
                                self.kafka_producer.send_batch(KAFKA_TOPIC_RAW_FLIGHT, batch_messages)
                                logger.info(f"✈️ Sent {len(batch_messages)} Airplanes.live flights to Kafka")
                except asyncio.TimeoutError:
                    logger.warning("⏱️ Airplanes.live API timeout")
                except Exception as e:
                    logger.error(f"Airplanes.live polling error: {type(e).__name__} {e}")
                
                await asyncio.sleep(1)

    async def start(self):
        logger.info("Starting Airplanes.live Consumer...")
        await self.poll()

    def stop(self):
        logger.info("Stopping Airplanes.live Consumer...")
        self.polling = False
        if self.conn and not self.conn.closed:
            self.conn.close()
        self.kafka_producer.close()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    consumer = AirplanesLiveConsumer()
    try:
        asyncio.run(consumer.start())
    except KeyboardInterrupt:
        consumer.stop()
