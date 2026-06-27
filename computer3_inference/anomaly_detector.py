"""
SkyGuard — Anomaly Detector (Computer 3)
==========================================
Rule-based anomaly detection on preprocessed flight features.
Migrated from modules/anomaly_model.py.
Structure is ready for ML model integration.
"""

import math
import time
import logging
import numpy as np
import psycopg2
from sklearn.ensemble import IsolationForest
from sklearn.svm import OneClassSVM
from sklearn.neighbors import LocalOutlierFactor
from shared.config.settings import ANOMALY_CONFIG, ALERT_THRESHOLDS

logger = logging.getLogger("skyguard.inference")

def haversine(lat1, lon1, lat2, lon2):
    R = 3440.065 # Radius of earth in Nautical Miles
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    return R * c


class AnomalyDetector:
    """Detect anomalous flight behavior from preprocessed features using Rule-based + 3 ML Models."""

    def __init__(self):
        self.config = ANOMALY_CONFIG
        self.models_trained = False
        self.warmup_data = []
        self.warmup_limit = 100

        # Initialize the 3 unsupervised ML models
        self.model_forest = IsolationForest(contamination=0.05, random_state=42)
        self.model_svm = OneClassSVM(nu=0.05, kernel="rbf")
        self.model_lof = LocalOutlierFactor(n_neighbors=20, novelty=True, contamination=0.05)

        # Attempt to train using history
        self._init_training()

    def _init_training(self):
        """Try to load historical data from PostgreSQL and train the models.
        If it fails or has insufficient data, it leaves models_trained = False to trigger warmup."""
        from shared.config.settings import (
            POSTGRES_HOST, POSTGRES_PORT,
            POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB
        )
        logger.info("🧠 ML Anomaly Detector: Initializing models...")
        try:
            conn = psycopg2.connect(
                host=POSTGRES_HOST,
                port=POSTGRES_PORT,
                user=POSTGRES_USER,
                password=POSTGRES_PASSWORD,
                dbname=POSTGRES_DB,
                connect_timeout=3
            )
            cursor = conn.cursor()
            cursor.execute("""
                SELECT latitude, longitude, altitude_feet, speed_knots, heading, COALESCE(climb_rate_fpm, 0)
                FROM preprocessed_flights
                WHERE latitude IS NOT NULL AND longitude IS NOT NULL
                LIMIT 1000
            """)
            rows = cursor.fetchall()
            cursor.close()
            conn.close()

            if len(rows) >= 100:
                logger.info(f"📊 Found {len(rows)} historical records in PostgreSQL. Training models...")
                self._train_models(rows)
                logger.info("✅ ML Models trained successfully on historical data (Opsi B).")
            else:
                logger.info(f"⚠️ Insufficient historical records in DB ({len(rows)}/100). Switching to Warm-up mode (Opsi A).")
        except Exception as e:
            logger.warning(f"⚠️ Cannot connect to DB for historical training ({e}). Switching to Warm-up mode (Opsi A).")

    def _train_models(self, data_list):
        """Train scikit-learn models on provided coordinate and flight dynamic features."""
        try:
            X = np.array(data_list, dtype=float)
            X = np.nan_to_num(X, nan=0.0, posinf=999999.0, neginf=-999999.0)

            # Fit Isolation Forest (Model 1)
            self.model_forest.fit(X)

            # Fit One-Class SVM (Model 2)
            self.model_svm.fit(X)

            # Fit Local Outlier Factor (Model 3)
            self.model_lof.fit(X)

            self.models_trained = True
        except Exception as e:
            logger.error(f"❌ Error training ML models: {e}")
            self.models_trained = False

    def _check_warmup_and_train(self, features):
        """Add current features to warmup buffer. Train when buffer limit reached."""
        if self.models_trained:
            return

        lat = features.get("latitude")
        lon = features.get("longitude")
        alt = features.get("altitude_feet") or features.get("altitude") or 0
        spd = features.get("speed_knots") or features.get("speed") or 0
        hdg = features.get("heading") or 0
        rate = features.get("climb_rate_fpm") or features.get("vertical_rate") or 0

        if lat is not None and lon is not None:
            self.warmup_data.append([lat, lon, alt, spd, hdg, rate])

        if len(self.warmup_data) >= self.warmup_limit:
            logger.info(f"🚀 Warm-up buffer reached {self.warmup_limit} items! Training ML models dynamically (Opsi A)...")
            self._train_models(self.warmup_data)
            self.warmup_data = []

    def detect_conflicts(self, batch):
        conflicts = {}
        for i in range(len(batch)):
            f1 = batch[i]
            if f1.get('on_ground') or not f1.get('latitude') or not f1.get('longitude') or not f1.get('altitude_feet'): continue
            for j in range(i+1, len(batch)):
                f2 = batch[j]
                if f2.get('on_ground') or not f2.get('latitude') or not f2.get('longitude') or not f2.get('altitude_feet'): continue
                
                alt_diff = abs(f1['altitude_feet'] - f2['altitude_feet'])
                if alt_diff < 1000: # 1000 ft vertical separation
                    dist_nm = haversine(f1['latitude'], f1['longitude'], f2['latitude'], f2['longitude'])
                    if dist_nm < 5.0: # 5 NM horizontal separation
                        conflicts.setdefault(f1['icao24'], []).append(f2['callsign'] or f2['icao24'])
                        conflicts.setdefault(f2['icao24'], []).append(f1['callsign'] or f1['icao24'])
        return conflicts

    def analyze(self, features):
        """
        Run anomaly detection on preprocessed flight features.

        Args:
            features: dict with preprocessed fields
                (icao24, altitude_feet, speed_knots, heading,
                 in_restricted_zone, near_airport, squawk, etc.)

        Returns:
            dict with anomaly_score, alert_level, reasons
        """
        score = 0.0
        reasons = []

        # --- ML Prediction & Scoring (Hybrid Warmup/Inference) ---
        ml_score = 0.0
        ml_reasons = []

        if not self.models_trained:
            self._check_warmup_and_train(features)
        
        if self.models_trained:
            try:
                lat = features.get("latitude")
                lon = features.get("longitude")
                alt = features.get("altitude_feet") or features.get("altitude") or 0
                spd = features.get("speed_knots") or features.get("speed") or 0
                hdg = features.get("heading") or 0
                rate = features.get("climb_rate_fpm") or features.get("vertical_rate") or 0

                if lat is not None and lon is not None:
                    sample = np.array([[lat, lon, alt, spd, hdg, rate]], dtype=float)
                    sample = np.nan_to_num(sample, nan=0.0)

                    # Model 1: Isolation Forest (predict: -1 = anomaly, 1 = normal)
                    pred_forest = self.model_forest.predict(sample)[0]
                    # Model 2: One-Class SVM
                    pred_svm = self.model_svm.predict(sample)[0]
                    # Model 3: Local Outlier Factor
                    pred_lof = self.model_lof.predict(sample)[0]

                    if pred_forest == -1:
                        ml_score += 0.25
                        ml_reasons.append("ML: Isolation Forest flagged abnormal flight profile")
                    if pred_svm == -1:
                        ml_score += 0.25
                        ml_reasons.append("ML: One-Class SVM flagged spatial coordinate anomaly")
                    if pred_lof == -1:
                        ml_score += 0.25
                        ml_reasons.append("ML: Local Outlier Factor flagged abnormal flight density/dynamics")
            except Exception as e:
                logger.error(f"Error during ML inference prediction: {e}")

        score += ml_score
        reasons.extend(ml_reasons)

        # --- Rule 1: Restricted zone entry ---
        if features.get("in_restricted_zone"):
            score += 0.4
            reasons.append(
                f"Entered restricted zone: {features.get('restricted_zone_name')}"
            )

        # --- Rule 2: Suspicious altitude ---
        altitude = features.get("altitude_feet", 0) or 0
        near_airport = features.get("near_airport", False)

        if altitude and not near_airport:
            if altitude < self.config["min_safe_altitude"]:
                score += 0.3
                reasons.append(
                    f"Very low altitude: {int(altitude)} ft (not near airport)"
                )
            elif altitude > self.config["max_normal_altitude"]:
                score += 0.2
                reasons.append(f"Unusually high altitude: {int(altitude)} ft")

        # --- Rule 3: Abnormal speed ---
        speed = features.get("speed_knots", 0) or 0
        on_ground = features.get("on_ground", False)

        if not on_ground and speed:
            if speed < self.config["min_cruise_speed"]:
                score += 0.2
                reasons.append(f"Unusually slow: {int(speed)} knots")
            elif speed > self.config["max_normal_speed"]:
                score += 0.25
                reasons.append(f"Very high speed: {int(speed)} knots")

        # --- Rule 4: Rapid climb / descent & MSAW ---
        climb_rate = features.get("climb_rate_fpm", 0) or 0
        if abs(climb_rate) > self.config["rapid_climb_rate"]:
            score += 0.25
            direction = "climb" if climb_rate > 0 else "descent"
            reasons.append(f"Rapid {direction}: {int(abs(climb_rate))} ft/min")
            
            # MSAW (Minimum Safe Altitude Warning)
            if climb_rate < -1000 and altitude < 5000 and not near_airport and not on_ground:
                score += 0.8
                reasons.append("MSAW: Rapid descent at low altitude")

        # --- Rule 5: Sudden course change ---
        heading_change = features.get("heading_change", 0) or 0
        if heading_change > self.config["erratic_course_change"]:
            score += 0.2
            reasons.append(f"Sudden course change: {int(heading_change)}°")

        # --- Rule 6: Emergency squawk codes ---
        squawk = features.get("squawk")
        if squawk:
            if squawk == "7500":  # hijack
                score += 1.0
                reasons.append("EMERGENCY: Hijack code (7500)")
            elif squawk == "7600":  # radio failure
                score += 0.6
                reasons.append("EMERGENCY: Radio failure (7600)")
            elif squawk == "7700":  # general emergency
                score += 0.8
                reasons.append("EMERGENCY: General emergency (7700)")

        # --- Rule 7: Loss of Communication ---
        last_contact = features.get("last_contact")
        if last_contact:
            # Assuming last_contact is epoch seconds
            age = time.time() - last_contact
            if age > 300: # 5 minutes
                score += 0.4
                reasons.append(f"Loss of Comms: >{int(age/60)} mins")

        # --- Rule 8: STCA (Short Term Conflict Alert) ---
        stca_conflicts = features.get("stca_conflicts")
        if stca_conflicts:
            score += 0.9
            reasons.append(f"STCA: Conflict with {', '.join(stca_conflicts)}")

        # Apply restricted zone multiplier
        if features.get("in_restricted_zone"):
            score *= features.get("zone_risk_multiplier", 1.0)

        # Cap at 1.0
        score = min(score, 1.0)

        # Determine alert level
        alert_level = "NORMAL"
        if score >= ALERT_THRESHOLDS["HIGH"]:
            alert_level = "HIGH"
        elif score >= ALERT_THRESHOLDS["MEDIUM"]:
            alert_level = "MEDIUM"
        elif score >= ALERT_THRESHOLDS["LOW"]:
            alert_level = "LOW"

        return {
            "icao24": features.get("icao24"),
            "callsign": features.get("callsign"),
            "origin_country": features.get("origin_country"),
            "latitude": features.get("latitude"),
            "longitude": features.get("longitude"),
            "altitude": features.get("altitude_feet", 0),
            "speed": features.get("speed_knots", 0),
            "heading": features.get("heading", 0),
            "anomaly_score": round(score, 3),
            "alert_level": alert_level,
            "reasons": reasons,
            "zone_name": features.get("restricted_zone_name", ""),
            "near_airport": near_airport,
            "airport_code": features.get("airport_code"),
            "airport_name": features.get("airport_name"),
            "squawk": squawk,
            "last_contact": last_contact,
            "vertical_rate": features.get("vertical_rate"),
            "timestamp": features.get("raw_timestamp"),
        }
