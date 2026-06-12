"""
SkyGuard — Store Preprocessed Data (Computer 2)
=================================================
Fallback storage module when Spark is not used.
Writes preprocessed flight data directly to PostgreSQL
using psycopg2.
"""

import logging
import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime

from computer2_preprocessing.config.settings import (
    POSTGRES_HOST, POSTGRES_PORT,
    POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB,
)

logger = logging.getLogger("skyguard.preprocessing")


class PreprocessedStore:
    """Store preprocessed flight data in PostgreSQL."""

    def __init__(self):
        self.conn = None
        self._connect()

    def _connect(self):
        """Establish PostgreSQL connection."""
        try:
            self.conn = psycopg2.connect(
                host=POSTGRES_HOST,
                port=POSTGRES_PORT,
                user=POSTGRES_USER,
                password=POSTGRES_PASSWORD,
                dbname=POSTGRES_DB,
            )
            self.conn.autocommit = True
            logger.info("✅ PostgreSQL connected (preprocessed store)")
        except Exception as e:
            logger.error("❌ PostgreSQL connection failed: %s", e)
            raise

    def store(self, features):
        """
        Store a single preprocessed flight record.

        Args:
            features: dict from FeatureEngine.extract_features()
        """
        sql = """
            INSERT INTO preprocessed_flights (
                icao24, callsign, origin_country,
                latitude, longitude,
                altitude_feet, speed_knots, heading, climb_rate_fpm,
                on_ground,
                altitude_change, heading_change, distance_traveled_km,
                near_airport, airport_code, airport_name,
                in_restricted_zone, restricted_zone_id, restricted_zone_name,
                zone_risk_multiplier,
                squawk, raw_timestamp
            ) VALUES (
                %(icao24)s, %(callsign)s, %(origin_country)s,
                %(latitude)s, %(longitude)s,
                %(altitude_feet)s, %(speed_knots)s, %(heading)s, %(climb_rate_fpm)s,
                %(on_ground)s,
                %(altitude_change)s, %(heading_change)s, %(distance_traveled_km)s,
                %(near_airport)s, %(airport_code)s, %(airport_name)s,
                %(in_restricted_zone)s, %(restricted_zone_id)s, %(restricted_zone_name)s,
                %(zone_risk_multiplier)s,
                %(squawk)s, %(raw_timestamp)s
            )
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute(sql, features)
        except Exception as e:
            logger.error("Insert preprocessed error: %s", e)

    def store_batch(self, features_list):
        """
        Store a batch of preprocessed flight records.

        Args:
            features_list: list of dicts from FeatureEngine.extract_features()
        """
        if not features_list:
            return 0

        columns = [
            "icao24", "callsign", "origin_country",
            "latitude", "longitude",
            "altitude_feet", "speed_knots", "heading", "climb_rate_fpm",
            "on_ground",
            "altitude_change", "heading_change", "distance_traveled_km",
            "near_airport", "airport_code", "airport_name",
            "in_restricted_zone", "restricted_zone_id", "restricted_zone_name",
            "zone_risk_multiplier",
            "squawk", "raw_timestamp",
        ]

        values = [
            tuple(f.get(c) for c in columns)
            for f in features_list
        ]

        sql = f"""
            INSERT INTO preprocessed_flights ({', '.join(columns)})
            VALUES %s
        """

        try:
            with self.conn.cursor() as cur:
                execute_values(cur, sql, values)
            logger.info("📦 Stored %d preprocessed records", len(values))
            return len(values)
        except Exception as e:
            logger.error("Batch insert error: %s", e)
            return 0

    def close(self):
        """Close PostgreSQL connection."""
        if self.conn:
            self.conn.close()
            logger.info("🛑 PostgreSQL connection closed (preprocessed store)")
