import os
import time
import logging
import requests
import psycopg2
from dotenv import load_dotenv

load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] skyguard.route_resolver: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("skyguard.route_resolver")

# Database Config
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5433")
POSTGRES_USER = os.getenv("POSTGRES_USER", "skyguard")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "skyguard_pass")
POSTGRES_DB = os.getenv("POSTGRES_DB", "skyguard_db")

def get_db_connection():
    return psycopg2.connect(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
        dbname=POSTGRES_DB,
    )

def resolve_routes():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Find up to 10 unique callsigns from recent preprocessed flights that don't have a route yet.
        # We only look at flights received in the last hour to save queries.
        cursor.execute("""
            SELECT DISTINCT callsign 
            FROM preprocessed_flights pf
            WHERE callsign IS NOT NULL 
              AND callsign != ''
              AND pf.timestamp > EXTRACT(EPOCH FROM NOW() - INTERVAL '1 hour') * 1000
              AND NOT EXISTS (
                  SELECT 1 FROM flight_routes fr WHERE fr.callsign = pf.callsign
              )
            LIMIT 10
        """)
        
        missing_callsigns = [row[0] for row in cursor.fetchall()]
        
        if not missing_callsigns:
            conn.close()
            return
            
        logger.info(f"Found {len(missing_callsigns)} unmapped callsigns. Attempting resolution...")
        
        for callsign in missing_callsigns:
            # Clean callsign
            clean_callsign = callsign.strip()
            
            # Fetch from OpenSky Routes API
            try:
                # OpenSky REST API for routes does NOT require authentication for low volume, 
                # but we'll use it cautiously.
                url = f"https://opensky-network.org/api/routes?callsign={clean_callsign}"
                response = requests.get(url, timeout=10)
                
                origin = None
                dest = None
                operator = None
                
                if response.status_code == 200:
                    data = response.json()
                    route = data.get("route", [])
                    if len(route) >= 2:
                        origin = route[0]
                        dest = route[-1]
                    operator = data.get("operatorIata") or data.get("operatorIcao")
                    logger.info(f"Resolved {clean_callsign}: {origin} -> {dest}")
                else:
                    # If 404, the route is not in their database.
                    # We still insert a NULL row to avoid querying it again (caching the negative result).
                    logger.debug(f"Route for {clean_callsign} not found or rate limited (Status {response.status_code})")
                
                # Insert into flight_routes
                cursor.execute("""
                    INSERT INTO flight_routes (callsign, origin_airport_icao, destination_airport_icao, operator_icao)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (callsign) DO UPDATE SET
                        origin_airport_icao = EXCLUDED.origin_airport_icao,
                        destination_airport_icao = EXCLUDED.destination_airport_icao,
                        operator_icao = EXCLUDED.operator_icao,
                        updated_at = NOW()
                """, (clean_callsign, origin, dest, operator))
                
                conn.commit()
                
                # Sleep a bit to avoid hammering the API
                time.sleep(2)
                
            except Exception as e:
                logger.error(f"Error fetching route for {clean_callsign}: {e}")
                
        conn.close()

    except Exception as e:
        logger.error(f"Database error: {e}")

if __name__ == "__main__":
    logger.info("Starting Background Route Resolver...")
    while True:
        resolve_routes()
        time.sleep(15)  # Check for new callsigns every 15 seconds
