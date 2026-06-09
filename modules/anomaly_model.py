"""
Anomaly Detection Model — Hybrid approach yang menggabungkan
Rule-Based Detection dan Isolation Forest untuk mendeteksi
kapal anomali di perairan Indonesia.
"""

import os
import logging
import numpy as np
from datetime import datetime
from sklearn.ensemble import IsolationForest
import joblib

from core.config import (
    ANOMALY_CONFIG, ALERT_THRESHOLDS, INDONESIA_FLAG_CODES,
    MODEL_PATH, MODEL_DIR, get_ship_type_name
)
from modules.feature_engine import FeatureEngine

logger = logging.getLogger("vessel_anomaly")


class AnomalyDetector:
    """
    Hybrid Anomaly Detector:
    - Layer 1: Rule-Based (deteksi instan untuk pelanggaran jelas)
    - Layer 2: Isolation Forest (ML untuk pola kompleks)
    - Layer 3: Composite Score (gabungan kedua layer)
    """

    def __init__(self, feature_engine: FeatureEngine):
        self.feature_engine = feature_engine
        self.model = None
        self.model_trained = False
        self.training_data = []
        self._load_model()

    def _load_model(self):
        """Load model yang sudah di-save sebelumnya."""
        if os.path.exists(MODEL_PATH):
            try:
                self.model = joblib.load(MODEL_PATH)
                self.model_trained = True
                logger.info("✅ Model loaded successfully from %s", MODEL_PATH)
            except Exception as e:
                logger.warning("⚠️ Failed to load model: %s", e)
                self._init_new_model()
        else:
            self._init_new_model()

    def _init_new_model(self):
        """Inisialisasi model Isolation Forest baru."""
        self.model = IsolationForest(
            n_estimators=ANOMALY_CONFIG["n_estimators"],
            contamination=ANOMALY_CONFIG["contamination"],
            random_state=42,
            n_jobs=-1
        )
        self.model_trained = False
        logger.info("🆕 New Isolation Forest model initialized")

    def analyze(self, vessel_data: dict) -> dict:
        """
        Analisis satu data point kapal dan return hasil deteksi.

        Returns:
            Dict berisi anomaly_score, alert_level, reasons, features
        """
        # Extract features
        features = self.feature_engine.extract_features(vessel_data)
        feature_vector = self.feature_engine.get_feature_vector(features)

        # Layer 1: Rule-Based Detection
        rule_result = self._rule_based_check(vessel_data, features)

        # Layer 2: ML-Based Detection (jika model sudah trained)
        ml_score = self._ml_score(feature_vector)

        # Layer 3: Composite Score
        composite_score = self._composite_score(
            rule_result["score"],
            ml_score,
            features
        )

        # Determine alert level
        alert_level = self._determine_alert_level(composite_score)

        # Collect training data
        self.training_data.append(feature_vector)

        result = {
            "mmsi": vessel_data.get("mmsi"),
            "anomaly_score": round(composite_score, 3),
            "alert_level": alert_level,
            "rule_score": round(rule_result["score"], 3),
            "ml_score": round(ml_score, 3) if ml_score is not None else None,
            "reasons": rule_result["reasons"],
            "features": features,
            "feature_vector": feature_vector,
            "latitude": vessel_data.get("latitude"),
            "longitude": vessel_data.get("longitude"),
            "speed": vessel_data.get("speed"),
            "ship_name": vessel_data.get("ship_name"),
            "flag_country": vessel_data.get("flag_country"),
            "zone_name": features.get("zone_name", "Unknown"),
            "timestamp": datetime.utcnow().isoformat()
        }

        return result

    def _rule_based_check(self, vessel_data: dict, features: dict) -> dict:
        """
        Layer 1: Deteksi berbasis aturan.
        Memberikan score dan alasan spesifik.
        """
        score = 0.0
        reasons = []

        flag = vessel_data.get("flag_country", "UNKNOWN") or "UNKNOWN"
        speed = vessel_data.get("speed", 0) or 0
        ship_type = vessel_data.get("ship_type")
        ship_type_name = get_ship_type_name(ship_type)

        # Rule 1: Kapal asing di EEZ Indonesia
        if features.get("is_foreign", 0) > 0 and features.get("zone_violation", 0) > 0:
            score += 0.4
            reasons.append(
                f"Kapal asing ({flag}) terdeteksi di {features.get('zone_name', 'Indonesia EEZ')}")

        # Rule 2: Kapal fishing asing di zona Indonesia
        if ship_type_name == "Fishing" and flag not in INDONESIA_FLAG_CODES:
            if features.get("zone_violation", 0) > 0:
                score += 0.3
                reasons.append(
                    f"Kapal fishing asing ({flag}) beroperasi di zona Indonesia")

        # Rule 3: Kecepatan anomali
        if features.get("speed_anomaly", 0) > 0.5:
            score += 0.2
            reasons.append(
                f"Kecepatan tidak wajar: {speed:.1f} knots untuk {ship_type_name}")

        # Rule 4: Loitering pattern
        if features.get("loitering_score", 0) > 0.5:
            score += 0.25
            reasons.append("Pola loitering terdeteksi (berputar di satu area)")

        # Rule 5: Aktivitas malam hari
        if features.get("night_activity", 0) > 0 and features.get("is_foreign", 0) > 0:
            score += 0.15
            reasons.append("Aktivitas malam hari oleh kapal asing")

        # Rule 6: AIS gap
        if features.get("ais_gap_score", 0) > 0.5:
            score += 0.2
            reasons.append(
                "Gap transmisi AIS terdeteksi (kemungkinan transponder dimatikan)")

        # Rule 7: Zigzag pattern (course change tinggi)
        if features.get("course_change_rate", 0) > 0.5:
            score += 0.15
            reasons.append("Pola zigzag terdeteksi (menghindari deteksi)")

        # Rule 8: Di zona kritis
        if features.get("in_critical_zone", False) and features.get("is_foreign", 0) > 0:
            score += 0.2
            reasons.append(
                f"Kapal asing di zona kritis: {features.get('zone_name')}")

        # Rule 9: Flag negara berisiko tinggi
        if features.get("flag_risk_score", 0) > 0.7:
            score += 0.15
            reasons.append(
                f"Negara bendera berisiko tinggi: {flag}")

        # Rule 10: 🆕 DARK VESSEL - Kapal masuk Indonesia lalu hilang
        dark_vessel_score = features.get("dark_vessel_score", 0)
        time_since_entry = features.get("time_since_entry_minutes", 0)
        is_quick_disappearance = features.get("is_quick_disappearance", False)
        
        if dark_vessel_score > 0.5:
            # Kapal baru masuk < 1 jam = SANGAT SUSPICIOUS
            if time_since_entry > 0 and time_since_entry < 60:
                score += 0.35
                reasons.append(
                    f"⚠️ DARK VESSEL THREAT: Kapal asing masuk Indonesia "
                    f"{time_since_entry:.0f} menit lalu, pola mencurigakan terdeteksi"
                )
            elif time_since_entry > 0:
                score += 0.2
                reasons.append(
                    f"Kapal asing baru masuk Indonesia ({time_since_entry:.0f} menit lalu)"
                )

        # Clamp score 0-1
        score = min(1.0, score)

        return {"score": score, "reasons": reasons}

    def _ml_score(self, feature_vector: list) -> float:
        """
        Layer 2: Skor anomali dari Isolation Forest.
        Returns None jika model belum di-train.
        """
        if not self.model_trained:
            return None

        try:
            # Isolation Forest score: -1 (anomaly) to 1 (normal)
            raw_score = self.model.decision_function(
                np.array([feature_vector])
            )[0]

            # Konversi ke 0-1 (0 = normal, 1 = anomaly)
            # decision_function returns negative for anomalies
            normalized = max(0.0, min(1.0, -raw_score))
            return normalized
        except Exception as e:
            logger.error("ML scoring error: %s", e)
            return None

    def _composite_score(self, rule_score: float, ml_score: float,
                         features: dict) -> float:
        """
        Layer 3: Gabungkan skor rule-based dan ML.
        """
        if ml_score is not None:
            # Weighted average: 60% rule, 40% ML
            base_score = (rule_score * 0.6) + (ml_score * 0.4)
        else:
            # Hanya rule-based jika ML belum ready
            base_score = rule_score

        # Bonus score untuk kombinasi faktor risiko
        bonus = 0.0

        # Foreign + night + critical zone = sangat suspicious
        if (features.get("is_foreign", 0) > 0 and
            features.get("night_activity", 0) > 0 and
            features.get("in_critical_zone", False)):
            bonus += 0.1

        # Loitering + fishing vessel = kemungkinan IUU
        if (features.get("loitering_score", 0) > 0.5 and
            features.get("flag_risk_score", 0) > 0.5):
            bonus += 0.1

        # 🆕 Dark Vessel + AIS Gap = EXTREME THREAT
        if (features.get("dark_vessel_score", 0) > 0.5 and
            features.get("ais_gap_score", 0) > 0.5):
            bonus += 0.15  # Massive bonus untuk kombinasi ini

        return min(1.0, base_score + bonus)

    def _determine_alert_level(self, score: float) -> str:
        """Menentukan level alert berdasarkan score."""
        if score >= ALERT_THRESHOLDS["HIGH"]:
            return "HIGH"
        elif score >= ALERT_THRESHOLDS["MEDIUM"]:
            return "MEDIUM"
        elif score >= ALERT_THRESHOLDS["LOW"]:
            return "LOW"
        return "NORMAL"

    def train_model(self, force=False):
        """
        Train atau retrain Isolation Forest model.
        """
        min_samples = ANOMALY_CONFIG["min_samples_for_training"]

        if len(self.training_data) < min_samples and not force:
            logger.info(
                "⏳ Not enough data for training: %d/%d",
                len(self.training_data), min_samples
            )
            return False

        try:
            X = np.array(self.training_data)
            self.model.fit(X)
            self.model_trained = True

            # Save model
            os.makedirs(MODEL_DIR, exist_ok=True)
            joblib.dump(self.model, MODEL_PATH)

            # Hitung anomaly ratio
            predictions = self.model.predict(X)
            anomaly_count = (predictions == -1).sum()
            anomaly_ratio = anomaly_count / len(predictions)

            logger.info(
                "✅ Model trained with %d samples, anomaly ratio: %.2f%%",
                len(self.training_data), anomaly_ratio * 100
            )

            return {
                "model_version": datetime.utcnow().strftime("%Y%m%d_%H%M%S"),
                "training_samples": len(self.training_data),
                "anomaly_ratio": anomaly_ratio,
                "features_used": FeatureEngine.get_feature_names()
            }

        except Exception as e:
            logger.error("❌ Model training failed: %s", e)
            return False

    def get_model_info(self) -> dict:
        """Mendapatkan informasi tentang model saat ini."""
        return {
            "model_trained": self.model_trained,
            "training_samples": len(self.training_data),
            "min_samples_needed": ANOMALY_CONFIG["min_samples_for_training"],
            "model_type": "IsolationForest",
            "contamination": ANOMALY_CONFIG["contamination"],
            "n_estimators": ANOMALY_CONFIG["n_estimators"]
        }
