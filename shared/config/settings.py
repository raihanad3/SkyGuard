"""
SkyGuard — Central Configuration Settings
==========================================
All configuration constants for the distributed pipeline.
Loads from .env file and provides defaults.
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ============================================================
# CENTRAL NODE CONFIGURATION
# ============================================================
CENTRAL_NODE_IP = os.getenv("CENTRAL_NODE_IP", "localhost")

# ============================================================
# KAFKA CONFIGURATION
# ============================================================
KAFKA_BOOTSTRAP_SERVERS = f"{CENTRAL_NODE_IP}:9093"

# Kafka Topics
KAFKA_TOPIC_RAW_FLIGHT = "raw_flight_data"
KAFKA_TOPIC_RAW_NEWS = "raw_news_data"
KAFKA_TOPIC_RAW_WEATHER = "raw_weather_data"
KAFKA_TOPIC_PREPROCESSED = "preprocessed_flight_data"
KAFKA_TOPIC_INFERENCE = "inference_results"

# Consumer Groups
KAFKA_CONSUMER_GROUP_PREPROCESSING = "skyguard-preprocessing"
KAFKA_CONSUMER_GROUP_INFERENCE = "skyguard-inference"

# ============================================================
# POSTGRESQL CONFIGURATION
# ============================================================
POSTGRES_HOST = CENTRAL_NODE_IP
POSTGRES_PORT = 5433
POSTGRES_USER = os.getenv("POSTGRES_USER", "skyguard")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "skyguard_pass")
POSTGRES_DB = os.getenv("POSTGRES_DB", "skyguard_db")

# Connection string
POSTGRES_CONNECTION_STRING = (
    f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@"
    f"{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
)

# ============================================================
# OPENSKY NETWORK API
# ============================================================
OPENSKY_API_URL = "https://opensky-network.org/api/states/all"
OPENSKY_USERNAME = os.getenv("OPENSKY_USERNAME", "")
OPENSKY_PASSWORD = os.getenv("OPENSKY_PASSWORD", "")
OPENSKY_UPDATE_INTERVAL = 300  # seconds (5 minutes = 288 req/day, SAFE for free account)

# ============================================================
# DEBEZIUM CDC CONFIGURATION
# ============================================================
DEBEZIUM_CONNECT_URL = f"http://{CENTRAL_NODE_IP}:8084"

# ============================================================
# ANOMALY DETECTION CONFIGURATION
# ============================================================
ANOMALY_CONFIG = {
    # Altitude thresholds (feet)
    "min_safe_altitude": 5000,
    "max_normal_altitude": 45000,
    
    # Speed thresholds (knots)
    "min_cruise_speed": 100,
    "max_normal_speed": 600,
    
    # Vertical rate thresholds (feet per minute)
    "rapid_climb_rate": 2500,
    "rapid_descent_rate": -2500,
    
    # Course change threshold (degrees)
    "erratic_course_change": 45,
    
    # Distance thresholds
    "airport_proximity_km": 15,
    "restricted_zone_buffer_km": 5,
}

# Alert Thresholds
ALERT_THRESHOLDS = {
    "LOW": 0.3,
    "MEDIUM": 0.6,
    "HIGH": 0.8,
}

# ============================================================
# ALERT SYSTEM CONFIGURATION
# ============================================================
ALERT_COOLDOWN_MINUTES = 5  # Prevent alert spam for same flight

# ============================================================
# LOGGING CONFIGURATION
# ============================================================
LOG_DIR = "./logs"
ALERT_LOG_FILE = "alerts.json"

# ============================================================
# WEATHER API (Optional)
# ============================================================
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY", "")
WEATHER_API_URL = "https://api.openweathermap.org/data/2.5/weather"

# ============================================================
# SPARK CONFIGURATION (Computer 2)
# ============================================================
SPARK_APP_NAME = "SkyGuard-Preprocessing"
SPARK_MASTER = "local[*]"  # Use local mode, adjust for cluster
SPARK_CHECKPOINT_DIR = "./spark_checkpoints"

# ============================================================
# DASHBOARD CONFIGURATION (Computer 4)
# ============================================================
DASHBOARD_REFRESH_INTERVAL_SEC = 30
DASHBOARD_MAX_FLIGHTS_DISPLAY = 100

# ============================================================
# FEATURE ENGINEERING DEFAULTS
# ============================================================
FLIGHT_HISTORY_LIMIT = 100  # Keep last N positions per flight

# ============================================================
# NEWS SCRAPER CONFIGURATION
# ============================================================
NEWS_FEED_URLS = [
    "https://www.flightradar24.com/blog/feed/",
    "http://rss.cnn.com/rss/edition_aviation.rss",
]
NEWS_UPDATE_INTERVAL_HOURS = 1
