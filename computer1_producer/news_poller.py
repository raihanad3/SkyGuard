"""
SkyGuard — Aviation News Poller
================================
Periodically scrapes aviation news from multiple sources and
produces them to Kafka topic 'raw-news-data'.

Migrated from news/ais_news.py — scraping logic preserved,
output changed from CSV/Redis to Kafka.
"""

import asyncio
import logging
import requests
import feedparser
from datetime import datetime, timedelta
from dateutil import parser as date_parser

from computer1_producer.config.settings import NEWS_API_KEY, KAFKA_TOPIC_RAW_NEWS
from computer1_producer.config.airspace import ASIA_AIR_COORDINATES

logger = logging.getLogger("skyguard.producer")


# ============================================================
# News Source URLs
# ============================================================
GOOGLE_NEWS_RSS = [
    "https://news.google.com/rss/search?q=asian+airspace+violation&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=foreign+aircraft+intercepted+asia&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=air+defense+scramble+asia&hl=en-US&gl=US&ceid=US:en",
]

AVIATION_NEWS_RSS = [
    "https://www.flightglobal.com/rss/",
    "https://www.aviationtoday.com/feed/",
]

AVIATION_KEYWORDS = (
    "(Asian airspace OR Asia aviation) OR "
    "(suspicious flight Asia OR unauthorized flight Asia) OR "
    "(airspace violation Asia OR flight violation Asia)"
)


# ============================================================
# Helper Functions
# ============================================================
def _extract_location_and_coordinates(text):
    """Extract location and coordinates from text."""
    text_lower = text.lower()
    detected = []
    coordinates = "N/A"

    for location, coords in ASIA_AIR_COORDINATES.items():
        if location in text_lower:
            detected.append(location.title())
            if coordinates == "N/A":
                coordinates = coords

    if not detected:
        for kw in ["airspace", "airport", "flight", "aviation"]:
            if kw in text_lower:
                detected.append("Unspecified Airspace")
                break

    return ", ".join(detected) if detected else "Unknown", coordinates


def _extract_flight_info(text):
    """Extract flight type information from text."""
    terms = []
    low = text.lower()

    if "commercial" in low or "airliner" in low:
        terms.append("Commercial Aircraft")
    if "military" in low or "fighter" in low:
        terms.append("Military Aircraft")
    if "private" in low or "jet" in low:
        terms.append("Private Jet")
    if "transponder" in low and "off" in low:
        terms.append("Transponder Off")
    if "unauthorized" in low or "violation" in low:
        terms.append("Airspace Violation")

    return ", ".join(terms) if terms else "Unspecified Aircraft"


def _calculate_threat_level(text):
    """Determine threat level from text content."""
    low = text.lower()
    high_kw = ["airspace violation", "hijack", "smuggling", "unauthorized", "7500", "intercept"]
    med_kw = ["suspicious", "unidentified", "patrol", "transponder off", "emergency"]

    high_count = sum(1 for kw in high_kw if kw in low)
    med_count = sum(1 for kw in med_kw if kw in low)

    if high_count >= 2:
        return "HIGH"
    elif high_count == 1 or med_count >= 2:
        return "MEDIUM"
    return "LOW"


def _categorize(text):
    """Categorize news article by aviation category."""
    low = text.lower()
    if any(x in low for x in ["airspace violation", "pelanggaran wilayah udara", "unauthorized flight"]):
        return "AIRSPACE_VIOLATION"
    if any(x in low for x in ["intercept", "intersepsi", "tni au", "scramble"]):
        return "AIR_DEFENSE"
    if any(x in low for x in ["suspicious", "unidentified", "dark flight", "transponder off"]):
        return "SUSPICIOUS_FLIGHT"
    if any(x in low for x in ["smuggling", "trafficking", "illegal cargo", "narkoba"]):
        return "AIR_SMUGGLING"
    if any(x in low for x in ["emergency", "distress", "7700", "hijack", "7500"]):
        return "EMERGENCY"
    if any(x in low for x in ["border", "patrol", "surveillance", "monitoring"]):
        return "BORDER_PATROL"
    return None


# ============================================================
# Scraping Functions
# ============================================================
async def _scrape_google_news():
    """Scrape Google News RSS for Asian aviation news."""
    articles = []
    for rss_url in GOOGLE_NEWS_RSS:
        try:
            feed = await asyncio.to_thread(lambda u=rss_url: feedparser.parse(u))
            for entry in feed.entries[:10]:
                title = entry.get("title", "")
                if not title:
                    continue

                published = entry.get("published", datetime.now().isoformat())

                # Filter: only recent data
                try:
                    pub_date = date_parser.parse(published)
                    if pub_date.year < 2026:
                        continue
                except Exception:
                    pass

                category = _categorize(title)
                if not category:
                    continue

                location, coordinates = _extract_location_and_coordinates(title)
                flight_info = _extract_flight_info(title)
                threat_level = _calculate_threat_level(title)
                source = entry.get("source", {}).get("title", "Google News")

                articles.append({
                    "timestamp": published,
                    "category": category,
                    "source": f"GoogleNews_{source[:20]}",
                    "title": title.strip().replace("\n", " "),
                    "location": location,
                    "flight_info": flight_info,
                    "threat_level": threat_level,
                    "coordinates": coordinates,
                })
        except Exception as e:
            logger.warning("Google RSS error: %s", e)

    logger.info("📰 Google News: %d articles", len(articles))
    return articles


