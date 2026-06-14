"""
SkyGuard — Computer 2: Preprocessing (Main Entry Point)
=========================================================
Consumes raw flight data + news from Kafka, applies:
- Feature extraction
- NLP sentiment analysis
- Regional risk scoring
- Time-window correlation

Stores preprocessed data + hybrid alerts.

Usage:
    # With Spark + News processing
    python -m computer2_preprocessing.main --spark --enable-news

    # Fallback mode
    python -m computer2_preprocessing.main
"""

import sys
import os
import json
import signal
import logging
import argparse

# Fix encoding for Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    os.environ.setdefault("PYTHONUTF8", "1")

from computer2_preprocessing.config.settings import (
    LOG_DIR,
    KAFKA_BOOTSTRAP_SERVERS,
    KAFKA_TOPIC_RAW_FLIGHT,
    KAFKA_TOPIC_PREPROCESSED,
    KAFKA_CONSUMER_GROUP_PREPROCESSING,
)


def setup_logging():
    """Setup logging for Computer 2."""
    os.makedirs(LOG_DIR, exist_ok=True)

    logger = logging.getLogger("skyguard.preprocessing")
    logger.setLevel(logging.INFO)

    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S"
    ))
    logger.addHandler(ch)

    fh = logging.FileHandler(
        os.path.join(LOG_DIR, "computer2_preprocessing.log"), encoding="utf-8"
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
║  SKYGUARD — Computer 2: Streaming Preprocessing            ║
║  Kafka Consumer → Spark/Feature Engine → PostgreSQL        ║
╚══════════════════════════════════════════════════════════════╝
"""
    print(banner)


def run_spark_mode(logger):
    """Run with Spark Structured Streaming."""
    logger.info("🔥 Starting Spark Structured Streaming mode...")

    from computer2_preprocessing.spark_preprocessor import start_streaming
    start_streaming()


def run_fallback_mode(logger):
    """Run without Spark — use kafka-python + psycopg2 directly."""
    from kafka import KafkaConsumer, KafkaProducer

    from computer2_preprocessing.feature_engine import FeatureEngine
    from computer2_preprocessing.store_preprocessed import PreprocessedStore

    logger.info("📦 Starting fallback mode (no Spark)...")

    # Initialize components
    feature_engine = FeatureEngine()
    store = PreprocessedStore()

    consumer = KafkaConsumer(
        KAFKA_TOPIC_RAW_FLIGHT,
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        group_id=KAFKA_CONSUMER_GROUP_PREPROCESSING,
        auto_offset_reset="latest",
        enable_auto_commit=True,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
    )

    # Forward producer (to send preprocessed data downstream)
    forward_producer = KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        key_serializer=lambda k: k.encode("utf-8") if k else None,
    )

    logger.info("✅ Consumer: topic='%s'", KAFKA_TOPIC_RAW_FLIGHT)
    logger.info("✅ Forward:  topic='%s'", KAFKA_TOPIC_PREPROCESSED)

    running = True

    def _signal_handler(sig, frame):
        nonlocal running
        logger.info("🛑 Shutdown signal received")
        running = False

    signal.signal(signal.SIGINT, _signal_handler)

    batch = []
    batch_size = 50
    msg_count = 0

    try:
        while running:
            # Poll with timeout
            records = consumer.poll(timeout_ms=1000)

            for topic_partition, messages in records.items():
                for message in messages:
                    flight_data = message.value
                    msg_count += 1

                    # Extract features
                    features = feature_engine.extract_features(flight_data)
                    batch.append(features)

                    # Forward preprocessed data to Kafka
                    try:
                        forward_producer.send(
                            KAFKA_TOPIC_PREPROCESSED,
                            key=features["icao24"],
                            value=features,
                        )
                    except Exception as e:
                        logger.error("Forward error: %s", e)

                    # Store batch when full
                    if len(batch) >= batch_size:
                        store.store_batch(batch)
                        forward_producer.flush()
                        logger.info(
                            "📊 Processed %d messages (total: %d)",
                            len(batch), msg_count
                        )
                        batch = []

            # Store remaining
            if batch and not records:
                store.store_batch(batch)
                forward_producer.flush()
                batch = []

    except KeyboardInterrupt:
        logger.info("🛑 Interrupted")
    finally:
        if batch:
            store.store_batch(batch)
        consumer.close()
        forward_producer.close()
        store.close()
        logger.info("👋 Computer 2 shutdown complete")


def main():
    parser = argparse.ArgumentParser(description="SkyGuard Computer 2 — Preprocessing")
    parser.add_argument(
        "--spark", action="store_true",
        help="Use Spark Structured Streaming (requires PySpark + JDK)"
    )
    args = parser.parse_args()

    logger = setup_logging()
    print_banner()

    if args.spark:
        run_spark_mode(logger)
    else:
        run_fallback_mode(logger)


if __name__ == "__main__":
    main()
