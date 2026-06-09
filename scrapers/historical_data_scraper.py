"""
Historical AIS Data Scraper
============================
Scrape REAL vessel data dari public sources untuk populate database.
Data ini adalah REAL vessels yang actual lewat Indonesian waters.

Sources:
- VesselFinder public API/tiles
- MarineTraffic public tiles
- AISHub historical data

NOTE: This scrapes PUBLIC data only, respecting rate limits and ToS.
"""

import asyncio
import requests
import logging
from datetime import datetime, timedelta
from core.config import CRITICAL_ZONES

logger = logging.getLogger("vessel_anomaly")


class HistoricalDataScraper:
    """Scrape real historical AIS data from public sources."""
    
    def __init__(self):
        self.scraped_vessels = []
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
        })
    
    async def scrape_vesselfinder_area(self, bbox):
        """
        Scrape current vessels from VesselFinder (real data).
        VesselFinder shows real vessels currently in area.
        
        bbox: [[lat_min, lon_min], [lat_max, lon_max]]
        """
        lat_min, lon_min = bbox[0]
        lat_max, lon_max = bbox[1]
        
        # VesselFinder public map data endpoint
        url = "https://www.vesselfinder.com/api/pub/vesselsonmap"
        
        params = {
            'bbox': f'{lon_min},{lat_min},{lon_max},{lat_max}',
            'zoom': 8,
            'mmsi': 0,
            'show_names': 1,
            'Fleet': '',
            'vtypes': '0'
        }
        
        try:
            logger.info(f"🌐 Scraping VesselFinder for bbox {bbox}...")
            
            response = await asyncio.to_thread(
                lambda: self.session.get(url, params=params, timeout=30)
            )
            
            if response.status_code != 200:
                logger.warning(f"❌ VesselFinder returned {response.status_code}")
                return []
            
            data = response.json()
            vessels = []
            
            # VesselFinder returns array of arrays
            # Format: [mmsi, lat, lon, course, speed, type, timestamp, name, ...]
            if isinstance(data, list):
                for vessel_array in data:
                    if not isinstance(vessel_array, list) or len(vessel_array) < 8:
                        continue
                    
                    try:
                        mmsi = str(vessel_array[0])
                        lat = float(vessel_array[1])
                        lon = float(vessel_array[2])
                        course = float(vessel_array[3]) if vessel_array[3] else 0
                        speed = float(vessel_array[4]) if vessel_array[4] else 0
                        ship_type = int(vessel_array[5]) if vessel_array[5] else 0
                        ship_name = str(vessel_array[7]) if len(vessel_array) > 7 else "UNKNOWN"
                        
                        if not mmsi or mmsi == '0':
                            continue
                        
                        vessels.append({
                            "mmsi": mmsi,
                            "latitude": lat,
                            "longitude": lon,
                            "speed": speed,
                            "course": course,
                            "heading": course,
                            "ship_name": ship_name.strip(),
                            "ship_type": ship_type,
                            "flag_country": "UNKNOWN",  # VF doesn't always provide
                            "timestamp": datetime.utcnow().isoformat(),
                            "destination": "",
                            "source": "VesselFinder"
                        })
                    
                    except (ValueError, TypeError, IndexError) as e:
                        continue
            
            logger.info(f"✅ VesselFinder: Got {len(vessels)} real vessels")
            return vessels
        
        except requests.exceptions.Timeout:
            logger.warning("⏱️ VesselFinder timeout")
        except Exception as e:
            logger.warning(f"❌ VesselFinder error: {type(e).__name__}: {e}")
        
        return []
    
    async def scrape_marinetraffic_area(self, bbox):
        """
        Scrape from MarineTraffic public tiles (real data).
        MT has public tile endpoint that shows real vessels.
        """
        lat_min, lon_min = bbox[0]
        lat_max, lon_max = bbox[1]
        
        # MarineTraffic public tile endpoint
        url = "https://www.marinetraffic.com/getData/get_data_json_4/z:6/X:0"
        
        # Calculate center
        center_lat = (lat_min + lat_max) / 2
        center_lon = (lon_min + lon_max) / 2
        
        params = {
            'bbox': f'{lon_min},{lat_min},{lon_max},{lat_max}',
            'station': '0',
            'fleet': '',
            'timespan': '20'  # Last 20 minutes
        }
        
        try:
            logger.info(f"🌐 Scraping MarineTraffic for bbox {bbox}...")
            
            response = await asyncio.to_thread(
                lambda: self.session.get(url, params=params, timeout=30)
            )
            
            if response.status_code != 200:
                logger.warning(f"❌ MarineTraffic returned {response.status_code}")
                return []
            
            data = response.json()
            vessels = []
            
            # Parse MT response format
            if isinstance(data, dict) and 'data' in data:
                for vessel in data['data']:
                    try:
                        mmsi = str(vessel.get('MMSI', ''))
                        if not mmsi:
                            continue
                        
                        vessels.append({
                            "mmsi": mmsi,
                            "latitude": float(vessel.get('LAT', 0)),
                            "longitude": float(vessel.get('LON', 0)),
                            "speed": float(vessel.get('SPEED', 0)),
                            "course": float(vessel.get('COURSE', 0)),
                            "heading": float(vessel.get('HEADING', 0)),
                            "ship_name": str(vessel.get('SHIPNAME', 'UNKNOWN')).strip(),
                            "ship_type": int(vessel.get('TYPE', 0)),
                            "flag_country": str(vessel.get('FLAG', 'UNKNOWN')),
                            "timestamp": datetime.utcnow().isoformat(),
                            "destination": str(vessel.get('DESTINATION', '')),
                            "source": "MarineTraffic"
                        })
                    except (ValueError, TypeError, KeyError):
                        continue
            
            logger.info(f"✅ MarineTraffic: Got {len(vessels)} real vessels")
            return vessels
        
        except requests.exceptions.Timeout:
            logger.warning("⏱️ MarineTraffic timeout")
        except Exception as e:
            logger.warning(f"❌ MarineTraffic error: {type(e).__name__}: {e}")
        
        return []
    
    async def scrape_indonesian_waters(self):
        """
        Scrape REAL vessels from all critical zones in Indonesian waters.
        Returns actual vessels currently in the area.
        """
        logger.info("=" * 60)
        logger.info("🌊 Scraping REAL vessels from Indonesian Waters")
        logger.info("=" * 60)
        
        all_vessels = []
        unique_mmsi = set()
        
        # Scrape each critical zone
        for zone_id, zone_info in CRITICAL_ZONES.items():
            zone_name = zone_info['name']
            bbox = zone_info['bbox']
            
            logger.info(f"📍 Scraping {zone_name}...")
            
            # Try VesselFinder first
            vessels = await self.scrape_vesselfinder_area(bbox)
            
            # If VF fails, try MarineTraffic
            if not vessels:
                await asyncio.sleep(2)  # Rate limit
                vessels = await self.scrape_marinetraffic_area(bbox)
            
            # Add to collection (avoid duplicates)
            for vessel in vessels:
                if vessel['mmsi'] not in unique_mmsi:
                    unique_mmsi.add(vessel['mmsi'])
                    all_vessels.append(vessel)
            
            logger.info(f"   ✓ Found {len(vessels)} vessels in {zone_name}")
            
            # Rate limiting
            await asyncio.sleep(3)
        
        logger.info("=" * 60)
        logger.info(f"✅ Total REAL vessels scraped: {len(all_vessels)}")
        logger.info("=" * 60)
        
        return all_vessels


# Singleton
scraper = HistoricalDataScraper()
