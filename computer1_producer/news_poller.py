"""
SkyGuard — Aviation News Poller
================================
Periodically scrapes aviation news from multiple RSS sources and
produces them to Kafka topic 'raw-news-data'.

Sources:
  - Simple Flying      (simpleflying.com/feed)
  - AeroTime           (aerotime.aero/feed)
  - Flightradar24 Blog (flightradar24.com/blog/feed)
  - The Aviationist    (theaviationist.com/feed/)
"""

import asyncio
import logging
import feedparser
from datetime import datetime
from dateutil import parser as date_parser

from shared.config.settings import KAFKA_TOPIC_RAW_NEWS
from shared.config.airspace import ASIA_AIR_COORDINATES

logger = logging.getLogger("skyguard.producer")


# ============================================================
# RSS Feed Sources
# ============================================================
AVIATION_RSS_FEEDS = [
    {
        "url": "https://simpleflying.com/feed/",
        "name": "SimpleFlying",
        "focus": "Insiden, berita maskapai global",
    },
    {
        "url": "https://aerotime.aero/feed/",
        "name": "AeroTime",
        "focus": "Aviasi umum, insiden, MRO",
    },
    {
        "url": "https://www.flightradar24.com/blog/feed/",
        "name": "Flightradar24",
        "focus": "Insiden, tracking, safety",
    },
    {
        "url": "https://theaviationist.com/feed/",
        "name": "TheAviationist",
        "focus": "Bisnis & militer aviasi",
    },
]


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
    # General aviation news that doesn't match specific threat categories
    if any(x in low for x in [
        "aircraft", "flight", "airline", "aviation", "airplane",
        "pilot", "airport", "air force", "crash", "incident",
        "safety", "accident", "grounded", "turbulence", "mro",
        "maintenance", "landing", "takeoff",
    ]):
        return "AVIATION_GENERAL"
    return None


# ============================================================
# Scraping Functions
# ============================================================
async def _scrape_rss_feeds():
    """Scrape all aviation RSS feeds."""
    all_articles = []

    for feed_info in AVIATION_RSS_FEEDS:
        rss_url = feed_info["url"]
        source_name = feed_info["name"]

        try:
            feed = await asyncio.to_thread(lambda u=rss_url: feedparser.parse(u))

            if feed.bozo and not feed.entries:
                logger.warning("⚠️  Feed error for %s: %s", source_name, feed.bozo_exception)
                continue

            for entry in feed.entries[:15]:
                title = entry.get("title", "")
                if not title:
                    continue

                # Combine title + summary for richer analysis
                summary = entry.get("summary", entry.get("description", ""))
                full_text = f"{title}. {summary}" if summary else title

                # Parse publication date
                published = entry.get("published", entry.get("updated", ""))
                if published:
                    try:
                        pub_date = date_parser.parse(published)
                        published = pub_date.isoformat()
                    except Exception:
                        published = datetime.now().isoformat()
                else:
                    published = datetime.now().isoformat()

                # Categorize article
                category = _categorize(full_text)
                if not category:
                    continue

                location, coordinates = _extract_location_and_coordinates(full_text)
                flight_info = _extract_flight_info(full_text)
                threat_level = _calculate_threat_level(full_text)

                # Extract article link
                link = entry.get("link", "")

                all_articles.append({
                    "timestamp": published,
                    "category": category,
                    "source": source_name,
                    "title": title.strip().replace("\n", " "),
                    "summary": summary[:300] if summary else "",
                    "link": link,
                    "location": location,
                    "flight_info": flight_info,
                    "threat_level": threat_level,
                    "coordinates": coordinates,
                })

            logger.info("📰 %s: %d entries parsed", source_name, len(feed.entries))

        except Exception as e:
            logger.warning("RSS error [%s]: %s", source_name, e)

    logger.info("📰 Total scraped articles: %d", len(all_articles))
    return all_articles


# ============================================================
# Main Poller
# ============================================================
class NewsPoller:
    """Periodically scrapes RSS news sources and produces to Kafka."""

    def __init__(self, kafka_producer):
        self.kafka_producer = kafka_producer
        self.running = False

    async def start(self):
        """Start news polling loop (60s interval)."""
        self.running = True

        logger.info("📰 News poller started (60s interval)")
        logger.info("📰 Sources: %s", ", ".join(f["name"] for f in AVIATION_RSS_FEEDS))

        while self.running:
            try:
                articles = await _scrape_rss_feeds()

                if articles:
                    messages = [
                        (art.get("category", "UNKNOWN"), art)
                        for art in articles
                    ]
                    self.kafka_producer.send_batch(KAFKA_TOPIC_RAW_NEWS, messages)
                    logger.info("📰 Produced %d news articles to Kafka", len(articles))

                await asyncio.sleep(60)

            except Exception as e:
                logger.error("News poller error: %s", e)
                await asyncio.sleep(60)

    def stop(self):
        """Stop the poller."""
        self.running = False
        logger.info("🛑 News poller stopped")
