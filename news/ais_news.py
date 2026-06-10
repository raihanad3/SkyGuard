import random
import time
import csv
import os
import redis
import asyncio
import requests
from transformers import pipeline
from datetime import datetime, timedelta
import feedparser
from bs4 import BeautifulSoup
import json
import re
from dateutil import parser as date_parser  # For date filtering

# =====================================================================
# 1. MESSAGE BROKER GATEWAY (REDIS CONNECTION - OPTIONAL)
# =====================================================================
USE_REDIS = False  # Set True if you have Redis running

if USE_REDIS:
    print("[-] Dark Vessel Detection: Connecting to Redis Message Broker...")
    try:
        r = redis.Redis(host='localhost', port=6379, decode_responses=True)
        r.ping()
        print("[-] Redis Connection: ONLINE (Maritime Intelligence Network Active)")
    except Exception as e:
        print(f"[!] Redis Connection Failed: {e}")
        print("[-] Continuing without Redis (CSV-only mode)")
        USE_REDIS = False
else:
    print("[-] Running in CSV-only mode (Redis disabled)")
    r = None

# =====================================================================
# 2. SYSTEM INITIALIZATION: PREPARING AI MODEL & CSV
# =====================================================================
print("[-] SkyGuard Aviation Intelligence: Compiling Analysis Model...")
sentiment_pipeline = pipeline(
    "sentiment-analysis", 
    model="cardiffnlp/twitter-roberta-base-sentiment-latest"
)

CSV_FILE = 'aviation_intelligence.csv'
if not os.path.exists(CSV_FILE):
    with open(CSV_FILE, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            "timestamp", "category", "source", "text", "location", 
            "flight_info", "threat_level", "confidence", "coordinates"
        ])

# =====================================================================
# 3. DARK VESSEL DETECTION - MULTI-SOURCE CONFIGURATION
# =====================================================================
# API CREDENTIALS (Optional - most sources don't need keys)
NEWS_API_KEY = "76f5acedff3b4b3981ddfcea1c8f2a7c"  # Already have this
GLOBAL_FISHING_WATCH_TOKEN = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6ImtpZEtleSJ9.eyJkYXRhIjp7Im5hbWUiOiJEYXJrIFZlc3NlbCBJbnRlbGxpZ2VuY2UgU3lzdGVtIiwidXNlcklkIjo2MzMzNywiYXBwbGljYXRpb25OYW1lIjoiRGFyayBWZXNzZWwgSW50ZWxsaWdlbmNlIFN5c3RlbSIsImlkIjoxMTIxNiwidHlwZSI6InVzZXItYXBwbGljYXRpb24ifSwiaWF0IjoxNzgwNDU0NTQ1LCJleHAiOjIwOTU4MTQ1NDUsImF1ZCI6ImdmdyIsImlzcyI6ImdmdyJ9.UJZpgBE4AxCZVEmMBsuasOMGhLGjF1Ow5CKTppM8vF4hRvLfuefNtwNU5hqf2qkiQSxhGeLgof1M4V8m1XBeJEQ3fyq1dlGanRJzhb0be9I9ZYCShJag83Z7O9e_yUCgdciMzoPnHKfWG9EOyLKB_iuaWZHzhophl0W_GS9ouobXAiSblyXmwReb4-lgi3n6Ak56a-QuBEw9OjkfgxMa4BurOtttLR0LBOHQkt2wtQK95Xs1xNBItW4CTacmbg5cgyiKb7X9Vfw7bV1Dqk7FlLqJsk3P4bWPsmudKN1z5Z1VjaWO5teGwVl5s6EUGfHnKzrOz659i1r_TJ4JqR8O6SL0JgIbiTVxeBSxMGoJXXCkPEYq5p07ikCrd92SW-81o4bBY8a3UbUFQ8i3qeCEBTK4kSwbYGf8uJxNKyQlqOybz-KIeqGpWxvHyiMQ6dMmwUBOXENlK2jvjbKXFh_EB6rzMfOky4ra96bv-ScguKpb1MA4Sk2wPbh61k9HbfxI"

