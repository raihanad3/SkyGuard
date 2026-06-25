"""
SkyGuard — Incidents Scraper
============================
Polls AVHerald and Simple Flying RSS using APScheduler.
Runs every 30 minutes.
"""

import asyncio
import logging
import psycopg2
from bs4 import BeautifulSoup
import feedparser
import requests
from dateutil import parser as date_parser
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from shared.config.settings import (
    POSTGRES_HOST, POSTGRES_PORT,
    POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB
)

logger = logging.getLogger("skyguard.producer.incidents")

class IncidentsScraper:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.conn = None

    def _connect_db(self):
        if self.conn is None or self.conn.closed:
            self.conn = psycopg2.connect(
                host=POSTGRES_HOST,
                port=POSTGRES_PORT,
                user=POSTGRES_USER,
                password=POSTGRES_PASSWORD,
                dbname=POSTGRES_DB,
            )
            self.conn.autocommit = True

    def insert_incident(self, source, title, link, pub_date, description):
        self._connect_db()
        # Check if already exists based on link
        check_sql = "SELECT id FROM incidents WHERE link = %s"
        insert_sql = """
            INSERT INTO incidents (source, title, link, pub_date, description)
            VALUES (%s, %s, %s, %s, %s)
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute(check_sql, (link,))
                if not cur.fetchone():
                    cur.execute(insert_sql, (source, title, link, pub_date, description))
                    logger.info("Inserted new incident from %s: %s", source, title)
        except Exception as e:
            logger.error("Error inserting incident: %s", e)

    def scrape_simple_flying(self):
        logger.info("Scraping Simple Flying RSS...")
        try:
            feed = feedparser.parse("https://simpleflying.com/feed/")
            for entry in feed.entries[:10]: # Process latest 10
                title = entry.get("title", "")
                link = entry.get("link", "")
                summary = entry.get("summary", "")
                pub_date_str = entry.get("published", "")
                try:
                    pub_date = date_parser.parse(pub_date_str) if pub_date_str else None
                except Exception:
                    pub_date = None
                
                # Filter for incident keywords if necessary, but we'll assume the feed might have them,
                # or just ingest to incidents table for simplicity.
                self.insert_incident("Simple Flying", title, link, pub_date, summary)
        except Exception as e:
            logger.error("Failed to scrape Simple Flying: %s", e)

    def scrape_avherald(self):
        logger.info("Scraping Aviation Herald...")
        try:
            # AVHerald has an RSS feed too, or we can scrape
            feed = feedparser.parse("https://avherald.com/rss.xml")
            for entry in feed.entries[:10]:
                title = entry.get("title", "")
                link = entry.get("link", "")
                summary = entry.get("summary", "")
                pub_date_str = entry.get("published", "")
                try:
                    pub_date = date_parser.parse(pub_date_str) if pub_date_str else None
                except Exception:
                    pub_date = None

                self.insert_incident("The Aviation Herald", title, link, pub_date, summary)
        except Exception as e:
            logger.error("Failed to scrape AVHerald: %s", e)

    def run_scrapers(self):
        self.scrape_simple_flying()
        self.scrape_avherald()

    def start(self):
        logger.info("Starting Incidents Scraper Scheduler...")
        # Run once immediately
        self.run_scrapers()
        
        # Schedule every 30 minutes
        self.scheduler.add_job(self.run_scrapers, 'interval', minutes=30)
        self.scheduler.start()

    def stop(self):
        logger.info("Stopping Incidents Scraper Scheduler...")
        self.scheduler.shutdown()
        if self.conn and not self.conn.closed:
            self.conn.close()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    scraper = IncidentsScraper()
    scraper.start()
    
    try:
        asyncio.get_event_loop().run_forever()
    except KeyboardInterrupt:
        scraper.stop()
