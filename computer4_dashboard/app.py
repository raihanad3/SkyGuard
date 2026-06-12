"""
SkyGuard — Computer 4: Streamlit Dashboard (Main App)
======================================================
Main entry point for the Streamlit multi-page dashboard.
Reads data from PostgreSQL (populated by Computer 3).

Usage:
    streamlit run computer4_dashboard/app.py
"""

import streamlit as st
from streamlit_autorefresh import st_autorefresh

from computer4_dashboard.components.sidebar import render_sidebar, get_db_connection


# ============================================================
# Page Configuration
# ============================================================
st.set_page_config(
    page_title="SkyGuard — Dashboard",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Auto-refresh every 10 seconds
st_autorefresh(interval=10_000, key="home_refresh")


# ============================================================
# Sidebar
# ============================================================
render_sidebar()


# ============================================================
# Main Content — Home Page
# ============================================================
st.title("📡 ATC SECTOR CONTROL: ASIAN FIR")
st.markdown("**SURVEILLANCE TERMINAL TERMINAL 1 — STATUS: ONLINE**")

st.divider()

# ATC specific overview
st.subheader("SYSTEM DIAGNOSTICS")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("""
    **RADAR FEEDS**
    - PRIMARY RADAR (OPENSKY): ONLINE
    - OSINT / NEWS: ONLINE
    - LATENCY: < 1.0s
    """)

with col2:
    st.markdown("""
    **PROCESSING**
    - KAFKA BROKER: CONNECTED
    - SPARK STREAMING: ACTIVE
    - INFERENCE ENGINE: ARMED
    """)

with col3:
    st.markdown("""
    **SECTOR ALERTS**
    - AUTO-INTERCEPT: DISABLED
    - ATC NOTIFICATIONS: ENABLED
    - DB LINK: ESTABLISHED
    """)

st.divider()

# Live status
st.subheader("REAL-TIME TRAFFIC METRICS")

try:
    conn = get_db_connection()
    cur = conn.cursor()

    # Recent activity
    cur.execute("""
        SELECT COUNT(*) FROM preprocessed_flights
        WHERE processed_at > NOW() - INTERVAL '5 minutes'
    """)
    recent_preprocessed = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*) FROM inference_results
        WHERE inferred_at > NOW() - INTERVAL '5 minutes'
    """)
    recent_inferences = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*) FROM alerts
        WHERE created_at > NOW() - INTERVAL '5 minutes'
    """)
    recent_alerts = cur.fetchone()[0]

    cur.execute("SELECT COUNT(DISTINCT icao24) FROM flight_info")
    total_flights = cur.fetchone()[0]

    conn.close()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("SCAN TARGETS (5M)", recent_preprocessed)
    col2.metric("THREAT SCANS", recent_inferences)
    col3.metric("ACTIVE ALERTS", recent_alerts)
    col4.metric("TOTAL AIRCRAFT", f"{total_flights:,}")

    # Pipeline health
    if recent_preprocessed > 0 and recent_inferences > 0:
        st.success("STATUS: GREEN — ALL RADAR SWEEPS NOMINAL")
    elif recent_preprocessed > 0:
        st.warning("STATUS: AMBER — RADAR ACTIVE, THREAT SCAN DELAYED")
    else:
        st.error("STATUS: RED — SIGNAL LOST. RESTART DATA LINK.")

except Exception as e:
    st.error(f"❌ Cannot connect to database: {e}")
    st.info("""
    **Setup Instructions:**
    1. Start infrastructure: `docker-compose up -d`
    2. Start Computer 1: `python -m computer1_producer.main`
    3. Start Computer 2: `python -m computer2_preprocessing.main`
    4. Start Computer 3: `python -m computer3_inference.main`
    """)

st.divider()

# Navigation
st.subheader("🧭 Navigation")
st.markdown("""
Use the **sidebar** or the links below to navigate:

| Page | Description |
|------|-------------|
| 🗺️ **Live Map** | Real-time flight positions on interactive map |
| 🚨 **Alerts** | Alert monitoring with filtering and timeline |
| 📊 **Analytics** | Statistical insights and visualizations |
""")
