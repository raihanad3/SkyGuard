"""
Database Manager untuk SkyGuard
Menyimpan data penerbangan dan alert ke SQLite.
"""

import sqlite3
import os
import logging
from datetime import datetime, timedelta
from core.config import DATABASE_PATH

logger = logging.getLogger("skyguard")


class DatabaseManager:
    """Manages SQLite database untuk flight data dan alerts."""
    
    def __init__(self):
        # Ensure data directory exists
        os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
        
        self.db_path = DATABASE_PATH
        self._create_tables()
    
    def _get_connection(self):
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _create_tables(self):
        """Create database tables if not exist."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Flights table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS flights (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                icao24 TEXT NOT NULL,
                callsign TEXT,
                origin_country TEXT,
                time_position INTEGER,
                last_contact INTEGER,
                longitude REAL,
                latitude REAL,
                baro_altitude REAL,
                on_ground INTEGER,
                velocity REAL,
                true_track REAL,
                vertical_rate REAL,
                sensors TEXT,
                geo_altitude REAL,
                squawk TEXT,
                spi INTEGER,
                position_source INTEGER,
                timestamp TEXT NOT NULL,
                UNIQUE(icao24, timestamp)
            )
        """)
        
        # Flight info table (metadata)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS flight_info (
                icao24 TEXT PRIMARY KEY,
                callsign TEXT,
                origin_country TEXT,
                first_seen TEXT,
                last_seen TEXT,
                total_positions INTEGER DEFAULT 0
            )
        """)
        
        # Alerts table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                icao24 TEXT NOT NULL,
                callsign TEXT,
                alert_level TEXT NOT NULL,
                anomaly_score REAL,
                latitude REAL,
                longitude REAL,
                altitude REAL,
                speed REAL,
                heading REAL,
                reasons TEXT,
                zone_name TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (icao24) REFERENCES flight_info(icao24)
            )
        """)
        
        # Create indices
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_flights_icao24 ON flights(icao24)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_flights_timestamp ON flights(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_alerts_icao24 ON alerts(icao24)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_alerts_level ON alerts(alert_level)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_alerts_created ON alerts(created_at)")
        
        conn.commit()
        conn.close()
    
    def insert_flight_position(self, flight_data):
        """Insert flight position data."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT OR IGNORE INTO flights (
                    icao24, callsign, origin_country, time_position, last_contact,
                    longitude, latitude, baro_altitude, on_ground, velocity,
                    true_track, vertical_rate, sensors, geo_altitude, squawk,
                    spi, position_source, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                flight_data.get("icao24"),
                flight_data.get("callsign"),
                flight_data.get("origin_country"),
                flight_data.get("time_position"),
                flight_data.get("last_contact"),
                flight_data.get("longitude"),
                flight_data.get("latitude"),
                flight_data.get("baro_altitude"),
                flight_data.get("on_ground", 0),
                flight_data.get("velocity"),
                flight_data.get("true_track"),
                flight_data.get("vertical_rate"),
                flight_data.get("sensors"),
                flight_data.get("geo_altitude"),
                flight_data.get("squawk"),
                flight_data.get("spi", 0),
                flight_data.get("position_source", 0),
                flight_data.get("timestamp", datetime.utcnow().isoformat())
            ))
            
            conn.commit()
        except sqlite3.IntegrityError:
            pass  # Duplicate, skip
        except Exception as e:
            logger.error(f"Insert flight error: {e}")
        finally:
            conn.close()
    
    def upsert_flight_info(self, flight_info):
        """Insert or update flight metadata."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO flight_info (icao24, callsign, origin_country, first_seen, last_seen, total_positions)
                VALUES (?, ?, ?, ?, ?, 1)
                ON CONFLICT(icao24) DO UPDATE SET
                    callsign = excluded.callsign,
                    origin_country = excluded.origin_country,
                    last_seen = excluded.last_seen,
                    total_positions = total_positions + 1
            """, (
                flight_info.get("icao24"),
                flight_info.get("callsign"),
                flight_info.get("origin_country"),
                datetime.utcnow().isoformat(),
                datetime.utcnow().isoformat()
            ))
            
            conn.commit()
        except Exception as e:
            logger.error(f"Upsert flight info error: {e}")
        finally:
            conn.close()
    
    def insert_alert(self, alert_data):
        """Insert alert."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO alerts (
                    icao24, callsign, alert_level, anomaly_score,
                    latitude, longitude, altitude, speed, heading,
                    reasons, zone_name, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                alert_data.get("icao24"),
                alert_data.get("callsign"),
                alert_data.get("alert_level"),
                alert_data.get("anomaly_score"),
                alert_data.get("latitude"),
                alert_data.get("longitude"),
                alert_data.get("altitude"),
                alert_data.get("speed"),
                alert_data.get("heading"),
                alert_data.get("reasons"),
                alert_data.get("zone_name"),
                alert_data.get("created_at", datetime.utcnow().isoformat())
            ))
            
            conn.commit()
            return cursor.lastrowid
        except Exception as e:
            logger.error(f"Insert alert error: {e}")
            return None
        finally:
            conn.close()
    
    def get_recent_alerts(self, limit=50):
        """Get recent alerts."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM alerts
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,))
        
        alerts = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return alerts
    
    def get_active_flights(self, minutes=30):
        """Get flights active in last N minutes."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cutoff = (datetime.utcnow() - timedelta(minutes=minutes)).isoformat()
        
        cursor.execute("""
            SELECT DISTINCT
                f.icao24,
                f.callsign,
                f.origin_country,
                f.latitude,
                f.longitude,
                f.baro_altitude,
                f.velocity,
                f.true_track,
                f.timestamp
            FROM flights f
            INNER JOIN (
                SELECT icao24, MAX(timestamp) as max_ts
                FROM flights
                WHERE timestamp > ?
                GROUP BY icao24
            ) latest ON f.icao24 = latest.icao24 AND f.timestamp = latest.max_ts
        """, (cutoff,))
        
        flights = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return flights
    
    def get_stats(self):
        """Get system statistics."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Total flights
        cursor.execute("SELECT COUNT(DISTINCT icao24) FROM flight_info")
        total_flights = cursor.fetchone()[0]
        
        # Total positions
        cursor.execute("SELECT COUNT(*) FROM flights")
        total_positions = cursor.fetchone()[0]
        
        # Alerts by level
        cursor.execute("""
            SELECT alert_level, COUNT(*) as count
            FROM alerts
            GROUP BY alert_level
        """)
        alerts_by_level = {row[0]: row[1] for row in cursor.fetchall()}
        
        conn.close()
        
        return {
            "total_flights": total_flights,
            "total_positions": total_positions,
            "alerts_by_level": alerts_by_level
        }
    
    def get_alert_count_by_level(self):
        """Get alert counts by level."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT alert_level, COUNT(*) as count
            FROM alerts
            GROUP BY alert_level
        """)
        
        counts = {row[0]: row[1] for row in cursor.fetchall()}
        conn.close()
        
        return counts
