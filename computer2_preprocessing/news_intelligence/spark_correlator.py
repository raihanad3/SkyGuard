# spark news correlator - time windowing + stateful join
import logging
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, window, from_json, udf
from pyspark.sql.types import StructType, StructField, StringType, DoubleType, TimestampType

logger = logging.getLogger("skyguard.preprocessing")


class SparkNewsCorrelator:
    """
    Spark Streaming job untuk correlate flight anomalies dengan news.
    Implements time-windowing stateful join.
    """
    
    def __init__(self, spark_session, sentiment_processor):
        self.spark = spark_session
        self.sentiment_processor = sentiment_processor
    
    def start_correlation_stream(self, kafka_bootstrap_servers):
        """
        Start Spark Streaming job yang:
        1. Read flight anomalies dari Kafka
        2. Read news dari Kafka
        3. Join dengan time window
        4. Upgrade alerts based on correlation
        """
        
        # schema for flight stream
        flight_schema = StructType([
            StructField("icao24", StringType(), True),
            StructField("anomaly_score", DoubleType(), True),
            StructField("latitude", DoubleType(), True),
            StructField("longitude", DoubleType(), True),
            StructField("region", StringType(), True),
            StructField("timestamp", TimestampType(), True),
            StructField("alert_level", StringType(), True)
        ])
        
        # schema for news stream
        news_schema = StructType([
            StructField("text", StringType(), True),
            StructField("location", StringType(), True),
            StructField("region", StringType(), True),
            StructField("timestamp", TimestampType(), True),
            StructField("sentiment", StringType(), True)
        ])
        
        # read flight anomaly stream
        flight_stream = self.spark \
            .readStream \
            .format("kafka") \
            .option("kafka.bootstrap.servers", kafka_bootstrap_servers) \
            .option("subscribe", "preprocessed-flight-data") \
            .option("startingOffsets", "latest") \
            .load() \
            .selectExpr("CAST(value AS STRING) as json") \
            .select(from_json(col("json"), flight_schema).alias("data")) \
            .select("data.*") \
            .withWatermark("timestamp", "2 hours")  # 2-hour window
        
        # read news stream
        news_stream = self.spark \
            .readStream \
            .format("kafka") \
            .option("kafka.bootstrap.servers", kafka_bootstrap_servers) \
            .option("subscribe", "raw-news-data") \
            .option("startingOffsets", "latest") \
            .load() \
            .selectExpr("CAST(value AS STRING) as json") \
            .select(from_json(col("json"), news_schema).alias("data")) \
            .select("data.*") \
            .withWatermark("timestamp", "2 hours")
        
        # join flights with news by region + time window
        # ini yang implement "Time-Window Stateful Join"
        correlated = flight_stream.alias("f") \
            .join(
                news_stream.alias("n"),
                (col("f.region") == col("n.region")) &
                (col("f.timestamp") >= col("n.timestamp") - window("2 hours")) &
                (col("f.timestamp") <= col("n.timestamp") + window("2 hours")),
                "left_outer"  # keep flights even if no matching news
            ) \
            .select(
                col("f.icao24"),
                col("f.anomaly_score"),
                col("f.region"),
                col("f.alert_level").alias("base_alert_level"),
                col("n.sentiment").alias("confirming_sentiment"),
                col("n.text").alias("confirming_news")
            )
        
        # upgrade alert level based on correlation
        def upgrade_alert(base_level, sentiment):
            if sentiment == "negative":
                if base_level == "YELLOW":
                    return "RED"  # confirmed!
            return base_level
        
        upgrade_udf = udf(upgrade_alert, StringType())
        
        final_alerts = correlated \
            .withColumn(
                "final_alert_level",
                upgrade_udf(col("base_alert_level"), col("confirming_sentiment"))
            )
        
        # write to kafka (upgraded alerts)
        query = final_alerts \
            .selectExpr("to_json(struct(*)) AS value") \
            .writeStream \
            .format("kafka") \
            .option("kafka.bootstrap.servers", kafka_bootstrap_servers) \
            .option("topic", "correlated-alerts") \
            .option("checkpointLocation", "/tmp/spark-checkpoint") \
            .start()
        
        return query
    
    def create_regional_risk_aggregation(self, kafka_bootstrap_servers):
        """
        Create tumbling window aggregation untuk regional risk scores.
        Updates every hour dengan 24-hour lookback.
        """
        
        news_schema = StructType([
            StructField("region", StringType(), True),
            StructField("sentiment_score", DoubleType(), True),
            StructField("timestamp", TimestampType(), True)
        ])
        
        # read news stream
        news_stream = self.spark \
            .readStream \
            .format("kafka") \
            .option("kafka.bootstrap.servers", kafka_bootstrap_servers) \
            .option("subscribe", "raw-news-data") \
            .load() \
            .selectExpr("CAST(value AS STRING) as json") \
            .select(from_json(col("json"), news_schema).alias("data")) \
            .select("data.*") \
            .withWatermark("timestamp", "24 hours")
        
        # aggregate by region + 1-hour tumbling window
        regional_risk = news_stream \
            .groupBy(
                window(col("timestamp"), "1 hour"),
                col("region")
            ) \
            .avg("sentiment_score") \
            .withColumnRenamed("avg(sentiment_score)", "avg_risk_score")
        
        # write aggregated risk scores
        query = regional_risk \
            .selectExpr("to_json(struct(*)) AS value") \
            .writeStream \
            .format("kafka") \
            .option("kafka.bootstrap.servers", kafka_bootstrap_servers) \
            .option("topic", "regional-risk-scores") \
            .option("checkpointLocation", "/tmp/spark-risk-checkpoint") \
            .outputMode("update") \
            .start()
        
        return query


# helper function untuk initialize
def create_spark_session():
    """Create Spark session with Kafka support."""
    return SparkSession.builder \
        .appName("SkyGuard-NewsCorrelation") \
        .config("spark.jars.packages", "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0") \
        .config("spark.sql.streaming.stateStore.providerClass", 
                "org.apache.spark.sql.execution.streaming.state.HDFSBackedStateStoreProvider") \
        .getOrCreate()
