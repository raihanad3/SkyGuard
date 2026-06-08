"""
Database Manager — SQLite database untuk menyimpan data kapal,
posisi, dan riwayat anomali alert.
"""

import sqlite3
import os
import json
import threading
from datetime import datetime, timedelta

from config import DATABASE_PATH


class DatabaseManager:
    """Thread-safe SQLite database manager."""

    _local = threading.local()

    def __init__(self):
        """Inisialisasi database dan buat tabel jika belum ada."""
        os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
        self._init_db()

    def _get_connection(self):
        """Mendapatkan koneksi SQLite per-thread."""
        if not hasattr(self._local, 'connection') or self._local.connection is None:
            self._local.connection = sqlite3.connect(
                DATABASE_PATH,
                check_same_thread=False,
                timeout=30
            )
            self._local.connection.row_factory = sqlite3.Row
            self._local.connection.execute("PRAGMA journal_mode=WAL")
            self._local.connection.execute("PRAGMA synchronous=NORMAL")
        return self._local.connection

    def _init_db(self):
        """Membuat tabel-tabel database."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Tabel posisi kapal (data streaming)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vessel_positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mmsi TEXT NOT NULL,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                speed REAL,
                course REAL,
                heading REAL,
                timestamp TEXT NOT NULL,
                received_at TEXT NOT NULL,
                ship_name TEXT,
                ship_type INTEGER,
                flag_country TEXT,
                destination TEXT,
                raw_data TEXT
            )
        """)

        # Tabel informasi statis kapal
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vessel_info (
                mmsi TEXT PRIMARY KEY,
                ship_name TEXT,
                ship_type INTEGER,
                ship_type_name TEXT,
                flag_country TEXT,
                imo TEXT,
                callsign TEXT,
                length REAL,
                width REAL,
                draught REAL,
                destination TEXT,
                eta TEXT,
                first_seen TEXT,
                last_seen TEXT,
                total_positions INTEGER DEFAULT 0
            )
        """)

        # Tabel anomaly alerts
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS anomaly_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mmsi TEXT NOT NULL,
                alert_level TEXT NOT NULL,
                anomaly_score REAL NOT NULL,
                latitude REAL,
                longitude REAL,
                speed REAL,
                ship_name TEXT,
                flag_country TEXT,
                reasons TEXT,
                zone_name TEXT,
                created_at TEXT NOT NULL,
                acknowledged INTEGER DEFAULT 0
            )
        """)

        # Tabel model metrics
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS model_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_version TEXT,
                training_samples INTEGER,
                anomaly_ratio REAL,
                features_used TEXT,
                trained_at TEXT NOT NULL
            )
        """)

        # Indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_positions_mmsi
            ON vessel_positions(mmsi)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_positions_timestamp
            ON vessel_positions(received_at)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_alerts_created
            ON anomaly_alerts(created_at)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_alerts_level
            ON anomaly_alerts(alert_level)
        """)

        conn.commit()

    def insert_position(self, data: dict):
        """Menyimpan posisi kapal baru."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO vessel_positions
            (mmsi, latitude, longitude, speed, course, heading,
             timestamp, received_at, ship_name, ship_type, flag_country,
             destination, raw_data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data.get("mmsi"),
            data.get("latitude"),
            data.get("longitude"),
            data.get("speed"),
            data.get("course"),
            data.get("heading"),
            data.get("timestamp"),
            datetime.utcnow().isoformat(),
            data.get("ship_name"),
            data.get("ship_type"),
            data.get("flag_country"),
            data.get("destination"),
            json.dumps(data.get("raw_data", {}))
        ))
        conn.commit()
        return cursor.lastrowid

    def upsert_vessel_info(self, data: dict):
        """Insert atau update informasi kapal."""
        conn = self._get_connection()
        cursor = conn.cursor()
        now = datetime.utcnow().isoformat()

        cursor.execute("""
            INSERT INTO vessel_info
            (mmsi, ship_name, ship_type, ship_type_name, flag_country,
             imo, callsign, length, width, draught, destination, eta,
             first_seen, last_seen, total_positions)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            ON CONFLICT(mmsi) DO UPDATE SET
                ship_name = COALESCE(excluded.ship_name, ship_name),
                ship_type = COALESCE(excluded.ship_type, ship_type),
                ship_type_name = COALESCE(excluded.ship_type_name, ship_type_name),
                flag_country = COALESCE(excluded.flag_country, flag_country),
                imo = COALESCE(excluded.imo, imo),
                callsign = COALESCE(excluded.callsign, callsign),
                length = COALESCE(excluded.length, length),
                width = COALESCE(excluded.width, width),
                draught = COALESCE(excluded.draught, draught),
                destination = COALESCE(excluded.destination, destination),
                eta = COALESCE(excluded.eta, eta),
                last_seen = ?,
                total_positions = total_positions + 1
        """, (
            data.get("mmsi"),
            data.get("ship_name"),
            data.get("ship_type"),
            data.get("ship_type_name"),
            data.get("flag_country"),
            data.get("imo"),
            data.get("callsign"),
            data.get("length"),
            data.get("width"),
            data.get("draught"),
            data.get("destination"),
            data.get("eta"),
            now, now, now
        ))
        conn.commit()

    def insert_alert(self, data: dict):
        """Menyimpan anomaly alert baru."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO anomaly_alerts
            (mmsi, alert_level, anomaly_score, latitude, longitude,
             speed, ship_name, flag_country, reasons, zone_name, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data.get("mmsi"),
            data.get("alert_level"),
            data.get("anomaly_score"),
            data.get("latitude"),
            data.get("longitude"),
            data.get("speed"),
            data.get("ship_name"),
            data.get("flag_country"),
            json.dumps(data.get("reasons", [])),
            data.get("zone_name"),
            datetime.utcnow().isoformat()
        ))
        conn.commit()
        return cursor.lastrowid

    def get_recent_positions(self, mmsi: str, minutes: int = 60):
        """Mendapatkan posisi terbaru kapal dalam N menit terakhir."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cutoff = (datetime.utcnow() - timedelta(minutes=minutes)).isoformat()
        cursor.execute("""
            SELECT * FROM vessel_positions
            WHERE mmsi = ? AND received_at > ?
            ORDER BY received_at DESC
        """, (mmsi, cutoff))
        return [dict(row) for row in cursor.fetchall()]

    def get_last_position(self, mmsi: str):
        """Mendapatkan posisi terakhir sebuah kapal."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM vessel_positions
            WHERE mmsi = ?
            ORDER BY received_at DESC
            LIMIT 1
        """, (mmsi,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_recent_alerts(self, limit: int = 50):
        """Mendapatkan alert terbaru."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM anomaly_alerts
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]

    def get_alert_count_by_level(self):
        """Mendapatkan jumlah alert per level."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT alert_level, COUNT(*) as count
            FROM anomaly_alerts
            GROUP BY alert_level
        """)
        return {row["alert_level"]: row["count"] for row in cursor.fetchall()}

    def get_active_vessels(self, minutes: int = 30):
        """Mendapatkan kapal yang aktif dalam N menit terakhir."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cutoff = (datetime.utcnow() - timedelta(minutes=minutes)).isoformat()
        cursor.execute("""
            SELECT vp.mmsi, vp.latitude, vp.longitude, vp.speed,
                   vp.course, vp.heading, vp.received_at,
                   vi.ship_name, vi.ship_type_name, vi.flag_country,
                   vi.destination
            FROM vessel_positions vp
            INNER JOIN (
                SELECT mmsi, MAX(received_at) as max_received
                FROM vessel_positions
                WHERE received_at > ?
                GROUP BY mmsi
            ) latest ON vp.mmsi = latest.mmsi
                    AND vp.received_at = latest.max_received
            LEFT JOIN vessel_info vi ON vp.mmsi = vi.mmsi
        """, (cutoff,))
        return [dict(row) for row in cursor.fetchall()]

    def get_all_positions_for_training(self):
        """Mendapatkan semua data posisi untuk training model."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT vp.*, vi.flag_country as info_flag,
                   vi.ship_type as info_ship_type,
                   vi.ship_type_name
            FROM vessel_positions vp
            LEFT JOIN vessel_info vi ON vp.mmsi = vi.mmsi
            ORDER BY vp.received_at
        """)
        return [dict(row) for row in cursor.fetchall()]

    def get_stats(self):
        """Mendapatkan statistik umum."""
        conn = self._get_connection()
        cursor = conn.cursor()

        stats = {}

        cursor.execute("SELECT COUNT(DISTINCT mmsi) FROM vessel_positions")
        stats["total_vessels"] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM vessel_positions")
        stats["total_positions"] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM anomaly_alerts")
        stats["total_alerts"] = cursor.fetchone()[0]

        # Alert per level
        stats["alerts_by_level"] = self.get_alert_count_by_level()

        # Top flag countries
        cursor.execute("""
            SELECT flag_country, COUNT(DISTINCT mmsi) as count
            FROM vessel_info
            WHERE flag_country IS NOT NULL AND flag_country != ''
            GROUP BY flag_country
            ORDER BY count DESC
            LIMIT 10
        """)
        stats["top_flags"] = {row["flag_country"]: row["count"]
                              for row in cursor.fetchall()}

        return stats

    def insert_model_metrics(self, data: dict):
        """Menyimpan metrics model training."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO model_metrics
            (model_version, training_samples, anomaly_ratio, features_used, trained_at)
            VALUES (?, ?, ?, ?, ?)
        """, (
            data.get("model_version"),
            data.get("training_samples"),
            data.get("anomaly_ratio"),
            json.dumps(data.get("features_used", [])),
            datetime.utcnow().isoformat()
        ))
        conn.commit()

    def check_recent_alert(self, mmsi: str, minutes: int = 15):
        """Cek apakah sudah ada alert recent untuk kapal ini (deduplication)."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cutoff = (datetime.utcnow() - timedelta(minutes=minutes)).isoformat()
        cursor.execute("""
            SELECT COUNT(*) FROM anomaly_alerts
            WHERE mmsi = ? AND created_at > ?
        """, (mmsi, cutoff))
        return cursor.fetchone()[0] > 0
