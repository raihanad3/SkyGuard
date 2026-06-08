"""
Feature Engine — Mengekstrak fitur-fitur anomali dari data AIS mentah
secara real-time untuk digunakan oleh model deteksi.
"""

import math
from datetime import datetime, timedelta, timezone
from geopy.distance import geodesic

from config import (
    ANOMALY_CONFIG, HIGH_RISK_FLAGS, INDONESIA_FLAG_CODES,
    CRITICAL_ZONES, INDONESIA_EEZ_BBOX, get_ship_type_name
)


class FeatureEngine:
    """Mengekstrak fitur anomali dari data AIS kapal."""

    def __init__(self, db_manager):
        self.db = db_manager
        # Cache posisi terakhir per kapal untuk kalkulasi delta
        self.vessel_cache = {}

    def extract_features(self, vessel_data: dict) -> dict:
        """
        Mengekstrak semua fitur dari satu data point kapal.

        Args:
            vessel_data: Dict berisi data AIS kapal

        Returns:
            Dict fitur-fitur anomali dengan skor 0-1
        """
        mmsi = vessel_data.get("mmsi", "")
        lat = vessel_data.get("latitude", 0)
        lon = vessel_data.get("longitude", 0)
        speed = vessel_data.get("speed", 0) or 0
        course = vessel_data.get("course", 0) or 0
        ship_type = vessel_data.get("ship_type")
        flag = vessel_data.get("flag_country", "UNKNOWN") or "UNKNOWN"
        timestamp = vessel_data.get("timestamp", datetime.utcnow().isoformat())

        features = {}

        # 1. Speed Anomaly
        features["speed_anomaly"] = self._calc_speed_anomaly(speed, ship_type)

        # 2. Flag Risk Score
        features["flag_risk_score"] = self._calc_flag_risk(flag)

        # 3. Zone Violation
        zone_info = self._check_zone_violation(lat, lon, flag)
        features["zone_violation"] = zone_info["score"]
        features["zone_name"] = zone_info["zone_name"]
        features["in_critical_zone"] = zone_info["in_critical_zone"]

        # 4. Night Activity
        features["night_activity"] = self._check_night_activity(timestamp)

        # 5. Course Change Rate (butuh data historis)
        features["course_change_rate"] = self._calc_course_change(mmsi, course)

        # 6. Loitering Score (butuh data historis)
        features["loitering_score"] = self._calc_loitering(mmsi, lat, lon)

        # 7. AIS Gap
        features["ais_gap_score"] = self._calc_ais_gap(mmsi)

        # 8. Speed Variance
        features["speed_variance"] = self._calc_speed_variance(mmsi, speed)

        # 9. Is foreign vessel
        features["is_foreign"] = 0.0 if flag in INDONESIA_FLAG_CODES else 1.0

        # 10. Proximity to territorial boundary
        features["proximity_score"] = self._calc_proximity_score(lat, lon)

        # Update cache
        self._update_cache(mmsi, lat, lon, speed, course, timestamp)

        return features

    def _calc_speed_anomaly(self, speed: float, ship_type) -> float:
        """
        Menghitung skor anomali kecepatan berdasarkan tipe kapal.
        Return 0-1 (1 = sangat anomali).
        """
        if speed is None or speed < 0:
            return 0.3  # Unknown speed = sedikit suspicious

        ship_type_name = get_ship_type_name(ship_type)

        # Kecepatan sangat rendah (loitering)
        if speed < ANOMALY_CONFIG["min_speed_loitering"]:
            return 0.4  # Bisa loitering tapi juga bisa docking

        if ship_type_name == "Fishing":
            if speed > ANOMALY_CONFIG["max_speed_fishing"]:
                return min(1.0, (speed - ANOMALY_CONFIG["max_speed_fishing"]) / 10)
        elif ship_type_name in ["Cargo", "Tanker"]:
            if speed > ANOMALY_CONFIG["max_speed_cargo"]:
                return min(1.0, (speed - ANOMALY_CONFIG["max_speed_cargo"]) / 10)

        return 0.0

    def _calc_flag_risk(self, flag: str) -> float:
        """Menghitung skor risiko berdasarkan negara bendera kapal."""
        if flag in INDONESIA_FLAG_CODES:
            return 0.0

        flag_info = HIGH_RISK_FLAGS.get(flag)
        if flag_info:
            return flag_info["risk"]

        # Negara tidak dikenal = moderate risk
        if not flag or flag == "UNKNOWN":
            return 0.8

        return 0.2  # Negara lain = low risk

    def _check_zone_violation(self, lat: float, lon: float, flag: str) -> dict:
        """
        Mengecek apakah kapal berada di zona yang seharusnya tidak boleh.
        """
        result = {
            "score": 0.0,
            "zone_name": "Open Sea",
            "in_critical_zone": False
        }

        # Cek apakah di dalam EEZ Indonesia
        in_eez = self._is_in_bbox(lat, lon, INDONESIA_EEZ_BBOX[0])

        if not in_eez:
            return result

        result["zone_name"] = "Indonesia EEZ"

        # Kapal asing di EEZ Indonesia sudah suspicious
        if flag not in INDONESIA_FLAG_CODES:
            result["score"] = 0.5

        # Cek zona kritis
        for zone_id, zone_info in CRITICAL_ZONES.items():
            if self._is_in_bbox(lat, lon, zone_info["bbox"]):
                result["zone_name"] = zone_info["name"]
                result["in_critical_zone"] = True
                if flag not in INDONESIA_FLAG_CODES:
                    result["score"] = min(1.0,
                        result["score"] * zone_info["risk_multiplier"])
                break

        return result

    def _check_night_activity(self, timestamp: str) -> float:
        """Mengecek apakah aktivitas terjadi di malam hari (WIB)."""
        try:
            if isinstance(timestamp, str):
                dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            else:
                dt = timestamp

            # Konversi ke WIB (UTC+7)
            wib_hour = (dt.hour + 7) % 24

            night_start = ANOMALY_CONFIG["night_start_hour"]
            night_end = ANOMALY_CONFIG["night_end_hour"]

            if wib_hour >= night_start or wib_hour < night_end:
                return 0.6  # Aktivitas malam
        except (ValueError, TypeError):
            pass

        return 0.0

    def _calc_course_change(self, mmsi: str, current_course: float) -> float:
        """
        Menghitung rate perubahan arah kapal.
        Zigzag pattern = menghindari deteksi.
        """
        if mmsi not in self.vessel_cache:
            return 0.0

        cache = self.vessel_cache[mmsi]
        if "courses" not in cache:
            return 0.0

        courses = cache["courses"]
        if len(courses) < 2:
            return 0.0

        # Hitung perubahan arah rata-rata
        total_change = 0
        for i in range(1, len(courses)):
            diff = abs(courses[i] - courses[i-1])
            if diff > 180:
                diff = 360 - diff
            total_change += diff

        avg_change = total_change / len(courses)
        threshold = ANOMALY_CONFIG["course_change_threshold"]

        if avg_change > threshold * 2:
            return 0.9  # Sangat zigzag
        elif avg_change > threshold:
            return 0.6
        elif avg_change > threshold * 0.5:
            return 0.3

        return 0.0

    def _calc_loitering(self, mmsi: str, lat: float, lon: float) -> float:
        """
        Mendeteksi pola loitering (berputar-putar di satu area).
        """
        if mmsi not in self.vessel_cache:
            return 0.0

        cache = self.vessel_cache[mmsi]
        if "positions" not in cache or len(cache["positions"]) < 3:
            return 0.0

        positions = cache["positions"]
        radius_nm = ANOMALY_CONFIG["loitering_radius_nm"]

        # Hitung jarak dari posisi pertama ke semua posisi lain
        first_pos = positions[0]
        max_distance = 0

        for pos in positions[1:]:
            try:
                dist = geodesic(
                    (first_pos[0], first_pos[1]),
                    (pos[0], pos[1])
                ).nautical
                max_distance = max(max_distance, dist)
            except Exception:
                continue

        # Jika semua posisi dalam radius kecil → loitering
        if max_distance < radius_nm and len(positions) >= 5:
            return 0.8
        elif max_distance < radius_nm * 2 and len(positions) >= 3:
            return 0.5

        return 0.0

    def _calc_ais_gap(self, mmsi: str) -> float:
        """
        Mendeteksi gap dalam transmisi AIS (kapal mematikan transponder).
        """
        if mmsi not in self.vessel_cache:
            return 0.0

        cache = self.vessel_cache[mmsi]
        last_seen = cache.get("last_timestamp")

        if not last_seen:
            return 0.0

        try:
            if isinstance(last_seen, str):
                last_dt = datetime.fromisoformat(
                    last_seen.replace("Z", "+00:00"))
            else:
                last_dt = last_seen

            now = datetime.now(timezone.utc)
            gap_minutes = (now - last_dt).total_seconds() / 60

            gap_threshold = ANOMALY_CONFIG["ais_gap_minutes"]

            if gap_minutes > gap_threshold * 3:
                return 0.95  # AIS mati sangat lama
            elif gap_minutes > gap_threshold * 2:
                return 0.7
            elif gap_minutes > gap_threshold:
                return 0.5
        except (ValueError, TypeError):
            pass

        return 0.0

    def _calc_speed_variance(self, mmsi: str, current_speed: float) -> float:
        """Menghitung variasi kecepatan — pola tidak konsisten."""
        if mmsi not in self.vessel_cache:
            return 0.0

        cache = self.vessel_cache[mmsi]
        speeds = cache.get("speeds", [])

        if len(speeds) < 3:
            return 0.0

        # Hitung standar deviasi kecepatan
        mean_speed = sum(speeds) / len(speeds)
        if mean_speed == 0:
            return 0.0

        variance = sum((s - mean_speed) ** 2 for s in speeds) / len(speeds)
        std_dev = math.sqrt(variance)

        # Coefficient of variation
        cv = std_dev / mean_speed if mean_speed > 0 else 0

        if cv > 1.5:
            return 0.8  # Kecepatan sangat tidak konsisten
        elif cv > 1.0:
            return 0.5
        elif cv > 0.5:
            return 0.3

        return 0.0

    def _calc_proximity_score(self, lat: float, lon: float) -> float:
        """
        Menghitung skor berdasarkan kedekatan dengan batas teritorial.
        Kapal yang tepat di batas lebih suspicious.
        """
        # Simplified: hitung jarak ke pusat Indonesia
        indonesia_center = (-2.5, 118.0)
        try:
            dist = geodesic((lat, lon), indonesia_center).nautical
            # Semakin dekat ke pusat Indonesia, semakin dalam di teritori
            if dist < 100:
                return 0.3  # Sangat dalam, mungkin di pelabuhan
            elif dist < 300:
                return 0.5  # Di dalam teritori
            elif dist < 500:
                return 0.7  # Dekat batas
            else:
                return 0.2  # Jauh
        except Exception:
            return 0.0

    def _is_in_bbox(self, lat: float, lon: float, bbox: list) -> bool:
        """Cek apakah koordinat berada dalam bounding box."""
        min_lat, min_lon = bbox[0]
        max_lat, max_lon = bbox[1]
        return min_lat <= lat <= max_lat and min_lon <= lon <= max_lon

    def _update_cache(self, mmsi: str, lat: float, lon: float,
                      speed: float, course: float, timestamp: str):
        """Update cache data kapal untuk kalkulasi fitur historis."""
        if mmsi not in self.vessel_cache:
            self.vessel_cache[mmsi] = {
                "positions": [],
                "speeds": [],
                "courses": [],
                "last_timestamp": None
            }

        cache = self.vessel_cache[mmsi]

        # Simpan maksimal 20 data terakhir
        cache["positions"].append((lat, lon))
        if len(cache["positions"]) > 20:
            cache["positions"].pop(0)

        cache["speeds"].append(speed)
        if len(cache["speeds"]) > 20:
            cache["speeds"].pop(0)

        cache["courses"].append(course)
        if len(cache["courses"]) > 20:
            cache["courses"].pop(0)

        cache["last_timestamp"] = timestamp

    def get_feature_vector(self, features: dict) -> list:
        """
        Konversi fitur dict ke vector numerik untuk model ML.
        """
        feature_names = [
            "speed_anomaly",
            "flag_risk_score",
            "zone_violation",
            "night_activity",
            "course_change_rate",
            "loitering_score",
            "ais_gap_score",
            "speed_variance",
            "is_foreign",
            "proximity_score",
        ]

        return [features.get(name, 0.0) for name in feature_names]

    @staticmethod
    def get_feature_names() -> list:
        """Mendapatkan nama-nama fitur (untuk labeling)."""
        return [
            "speed_anomaly",
            "flag_risk_score",
            "zone_violation",
            "night_activity",
            "course_change_rate",
            "loitering_score",
            "ais_gap_score",
            "speed_variance",
            "is_foreign",
            "proximity_score",
        ]
