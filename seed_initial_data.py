"""
Scrape Real Data via AISHub FREE API
=====================================
Scrape REAL vessel data dari AISHub using FREE DEMO account.
This is LEGAL - using official AISHub free tier API.

Data ini adalah REAL vessels yang actual ada di Indonesian waters!

Usage:
    python seed_initial_data.py
"""

import sys
import asyncio
from datetime import datetime
from core.database import DatabaseManager
from core.config import get_ship_type_name
from scrapers.aishub_scraper import aishub_scraper

async def scrape_and_save():
    """Scrape real vessels from AISHub and save to database."""
    
    print("\n" + "="*60)
    print("🌊 Fetching REAL Vessels via AISHub FREE API")
    print("="*60)
    print("📡 Source: AISHub.net (DEMO account)")
    print("⚖️  Legal: YES (official free tier)")
    print("📍 Areas: Indonesian Waters (all critical zones)")
    print()
    print("⏳ This may take 1-2 minutes due to rate limiting...")
    print()
    
    # Scrape with retry (AISHub demo might be rate limited)
    vessels = await aishub_scraper.scrape_with_retry(max_retries=3, delay=60)
    
    if not vessels:
        print()
        print("❌ No vessels found after retries!")
        print()
        print("💡 Options:")
        print("   1. Wait 5-10 minutes and try again")
        print("   2. AISHub DEMO account might be heavily rate-limited")
        print("   3. No vessels in Indonesian waters at this moment")
        print()
        print("🔄 Suggestion: Try again later when more vessels pass through")
        print()
        return
    
    # Save to database
    print()
    print(f"💾 Saving {len(vessels)} REAL vessels to database...")
    print()
    
    db = DatabaseManager()
    
    for vessel in vessels:
        # Insert position
        db.insert_position(vessel)
        
        # Insert vessel info
        db.upsert_vessel_info({
            "mmsi": vessel["mmsi"],
            "ship_name": vessel["ship_name"],
            "ship_type": vessel["ship_type"],
            "ship_type_name": get_ship_type_name(vessel["ship_type"]),
            "flag_country": vessel["flag_country"],
        })
        
        print(f"  ✓ {vessel['ship_name']} ({vessel['mmsi']}) - {vessel['flag_country']}")
    
    print()
    print("✅ Scraping complete!")
    print(f"   Total REAL vessels saved: {len(vessels)}")
    print()
    print("📊 Database Stats:")
    stats = db.get_stats()
    print(f"   Vessels: {stats.get('total_vessels', 0)}")
    print(f"   Positions: {stats.get('total_positions', 0)}")
    print()
    print("🚀 Now run: python main.py")
    print("   Dashboard will show these REAL vessels!")
    print()
    print("💡 Note: These are REAL vessels from AISHub free API")
    print("   Data is actual, not simulated!")
    print("="*60 + "\n")

if __name__ == "__main__":
    asyncio.run(scrape_and_save())
