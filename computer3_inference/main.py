"""
SkyGuard — Computer 3: Inference (Main Entry Point)
=====================================================
Consumes preprocessed flight data from Kafka,
runs anomaly detection, generates alerts,
and stores results in PostgreSQL.

Usage:
    python -m computer3_inference.main
"""

import sys
import os
import signal
import logging

# Fix encoding for Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    os.environ.setdefault("PYTHONUTF8", "1")

from computer3_inference.config.settings import LOG_DIR
from computer3_inference.kafka_consumer import InferenceConsumer
from computer3_inference.anomaly_detector import AnomalyDetector
from computer3_inference.alert_system import AlertSystem
from computer3_inference.store_results import ResultStore


def setup_logging():
    """Setup logging for Computer 3."""
    os.makedirs(LOG_DIR, exist_ok=True)

    logger = logging.getLogger("skyguard.inference")
    logger.setLevel(logging.INFO)

    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S"
    ))
    logger.addHandler(ch)

    fh = logging.FileHandler(
        os.path.join(LOG_DIR, "computer3_inference.log"), encoding="utf-8"
    )
    fh.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    logger.addHandler(fh)

    return logger


def print_banner():
    banner = """
╔══════════════════════════════════════════════════════════════╗
║  SKYGUARD — Computer 3: Anomaly Inference                  ║
║  Kafka Consumer → Anomaly Detection → PostgreSQL           ║
╚══════════════════════════════════════════════════════════════╝
"""
    print(banner)


def main():
    logger = setup_logging()
    print_banner()

    logger.info("🔧 Initializing Computer 3 — Inference...")

    # Initialize components
    consumer = InferenceConsumer()
    consumer.connect()

    detector = AnomalyDetector()
    alert_system = AlertSystem()
    store = ResultStore()

    logger.info("✅ All components initialized")
    logger.info("🚀 Starting inference loop...")

    running = True
    total_processed = 0
    total_alerts = 0

    def _signal_handler(sig, frame):
        nonlocal running
        logger.info("🛑 Shutdown signal received")
        running = False

    signal.signal(signal.SIGINT, _signal_handler)

    try:
        while running:
            # Poll for preprocessed data
            messages = consumer.poll(timeout_ms=1000)

            if not messages:
                continue

            inference_batch = []
            batch_alerts = 0

            for features in messages:
                total_processed += 1

                # Run anomaly detection
                analysis = detector.analyze(features)
                inference_batch.append(analysis)

                # Process alerts
                alert_data = alert_system.process(analysis)
                if alert_data:
                    store.store_alert(alert_data)
                    batch_alerts += 1
                    total_alerts += 1

                # Update flight metadata
                store.store_flight_info(
                    features.get("icao24"),
                    features.get("callsign"),
                    features.get("origin_country"),
                )

            # Store inference results in batch
            store.store_inference_batch(inference_batch)

            logger.info(
                "🧠 Batch: %d inferred, %d alerts | Total: %d processed, %d alerts",
                len(inference_batch), batch_alerts,
                total_processed, total_alerts,
            )

    except KeyboardInterrupt:
        logger.info("🛑 Interrupted")
    finally:
        consumer.close()
        store.close()
        logger.info("👋 Computer 3 shutdown complete")


if __name__ == "__main__":
    main()
