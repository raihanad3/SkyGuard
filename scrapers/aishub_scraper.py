"""
AISHub Free API Scraper
========================
Scrape REAL vessel data dari AISHub using FREE DEMO account.
This is LEGAL and uses their official API.

API Docs: http://www.aishub.net/api
Free tier: Demo account (limited but legal)
"""

import asyncio
import requests
import logging
from datetime import datetime
from core.config import CRITICAL_ZONES

logger = logging.getLogger("vessel_anomaly")


class AISHubScraper:
    """Scrape real AIS data from AISHub free API."""
    
    def __init__(self):
        self.base_url = "http://data.aishub.net/ws.php"
        self.username = "DEMO"  # Free demo account
        self.session = requests.Session()
    
    async def scrape_area(self, bbox):
        """
        Scrape vessels from specific area using AISHub API.
        
        bbox: [[lat_min, lon_min], [lat_max, lon_max]]
        Returns: List of real vessel data
        """
        lat_min, lon_min = bbox[0]
        lat_max, lon_max = bbox[1]
        
        params = {
            'username': self.username,
            'format': '1',  # JSON format
            'output': 'json',
            'compress': '0',
            'latmin': lat_min,
            'latmax': lat_max,
            'lonmin': lon_min,
            'lonmax': lon_max
        }
        
        try:
            response = await asyncio.to_thread(
                lambda: self.session.get(self.base_url, params=params, timeout=30)
            )
            
            if response.status_code != 200:
                logger.warning(f"⚠️ AISHub returned status {response.status_code}")
                return []
            
            if not response.text or response.text.strip() == '':
                logger.warning(f"⚠️ AISHub returned empty response")
                return []
            
            data = response.json()
            
            # Check for error
            if isinstance(data, dict) and data.get('ERROR'):
                logger.warning(f"⚠️ AISHub error: {data.get('ERROR')}")
                return []
            
            vessels = []
            vessel_data = data.get('DATA', data.get('data', []))
            
            if not vessel_data:
                return []
            
            for vessel in vessel_data:
                try:
                    mmsi = str(vessel.get('MMSI', ''))
                    if not mmsi or mmsi == '0':
                        continue
                    
                    vessels.append({
                        "mmsi": mmsi,
                        "latitude": float(vessel.get('LATITUDE', 0)),
                        "longitude": float(vessel.get('LONGITUDE', 0)),
                        "speed": float(vessel.get('SOG', 0)),
                        "course": float(vessel.get('COG', 0)),
                        "heading": float(vessel.get('HEADING', 0)),
                        "ship_name": str(vessel.get('NAME', 'UNKNOWN')).strip(),
                        "ship_type": int(vessel.get('TYPE', 0)),
                        "flag_country": str(vessel.get('COUNTRY', 'UNKNOWN')),
                        "timestamp": datetime.utcnow().isoformat(),
                        "destination": str(vessel.get('DESTINATION', '')),
                        "source": "AISHub-DEMO"
                    })
                
                except (ValueError, TypeError, KeyError) as e:
                    logger.debug(f"Parse error: {e}")
                    continue
            
            return vessels
        
        except requests.exceptions.Timeout:
            logger.warning("⏱️ AISHub timeout")
        except requests.exceptions.RequestException as e:
            logger.warning(f"🔌 AISHub connection error: {e}")
        except Exception as e:
            logger.warning(f"❌ AISHub error: {type(e).__name__}: {e}")
        
        return []
    
    async def scrape_indonesian_waters(self):
        """
        Scrape REAL vessels from Indonesian waters using AISHub API.
        Returns actual vessels from the FREE demo account.
        """
        logger.info("=" * 60)
        logger.info("🌊 Scraping REAL Vessels via AISHub FREE API")
        logger.info("=" * 60)
        logger.info("📡 Source: AISHub.net (DEMO account)")
        logger.info("⚖️  Legal: YES (official free tier)")
        logger.info("⚠️  Limitation: Demo account is rate-limited & may have delays")
        logger.info("")
        
        all_vessels = []
        unique_mmsi = set()
        
        # Scrape each critical zone
        for zone_id, zone_info in CRITICAL_ZONES.items():
            zone_name = zone_info['name']
            bbox = zone_info['bbox']
            
            logger.info(f"📍 Checking {zone_name}...")
            
            vessels = await self.scrape_area(bbox)
            
            # Add to collection (avoid duplicates)
            new_count = 0
            for vessel in vessels:
                if vessel['mmsi'] not in unique_mmsi:
                    unique_mmsi.add(vessel['mmsi'])
                    all_vessels.append(vessel)
                    new_count += 1
            
            if vessels:
                logger.info(f"   ✅ Found {new_count} real vessels in {zone_name}")
            else:
                logger.info(f"   ⚪ No vessels in {zone_name} (or rate limited)")
            
            # Rate limiting (be nice to free API)
            await asyncio.sleep(5)
        
        logger.info("")
        logger.info("=" * 60)
        
        if all_vessels:
            logger.info(f"✅ Total REAL vessels found: {len(all_vessels)}")
            logger.info("")
            logger.info("📋 Sample vessels:")
            for i, v in enumerate(all_vessels[:5]):
                logger.info(f"   {i+1}. {v['ship_name']} ({v['mmsi']}) - {v['flag_country']}")
            if len(all_vessels) > 5:
                logger.info(f"   ... and {len(all_vessels) - 5} more")
        else:
            logger.warning("⚠️ No vessels found!")
            logger.info("")
            logger.info("💡 Possible reasons:")
            logger.info("   - DEMO account rate limited (wait 1-5 minutes)")
            logger.info("   - No vessels in Indonesian waters at this time")
            logger.info("   - API temporarily down")
            logger.info("")
            logger.info("🔄 Try running again in a few minutes...")
        
        logger.info("=" * 60)
        
        return all_vessels
    
    async def scrape_with_retry(self, max_retries=3, delay=60):
        """
        Scrape with retry logic for rate limiting.
        
        Args:
            max_retries: Number of retry attempts
            delay: Seconds to wait between retries
        """
        for attempt in range(max_retries):
            logger.info(f"🔄 Attempt {attempt + 1}/{max_retries}")
            
            vessels = await self.scrape_indonesian_waters()
            
            if vessels:
                return vessels
            
            if attempt < max_retries - 1:
                logger.info(f"⏳ Waiting {delay} seconds before retry...")
                await asyncio.sleep(delay)
        
        logger.warning("❌ All retry attempts exhausted")
        return []


# Singleton
aishub_scraper = AISHubScraper()
