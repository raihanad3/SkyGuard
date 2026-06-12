"""
SkyGuard — Live Map Page
=========================
Real-time flight map using Folium / streamlit-folium.
Shows active flights with color-coded markers by alert level.
"""

import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from streamlit_autorefresh import st_autorefresh

from computer4_dashboard.components.sidebar import render_sidebar, get_db_connection


# Page config
st.set_page_config(
    page_title="SkyGuard — Live Map",
    page_icon="🗺️",
    layout="wide",
)

# Auto-refresh every 10 seconds
st_autorefresh(interval=10_000, key="map_refresh")

# Sidebar
render_sidebar()

# Main content
st.title("📡 RADAR: ASIAN FIR")
st.caption("LIVE SURVEILLANCE & THREAT DETECTION")

# Alert level colors (ATC Radar colors)
ALERT_COLORS = {
    "HIGH": "#ff0000",
    "MEDIUM": "#ffbf00",
    "LOW": "#00a2ff",
    "NORMAL": "#00ff00",
}

ALERT_ICONS = {
    "HIGH": "remove-circle",
    "MEDIUM": "warning-sign",
    "LOW": "info-sign",
    "NORMAL": "plane",
}

try:
    conn = get_db_connection()

    # Get latest inference results (last 30 min)
    df = pd.read_sql("""
        SELECT DISTINCT ON (icao24)
            icao24, callsign, origin_country,
            latitude, longitude, altitude, speed, heading,
            anomaly_score, alert_level, reasons,
            inferred_at
        FROM inference_results
        WHERE inferred_at > NOW() - INTERVAL '30 minutes'
          AND latitude IS NOT NULL
          AND longitude IS NOT NULL
        ORDER BY icao24, inferred_at DESC
    """, conn)

    conn.close()

    if df.empty:
        st.info("📡 Waiting for flight data... Make sure Computer 1, 2, and 3 are running.")
    else:
        # Stats row
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("CONTACTS", len(df))
        col2.metric("LVL 1 THREAT", len(df[df["alert_level"] == "HIGH"]))
        col3.metric("LVL 2 WARN", len(df[df["alert_level"] == "MEDIUM"]))
        col4.metric("LVL 3 NOTICE", len(df[df["alert_level"] == "LOW"]))

        # Create Folium map centered on Asia
        m = folium.Map(
            location=[25.0, 105.0],
            zoom_start=3,
            tiles="CartoDB dark_matter",
        )

        # Add flight markers
        for _, row in df.iterrows():
            level = row["alert_level"]
            color = ALERT_COLORS.get(level, "gray")
            icon = ALERT_ICONS.get(level, "plane")

            popup_html = f"""
            <div style="font-family: 'Courier New', Courier, monospace; min-width: 200px; color: #000; background-color: #fff; padding: 5px; border: 2px solid {color};">
                <b>FLT: {row['callsign'] or 'N/A'}</b> ({row['icao24']})<br>
                <hr style="margin: 4px 0; border-color: #333;">
                ORG: {row['origin_country']}<br>
                POS: {row['latitude']:.4f}, {row['longitude']:.4f}<br>
                ALT: {row['altitude']:.0f} FL<br>
                SPD: {row['speed']:.0f} KTS<br>
                HDG: {row['heading']:.0f}°<br>
                <hr style="margin: 4px 0; border-color: #333;">
                ANOMALY: {row['anomaly_score']:.1%}<br>
                STATUS: <b style="color: {color}">{level}</b>
            </div>
            """

            folium.Marker(
                location=[row["latitude"], row["longitude"]],
                popup=folium.Popup(popup_html, max_width=300),
                tooltip=f"{row['callsign'] or row['icao24']} — {level}",
                icon=folium.Icon(color=color, icon=icon, prefix="glyphicon"),
            ).add_to(m)

        # Render map
        st_folium(m, width=None, height=600, use_container_width=True)

        # Flight table
        st.subheader("CONTACT LOG")
        
        # Add ATC recommendation
        def get_atc_action(level):
            if level == "HIGH": return "INTERCEPT"
            if level == "MEDIUM": return "RADIO CONTACT"
            if level == "LOW": return "MONITOR"
            return "CLEAR"
            
        display_df = df[[
            "icao24", "callsign", "origin_country",
            "altitude", "speed", "heading", "anomaly_score", "alert_level"
        ]].copy()
        
        display_df["atc_action"] = display_df["alert_level"].apply(get_atc_action)
        
        display_df.columns = [
            "ICAO", "CALLSIGN", "ORG",
            "ALT", "SPD", "HDG", "ANOMALY", "LVL", "ATC ACTION"
        ]
        
        # Force string formatting to look monospace-like in Streamlit dataframe
        display_df["ALT"] = display_df["ALT"].apply(lambda x: f"{x:05.0f}")
        display_df["SPD"] = display_df["SPD"].apply(lambda x: f"{x:03.0f}")
        display_df["HDG"] = display_df["HDG"].apply(lambda x: f"{x:03.0f}")
        display_df["ANOMALY"] = display_df["ANOMALY"].apply(lambda x: f"{x:.2f}")

        st.dataframe(display_df, use_container_width=True, height=300)

except Exception as e:
    st.error(f"❌ Database error: {e}")
    st.info("Make sure PostgreSQL is running (docker-compose up)")
