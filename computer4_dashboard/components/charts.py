"""
SkyGuard — Chart Components
==============================
Reusable Plotly chart components for the dashboard.
"""

import plotly.express as px
import plotly.graph_objects as go
import pandas as pd


def create_alert_pie_chart(alert_counts):
    """
    Create a pie chart showing alert distribution by level.

    Args:
        alert_counts: dict like {"HIGH": 10, "MEDIUM": 25, "LOW": 50}
    """
    if not alert_counts:
        return None

    colors = {"HIGH": "#ef4444", "MEDIUM": "#f59e0b", "LOW": "#3b82f6", "NORMAL": "#10b981"}

    labels = list(alert_counts.keys())
    values = list(alert_counts.values())
    chart_colors = [colors.get(l, "#6b7280") for l in labels]

    fig = go.Figure(data=[go.Pie(
        labels=labels,
        values=values,
        marker=dict(colors=chart_colors),
        hole=0.4,
        textinfo="label+value",
        textfont_size=14,
    )])

    fig.update_layout(
        title="Alert Distribution",
        showlegend=True,
        height=350,
        margin=dict(t=40, b=20, l=20, r=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#e2e8f0"),
    )

    return fig


def create_alerts_timeline(df):
    """
    Create a timeline chart of alerts over time.

    Args:
        df: DataFrame with 'created_at' and 'alert_level' columns
    """
    if df is None or df.empty:
        return None

    df["created_at"] = pd.to_datetime(df["created_at"])
    df["hour"] = df["created_at"].dt.floor("h")

    grouped = df.groupby(["hour", "alert_level"]).size().reset_index(name="count")

    color_map = {"HIGH": "#ef4444", "MEDIUM": "#f59e0b", "LOW": "#3b82f6"}

    fig = px.bar(
        grouped,
        x="hour",
        y="count",
        color="alert_level",
        color_discrete_map=color_map,
        barmode="stack",
        labels={"hour": "Time", "count": "Alerts", "alert_level": "Level"},
    )

    fig.update_layout(
        title="Alert Timeline",
        height=350,
        margin=dict(t=40, b=20, l=20, r=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#e2e8f0"),
        xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.1)"),
    )

    return fig


def create_country_bar_chart(df):
    """
    Create a bar chart showing flights by country of origin.

    Args:
        df: DataFrame with 'origin_country' column
    """
    if df is None or df.empty:
        return None

    country_counts = df["origin_country"].value_counts().head(15).reset_index()
    country_counts.columns = ["country", "count"]

    fig = px.bar(
        country_counts,
        x="count",
        y="country",
        orientation="h",
        color="count",
        color_continuous_scale="Viridis",
    )

    fig.update_layout(
        title="Top 15 Countries",
        height=400,
        margin=dict(t=40, b=20, l=20, r=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#e2e8f0"),
        xaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.1)"),
        yaxis=dict(showgrid=False),
        coloraxis_showscale=False,
    )

    return fig


def create_speed_altitude_scatter(df):
    """
    Create a scatter plot of speed vs altitude colored by anomaly score.

    Args:
        df: DataFrame with 'speed', 'altitude', 'anomaly_score' columns
    """
    if df is None or df.empty:
        return None

    fig = px.scatter(
        df,
        x="speed",
        y="altitude",
        color="anomaly_score",
        color_continuous_scale="RdYlGn_r",
        hover_data=["icao24", "callsign", "alert_level"],
        labels={
            "speed": "Speed (knots)",
            "altitude": "Altitude (ft)",
            "anomaly_score": "Anomaly Score",
        },
    )

    fig.update_layout(
        title="Speed vs Altitude (colored by anomaly score)",
        height=400,
        margin=dict(t=40, b=20, l=20, r=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#e2e8f0"),
        xaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.1)"),
        yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.1)"),
    )

    return fig