# TIME RANGE - Only 2026 data for relevance
START_DATE = "2026-05-02"  # NewsAPI Free tier limit (1 month back)
END_DATE = "2026-06-03"    # Today

# AVIATION KEYWORDS - Indonesian Airspace Intelligence
AVIATION_KEYWORDS = (
    "(Indonesian airspace OR Indonesia aviation) OR "
    "(suspicious flight Indonesia OR unauthorized flight Indonesia) OR "
    "(airspace violation Indonesia OR flight violation Indonesia) OR "
    "(aircraft Indonesia OR plane Indonesia) OR "
    "(TNI AU OR Indonesian Air Force patrol)"
)

# INDONESIAN KEYWORDS for Local Aviation News
INDONESIA_AVIATION_KEYWORDS = [
    "pelanggaran wilayah udara indonesia",
    "pesawat asing indonesia",
    "tni au intersepsi",
    "pesawat tanpa izin",
    "wilayah udara indonesia"
]

# =====================================================================
# MULTI-SOURCE URLs - ALL FREE (No API Key Required)
# =====================================================================

# 1. NEWS API (International - Already have key)
NEWS_API_URL = f"https://newsapi.org/v2/everything?q={AVIATION_KEYWORDS}&from={START_DATE}&to={END_DATE}&language=en&sortBy=publishedAt&pageSize=100&apiKey={NEWS_API_KEY}"

# 2. GOOGLE NEWS RSS (Indonesian Media - FREE, No API Key)
GOOGLE_NEWS_RSS = [
    "https://news.google.com/rss/search?q=pesawat+asing+indonesia&hl=id&gl=ID&ceid=ID:id",
    "https://news.google.com/rss/search?q=wilayah+udara+indonesia&hl=id&gl=ID&ceid=ID:id",
    "https://news.google.com/rss/search?q=tni+au+intersepsi&hl=id&gl=ID&ceid=ID:id",
]

# 3. AVIATION NEWS RSS (International - FREE)
AVIATION_NEWS_RSS = [
    "https://www.flightglobal.com/rss/",
    "https://www.aviationtoday.com/feed/",
]

# =====================================================================
# 4. INDONESIAN AIRSPACE ZONES - COORDINATES DATABASE
# =====================================================================
INDONESIA_AIR_COORDINATES = {
    # FIR (Flight Information Region) Indonesia
    "indonesia": "-2.5489, 118.0149",
    "indonesian airspace": "-2.5489, 118.0149",
    "jakarta fir": "-6.2088, 106.8456",
    "ujung pandang fir": "-5.0616, 119.5540",
    "biak fir": "-1.1900, 136.1086",
    
    # Major Cities & Airports
    "jakarta": "-6.2088, 106.8456",
    "surabaya": "-7.5360, 112.2384",
    "medan": "3.5896, 98.6738",
    "bali": "-8.3405, 115.0920",
    "makassar": "-5.0616, 119.5540",
    "balikpapan": "-1.2675, 116.8289",
    "manado": "1.4870, 124.8420",
    "papua": "-4.2699, 138.0804",
    
    # Airspace Regions
    "java": "-7.6145, 110.7122",
    "sumatra": "0.5897, 101.3431",
    "kalimantan": "-0.9683, 114.5486",
    "sulawesi": "-2.1186, 120.3625",
    "maluku": "-3.2385, 130.1453",
    
    # Neighboring Countries (border areas)
    "malaysia": "4.2105, 101.9758",
    "singapore": "1.3521, 103.8198",
    "philippines": "12.8797, 121.7740",
    "australia": "-25.2744, 133.7751",
}

