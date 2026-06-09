"""
Model Trainer — Periodic training dan retraining
Isolation Forest model.
"""

import asyncio
import logging
from datetime import datetime

from core.config import ANOMALY_CONFIG

logger = logging.getLogger("vessel_anomaly")


class ModelTrainer:
    """
    Periodic model trainer.
    Retrain Isolation Forest setiap N jam dengan data baru.
    """

    def __init__(self, anomaly_detector, db_manager):
        self.detector = anomaly_detector
        self.db = db_manager
        self.is_running = False
        self.last_training_time = None
        self.training_count = 0

    async def start_periodic_training(self):
        """Mulai periodic training loop."""
        self.is_running = True
        interval_hours = ANOMALY_CONFIG["retrain_interval_hours"]
        interval_seconds = interval_hours * 3600

        logger.info(
            "🎓 Model trainer started (retrain every %d hours)",
            interval_hours
        )

        while self.is_running:
            # Tunggu interval
            await asyncio.sleep(interval_seconds)

            if not self.is_running:
                break

            # Train model
            logger.info("🔄 Starting periodic model retraining...")
            result = self.detector.train_model()

            if result:
                self.training_count += 1
                self.last_training_time = datetime.utcnow().isoformat()

                # Simpan metrics ke database
                self.db.insert_model_metrics(result)

                logger.info(
                    "✅ Model retrained successfully (#%d) - "
                    "%d samples, %.2f%% anomaly ratio",
                    self.training_count,
                    result["training_samples"],
                    result["anomaly_ratio"] * 100
                )
            else:
                logger.info("⏳ Model retraining skipped (not enough data)")

    async def initial_training_check(self):
        """
        Cek apakah ada cukup data untuk training awal.
        Dipanggil setelah beberapa menit streaming.
        """
        min_samples = ANOMALY_CONFIG["min_samples_for_training"]

        logger.info(
            "⏳ Waiting for minimum %d samples before initial training...",
            min_samples
        )

        while self.is_running:
            await asyncio.sleep(30)  # Check setiap 30 detik

            current_samples = len(self.detector.training_data)

            if current_samples >= min_samples:
                logger.info(
                    "📊 Minimum samples reached (%d). Starting initial training...",
                    current_samples
                )
                result = self.detector.train_model()

                if result:
                    self.training_count += 1
                    self.last_training_time = datetime.utcnow().isoformat()
                    self.db.insert_model_metrics(result)
                    logger.info(
                        "✅ Initial model training complete! "
                        "ML-based detection is now active."
                    )
                break

            if current_samples > 0 and current_samples % 10 == 0:
                logger.info(
                    "📊 Collecting data: %d/%d samples",
                    current_samples, min_samples
                )

    def stop(self):
        """Stop trainer."""
        self.is_running = True
        logger.info("🛑 Model trainer stopping...")

    def get_info(self) -> dict:
        """Get trainer info."""
        return {
            "training_count": self.training_count,
            "last_training_time": self.last_training_time,
            "model_info": self.detector.get_model_info()
        }