async def _scrape_aviation_rss():
    """Scrape international aviation news RSS."""
    articles = []
    for rss_url in AVIATION_NEWS_RSS:
        try:
            feed = await asyncio.to_thread(lambda u=rss_url: feedparser.parse(u))
            for entry in feed.entries[:10]:
                title = entry.get("title", "")
                if not title:
                    continue

                low = title.lower()
                if not any(x in low for x in [
                    "indonesia", "southeast asia", "asia",
                    "airspace", "violation", "intercept", "emergency"
                ]):
                    continue

                category = _categorize(title)
                if not category:
                    continue

                location, coordinates = _extract_location_and_coordinates(title)
                flight_info = _extract_flight_info(title)
                threat_level = _calculate_threat_level(title)

                articles.append({
                    "timestamp": entry.get("published", datetime.now().isoformat()),
                    "category": category,
                    "source": "AviationNews",
                    "title": title.strip().replace("\n", " "),
                    "location": location,
                    "flight_info": flight_info,
                    "threat_level": threat_level,
                    "coordinates": coordinates,
                })
        except Exception as e:
            logger.warning("Aviation RSS error: %s", e)

    logger.info("📰 Aviation RSS: %d articles", len(articles))
    return articles


async def _scrape_newsapi():
    """Scrape NewsAPI for international aviation intel."""
    if not NEWS_API_KEY:
        return []

    articles = []
    try:
        today = datetime.now()
        start = (today - timedelta(days=7)).strftime("%Y-%m-%d")
        end = today.strftime("%Y-%m-%d")
        url = (
            f"https://newsapi.org/v2/everything?q={AVIATION_KEYWORDS}"
            f"&from={start}&to={end}&language=en&sortBy=publishedAt"
            f"&pageSize=50&apiKey={NEWS_API_KEY}"
        )
        response = await asyncio.to_thread(
            lambda: requests.get(url, timeout=30).json()
        )

        if response.get("status") != "ok":
            return []

        for article in response.get("articles", []):
            title = article.get("title", "")
            desc = article.get("description", "")
            if not title:
                continue

            full = f"{title}. {desc}"
            low = full.lower()

            if not any(x in low for x in [
                "aircraft", "flight", "airspace", "aviation",
                "airplane", "pilot", "airport", "air force", "transponder"
            ]):
                continue

            category = _categorize(full)
            if not category:
                continue

            location, coordinates = _extract_location_and_coordinates(full)
            flight_info = _extract_flight_info(full)
            threat_level = _calculate_threat_level(full)

            articles.append({
                "timestamp": article.get("publishedAt"),
                "category": category,
                "source": article.get("source", {}).get("name", "NewsAPI"),
                "title": title.strip().replace("\n", " "),
                "location": location,
                "flight_info": flight_info,
                "threat_level": threat_level,
                "coordinates": coordinates,
            })

        logger.info("📰 NewsAPI: %d articles", len(articles))
    except Exception as e:
        logger.warning("NewsAPI error: %s", e)

    return articles


# ============================================================
# Main Poller
# ============================================================
class NewsPoller:
    """Periodically scrapes news sources and produces to Kafka."""

    def __init__(self, kafka_producer):
        self.kafka_producer = kafka_producer
        self.running = False

    async def start(self):
        """Start news polling loop (60s interval)."""
        self.running = True
        cycle = 0

        logger.info("📰 News poller started (60s interval)")

        while self.running:
            try:
                tasks = [_scrape_google_news()]

                # Every 3 cycles (3 min): aviation RSS
                if cycle % 3 == 0:
                    tasks.append(_scrape_aviation_rss())

                # Every 15 cycles (15 min): NewsAPI
                if cycle % 15 == 0:
                    tasks.append(_scrape_newsapi())

                results = await asyncio.gather(*tasks, return_exceptions=True)

                all_articles = []
                for result in results:
                    if isinstance(result, list):
                        all_articles.extend(result)

                if all_articles:
                    messages = [
                        (art.get("category", "UNKNOWN"), art)
                        for art in all_articles
                    ]
                    self.kafka_producer.send_batch(KAFKA_TOPIC_RAW_NEWS, messages)

                cycle += 1
                await asyncio.sleep(60)

            except Exception as e:
                logger.error("News poller error: %s", e)
                await asyncio.sleep(60)

    def stop(self):
        """Stop the poller."""
        self.running = False
        logger.info("🛑 News poller stopped")