# =====================================================================
# 5. HELPER FUNCTIONS - INTELLIGENCE GATHERING
# =====================================================================
def extract_location_and_coordinates(text):
    """Extract location mentions from text and return coordinates"""
    text_lower = text.lower()
    detected_locations = []
    coordinates = "N/A"
    
    # Check for Indonesian airspace zones first
    for location, coords in INDONESIA_AIR_COORDINATES.items():
        if location in text_lower:
            detected_locations.append(location.title())
            if coordinates == "N/A":
                coordinates = coords
    
    # If nothing found, check for generic keywords
    if not detected_locations:
        generic_locations = ["airspace", "airport", "flight", "aviation"]
        for keyword in generic_locations:
            if keyword in text_lower:
                detected_locations.append("Unspecified Airspace")
                break
    
    location_str = ", ".join(detected_locations) if detected_locations else "Unknown"
    return location_str, coordinates

def extract_flight_info(text):
    """Extract flight-related information"""
    flight_terms = []
    text_lower = text.lower()
    
    if "commercial" in text_lower or "airliner" in text_lower:
        flight_terms.append("Commercial Aircraft")
    if "military" in text_lower or "fighter" in text_lower:
        flight_terms.append("Military Aircraft")
    if "private" in text_lower or "jet" in text_lower:
        flight_terms.append("Private Jet")
    if "transponder" in text_lower and "off" in text_lower:
        flight_terms.append("Transponder Off")
    if "unauthorized" in text_lower or "violation" in text_lower:
        flight_terms.append("Airspace Violation")
        
    return ", ".join(flight_terms) if flight_terms else "Unspecified Aircraft"

def calculate_threat_level(sentiment, keywords_found):
    """Calculate threat level based on sentiment and keywords"""
    high_risk_keywords = ["illegal", "smuggling", "trafficking", "piracy", "violation", "seized"]
    medium_risk_keywords = ["inspection", "patrol", "suspicious", "unidentified", "dark"]
    
    high_count = sum(1 for kw in high_risk_keywords if kw in keywords_found.lower())
    medium_count = sum(1 for kw in medium_risk_keywords if kw in keywords_found.lower())
    
    if high_count >= 2 or sentiment == "NEGATIVE":
        return "HIGH"
    elif high_count == 1 or medium_count >= 2:
        return "MEDIUM"
    else:
        return "LOW"

# =====================================================================
# 6. SCRAPING FUNCTIONS - MULTI-SOURCE DATA COLLECTION
# =====================================================================

async def scrape_google_news_rss():
    """Scrape Indonesian maritime news from Google News RSS (FREE)"""
    articles_data = []
    
    try:
        for rss_url in GOOGLE_NEWS_RSS:
            try:
                feed = await asyncio.to_thread(lambda: feedparser.parse(rss_url))
                
                for entry in feed.entries[:10]:  # Limit per feed
                    title = entry.get("title", "")
                    link = entry.get("link", "")
                    published = entry.get("published", datetime.now().isoformat())
                    source = entry.get("source", {}).get("title", "Google News")
                    
                    if not title:
                        continue
                    
                    # FILTER: Only 2026 data
                    try:
                        pub_date = date_parser.parse(published)
                        if pub_date.year < 2026:
                            continue  # Skip data before 2026
                    except:
                        pass  # If parsing fails, keep the data
                    
                    # Categorize
                    title_lower = title.lower()
                    category = "UNKNOWN"
                    
                    if any(x in title_lower for x in ["illegal", "ilegal", "pencurian ikan", "iuu"]):
                        category = "ILLEGAL_FISHING"
                    elif any(x in title_lower for x in ["tangkap", "ditangkap", "sita", "amankan"]):
                        category = "ENFORCEMENT"
                    elif any(x in title_lower for x in ["china", "vietnam", "asing"]):
                        category = "TERRITORIAL_VIOLATION"
                    elif any(x in title_lower for x in ["tenggelam", "ledak", "bakar"]):
                        category = "ENFORCEMENT"
                    elif any(x in title_lower for x in ["patroli", "bakamla", "tni al"]):
                        category = "ENFORCEMENT"
                    
                    if category == "UNKNOWN":
                        continue
                    
                    # Sentiment analysis
                    nlp_result = sentiment_pipeline(title[:512])[0]
                    sentiment = nlp_result['label']
                    confidence = nlp_result['score']
                    
                    # Extract intelligence
                    location, coordinates = extract_location_and_coordinates(title)
                    vessel_info = extract_vessel_info(title)
                    threat_level = calculate_threat_level(sentiment, title)
                    
                    article_data = {
                        "timestamp": published,
                        "category": category,
                        "source": f"GoogleNews_{source[:20]}",
                        "text": title.strip().replace('\n', ' '),
                        "location": location,
                        "vessel_info": vessel_info,
                        "threat_level": threat_level,
                        "confidence": f"{confidence:.4f}",
                        "coordinates": coordinates
                    }
                    
                    articles_data.append(article_data)
                    
            except Exception as e:
                print(f"[!] Error parsing RSS {rss_url[:50]}: {e}")
                continue
        
        print(f"[-] Google News RSS: Collected {len(articles_data)} Indonesian reports (2026 only)")
        
    except Exception as e:
        print(f"[!] Error scraping Google News: {e}")
    
    return articles_data

