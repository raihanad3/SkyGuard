"""
SkyGuard — Computer 1: Producer (Main Entry Point)
====================================================
Polls OpenSky Network and aviation news sources,
then produces raw data to Kafka topics.

Usage:
    python -m computer1_producer.main
"""

import asyncio
import sys
import os
import signal
import logging

# Fix encoding for Windows console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    os.environ.setdefault("PYTHONUTF8", "1")

from shared.config.settings import LOG_DIR
from computer1_producer.kafka_producer import SkyGuardProducer
from computer1_producer.opensky_poller import OpenSkyPoller
from computer1_producer.news_poller import NewsPoller
from computer1_producer.airplanes_live_consumer import AirplanesLiveConsumer
from computer1_producer.incidents_scraper import IncidentsScraper


def setup_logging():
    """Setup logging for Computer 1."""
    os.makedirs(LOG_DIR, exist_ok=True)

    logger = logging.getLogger("skyguard.producer")
    logger.setLevel(logging.INFO)

    # Console
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S"
    ))
    logger.addHandler(ch)

    # File
    fh = logging.FileHandler(
        os.path.join(LOG_DIR, "computer1_producer.log"), encoding="utf-8"
    )
    fh.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    logger.addHandler(fh)

    return logger


def print_banner():
    """Print startup banner."""
    banner = """
╔══════════════════════════════════════════════════════════════╗
║  SKYGUARD — Computer 1: Data Producer                      ║
║  OpenSky Polling → Kafka | News Scraping → Kafka           ║
║  Airplanes.live → DB     | Incidents Scraper → DB          ║
╚══════════════════════════════════════════════════════════════╝
"""
    print(banner)


async def run(logger):
    """Main async runner."""
    # Initialize Kafka producer
    producer = SkyGuardProducer()

    # Initialize pollers
    opensky = OpenSkyPoller(producer)
    news = NewsPoller(producer)
    airplanes = AirplanesLiveConsumer()
    incidents = IncidentsScraper()

    # Handle shutdown
    shutdown = asyncio.Event()

    def _signal_handler(sig, frame):
        logger.info("🛑 Shutdown signal received")
        opensky.stop()
        news.stop()
        airplanes.stop()
        incidents.stop()
        shutdown.set()

    signal.signal(signal.SIGINT, _signal_handler)

    logger.info("🚀 Starting pollers...")

    try:
        incidents.start()
        await asyncio.gather(
            opensky.start(),
            news.start(),
            airplanes.start(),
            return_exceptions=True,
        )
    except Exception as e:
        logger.error("Fatal error: %s", e)
    finally:
        producer.close()
        logger.info("👋 Computer 1 shutdown complete")


def main():
    """Entry point."""
    logger = setup_logging()
    print_banner()

    logger.info("🔧 Initializing Computer 1 — Producer...")
    asyncio.run(run(logger))


if __name__ == "__main__":
    main()
