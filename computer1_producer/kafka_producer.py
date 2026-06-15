"""
SkyGuard — Kafka Producer
==========================
Wrapper around kafka-python producer for sending flight and news data
to Kafka topics.
"""

import json
import logging
from kafka import KafkaProducer
from shared.config.settings import KAFKA_BOOTSTRAP_SERVERS

logger = logging.getLogger("skyguard.producer")


class SkyGuardProducer:
    """Kafka producer for raw flight data and news intelligence."""

    def __init__(self):
        self.producer = None
        self._connect()

    def _connect(self):
        """Establish connection to Kafka broker."""
        try:
            self.producer = KafkaProducer(
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                key_serializer=lambda k: k.encode("utf-8") if k else None,
                acks="all",
                retries=3,
                max_block_ms=10000,
            )
            logger.info("✅ Kafka producer connected to %s", KAFKA_BOOTSTRAP_SERVERS)
        except Exception as e:
            logger.error("❌ Kafka producer connection failed: %s", e)
            raise

    def send(self, topic, key, value):
        """
        Send a single message to a Kafka topic.

        Args:
            topic: Kafka topic name
            key: Message key (e.g. icao24 for partitioning)
            value: Message value (dict, will be JSON-serialized)
        """
        try:
            future = self.producer.send(topic, key=key, value=value)
            future.get(timeout=10)  # Block until sent
        except Exception as e:
            logger.error("❌ Failed to send message to %s: %s", topic, e)

    def send_batch(self, topic, messages):
        """
        Send a batch of messages to a Kafka topic.

        Args:
            topic: Kafka topic name
            messages: list of (key, value) tuples
        """
        count = 0
        for key, value in messages:
            try:
                self.producer.send(topic, key=key, value=value)
                count += 1
            except Exception as e:
                logger.error("❌ Batch send error: %s", e)

        self.producer.flush()
        logger.info("📤 Sent %d messages to topic '%s'", count, topic)
        return count

    def close(self):
        """Close the producer connection."""
        if self.producer:
            self.producer.flush()
            self.producer.close()
            logger.info("🛑 Kafka producer closed")