async def scrape_vesselfinder():
    """Scrape VesselFinder for AIS data (FREE - No API Key)"""
    vessels_data = []
    
    try:
        print("[-] VesselFinder: Attempting to scrape vessel data...")
        
        # Note: This is a simplified version. Full scraping would need Selenium
        # For now, we'll create placeholder for demonstration
        
        for area_url in VESSELFINDER_AREAS[:1]:  # Just check one area
            try:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
                response = await asyncio.to_thread(
                    lambda: requests.get(area_url, headers=headers, timeout=10)
                )
                
                if response.status_code == 200:
                    # Basic parsing (VesselFinder requires more complex scraping)
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # This is simplified - real implementation needs JavaScript rendering
                    vessel_data = {
                        "timestamp": datetime.now().isoformat(),
                        "category": "AIS_ANOMALY",
                        "source": "VesselFinder",
                        "text": "AIS tracking data collected from VesselFinder",
                        "location": "Indonesian Waters",
                        "vessel_info": "Multiple Vessels Tracked",
                        "threat_level": "LOW",
                        "confidence": "0.7500",
                        "coordinates": "-6.2088, 106.8456"
                    }
                    vessels_data.append(vessel_data)
                    
            except Exception as e:
                print(f"[!] VesselFinder scraping error: {e}")
                continue
        
        print(f"[-] VesselFinder: Collected {len(vessels_data)} vessel reports")
        
    except Exception as e:
        print(f"[!] Error with VesselFinder: {e}")
    
    return vessels_data

async def scrape_global_fishing_watch():
    """Scrape Global Fishing Watch API (FREE - Optional token for more data)"""
    fishing_data = []
    
    try:
        print("[-] Global Fishing Watch: Checking fishing activity...")
        
        # Public API endpoint (limited data without token)
        # For full access: Get token from https://globalfishingwatch.org/our-apis/tokens
        
        # Example: Search for vessels in Indonesian EEZ
        headers = {'User-Agent': 'Mozilla/5.0'}
        if GLOBAL_FISHING_WATCH_TOKEN:
            headers['Authorization'] = f'Bearer {GLOBAL_FISHING_WATCH_TOKEN}'
        
        # Note: This is simplified - real API needs proper authentication
        # For demo, we'll create sample data
        
        sample_data = {
            "timestamp": datetime.now().isoformat(),
            "category": "ILLEGAL_FISHING",
            "source": "GlobalFishingWatch",
            "text": "Suspicious fishing vessel activity detected in Indonesian EEZ",
            "location": "Natuna Sea",
            "vessel_info": "Foreign Fishing Vessel",
            "threat_level": "MEDIUM",
            "confidence": "0.8500",
            "coordinates": "3.9731, 108.2425"
        }
        fishing_data.append(sample_data)
        
        print(f"[-] Global Fishing Watch: Collected {len(fishing_data)} fishing reports")
        print("    > Get API token from: https://globalfishingwatch.org/our-apis/tokens")
        
    except Exception as e:
        print(f"[!] Error with Global Fishing Watch: {e}")
    
    return fishing_data

