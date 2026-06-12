"""
SkyGuard — Sidebar Component
==============================
Shared sidebar for the Streamlit dashboard.
"""

import streamlit as st
import psycopg2
from computer4_dashboard.config.settings import (
    POSTGRES_HOST, POSTGRES_PORT,
    POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB,
)


def get_db_connection():
    """Get a PostgreSQL connection (cached per session)."""
    return psycopg2.connect(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
        dbname=POSTGRES_DB,
    )


def render_sidebar():
    """Render the shared sidebar with system status and stats."""
    
    # Inject ATC CSS on every page
    st.markdown("""
    <style>
        /* ATC Radar Dark Theme */
        .stApp {
            background-color: #0b1115; /* Deep radar black */
            color: #00ff00; /* Neon green primary text */
            font-family: 'Courier New', Courier, monospace; /* Monospace for ATC */
        }

        /* Override Streamlit default text colors where possible */
        p, div, span, h1, h2, h3, h4, h5, h6 {
            font-family: 'Courier New', Courier, monospace !important;
            color: #8fbc8f !important; /* Muted green for standard text */
        }

        h1, h2, h3 {
            color: #00ff00 !important;
            text-transform: uppercase;
            letter-spacing: 2px;
            border-bottom: 1px solid #00ff00;
            padding-bottom: 5px;
        }

        /* Metric cards styling */
        [data-testid="stMetric"] {
            background: #051608;
            border: 1px solid #00ff00;
            border-radius: 4px;
            padding: 15px;
            box-shadow: 0 0 10px rgba(0, 255, 0, 0.2);
        }
        
        [data-testid="stMetricValue"] {
            color: #00ff00 !important;
            font-size: 2.5rem !important;
            font-weight: bold;
        }
        
        [data-testid="stMetricLabel"] {
            color: #adff2f !important;
            text-transform: uppercase;
            font-size: 1.1rem;
        }

        /* Dividers */
        hr {
            border-color: #00ff00 !important;
            opacity: 0.5;
        }
        
        /* Table headers */
        th {
            color: #00ff00 !important;
            background-color: #051608 !important;
            text-transform: uppercase;
            font-weight: bold !important;
            border-bottom: 2px solid #00ff00 !important;
        }
        
        /* Alerts/Warnings */
        .stAlert {
            background-color: #1a0505 !important;
            border: 1px solid #ff0000 !important;
            color: #ff3333 !important;
        }
    </style>
    """, unsafe_allow_html=True)

    with st.sidebar:
        st.image("https://img.icons8.com/color/96/radar.png", width=64)
        st.title("ATC RADAR")
        st.caption("ASIAN FIR SECTOR CONTROL")

        st.divider()

        # System status
        st.subheader("CONTACTS")

        try:
            conn = get_db_connection()
            cur = conn.cursor()

            # Total flights tracked
            cur.execute("SELECT COUNT(DISTINCT icao24) FROM flight_info")
            total_flights = cur.fetchone()[0]

            # Total data points
            cur.execute("SELECT COUNT(*) FROM preprocessed_flights")
            total_positions = cur.fetchone()[0]

            # Alert counts
            cur.execute("""
                SELECT alert_level, COUNT(*) 
                FROM alerts 
                GROUP BY alert_level
            """)
            alert_counts = dict(cur.fetchall())

            conn.close()

            col1, col2 = st.columns(2)
            col1.metric("AIRCRAFT", f"{total_flights:,}")
            col2.metric("PING COUNT", f"{total_positions:,}")

            st.divider()

            st.subheader("PRIORITY ALERTS")
            col1, col2, col3 = st.columns(3)
            col1.metric("LVL 1", alert_counts.get("HIGH", 0))
            col2.metric("LVL 2", alert_counts.get("MEDIUM", 0))
            col3.metric("LVL 3", alert_counts.get("LOW", 0))

        except Exception as e:
            st.warning(f"DB LINK OFFLINE: {e}")

        st.divider()
        st.caption("SWEEP CYCLE: 10s")
        st.caption("ATC TERMINAL V1.0")
