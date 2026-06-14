# news sentiment processor - NLP + regional risk
import logging
from datetime import datetime, timedelta
from transformers import pipeline
from collections import defaultdict

logger = logging.getLogger("skyguard.preprocessing")


class NewsSentimentProcessor:
    """
    Process news sentiment dan calculate regional risk scores.
    Implements Hybrid Approach:
    1. Contextual Risk Scoring (regional sentiment baseline)
    2. Time-window correlation (confirm anomalies with news)
    """
    
    def __init__(self):
        # load NLP model
        logger.info("Loading NLP sentiment model...")
        try:
            self.sentiment_model = pipeline(
                "sentiment-analysis",
                model="cardiffnlp/twitter-roberta-base-sentiment-latest"
            )
            logger.info("NLP model loaded")
        except Exception as e:
            logger.error(f"Failed to load NLP model: {e}")
            self.sentiment_model = None
        
        # regional risk map (Asia regions)
        self.regional_risk = defaultdict(lambda: {
            "sentiment_scores": [],
            "last_updated": None,
            "risk_level": 0.0
        })
        
        # time window buffer (2 hours) - untuk confirmation
        self.pending_alerts = []  # List of (flight, timestamp, region)
        self.confirmed_news = []  # List of (news, timestamp, region)
    
    def process_news_batch(self, news_batch):
        """
        Process batch of news dan update regional risk scores.
        
        Args:
            news_batch: List of news dicts with 'text', 'location', 'timestamp'
        
        Returns:
            Updated regional risk map
        """
        for news in news_batch:
            sentiment = self._analyze_sentiment(news.get("text", ""))
            region = self._extract_region(news.get("location", ""))
            
            if sentiment and region:
                # update regional risk
                self._update_regional_risk(region, sentiment)
                
                # add to confirmed news buffer
                self.confirmed_news.append({
                    "region": region,
                    "sentiment": sentiment,
                    "timestamp": news.get("timestamp"),
                    "text": news.get("text", "")
                })
        
        # cleanup old confirmed news (older than 2 hours)
        self._cleanup_old_news()
        
        return self.regional_risk
    
    def _analyze_sentiment(self, text):
        """Run NLP sentiment analysis."""
        if not self.sentiment_model or not text:
            return None
        
        try:
            # truncate to 512 tokens
            result = self.sentiment_model(text[:512])[0]
            
            # convert to risk score (0-1)
            # NEGATIVE sentiment = HIGH risk
            if result['label'] == 'negative':
                risk_score = result['score']
            elif result['label'] == 'neutral':
                risk_score = 0.5
            else:  # positive
                risk_score = 1.0 - result['score']
            
            return {
                "label": result['label'],
                "confidence": result['score'],
                "risk_score": risk_score
            }
        except Exception as e:
            logger.debug(f"Sentiment analysis error: {e}")
            return None
    
    def _extract_region(self, location_text):
        """Extract Asia region from location text."""
        location_lower = location_text.lower()
        
        # map keywords to regions
        region_map = {
            "south china sea": "South China Sea",
            "east china sea": "East China Sea",
            "taiwan strait": "Taiwan Strait",
            "korean peninsula": "Korean Peninsula",
            "sea of japan": "Sea of Japan",
            "malacca strait": "Malacca Strait",
            "indonesia": "Indonesian Airspace",
            "philippines": "Philippine Airspace",
            "vietnam": "Vietnam Airspace",
            "thailand": "Thailand Airspace",
            "malaysia": "Malaysian Airspace",
            "singapore": "Singapore Airspace",
            "india": "Indian Airspace",
            "pakistan": "Pakistan Airspace",
            "myanmar": "Myanmar Airspace"
        }
        
        for keyword, region in region_map.items():
            if keyword in location_lower:
                return region
        
        return "Asia General"
    
    def _update_regional_risk(self, region, sentiment):
        """Update regional risk score dengan new sentiment."""
        risk_data = self.regional_risk[region]
        
        # add sentiment score
        risk_data["sentiment_scores"].append({
            "score": sentiment["risk_score"],
            "timestamp": datetime.utcnow()
        })
        
        # keep only last 24 hours of scores
        cutoff = datetime.utcnow() - timedelta(hours=24)
        risk_data["sentiment_scores"] = [
            s for s in risk_data["sentiment_scores"]
            if s["timestamp"] > cutoff
        ]
        
        # calculate average risk (last 24h)
        if risk_data["sentiment_scores"]:
            avg_risk = sum(s["score"] for s in risk_data["sentiment_scores"]) / len(risk_data["sentiment_scores"])
            risk_data["risk_level"] = avg_risk
        else:
            risk_data["risk_level"] = 0.0
        
        risk_data["last_updated"] = datetime.utcnow()
    
    def get_regional_risk(self, region):
        """Get current risk level for a region."""
        return self.regional_risk.get(region, {}).get("risk_level", 0.0)
    
    def _cleanup_old_news(self):
        """Remove confirmed news older than 2 hours."""
        cutoff = datetime.utcnow() - timedelta(hours=2)
        self.confirmed_news = [
            n for n in self.confirmed_news
            if datetime.fromisoformat(n["timestamp"]) > cutoff
        ]
    
    def check_time_window_confirmation(self, flight_alert, region):
        """
        Check if ada confirming news dalam 2-hour window.
        
        Args:
            flight_alert: Dict with flight anomaly info
            region: Region where anomaly detected
        
        Returns:
            bool: True if confirmed by news
        """
        flight_time = datetime.fromisoformat(flight_alert["timestamp"])
        
        # cek apakah ada news di region yang sama dalam 2 jam
        for news in self.confirmed_news:
            if news["region"] != region:
                continue
            
            news_time = datetime.fromisoformat(news["timestamp"])
            time_diff = abs((news_time - flight_time).total_seconds())
            
            # dalam 2 jam (7200 detik)
            if time_diff <= 7200:
                # check sentiment = negative (confirming threat)
                if news["sentiment"]["label"] == "negative":
                    logger.info(f"✅ Alert CONFIRMED by news: {news['text'][:100]}")
                    return True
        
        return False
    
    def add_pending_alert(self, flight_data, region):
        """Add flight anomaly to pending buffer (wait for confirmation)."""
        self.pending_alerts.append({
            "flight": flight_data,
            "region": region,
            "timestamp": datetime.utcnow()
        })
        
        # cleanup old pending (older than 2 hours)
        cutoff = datetime.utcnow() - timedelta(hours=2)
        self.pending_alerts = [
            a for a in self.pending_alerts
            if a["timestamp"] > cutoff
        ]
    
    def process_pending_alerts(self):
        """
        Check pending alerts untuk confirmation.
        Returns list of alerts yang perlu di-upgrade ke RED.
        """
        confirmed_alerts = []
        
        for pending in self.pending_alerts:
            region = pending["region"]
            
            # check confirmation
            if self.check_time_window_confirmation(
                pending["flight"], region
            ):
                confirmed_alerts.append(pending["flight"])
        
        return confirmed_alerts
    
    def get_hybrid_alert_level(self, anomaly_score, region):
        """
        Calculate hybrid alert level.
        Combines anomaly score + regional risk.
        
        Returns:
            - "GREEN": Normal (score < 0.3)
            - "YELLOW": Early warning (regional risk high OR small anomaly in hot zone)
            - "RED": Confirmed threat (anomaly + news confirmation)
        """
        regional_risk = self.get_regional_risk(region)
        
        # base alert from anomaly score
        if anomaly_score < 0.3:
            base_level = "GREEN"
        elif anomaly_score < 0.5:
            base_level = "YELLOW"
        else:
            base_level = "RED"
        
        # upgrade kalau regional risk tinggi
        if regional_risk > 0.7:  # hot zone
            if anomaly_score > 0.2:  # even small anomaly
                return "YELLOW"  # early warning
        
        # upgrade kalau kombinasi tinggi
        combined = anomaly_score + (regional_risk * 0.5)
        if combined > 0.8:
            return "RED"
        elif combined > 0.5:
            return "YELLOW"
        
        return base_level
    
    def get_risk_summary(self):
        """Get summary of all regional risks."""
        summary = {}
        for region, data in self.regional_risk.items():
            summary[region] = {
                "risk_level": round(data["risk_level"], 3),
                "num_reports": len(data["sentiment_scores"]),
                "last_updated": data["last_updated"].isoformat() if data["last_updated"] else None
            }
        return summary
