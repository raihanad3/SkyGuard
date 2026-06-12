"""
SkyGuard — Kafka Consumer (Computer 2)
========================================
Consumes raw flight data from Kafka topic using kafka-python.
Used as fallback if Spark Structured Streaming is not available.
"""

import json
import logging
from kafka import KafkaConsumer
from computer2_preprocessing.config.settings import KAFKA_BOOTSTRAP_SERVERS, KAFKA_CONSUMER_GROUP_PREPROCESSING

logger = logging.getLogger("skyguard.preprocessing")


class FlightConsumer:
    """Consume raw flight data from Kafka for preprocessing."""

    def __init__(self, topic, group_id=None):
        self.topic = topic
        self.group_id = group_id or KAFKA_CONSUMER_GROUP_PREPROCESSING
        self.consumer = None

    def connect(self):
        """Connect to Kafka broker."""
        self.consumer = KafkaConsumer(
            self.topic,
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            group_id=self.group_id,
            auto_offset_reset="latest",
            enable_auto_commit=True,
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
            consumer_timeout_ms=5000,
        )
        logger.info("✅ Consumer connected: topic='%s', group='%s'",
                     self.topic, self.group_id)

    def consume(self):
        """
        Generator that yields deserialized messages.

        Yields:
            dict: Deserialized flight data
        """
        if not self.consumer:
            self.connect()

        for message in self.consumer:
            yield message.value

    def close(self):
        """Close consumer connection."""
        if self.consumer:
            self.consumer.close()
            logger.info("🛑 Consumer closed")
