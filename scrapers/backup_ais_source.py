"""
Backup AIS Data Source
=======================
Ambil data AIS REAL dari sumber alternatif kalau AISstream tidak dapat data.
Data 100% real dari kapal, bukan simulasi.

Priority:
1. VesselFinder (Public API - NO KEY NEEDED)
2. MyShipTracking (Free API)
3. AISHub (Demo account - limited)

NOTE: Free AIS APIs are very limited. Most require payment for real-time data.
The best free option is still AISstream.io (which you already have).
"""

import requests
import asyncio
import logging
from datetime import datetime
import json

logger = logging.getLogger("vessel_anomaly")


class BackupAISSource:
    """
    Backup AIS data source menggunakan public APIs.
    
    REALITY CHECK: Kebanyakan AIS API gratis sangat limited atau perlu registration.
    AISstream.io (yang udah kamu punya) adalah salah satu yang paling generous.
    
    Backup ini untuk fallback saja, tapi jangan expect banyak data gratis.
    """
    
    def __init__(self):
        self.last_fetch = None
        self.cached_vessels = []
        
        # API keys (optional, will use free tier if not set)
        self.vesselfinder_key = None
        self.myshiptracking_key = None
    
    async def get_vessels_in_area(self, bbox):
        """
        Get real vessel data dari area tertentu.
        bbox format: [[lat_min, lon_min], [lat_max, lon_max]]
        
        Returns: List of vessel data (real AIS data)
        
        NOTE: Free AIS APIs are VERY LIMITED. Most return empty or require payment.
        """
        lat_min, lon_min = bbox[0]
        lat_max, lon_max = bbox[1]
        
        vessels = []
        
        # Try VesselFinder (public scraping)
        try:
            vessels = await self._fetch_vesselfinder(lat_min, lon_min, lat_max, lon_max)
            if vessels:
                logger.info(f"✅ VesselFinder: Got {len(vessels)} REAL vessels")
                return vessels
        except Exception as e:
            logger.debug(f"VesselFinder failed: {e}")
        
        # Try MyShipTracking
        try:
            vessels = await self._fetch_myshiptracking(lat_min, lon_min, lat_max, lon_max)
            if vessels:
                logger.info(f"✅ MyShipTracking: Got {len(vessels)} REAL vessels")
                return vessels
        except Exception as e:
            logger.debug(f"MyShipTracking failed: {e}")
        
        # Try AISHub (very limited)
        try:
            vessels = await self._fetch_aishub(lat_min, lon_min, lat_max, lon_max)
            if vessels:
                logger.info(f"✅ AISHub: Got {len(vessels)} REAL vessels")
                return vessels
        except Exception as e:
            logger.debug(f"AISHub failed: {e}")
        
        logger.warning("⚠️ All backup sources failed or returned empty")
        logger.info("💡 TIP: AISstream.io (yang udah kamu punya) is actually the best free option!")
        logger.info("💡 Free AIS data is VERY hard to get. Consider using AISstream.io as primary source.")
        
        return []
    
    async def _fetch_vesselfinder(self, lat_min, lon_min, lat_max, lon_max):
        """
        VesselFinder - Scrape dari public endpoint
        https://www.vesselfinder.com/
        
        NOTE: This is web scraping, might break anytime.
        VesselFinder has API but requires paid subscription.
        """
        vessels = []
        
        # VesselFinder map data endpoint (used by their website)
        url = "https://www.vesselfinder.com/api/pub/vesselsonmap"
        
        params = {
            "bbox": f"{lon_min},{lat_min},{lon_max},{lat_max}",
            "zoom": 10,
            "mmsi": 0,
            "show_names": 1
        }
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': '*/*',
            'Referer': 'https://www.vesselfinder.com/',
            'X-Requested-With': 'XMLHttpRequest'
        }
        
        try:
            response = await asyncio.to_thread(
                lambda: requests.get(url, params=params, headers=headers, timeout=15)
            )
            
            logger.info(f"🔍 VesselFinder response: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"🔍 VesselFinder data type: {type(data)}")
                
                # VesselFinder returns array of arrays: [mmsi, lat, lon, course, speed, type, timestamp, name, ...]
                vessel_count = 0
                
                if isinstance(data, list):
                    for vessel_array in data:
                        try:
                            if not isinstance(vessel_array, list) or len(vessel_array) < 8:
                                continue
                            
                            mmsi = str(vessel_array[0])
                            lat = float(vessel_array[1])
                            lon = float(vessel_array[2])
                            course = float(vessel_array[3]) if vessel_array[3] else 0
                            speed = float(vessel_array[4]) if vessel_array[4] else 0
                            ship_type = int(vessel_array[5]) if vessel_array[5] else 0
                            # timestamp = vessel_array[6]
                            ship_name = str(vessel_array[7]) if len(vessel_array) > 7 else "UNKNOWN"
                            
                            if not mmsi or lat == 0 or lon == 0:
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
                                "flag_country": "UNKNOWN",
                                "timestamp": datetime.utcnow().isoformat(),
                                "destination": "",
                                "source": "VesselFinder"
                            })
                            vessel_count += 1
                            
                        except (ValueError, TypeError, IndexError) as e:
                            logger.debug(f"Parse error: {e}")
                            continue
                
                logger.info(f"✅ VesselFinder: Parsed {vessel_count} vessels")
                return vessels
            else:
                logger.warning(f"⚠️ VesselFinder returned status {response.status_code}")
                
        except requests.exceptions.Timeout:
            logger.warning("⏱️ VesselFinder timeout")
        except Exception as e:
            logger.warning(f"❌ VesselFinder error: {type(e).__name__}: {e}")
        
        return []
    
    async def _fetch_myshiptracking(self, lat_min, lon_min, lat_max, lon_max):
        """
        MyShipTracking - Public AIS data
        https://www.myshiptracking.com/
        
        NOTE: Limited free access, might require registration.
        """
        vessels = []
        
        # MyShipTracking public API endpoint
        url = "https://www.myshiptracking.com/requests/vesselsonmap.php"
        
        params = {
            "type": "json",
            "minlat": lat_min,
            "maxlat": lat_max,
            "minlon": lon_min,
            "maxlon": lon_max
        }
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
            'Referer': 'https://www.myshiptracking.com/'
        }
        
        try:
            response = await asyncio.to_thread(
                lambda: requests.get(url, params=params, headers=headers, timeout=15)
            )
            
            logger.info(f"🔍 MyShipTracking response: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"🔍 MyShipTracking data type: {type(data)}")
                
                vessel_list = []
                if isinstance(data, dict):
                    vessel_list = data.get('DATA', data.get('data', data.get('vessels', [])))
                elif isinstance(data, list):
                    vessel_list = data
                
                logger.info(f"🔍 MyShipTracking found {len(vessel_list)} vessels")
                
                for vessel in vessel_list:
                    try:
                        mmsi = str(vessel.get('MMSI', vessel.get('mmsi', '')))
                        lat = float(vessel.get('LAT', vessel.get('lat', 0)))
                        lon = float(vessel.get('LON', vessel.get('lon', 0)))
                        
                        if not mmsi or not lat or not lon:
                            continue
                        
                        vessels.append({
                            "mmsi": mmsi,
                            "latitude": lat,
                            "longitude": lon,
                            "speed": float(vessel.get('SPEED', vessel.get('speed', 0))),
                            "course": float(vessel.get('COURSE', vessel.get('course', 0))),
                            "heading": float(vessel.get('HEADING', vessel.get('heading', 0))),
                            "ship_name": str(vessel.get('SHIPNAME', vessel.get('name', 'UNKNOWN'))).strip(),
                            "ship_type": int(vessel.get('TYPE', vessel.get('type', 0))),
                            "flag_country": str(vessel.get('FLAG', vessel.get('flag', 'UNKNOWN'))),
                            "timestamp": datetime.utcnow().isoformat(),
                            "destination": str(vessel.get('DEST', vessel.get('destination', ''))),
                            "source": "MyShipTracking"
                        })
                    except (ValueError, TypeError, KeyError) as e:
                        logger.debug(f"Parse error: {e}")
                        continue
                
                return vessels
            else:
                logger.warning(f"⚠️ MyShipTracking returned status {response.status_code}")
                
        except requests.exceptions.Timeout:
            logger.warning("⏱️ MyShipTracking timeout")
        except Exception as e:
            logger.warning(f"❌ MyShipTracking error: {type(e).__name__}: {e}")
        
        return []
    
    async def _fetch_aishub(self, lat_min, lon_min, lat_max, lon_max):
        """
        AISHub - Free API (demo account)
        http://www.aishub.net/api
        """
        vessels = []
        
        # AISHub free API endpoint
        url = "http://data.aishub.net/ws.php"
        params = {
            "username": "DEMO",  # Demo account
            "format": "1",  # JSON
            "output": "json",
            "compress": "0",
            "latmin": lat_min,
            "latmax": lat_max,
            "lonmin": lon_min,
            "lonmax": lon_max
        }
        
        try:
            response = await asyncio.to_thread(
                lambda: requests.get(url, params=params, timeout=15)
            )
            
            logger.info(f"🔍 AISHub response: {response.status_code}")
            
            if response.status_code == 200 and response.text:
                data = response.json()
                logger.info(f"🔍 AISHub data type: {type(data)}, keys: {list(data.keys()) if isinstance(data, dict) else 'list'}")
                
                # Parse AISHub format
                vessel_list = data.get("data", data.get("DATA", []))
                logger.info(f"🔍 AISHub found {len(vessel_list)} vessels in response")
                
                for vessel in vessel_list:
                    try:
                        mmsi = str(vessel.get("MMSI", ""))
                        if not mmsi:
                            continue
                        
                        vessels.append({
                            "mmsi": mmsi,
                            "latitude": float(vessel.get("LATITUDE", 0)),
                            "longitude": float(vessel.get("LONGITUDE", 0)),
                            "speed": float(vessel.get("SOG", 0)),
                            "course": float(vessel.get("COG", 0)),
                            "heading": float(vessel.get("HEADING", 0)),
                            "ship_name": vessel.get("NAME", "UNKNOWN"),
                            "ship_type": vessel.get("TYPE", 0),
                            "flag_country": vessel.get("COUNTRY", "UNKNOWN"),
                            "timestamp": datetime.utcnow().isoformat(),
                            "destination": vessel.get("DESTINATION", ""),
                            "source": "AISHub"
                        })
                    except (ValueError, TypeError, KeyError) as e:
                        logger.debug(f"Parse error: {e}")
                        continue
                
                if vessels:
                    logger.info(f"✅ AISHub: Got {len(vessels)} vessels")
                
                return vessels
            else:
                logger.warning(f"⚠️ AISHub returned status {response.status_code}")
                
        except requests.exceptions.Timeout:
            logger.warning("⏱️ AISHub timeout after 15s")
        except requests.exceptions.ConnectionError as e:
            logger.warning(f"🔌 AISHub connection error: {e}")
        except Exception as e:
            logger.warning(f"❌ AISHub error: {type(e).__name__}: {e}")
        
        return []


# Singleton instance
backup_source = BackupAISSource()


# Test function untuk debugging
async def test_backup_sources():
    """Test all backup AIS sources untuk debugging."""
    print("🧪 Testing Backup AIS Sources...")
    print("=" * 60)
    
    # Singapore Strait (very busy area)
    bbox = [[1.0, 103.0], [4.0, 105.0]]
    lat_min, lon_min = bbox[0]
    lat_max, lon_max = bbox[1]
    
    print(f"📍 Test Area: Singapore Strait")
    print(f"   Bbox: {bbox}")
    print()
    
    # Test VesselFinder
    print("1️⃣ Testing VesselFinder (web scraping)...")
    try:
        vessels = await backup_source._fetch_vesselfinder(lat_min, lon_min, lat_max, lon_max)
        print(f"   Result: {len(vessels)} vessels")
        if vessels:
            print(f"   Sample: {vessels[0]}")
    except Exception as e:
        print(f"   Error: {e}")
    print()
    
    # Test MyShipTracking
    print("2️⃣ Testing MyShipTracking...")
    try:
        vessels = await backup_source._fetch_myshiptracking(lat_min, lon_min, lat_max, lon_max)
        print(f"   Result: {len(vessels)} vessels")
        if vessels:
            print(f"   Sample: {vessels[0]}")
    except Exception as e:
        print(f"   Error: {e}")
    print()
    
    # Test AISHub
    print("3️⃣ Testing AISHub (DEMO account - very limited)...")
    try:
        vessels = await backup_source._fetch_aishub(lat_min, lon_min, lat_max, lon_max)
        print(f"   Result: {len(vessels)} vessels")
        if vessels:
            print(f"   Sample: {vessels[0]}")
    except Exception as e:
        print(f"   Error: {e}")
    print()
    
    print("=" * 60)
    print("✅ Test complete!")
    print()
    print("💡 REALITY CHECK:")
    print("   Free AIS data is VERY hard to get. Most APIs require payment.")
    print("   AISstream.io (yang udah kamu punya) is actually one of the best free options!")
    print("   Consider focusing on getting data from AISstream instead of backup sources.")



if __name__ == "__main__":
    # Run test when script is executed directly
    import sys
    logging.basicConfig(level=logging.INFO)
    asyncio.run(test_backup_sources())
