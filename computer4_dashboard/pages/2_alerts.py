"""
SkyGuard — Alerts Page
========================
Alert monitoring with filtering, details, and timeline.
"""

import streamlit as st
import pandas as pd
import json
from streamlit_autorefresh import st_autorefresh

from computer4_dashboard.components.sidebar import render_sidebar, get_db_connection
from computer4_dashboard.components.charts import create_alerts_timeline, create_alert_pie_chart


# Page config
st.set_page_config(
    page_title="SkyGuard — Alerts",
    page_icon="🚨",
    layout="wide",
)

# Auto-refresh
st_autorefresh(interval=10_000, key="alerts_refresh")

# Sidebar
render_sidebar()

# Main content
st.title("🚨 THREAT LOG")
st.caption("PRIORITY ANOMALY ALERTS (ASIAN FIR)")

try:
    conn = get_db_connection()

    # Filters
    col1, col2, col3 = st.columns(3)

    with col1:
        level_filter = st.multiselect(
            "Alert Level",
            ["HIGH", "MEDIUM", "LOW"],
            default=["HIGH", "MEDIUM", "LOW"],
        )

    with col2:
        time_range = st.selectbox(
            "Time Range",
            ["Last 1 hour", "Last 6 hours", "Last 24 hours", "Last 7 days"],
            index=1,
        )

    with col3:
        limit = st.slider("Max Results", 10, 200, 50)

    # Build time filter
    time_map = {
        "Last 1 hour": "1 hour",
        "Last 6 hours": "6 hours",
        "Last 24 hours": "24 hours",
        "Last 7 days": "7 days",
    }
    interval = time_map[time_range]

    if not level_filter:
        st.warning("⚠️ Please select at least one Alert Level.")
        st.stop()

    # Fetch alerts
    levels_str = ", ".join([f"'{l}'" for l in level_filter])
    query = f"""
        SELECT a.id, a.icao24, a.callsign, a.alert_level, a.anomaly_score,
               a.latitude, a.longitude, a.altitude, a.speed, a.heading,
               a.reasons, a.zone_name, a.created_at,
               r.origin_airport_icao, r.destination_airport_icao,
               r.registration, r.aircraft_type, r.aircraft_desc
        FROM alerts a
        LEFT JOIN flight_routes r ON TRIM(a.callsign) = TRIM(r.callsign)
        WHERE a.alert_level IN ({levels_str})
          AND a.created_at > NOW() - INTERVAL '{interval}'
        ORDER BY a.created_at DESC
        LIMIT {limit}
    """

    df = pd.read_sql(query, conn)

    # Alert counts for pie chart
    cur = conn.cursor()
    cur.execute(f"""
        SELECT alert_level, COUNT(*)
        FROM alerts
        WHERE created_at > NOW() - INTERVAL '{interval}'
        GROUP BY alert_level
    """)
    alert_counts = dict(cur.fetchall())
    conn.close()

    if df.empty:
        st.info("📡 No alerts in selected time range.")
    else:
        # Summary metrics
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("🔴 LVL 1 THREAT", alert_counts.get("HIGH", 0))
        col2.metric("🟡 LVL 2 WARN", alert_counts.get("MEDIUM", 0))
        col3.metric("🔵 LVL 3 NOTICE", alert_counts.get("LOW", 0))
        col4.metric("📊 TOTAL INCIDENTS", len(df))

        st.divider()

        # Charts row
        chart_col1, chart_col2 = st.columns(2)

        with chart_col1:
            pie = create_alert_pie_chart(alert_counts)
            if pie:
                st.plotly_chart(pie, use_container_width=True)

        with chart_col2:
            timeline = create_alerts_timeline(df)
            if timeline:
                st.plotly_chart(timeline, use_container_width=True)

        st.divider()

        # Alert table
        st.subheader("📋 INCIDENT DETAILS")

        for _, row in df.iterrows():
            level = row["alert_level"]
            emoji = "🔴" if level == "HIGH" else "🟡" if level == "MEDIUM" else "🔵"
            color = "#ef4444" if level == "HIGH" else "#f59e0b" if level == "MEDIUM" else "#3b82f6"

            with st.expander(
                f"{emoji} {level} — {row['callsign'] or row['icao24']} "
                f"| Score: {row['anomaly_score']:.0%} "
                f"| {row['created_at']}"
            ):
                col1, col2, col3 = st.columns(3)

                with col1:
                    st.markdown("**Flight Info**")
                    st.text(f"ICAO24:  {row['icao24']}")
                    st.text(f"Callsign: {row['callsign'] or 'N/A'}")
                    st.text(f"Reg: {row.get('registration') or 'N/A'} ({row.get('aircraft_type') or 'N/A'})")
                    st.text(f"Route: {row.get('origin_airport_icao') or '?'} -> {row.get('destination_airport_icao') or '?'}")

                with col2:
                    st.markdown("**Position**")
                    st.text(f"Lat: {row['latitude']:.4f}")
                    st.text(f"Lon: {row['longitude']:.4f}")
                    st.text(f"Alt: {row['altitude']:.0f} ft")

                with col3:
                    st.markdown("**Motion**")
                    st.text(f"Speed: {row['speed']:.0f} kts")
                    st.text(f"Heading: {row['heading']:.0f}°")

                # Reasons
                reasons = row["reasons"]
                if isinstance(reasons, str):
                    try:
                        reasons = json.loads(reasons)
                    except Exception:
                        reasons = [reasons]

                if reasons:
                    st.markdown("**⚠️ Reasons:**")
                    for r in reasons:
                        st.markdown(f"- {r}")

                if row["zone_name"]:
                    st.warning(f"📍 Zone: {row['zone_name']}")

except Exception as e:
    st.error(f"❌ Database error: {e}")
    st.info("Make sure PostgreSQL is running (docker-compose up)")
