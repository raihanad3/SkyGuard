"""
SkyGuard — Global Settings
===========================
Centralized configuration loaded from environment variables.
Used by all 4 computer components.
"""

import os
from dotenv import load_dotenv

# Load .env file (looks in project root)
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env"))


# ============================================================
# Kafka Configuration
# ============================================================
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC_RAW_FLIGHT = os.getenv("KAFKA_TOPIC_RAW_FLIGHT", "raw-flight-data")
KAFKA_TOPIC_RAW_NEWS = os.getenv("KAFKA_TOPIC_RAW_NEWS", "raw-news-data")
KAFKA_TOPIC_PREPROCESSED = os.getenv("KAFKA_TOPIC_PREPROCESSED", "preprocessed-flight-data")
KAFKA_CONSUMER_GROUP_PREPROCESSING = os.getenv("KAFKA_CONSUMER_GROUP_PREPROCESSING", "skyguard-preprocessing")
KAFKA_CONSUMER_GROUP_INFERENCE = os.getenv("KAFKA_CONSUMER_GROUP_INFERENCE", "skyguard-inference")


# ============================================================
# PostgreSQL Configuration
# ============================================================
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_USER = os.getenv("POSTGRES_USER", "skyguard")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "skyguard_pass")
POSTGRES_DB = os.getenv("POSTGRES_DB", "skyguard_db")

POSTGRES_URL = (
    f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
    f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
)

# JDBC URL (for Spark)
POSTGRES_JDBC_URL = (
    f"jdbc:postgresql://{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
)


# ============================================================
# OpenSky Network API
# ============================================================
OPENSKY_API_URL = os.getenv("OPENSKY_API_URL", "https://opensky-network.org/api/states/all")
OPENSKY_UPDATE_INTERVAL = int(os.getenv("OPENSKY_UPDATE_INTERVAL", "10"))


# ============================================================
# News API
# ============================================================
NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")


# ============================================================
# Debezium
# ============================================================
DEBEZIUM_CONNECT_URL = os.getenv("DEBEZIUM_CONNECT_URL", "http://localhost:8083")


# ============================================================
# Dashboard
# ============================================================
DASHBOARD_PORT = int(os.getenv("DASHBOARD_PORT", "8501"))


# ============================================================
# Anomaly Detection Parameters
# ============================================================
ANOMALY_CONFIG = {
    # Altitude thresholds (feet)
    "min_safe_altitude": 1000,
    "max_normal_altitude": 45000,
    "rapid_climb_rate": 2000,       # ft/min

    # Speed thresholds (knots)
    "min_cruise_speed": 100,
    "max_normal_speed": 600,
    "max_military_speed": 1200,

    # Course change
    "erratic_course_change": 90,    # degrees

    # Transponder off
    "transponder_timeout": 300,     # seconds

    # Ground proximity
    "airport_buffer_km": 20,
}


# ============================================================
# Alert Thresholds
# ============================================================
ALERT_THRESHOLDS = {
    "HIGH": 0.7,
    "MEDIUM": 0.5,
    "LOW": 0.3,
}

ALERT_COOLDOWN_MINUTES = 10


# ============================================================
# Logging
# ============================================================
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs")
LOG_FILE = os.path.join(LOG_DIR, "skyguard.log")
ALERT_LOG_FILE = os.path.join(LOG_DIR, "alerts.log")