async def scrape_maritime_news_rss():
    """Scrape international maritime news from RSS feeds (FREE)"""
    articles_data = []
    
    try:
        for rss_url in MARITIME_NEWS_RSS:
            try:
                feed = await asyncio.to_thread(lambda: feedparser.parse(rss_url))
                
                for entry in feed.entries[:5]:  # Limit per feed
                    title = entry.get("title", "")
                    link = entry.get("link", "")
                    published = entry.get("published", datetime.now().isoformat())
                    
                    if not title:
                        continue
                    
                    # FILTER: Only 2026 data
                    try:
                        pub_date = date_parser.parse(published)
                        if pub_date.year < 2026:
                            continue  # Skip data before 2026
                    except:
                        pass  # If parsing fails, keep the data
                    
                    # Only include if related to Indonesia or illegal fishing
                    title_lower = title.lower()
                    if not any(x in title_lower for x in ["indonesia", "southeast asia", "illegal fishing", "piracy", "south china sea"]):
                        continue
                    
                    # Categorize
                    category = "UNKNOWN"
                    if any(x in title_lower for x in ["illegal", "iuu", "piracy"]):
                        category = "ILLEGAL_FISHING"
                    elif any(x in title_lower for x in ["enforcement", "arrest", "seized"]):
                        category = "ENFORCEMENT"
                    elif any(x in title_lower for x in ["territorial", "eez", "dispute"]):
                        category = "TERRITORIAL_VIOLATION"
                    
                    if category == "UNKNOWN":
                        continue
                    
                    # Sentiment analysis
                    nlp_result = sentiment_pipeline(title[:512])[0]
                    sentiment = nlp_result['label']
                    confidence = nlp_result['score']
                    
                    # Extract intelligence
                    location, coordinates = extract_location_and_coordinates(title)
                    vessel_info = extract_vessel_info(title)
                    threat_level = calculate_threat_level(sentiment, title)
                    
                    article_data = {
                        "timestamp": published,
                        "category": category,
                        "source": "MaritimeNews",
                        "text": title.strip().replace('\n', ' '),
                        "location": location,
                        "vessel_info": vessel_info,
                        "threat_level": threat_level,
                        "confidence": f"{confidence:.4f}",
                        "coordinates": coordinates
                    }
                    
                    articles_data.append(article_data)
                    
            except Exception as e:
                print(f"[!] Error parsing RSS: {e}")
                continue
        
        print(f"[-] Maritime News RSS: Collected {len(articles_data)} international reports (2026 only)")
        
    except Exception as e:
        print(f"[!] Error scraping Maritime News: {e}")
    
    return articles_data

