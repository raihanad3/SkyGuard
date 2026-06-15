"""
SkyGuard — Kafka Consumer (Computer 3)
========================================
Consumes preprocessed flight data from Kafka for inference.
Listens to either:
  - 'preprocessed-flight-data' (from Computer 2 Kafka forward)
  - 'dbserver1.public.preprocessed_flights' (from Debezium CDC)
"""

import json
import logging
from kafka import KafkaConsumer

from shared.config.settings import (
    KAFKA_BOOTSTRAP_SERVERS,
    KAFKA_TOPIC_PREPROCESSED,
    KAFKA_CONSUMER_GROUP_INFERENCE,
)

logger = logging.getLogger("skyguard.inference")


class InferenceConsumer:
    """Consume preprocessed data for anomaly inference."""

    def __init__(self, topic=None, group_id=None):
        self.topic = topic or KAFKA_TOPIC_PREPROCESSED
        self.group_id = group_id or KAFKA_CONSUMER_GROUP_INFERENCE
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
        )
        logger.info("✅ Inference consumer connected: topic='%s', group='%s'",
                     self.topic, self.group_id)

    def poll(self, timeout_ms=1000):
        """
        Poll for new messages.

        Returns:
            list of deserialized preprocessed flight dicts
        """
        if not self.consumer:
            self.connect()

        records = self.consumer.poll(timeout_ms=timeout_ms)
        messages = []
        for tp, msgs in records.items():
            for msg in msgs:
                messages.append(msg.value)
        return messages

    def close(self):
        """Close consumer."""
        if self.consumer:
            self.consumer.close()
            logger.info("🛑 Inference consumer closed")
