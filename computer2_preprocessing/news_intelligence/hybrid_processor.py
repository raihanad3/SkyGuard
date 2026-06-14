# hybrid processor - integrate news sentiment + flight anomaly
import logging
import json
from datetime import datetime
from kafka import KafkaConsumer, KafkaProducer

# fix import path - support running from root or inside folder
try:
    from computer2_preprocessing.news_intelligence.sentiment_processor import NewsSentimentProcessor
    from computer2_preprocessing.feature_engine import FeatureEngine
    from computer2_preprocessing.config.settings import (
        KAFKA_BOOTSTRAP_SERVERS,
        KAFKA_TOPIC_RAW_NEWS,
        KAFKA_TOPIC_RAW_FLIGHT,
        KAFKA_TOPIC_PREPROCESSED
    )
except ModuleNotFoundError:
    from news_intelligence.sentiment_processor import NewsSentimentProcessor
    from feature_engine import FeatureEngine
    from config.settings import (
        KAFKA_BOOTSTRAP_SERVERS,
        KAFKA_TOPIC_RAW_NEWS,
        KAFKA_TOPIC_RAW_FLIGHT,
        KAFKA_TOPIC_PREPROCESSED
    )

logger = logging.getLogger("skyguard.preprocessing")


class HybridProcessor:
    """
    Hybrid processor combining:
    1. Flight feature extraction
    2. News sentiment analysis
    3. Regional risk scoring
    4. Time-window correlation
    """
    
    def __init__(self):
        # processors
        self.feature_engine = FeatureEngine()
        self.sentiment_processor = NewsSentimentProcessor()
        
        # kafka consumers
        self.news_consumer = KafkaConsumer(
            KAFKA_TOPIC_RAW_NEWS,
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            group_id="preprocessing-news",
            auto_offset_reset='latest'
        )
        
        self.flight_consumer = KafkaConsumer(
            KAFKA_TOPIC_RAW_FLIGHT,
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            group_id="preprocessing-flight",
            auto_offset_reset='latest'
        )
        
        # kafka producer
        self.producer = KafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
    
    def start_processing(self):
        """Start hybrid processing loop."""
        logger.info("🚀 Starting Hybrid Processor...")
        logger.info("   - News sentiment analysis")
        logger.info("   - Regional risk scoring")
        logger.info("   - Time-window correlation")
        
        try:
            while True:
                # process news batch
                self._process_news_batch()
                
                # process flight batch
                self._process_flight_batch()
                
                # check pending alerts for confirmation
                self._check_pending_confirmations()
        
        except KeyboardInterrupt:
            logger.info("Shutting down...")
        finally:
            self.news_consumer.close()
            self.flight_consumer.close()
            self.producer.close()
    
    def _process_news_batch(self):
        """Process news batch dan update regional risks."""
        news_batch = []
        
        # consume up to 10 news items
        for _ in range(10):
            msg = next(self.news_consumer, None)
            if msg:
                news_batch.append(msg.value)
        
        if news_batch:
            logger.info(f"📰 Processing {len(news_batch)} news items")
            
            # run sentiment analysis + regional risk update
            self.sentiment_processor.process_news_batch(news_batch)
            
            # log risk summary
            risk_summary = self.sentiment_processor.get_risk_summary()
            for region, data in risk_summary.items():
                if data["risk_level"] > 0.5:
                    logger.warning(
                        f"⚠️  {region}: Risk={data['risk_level']:.2f} "
                        f"({data['num_reports']} reports)"
                    )
    
    def _process_flight_batch(self):
        """Process flight batch dengan hybrid alert logic."""
        flight_batch = []
        
        # consume up to 50 flights
        for _ in range(50):
            msg = next(self.flight_consumer, None)
            if msg:
                flight_batch.append(msg.value)
        
        if not flight_batch:
            return
        
        logger.info(f"✈️  Processing {len(flight_batch)} flights")
        
        for flight in flight_batch:
            # extract features
            features = self.feature_engine.extract_features(flight)
            
            # get region
            region = self._determine_region(
                features.get("latitude"),
                features.get("longitude")
            )
            
            # calculate base anomaly score (placeholder - nanti dari anomaly detector)
            anomaly_score = self._calculate_base_anomaly(features)
            
            # get hybrid alert level
            hybrid_level = self.sentiment_processor.get_hybrid_alert_level(
                anomaly_score,
                region
            )
            
            # add regional risk to features
            features["region"] = region
            features["regional_risk"] = self.sentiment_processor.get_regional_risk(region)
            features["hybrid_alert_level"] = hybrid_level
            features["anomaly_score"] = anomaly_score
            
            # jika YELLOW, add to pending (wait for confirmation)
            if hybrid_level == "YELLOW":
                self.sentiment_processor.add_pending_alert(
                    {
                        "icao24": features["icao24"],
                        "timestamp": features["timestamp"],
                        "anomaly_score": anomaly_score
                    },
                    region
                )
                logger.info(
                    f"🟡 YELLOW alert: {features['icao24']} in {region} "
                    f"(score={anomaly_score:.2f}, regional_risk={features['regional_risk']:.2f})"
                )
            
            # forward to kafka
            self.producer.send(KAFKA_TOPIC_PREPROCESSED, features)
    
    def _check_pending_confirmations(self):
        """Check pending YELLOW alerts untuk upgrade ke RED."""
        confirmed = self.sentiment_processor.process_pending_alerts()
        
        for alert in confirmed:
            logger.info(
                f"🔴 YELLOW → RED: {alert['icao24']} "
                "confirmed by news within 2-hour window"
            )
            
            # send upgraded alert
            self.producer.send(KAFKA_TOPIC_PREPROCESSED, {
                "icao24": alert["icao24"],
                "alert_upgrade": "YELLOW_TO_RED",
                "confirmation_type": "news_correlation",
                "timestamp": datetime.utcnow().isoformat()
            })
    
    def _determine_region(self, lat, lon):
        """Determine Asia region from coordinates."""
        if not lat or not lon:
            return "Asia General"
        
        # simple region mapping (bisa diperluas)
        if -11 <= lat <= 6 and 95 <= lon <= 141:
            return "Indonesian Airspace"
        elif 10 <= lat <= 25 and 105 <= lon <= 125:
            return "South China Sea"
        elif 20 <= lat <= 30 and 118 <= lon <= 128:
            return "East China Sea"
        elif 23 <= lat <= 26 and 118 <= lon <= 122:
            return "Taiwan Strait"
        elif 1 <= lat <= 8 and 98 <= lon <= 105:
            return "Malacca Strait"
        else:
            return "Asia General"
    
    def _calculate_base_anomaly(self, features):
        """
        Calculate base anomaly score (simplified).
        Nanti diganti sama full anomaly detector.
        """
        score = 0.0
        
        # low altitude
        if features.get("altitude_feet", 0) < 2000:
            if not features.get("near_airport"):
                score += 0.3
        
        # restricted zone
        if features.get("in_restricted_zone"):
            score += 0.4
        
        # unusual speed
        speed = features.get("speed_knots", 0)
        if speed > 0:
            if speed < 150 or speed > 600:
                score += 0.2
        
        return min(score, 1.0)


# main entry point
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )
    
    processor = HybridProcessor()
    processor.start_processing()
