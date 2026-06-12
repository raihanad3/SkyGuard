"""
SkyGuard — Store Inference Results (Computer 3)
=================================================
Stores anomaly detection results and alerts into PostgreSQL.
"""

import json
import logging
import psycopg2
from psycopg2.extras import execute_values, Json
from datetime import datetime

from computer3_inference.config.settings import (
    POSTGRES_HOST, POSTGRES_PORT,
    POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB,
)

logger = logging.getLogger("skyguard.inference")


class ResultStore:
    """Store inference results and alerts in PostgreSQL."""

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
            logger.info("✅ PostgreSQL connected (result store)")
        except Exception as e:
            logger.error("❌ PostgreSQL connection failed: %s", e)
            raise

    def store_inference(self, result):
        """
        Store a single inference result.

        Args:
            result: dict from AnomalyDetector.analyze()
        """
        sql = """
            INSERT INTO inference_results (
                icao24, callsign, origin_country,
                latitude, longitude, altitude, speed, heading,
                anomaly_score, alert_level, reasons, zone_name
            ) VALUES (
                %(icao24)s, %(callsign)s, %(origin_country)s,
                %(latitude)s, %(longitude)s, %(altitude)s, %(speed)s, %(heading)s,
                %(anomaly_score)s, %(alert_level)s, %(reasons)s, %(zone_name)s
            )
        """
        try:
            params = dict(result)
            params["reasons"] = Json(params.get("reasons", []))
            with self.conn.cursor() as cur:
                cur.execute(sql, params)
        except Exception as e:
            logger.error("Store inference error: %s", e)

    def store_inference_batch(self, results):
        """Store a batch of inference results."""
        if not results:
            return 0

        values = [
            (
                r.get("icao24"), r.get("callsign"), r.get("origin_country"),
                r.get("latitude"), r.get("longitude"),
                r.get("altitude"), r.get("speed"), r.get("heading"),
                r.get("anomaly_score"), r.get("alert_level"),
                Json(r.get("reasons", [])), r.get("zone_name", ""),
            )
            for r in results
        ]

        sql = """
            INSERT INTO inference_results (
                icao24, callsign, origin_country,
                latitude, longitude, altitude, speed, heading,
                anomaly_score, alert_level, reasons, zone_name
            ) VALUES %s
        """
        try:
            with self.conn.cursor() as cur:
                execute_values(cur, sql, values)
            logger.info("📊 Stored %d inference results", len(values))
            return len(values)
        except Exception as e:
            logger.error("Batch inference store error: %s", e)
            return 0

    def store_alert(self, alert_data):
        """
        Store a single alert record.

        Args:
            alert_data: dict from AlertSystem.process()
        """
        sql = """
            INSERT INTO alerts (
                icao24, callsign, alert_level, anomaly_score,
                latitude, longitude, altitude, speed, heading,
                reasons, zone_name, created_at
            ) VALUES (
                %(icao24)s, %(callsign)s, %(alert_level)s, %(anomaly_score)s,
                %(latitude)s, %(longitude)s, %(altitude)s, %(speed)s, %(heading)s,
                %(reasons)s, %(zone_name)s, %(created_at)s
            )
        """
        try:
            params = dict(alert_data)
            params["reasons"] = Json(params.get("reasons", []))
            with self.conn.cursor() as cur:
                cur.execute(sql, params)
            return True
        except Exception as e:
            logger.error("Store alert error: %s", e)
            return False

    def store_flight_info(self, icao24, callsign, origin_country):
        """Upsert flight metadata."""
        sql = """
            INSERT INTO flight_info (icao24, callsign, origin_country, first_seen, last_seen, total_positions)
            VALUES (%s, %s, %s, NOW(), NOW(), 1)
            ON CONFLICT (icao24) DO UPDATE SET
                callsign = EXCLUDED.callsign,
                origin_country = EXCLUDED.origin_country,
                last_seen = NOW(),
                total_positions = flight_info.total_positions + 1
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute(sql, (icao24, callsign, origin_country))
        except Exception as e:
            logger.error("Upsert flight info error: %s", e)

    def close(self):
        """Close PostgreSQL connection."""
        if self.conn:
            self.conn.close()
            logger.info("🛑 PostgreSQL connection closed (result store)")
