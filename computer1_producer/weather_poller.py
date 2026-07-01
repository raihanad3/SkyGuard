import time
import requests
import psycopg2
import json
import logging
from shared.config.settings import (
    POSTGRES_HOST, POSTGRES_PORT,
    POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("weather_poller")

def get_db_connection():
    return psycopg2.connect(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
        dbname=POSTGRES_DB
    )

def fetch_and_store_weather():
    url = "https://aviationweather.gov/api/data/isigmet?format=geojson"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        features = data.get("features", [])
        logger.info(f"Fetched {len(features)} ISIGMET weather zones.")

        conn = get_db_connection()
        cur = conn.cursor()

        # Clear old weather zones
        cur.execute("TRUNCATE TABLE weather_zones RESTART IDENTITY")

        insert_query = """
            INSERT INTO weather_zones (firId, hazard, severity, validTimeFrom, validTimeTo, geometry)
            VALUES (%s, %s, %s, %s, %s, %s)
        """

        count = 0
        for feature in features:
            props = feature.get("properties", {})
            geom = feature.get("geometry", {})
            if not geom:
                continue

            # Only store hazards like TURB (Turbulence), ICE (Icing), TS (Thunderstorm)
            hazard = props.get("hazard")
            if hazard not in ["TURB", "ICE", "TS", "CONVECTIVE"]:
                continue

            cur.execute(insert_query, (
                props.get("firId"),
                hazard,
                props.get("severity"),
                props.get("validTimeFrom"),
                props.get("validTimeTo"),
                json.dumps(geom)
            ))
            count += 1

        conn.commit()
        cur.close()
        conn.close()
        logger.info(f"Stored {count} relevant weather zones to database.")

    except Exception as e:
        logger.error(f"Error fetching weather: {e}")

if __name__ == "__main__":
    logger.info("Starting NOAA Weather Poller...")
    while True:
        fetch_and_store_weather()
        time.sleep(25) # Poll every 25 seconds
