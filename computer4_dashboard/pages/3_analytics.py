"""
SkyGuard — Analytics Page
===========================
Statistical analysis and visualizations of flight data.
"""

import streamlit as st
import pandas as pd
from streamlit_autorefresh import st_autorefresh

from computer4_dashboard.components.sidebar import render_sidebar, get_db_connection
from computer4_dashboard.components.charts import (
    create_country_bar_chart,
    create_speed_altitude_scatter,
    create_alert_pie_chart,
    create_alerts_timeline,
)


# Page config
st.set_page_config(
    page_title="SkyGuard — Analytics",
    page_icon="📊",
    layout="wide",
)

# Auto-refresh every 30s (analytics doesn't need to be as fast)
st_autorefresh(interval=30_000, key="analytics_refresh")

# Sidebar
render_sidebar()

# Main content
st.title("📊 SYSTEM ANALYTICS")
st.caption("STATISTICAL INSIGHTS ON ASIAN FIR ACTIVITY")

try:
    conn = get_db_connection()

    # ---- Overall Stats ----
    st.subheader("📈 OVERVIEW")

    cur = conn.cursor()

    cur.execute("SELECT COUNT(DISTINCT icao24) FROM flight_info")
    total_flights = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM preprocessed_flights")
    total_positions = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM alerts")
    total_alerts = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM inference_results")
    total_inferences = cur.fetchone()[0]

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("✈️ UNIQUE FLIGHTS", f"{total_flights:,}")
    col2.metric("📍 DATA POINTS", f"{total_positions:,}")
    col3.metric("🧠 INFERENCES", f"{total_inferences:,}")
    col4.metric("🚨 TOTAL INCIDENTS", f"{total_alerts:,}")

    st.divider()

    # ---- Charts Row 1: Country Distribution + Alert Pie ----
    chart_row1_col1, chart_row1_col2 = st.columns(2)

    with chart_row1_col1:
        st.subheader("🌍 TARGETS BY REGION")
        df_countries = pd.read_sql("""
            SELECT origin_country
            FROM flight_info
            WHERE origin_country IS NOT NULL
        """, conn)
        chart = create_country_bar_chart(df_countries)
        if chart:
            st.plotly_chart(chart, use_container_width=True)
        else:
            st.info("No country data yet")

    with chart_row1_col2:
        st.subheader("🚨 INCIDENT BREAKDOWN")
        cur.execute("""
            SELECT alert_level, COUNT(*)
            FROM alerts
            GROUP BY alert_level
        """)
        alert_counts = dict(cur.fetchall())
        chart = create_alert_pie_chart(alert_counts)
        if chart:
            st.plotly_chart(chart, use_container_width=True)
        else:
            st.info("No alerts yet")

    st.divider()

    # ---- Charts Row 2: Speed/Altitude Scatter + Timeline ----
    chart_row2_col1, chart_row2_col2 = st.columns(2)

    with chart_row2_col1:
        st.subheader("💨 SPEED vs ALTITUDE")
        df_scatter = pd.read_sql("""
            SELECT icao24, callsign, speed, altitude,
                   anomaly_score, alert_level
            FROM inference_results
            WHERE speed IS NOT NULL
              AND altitude IS NOT NULL
              AND speed > 0
              AND altitude > 0
            ORDER BY inferred_at DESC
            LIMIT 500
        """, conn)
        chart = create_speed_altitude_scatter(df_scatter)
        if chart:
            st.plotly_chart(chart, use_container_width=True)
        else:
            st.info("No inference data yet")

    with chart_row2_col2:
        st.subheader("📅 INCIDENT TIMELINE")
        df_timeline = pd.read_sql("""
            SELECT alert_level, created_at
            FROM alerts
            WHERE created_at > NOW() - INTERVAL '24 hours'
            ORDER BY created_at DESC
        """, conn)
        chart = create_alerts_timeline(df_timeline)
        if chart:
            st.plotly_chart(chart, use_container_width=True)
        else:
            st.info("No alerts in last 24h")

    st.divider()

    # ---- Top Alerted Flights ----
    st.subheader("🏆 TOP REPEAT OFFENDERS")
    df_top = pd.read_sql("""
        SELECT icao24, callsign,
               COUNT(*) as alert_count,
               MAX(anomaly_score) as max_score,
               MAX(alert_level) as highest_level,
               MAX(created_at) as last_alert
        FROM alerts
        GROUP BY icao24, callsign
        ORDER BY alert_count DESC
        LIMIT 20
    """, conn)

    if not df_top.empty:
        df_top.columns = [
            "ICAO24", "Callsign", "Alert Count",
            "Max Score", "Highest Level", "Last Alert"
        ]
        st.dataframe(df_top, use_container_width=True)
    else:
        st.info("No alerted flights yet")

    conn.close()

except Exception as e:
    st.error(f"❌ Database error: {e}")
    st.info("Make sure PostgreSQL is running (docker-compose up)")