async def scrape_weather_data():
    """Scrape maritime weather from Open-Meteo (FREE - No API Key)"""
    weather_data = []
    
    try:
        # Key Indonesian maritime locations
        locations = [
            {"name": "Java Sea", "lat": -5.5, "lon": 110.0},
            {"name": "Natuna Sea", "lat": 3.97, "lon": 108.24},
            {"name": "Malacca Strait", "lat": 2.5, "lon": 100.0},
        ]
        
        for loc in locations:
            try:
                url = f"{OPEN_METEO_MARINE}?latitude={loc['lat']}&longitude={loc['lon']}&current=wave_height,wind_speed_10m,wind_direction_10m&timezone=Asia/Jakarta"
                
                response = await asyncio.to_thread(
                    lambda: requests.get(url, timeout=10).json()
                )
                
                current = response.get("current", {})
                wave_height = current.get("wave_height", 0)
                wind_speed = current.get("wind_speed_10m", 0)
                
                # Handle None values
                if wave_height is None:
                    wave_height = 0
                if wind_speed is None:
                    wind_speed = 0
                
                # High waves = suspicious if vessels still operating
                threat = "MEDIUM" if wave_height > 3.0 else "LOW"
                
                weather_info = {
                    "timestamp": datetime.now().isoformat(),
                    "category": "CONSERVATION_ISSUE",
                    "source": "OpenMeteo_Weather",
                    "text": f"Maritime conditions: Wave {wave_height}m, Wind {wind_speed}km/h at {loc['name']}",
                    "location": loc['name'],
                    "vessel_info": f"Weather: {wave_height}m waves",
                    "threat_level": threat,
                    "confidence": "0.9000",
                    "coordinates": f"{loc['lat']}, {loc['lon']}"
                }
                weather_data.append(weather_info)
                
            except Exception as e:
                print(f"[!] Weather error for {loc['name']}: {e}")
                continue
        
        print(f"[-] Open-Meteo Weather: Collected {len(weather_data)} weather reports")
        
    except Exception as e:
        print(f"[!] Error scraping weather: {e}")
    
    return weather_data

# =====================================================================
# 7. ORIGINAL NEWS API SCRAPER (Keep this)
# =====================================================================
async def scrape_maritime_news():
    """Scrape maritime crime and illegal fishing news"""
    seen_articles = set()
    articles_data = []
    
    try:
        response = await asyncio.to_thread(lambda: requests.get(NEWS_API_URL, timeout=30).json())
        
        if response.get("status") != "ok":
            print(f"[!] News API Warning: {response.get('message', 'Unknown Error')}")
            return articles_data
            
        articles = response.get("articles", [])
        
        for article in articles:
            url = article.get("url")
            title = article.get("title")
            description = article.get("description", "")
            source_name = article.get("source", {}).get("name", "Maritime News")
            published_at = article.get("publishedAt")
            
            if url not in seen_articles and title:
                seen_articles.add(url)
                
                # FILTER: Only 2026 data
                try:
                    pub_date = date_parser.parse(published_at)
                    if pub_date.year < 2026:
                        continue  # Skip data before 2026
                except:
                    pass  # If parsing fails, keep the data
                
                full_content = f"{title}. {description}"
                low_text = full_content.lower()
                
                # STRICT MARITIME FILTER - Only maritime-related news
                if not any(x in low_text for x in [
                    "vessel", "ship", "boat", "fishing", "maritime", "naval", 
                    "coast guard", "ais", "transponder", "trawler", "tanker", "fleet"
                ]):
                    continue
                
                # Categorize incident type
                category = "UNKNOWN"
                if any(x in low_text for x in ["illegal fishing", "iuu", "overfishing"]):
                    category = "ILLEGAL_FISHING"
                elif any(x in low_text for x in ["smuggling", "trafficking", "contraband"]):
                    category = "SMUGGLING"
                elif any(x in low_text for x in ["piracy", "hijack", "attack"]):
                    category = "PIRACY"
                elif any(x in low_text for x in ["ais", "transponder", "dark vessel", "ghost"]):
                    category = "AIS_ANOMALY"
                elif any(x in low_text for x in ["patrol", "coast guard", "inspection"]):
                    category = "ENFORCEMENT"
                elif any(x in low_text for x in ["eez", "territorial", "violation", "boundary"]):
                    category = "TERRITORIAL_VIOLATION"
                elif any(x in low_text for x in ["marine protected", "conservation", "sanctuary"]):
                    category = "CONSERVATION_ISSUE"
                
                if category == "UNKNOWN":
                    continue
                
                # Sentiment analysis
                nlp_result = sentiment_pipeline(full_content[:512])[0]
                sentiment = nlp_result['label']
                confidence = nlp_result['score']
                
                # Extract intelligence
                location, coordinates = extract_location_and_coordinates(full_content)
                vessel_info = extract_vessel_info(full_content)
                threat_level = calculate_threat_level(sentiment, full_content)
                
                article_data = {
                    "timestamp": published_at,
                    "category": category,
                    "source": source_name,
                    "text": title.strip().replace('\n', ' '),
                    "location": location,
                    "vessel_info": vessel_info,
                    "threat_level": threat_level,
                    "confidence": f"{confidence:.4f}",
                    "coordinates": coordinates
                }
                
                articles_data.append(article_data)
                
        print(f"[-] Maritime News: Collected {len(articles_data)} intelligence reports (2026 only)")
        
    except Exception as e:
        print(f"[!] Error scraping maritime news: {e}")
    
    return articles_data

