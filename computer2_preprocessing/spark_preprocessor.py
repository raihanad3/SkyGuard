"""
SkyGuard — Spark Structured Streaming Preprocessor (Computer 2)
================================================================
Reads raw flight data from Kafka topic 'raw-flight-data',
applies feature extraction via Spark Structured Streaming,
and writes preprocessed data to:
  1. PostgreSQL table 'preprocessed_flights'
  2. Kafka topic 'preprocessed-flight-data' (for downstream consumption)
"""

import json
import logging

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, from_json, udf, struct, to_json, current_timestamp
)
from pyspark.sql.types import (
    StructType, StructField, StringType, DoubleType,
    BooleanType, LongType, FloatType
)

from computer2_preprocessing.config.settings import (
    KAFKA_BOOTSTRAP_SERVERS,
    KAFKA_TOPIC_RAW_FLIGHT,
    KAFKA_TOPIC_PREPROCESSED,
    POSTGRES_JDBC_URL,
    POSTGRES_USER,
    POSTGRES_PASSWORD,
)

logger = logging.getLogger("skyguard.preprocessing")


# ============================================================
# Schema for raw flight data from Kafka
# ============================================================
RAW_FLIGHT_SCHEMA = StructType([
    StructField("icao24", StringType(), True),
    StructField("callsign", StringType(), True),
    StructField("origin_country", StringType(), True),
    StructField("time_position", LongType(), True),
    StructField("last_contact", LongType(), True),
    StructField("longitude", DoubleType(), True),
    StructField("latitude", DoubleType(), True),
    StructField("baro_altitude", DoubleType(), True),
    StructField("on_ground", BooleanType(), True),
    StructField("velocity", DoubleType(), True),
    StructField("true_track", DoubleType(), True),
    StructField("vertical_rate", DoubleType(), True),
    StructField("sensors", StringType(), True),
    StructField("geo_altitude", DoubleType(), True),
    StructField("squawk", StringType(), True),
    StructField("spi", BooleanType(), True),
    StructField("position_source", LongType(), True),
    StructField("timestamp", StringType(), True),
])


def create_spark_session():
    """Create SparkSession with Kafka and PostgreSQL support."""
    spark = (
        SparkSession.builder
        .appName("SkyGuard-Preprocessing")
        .config("spark.jars.packages",
                "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.1,"
                "org.postgresql:postgresql:42.7.3")
        .config("spark.sql.streaming.checkpointLocation",
                "/tmp/skyguard_checkpoint")
        .config("spark.driver.memory", "2g")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")
    return spark


def start_streaming():
    """
    Start the Spark Structured Streaming pipeline.

    Pipeline:
        Kafka (raw-flight-data)
        → parse JSON
        → feature extraction (UDFs)
        → write to PostgreSQL (foreachBatch)
        → write to Kafka (preprocessed-flight-data)
    """
    spark = create_spark_session()
    logger.info("✅ Spark session created")

    # ----- Read from Kafka -----
    raw_stream = (
        spark.readStream
        .format("kafka")
        .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS)
        .option("subscribe", KAFKA_TOPIC_RAW_FLIGHT)
        .option("startingOffsets", "latest")
        .option("failOnDataLoss", "false")
        .load()
    )

    # ----- Parse JSON values -----
    parsed = (
        raw_stream
        .selectExpr("CAST(value AS STRING) as json_str")
        .select(from_json(col("json_str"), RAW_FLIGHT_SCHEMA).alias("data"))
        .select("data.*")
    )

    # ----- Feature Extraction UDFs -----
    @udf(returnType=DoubleType())
    def to_knots(velocity):
        """Convert m/s to knots."""
        if velocity is None:
            return 0.0
        return float(velocity * 1.94384)

    @udf(returnType=DoubleType())
    def to_fpm(vertical_rate):
        """Convert m/s vertical rate to feet per minute."""
        if vertical_rate is None:
            return 0.0
        return float(vertical_rate * 196.85)

    # ----- Apply transformations -----
    preprocessed = (
        parsed
        .withColumn("altitude_feet", col("baro_altitude"))
        .withColumn("speed_knots", to_knots(col("velocity")))
        .withColumn("heading", col("true_track"))
        .withColumn("climb_rate_fpm", to_fpm(col("vertical_rate")))
        .withColumn("processed_at", current_timestamp())
        .select(
            "icao24", "callsign", "origin_country",
            "latitude", "longitude",
            "altitude_feet", "speed_knots", "heading", "climb_rate_fpm",
            "on_ground", "squawk", "timestamp", "processed_at"
        )
    )

    # ----- Write to PostgreSQL (foreachBatch) -----
    def write_to_postgres(batch_df, batch_id):
        """Write each micro-batch to PostgreSQL."""
        if batch_df.count() == 0:
            return

        (
            batch_df.write
            .format("jdbc")
            .option("url", POSTGRES_JDBC_URL)
            .option("dbtable", "preprocessed_flights")
            .option("user", POSTGRES_USER)
            .option("password", POSTGRES_PASSWORD)
            .option("driver", "org.postgresql.Driver")
            .mode("append")
            .save()
        )
        logger.info("📦 Batch #%d: %d rows → PostgreSQL", batch_id, batch_df.count())

    # ----- Stream 1: PostgreSQL sink -----
    pg_query = (
        preprocessed.writeStream
        .foreachBatch(write_to_postgres)
        .outputMode("append")
        .option("checkpointLocation", "/tmp/skyguard_checkpoint/postgres")
        .start()
    )

    # ----- Stream 2: Kafka sink (for downstream inference) -----
    kafka_query = (
        preprocessed
        .select(
            col("icao24").alias("key"),
            to_json(struct("*")).alias("value"),
        )
        .writeStream
        .format("kafka")
        .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS)
        .option("topic", KAFKA_TOPIC_PREPROCESSED)
        .option("checkpointLocation", "/tmp/skyguard_checkpoint/kafka")
        .outputMode("append")
        .start()
    )

    logger.info("🚀 Spark Streaming started — waiting for data...")
    logger.info("   Source: Kafka topic '%s'", KAFKA_TOPIC_RAW_FLIGHT)
    logger.info("   Sink 1: PostgreSQL 'preprocessed_flights'")
    logger.info("   Sink 2: Kafka topic '%s'", KAFKA_TOPIC_PREPROCESSED)

    # Wait for termination
    spark.streams.awaitAnyTermination()
