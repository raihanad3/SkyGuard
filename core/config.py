"""
Konfigurasi sistem deteksi kapal anomali.
Semua parameter konfigurasi terpusat di sini.
"""

import os

# ============================================================
# AISstream.io API Configuration
# ============================================================
# Daftar gratis di https://aisstream.io untuk mendapatkan API key
AISSTREAM_API_KEY = os.environ.get("AISSTREAM_API_KEY", "YOUR_API_KEY_HERE")
AISSTREAM_WS_URL = "wss://stream.aisstream.io/v0/stream"

# ============================================================
# Indonesia Maritime Boundaries (Bounding Boxes)
# ============================================================
# EEZ (Exclusive Economic Zone) - area terluas
INDONESIA_EEZ_BBOX = [
    [[-14.0, 92.0], [8.0, 141.5]]
]

# Zona Kritis - area yang sering terjadi pelanggaran
CRITICAL_ZONES = {
    "natuna_sea": {
        "name": "Laut Natuna Utara",
        "bbox": [[1.0, 105.0], [7.0, 112.0]],
        "risk_multiplier": 1.5
    },
    "malacca_strait": {
        "name": "Selat Malaka",
        "bbox": [[0.5, 98.0], [4.0, 104.0]],
        "risk_multiplier": 1.3
    },
    "arafura_sea": {
        "name": "Laut Arafura",
        "bbox": [[-10.0, 131.0], [-4.0, 141.0]],
        "risk_multiplier": 1.4
    },
    "sulawesi_sea": {
        "name": "Laut Sulawesi",
        "bbox": [[-1.0, 117.0], [5.0, 127.0]],
        "risk_multiplier": 1.2
    },
    "java_sea": {
        "name": "Laut Jawa",
        "bbox": [[-8.0, 106.0], [-4.0, 117.0]],
        "risk_multiplier": 1.1
    }
}

# ============================================================
# Negara dengan Risiko IUU (Illegal, Unreported, Unregulated) Tinggi
# Berdasarkan data historis pelanggaran di perairan Indonesia
# ============================================================
HIGH_RISK_FLAGS = {
    "CN": {"name": "China", "risk": 0.9},
    "VN": {"name": "Vietnam", "risk": 0.85},
    "PH": {"name": "Philippines", "risk": 0.6},
    "TH": {"name": "Thailand", "risk": 0.7},
    "MY": {"name": "Malaysia", "risk": 0.5},
    "TW": {"name": "Taiwan", "risk": 0.65},
    "KR": {"name": "South Korea", "risk": 0.4},
    "UNKNOWN": {"name": "Unknown Flag", "risk": 0.95},
}

# Negara bendera Indonesia (tidak di-flag)
INDONESIA_FLAG_CODES = ["ID", "IDN", "360"]

# ============================================================
# Anomaly Detection Parameters
# ============================================================
ANOMALY_CONFIG = {
    # Isolation Forest
    "contamination": 0.1,          # Estimasi 10% data adalah anomali
    "n_estimators": 100,           # Jumlah trees
    "min_samples_for_training": 50, # Minimum data sebelum training
    "retrain_interval_hours": 6,   # Retrain setiap 6 jam

    # Speed thresholds (knots)
    "max_speed_fishing": 8,        # Maks kecepatan kapal fishing normal
    "max_speed_cargo": 25,         # Maks kecepatan kapal cargo
    "min_speed_loitering": 0.5,    # Di bawah ini = loitering
    "max_speed_territorial": 15,   # Maks kecepatan di territorial

    # AIS Gap
    "ais_gap_minutes": 30,         # Gap AIS > 30 menit = suspicious

    # Loitering
    "loitering_radius_nm": 2.0,    # Radius loitering (nautical miles)
    "loitering_duration_min": 60,  # Durasi loitering minimum (menit)

    # Course change
    "course_change_threshold": 45, # Perubahan arah > 45° = significant

    # Night activity
    "night_start_hour": 22,        # Jam mulai "malam" (WIB)
    "night_end_hour": 5,           # Jam akhir "malam" (WIB)
}

# ============================================================
# Alert Thresholds
# ============================================================
ALERT_THRESHOLDS = {
    "HIGH": 0.7,       # Score >= 0.7 → HIGH ALERT (merah)
    "MEDIUM": 0.5,     # Score >= 0.5 → MEDIUM (kuning)
    "LOW": 0.3,        # Score >= 0.3 → LOW (biru)
}

# Cooldown alert per kapal (menit) - hindari spam
ALERT_COOLDOWN_MINUTES = 15

# ============================================================
# Database Configuration
# ============================================================
DATABASE_PATH = os.path.join(os.path.dirname(__file__), "data", "vessel_tracker.db")

# ============================================================
# Logging Configuration
# ============================================================
LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
LOG_FILE = os.path.join(LOG_DIR, "alerts.log")
SYSTEM_LOG_FILE = os.path.join(LOG_DIR, "system.log")

# ============================================================
# Dashboard Configuration
# ============================================================
DASHBOARD_HOST = "0.0.0.0"
DASHBOARD_PORT = 5000

# ============================================================
# Model Save Path
# ============================================================
MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")
MODEL_PATH = os.path.join(MODEL_DIR, "isolation_forest.pkl")

# ============================================================
# Ship Type Mapping (AIS Ship Type codes)
# ============================================================
SHIP_TYPE_MAP = {
    range(20, 30): "Wing in Ground",
    range(30, 40): "Fishing",
    range(40, 50): "High Speed Craft",
    range(50, 60): "Special Craft",
    range(60, 70): "Passenger",
    range(70, 80): "Cargo",
    range(80, 90): "Tanker",
    range(90, 100): "Other",
}

def get_ship_type_name(type_code):
    """Konversi kode tipe kapal AIS ke nama yang readable."""
    if type_code is None:
        return "Unknown"
    for code_range, name in SHIP_TYPE_MAP.items():
        if type_code in code_range:
            return name
    return "Unknown"

# Flag emoji mapping
FLAG_EMOJI = {
    "CN": "🇨🇳", "VN": "🇻🇳", "PH": "🇵🇭", "TH": "🇹🇭",
    "MY": "🇲🇾", "TW": "🇹🇼", "KR": "🇰🇷", "ID": "🇮🇩",
    "JP": "🇯🇵", "SG": "🇸🇬", "US": "🇺🇸", "PA": "🇵🇦",
    "LR": "🇱🇷", "MH": "🇲🇭", "HK": "🇭🇰", "UNKNOWN": "🏴",
}

def get_flag_emoji(country_code):
    """Mendapatkan emoji bendera dari kode negara."""
    return FLAG_EMOJI.get(country_code, "🏳️")