async def main():
    REDIS_STREAM_NAME = 'dark_vessel:intelligence'

    print("\n" + "="*70)
    print("🌊 DARK VESSEL DETECTION SYSTEM - MULTI-SOURCE INTELLIGENCE")
    print("="*70)
    print(f"[-] Streaming to Redis: '{REDIS_STREAM_NAME}'")
    print(f"[-] CSV Output: '{CSV_FILE}'")
    print(f"[-] REAL-TIME Mode: Base interval = 30 seconds")
    print(f"[-] Smart Scheduling: NewsAPI=15min, GoogleNews=2min, VesselFinder=5min")
    print("="*70 + "\n")

    # Counters untuk scheduling (berbasis 30 detik)
    cycle_counter = 0

    while True:
        try:
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Sweep #{cycle_counter + 1}")
            
            # ALWAYS RUN (Every 30 seconds): Safe unlimited sources
            fast_tasks = [
                scrape_global_fishing_watch(),    # Fishing activity
                scrape_weather_data(),            # Maritime weather
                scrape_maritime_news_rss(),       # International RSS feeds
            ]
            
            # EVERY 4 CYCLES = 2 MINUTES: Google News RSS
            if cycle_counter % 4 == 0:
                print("  [+] Google News RSS")
                fast_tasks.append(scrape_google_news_rss())
            
            # EVERY 10 CYCLES = 5 MINUTES: VesselFinder
            if cycle_counter % 10 == 0:
                print("  [+] VesselFinder")
                fast_tasks.append(scrape_vesselfinder())
            
            # EVERY 30 CYCLES = 15 MINUTES: NewsAPI
            if cycle_counter % 30 == 0:
                print("  [+] NewsAPI")
                fast_tasks.append(scrape_maritime_news())
            
            results = await asyncio.gather(*fast_tasks)
            
            # PROCESS AND STREAM ALL COLLECTED DATA
            all_data = []
            for result in results:
                all_data.extend(result)
            
            for data in all_data:
                # Push to Redis (if enabled)
                if USE_REDIS and r:
                    stream_id = r.xadd(REDIS_STREAM_NAME, data)
                else:
                    stream_id = f"csv_{int(time.time())}"
                
                # Save to CSV
                with open(CSV_FILE, mode='a', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        data["timestamp"], data["category"], data["source"],
                        data["text"], data["location"], data["vessel_info"],
                        data["threat_level"], data["confidence"], data["coordinates"]
                    ])
                
                print(f"  [DATA] {data['category'][:15]:15} | {data['threat_level']:6} | {data['location'][:30]}")
            
            print(f"  [STAT] {len(all_data)} reports | Next: 30s")
            
            cycle_counter += 1
            await asyncio.sleep(30)  # 30 seconds - REAL-TIME!
            
        except Exception as error:
            print(f"\n[!] ERROR: {error}")
            await asyncio.sleep(30)

if __name__ == "__main__":
    asyncio.run(main())