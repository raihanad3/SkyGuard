"""
Aviation News Intelligence Scraper
Scrape berita penerbangan suspicious activity di Indonesian airspace.
"""

import asyncio
import requests
import feedparser
from datetime import datetime
from transformers import pipeline

sentiment_pipeline = pipeline(
    "sentiment-analysis",
    model="cardiffnlp/twitter-roberta-base-sentiment-latest"
)

NEWS_API_KEY = "76f5acedff3b4b3981ddfcea1c8f2a7c"

AVIATION_KEYWORDS = (
    "(Indonesian airspace OR Indonesia aviation) OR "
    "(suspicious flight OR unauthorized flight) OR "
    "(flight violation Indonesia OR airspace violation)"
)

async def scrape_aviation_news():
    """Scrape aviation news dari NewsAPI."""
    articles = []
    
    try:
        url = f"https://newsapi.org/v2/everything?q={AVIATION_KEYWORDS}&language=en&sortBy=publishedAt&pageSize=20&apiKey={NEWS_API_KEY}"
        
        response = await asyncio.to_thread(
            lambda: requests.get(url, timeout=30).json()
        )
        
        if response.get("status") == "ok":
            for article in response.get("articles", []):
                title = article.get("title", "")
                if not title:
                    continue
                
                nlp_result = sentiment_pipeline(title[:512])[0]
                
                articles.append({
                    "timestamp": article.get("publishedAt"),
                    "title": title,
                    "source": article.get("source", {}).get("name", "Unknown"),
                    "sentiment": nlp_result['label'],
                    "confidence": nlp_result['score']
                })
        
        print(f"Aviation news: Found {len(articles)} articles")
    
    except Exception as e:
        print(f"Aviation news error: {e}")
    
    return articles

if __name__ == "__main__":
    asyncio.run(scrape_aviation_news())
