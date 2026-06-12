from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import psycopg2
from psycopg2.extras import RealDictCursor
import logging
from computer4_dashboard.config.settings import (
    POSTGRES_HOST, POSTGRES_PORT,
    POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB,
)

app = FastAPI(title="SkyGuard ATC API", description="Backend API for React Dashboard")

# Allow CORS for Vite dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger = logging.getLogger("skyguard.api")

def get_db_connection():
    return psycopg2.connect(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
        dbname=POSTGRES_DB,
        cursor_factory=RealDictCursor
    )

@app.get("/api/flights/live")
def get_live_flights():
    """Get flights from the last 30 minutes."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT DISTINCT ON (i.icao24)
                i.icao24, i.callsign, i.origin_country,
                i.latitude, i.longitude, i.altitude, i.speed, i.heading,
                i.anomaly_score, i.alert_level, i.reasons,
                i.vertical_rate, i.last_contact, i.squawk,
                i.inferred_at,
                r.origin_airport_icao, r.destination_airport_icao
            FROM inference_results i
            LEFT JOIN flight_routes r ON TRIM(i.callsign) = TRIM(r.callsign)
            WHERE i.inferred_at > NOW() - INTERVAL '30 minutes'
              AND i.latitude IS NOT NULL
              AND i.longitude IS NOT NULL
            ORDER BY i.icao24, i.inferred_at DESC
        """)
        flights = cur.fetchall()
        conn.close()
        return flights
    except Exception as e:
        logger.error(f"DB Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/weather/live")
def get_live_weather():
    """Get active weather zones."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT hazard, severity, validTimeFrom, validTimeTo, geometry
            FROM weather_zones
        """)
        zones = cur.fetchall()
        conn.close()
        return zones
    except Exception as e:
        logger.error(f"DB Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/flights/{icao24}/history")
def get_flight_history(icao24: str):
    """Get recent telemetry history for a specific flight."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT latitude, longitude, altitude, speed, heading, vertical_rate, inferred_at
            FROM inference_results
            WHERE icao24 = %s
              AND inferred_at > NOW() - INTERVAL '60 minutes'
            ORDER BY inferred_at ASC
        """, (icao24,))
        history = cur.fetchall()
        conn.close()
        return history
    except Exception as e:
        logger.error(f"DB Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/alerts/recent")
def get_recent_alerts(limit: int = 50, hours: int = 24):
    """Get recent alerts."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(f"""
            SELECT a.id, a.icao24, a.callsign, a.alert_level, a.anomaly_score,
                   a.latitude, a.longitude, a.altitude, a.speed, a.heading,
                   a.reasons, a.zone_name, a.created_at,
                   r.origin_airport_icao, r.destination_airport_icao
            FROM alerts a
            LEFT JOIN flight_routes r ON TRIM(a.callsign) = TRIM(r.callsign)
            WHERE a.created_at > NOW() - INTERVAL '{hours} hours'
            ORDER BY a.created_at DESC
            LIMIT {limit}
        """)
        alerts = cur.fetchall()
        conn.close()
        return alerts
    except Exception as e:
        logger.error(f"DB Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/analytics/stats")
def get_analytics_stats():
    """Get aggregated metrics."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("SELECT COUNT(DISTINCT icao24) as count FROM flight_info")
        total_flights = cur.fetchone()['count']
        
        cur.execute("SELECT COUNT(*) as count FROM preprocessed_flights")
        total_positions = cur.fetchone()['count']
        
        cur.execute("SELECT COUNT(*) as count FROM inference_results")
        total_inferences = cur.fetchone()['count']
        
        cur.execute("SELECT COUNT(*) as count FROM alerts")
        total_alerts = cur.fetchone()['count']

        cur.execute("""
            SELECT alert_level, COUNT(*) as count 
            FROM alerts 
            GROUP BY alert_level
        """)
        alert_distribution = cur.fetchall()

        # Country distribution
        cur.execute("""
            SELECT origin_country as country, COUNT(*) as count
            FROM flight_info
            WHERE origin_country IS NOT NULL
            GROUP BY origin_country
            ORDER BY count DESC
            LIMIT 15
        """)
        country_distribution = cur.fetchall()

        # Alert Timeline (last 24 hours, grouped by hour)
        cur.execute("""
            SELECT date_trunc('hour', created_at) as hour, alert_level, COUNT(*) as count
            FROM alerts
            WHERE created_at > NOW() - INTERVAL '24 hours'
            GROUP BY 1, 2
            ORDER BY 1 ASC
        """)
        timeline = cur.fetchall()

        # Top Offenders
        cur.execute("""
            SELECT icao24, callsign,
                   COUNT(*) as alert_count,
                   MAX(anomaly_score) as max_score,
                   MAX(alert_level) as highest_level,
                   MAX(created_at) as last_alert
            FROM alerts
            GROUP BY icao24, callsign
            ORDER BY alert_count DESC
            LIMIT 15
        """)
        top_offenders = cur.fetchall()

        conn.close()
        
        return {
            "overview": {
                "total_flights": total_flights,
                "total_positions": total_positions,
                "total_inferences": total_inferences,
                "total_alerts": total_alerts
            },
            "alert_distribution": alert_distribution,
            "country_distribution": country_distribution,
            "timeline": timeline,
            "top_offenders": top_offenders
        }
    except Exception as e:
        logger.error(f"DB Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
