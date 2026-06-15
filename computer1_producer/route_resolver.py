import time
import logging
import psycopg2
from shared.config.settings import (
    POSTGRES_HOST, POSTGRES_PORT,
    POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] skyguard.route_resolver: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("skyguard.route_resolver")

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

        # Get latest metadata for recent callsigns from preprocessed_flights
        cursor.execute("""
            SELECT callsign, registration, aircraft_type, aircraft_desc
            FROM (
                SELECT callsign, registration, aircraft_type, aircraft_desc,
                       ROW_NUMBER() OVER(PARTITION BY callsign ORDER BY processed_at DESC) as rn
                FROM preprocessed_flights
                WHERE callsign IS NOT NULL AND callsign != ''
                  AND processed_at > NOW() - INTERVAL '1 hour'
            ) t
            WHERE rn = 1
            LIMIT 200
        """)
        
        recent_flights = cursor.fetchall()
        
        if not recent_flights:
            conn.close()
            return
            
        logger.info(f"Processing metadata for {len(recent_flights)} callsigns...")
        
        for row in recent_flights:
            callsign, reg, ac_type, ac_desc = row
            clean_callsign = callsign.strip()
            
            # Upsert into flight_routes.
            # Insert 'UNKNOWN' for routes, but update the metadata fields.
            cursor.execute("""
                INSERT INTO flight_routes (
                    callsign, origin_airport_icao, destination_airport_icao, operator_icao,
                    registration, aircraft_type, aircraft_desc
                )
                VALUES (%s, 'UNKNOWN', 'UNKNOWN', 'UNKNOWN', %s, %s, %s)
                ON CONFLICT (callsign) DO UPDATE SET
                    registration = COALESCE(EXCLUDED.registration, flight_routes.registration),
                    aircraft_type = COALESCE(EXCLUDED.aircraft_type, flight_routes.aircraft_type),
                    aircraft_desc = COALESCE(EXCLUDED.aircraft_desc, flight_routes.aircraft_desc),
                    updated_at = NOW()
            """, (clean_callsign, reg, ac_type, ac_desc))
            
        conn.commit()
        conn.close()

    except Exception as e:
        logger.error(f"Database error: {e}")

if __name__ == "__main__":
    logger.info("Starting Background Route Resolver...")
    while True:
        resolve_routes()
        time.sleep(15)  # Check for new callsigns every 15 seconds
