"""
Dashboard — Flask web server dengan SocketIO
untuk monitoring kapal secara real-time.
"""

import logging
from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO

from config import DASHBOARD_HOST, DASHBOARD_PORT

logger = logging.getLogger("vessel_anomaly")


def create_dashboard(db_manager):
    """
    Membuat Flask dashboard app.

    Returns:
        tuple: (app, socketio)
    """
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "vessel-anomaly-detection-2026"

    socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

    # ============================================================
    # Routes
    # ============================================================

    @app.route("/")
    def index():
        """Halaman utama dashboard."""
        return render_template("index.html")

    @app.route("/api/stats")
    def api_stats():
        """API endpoint untuk statistik."""
        stats = db_manager.get_stats()
        return jsonify(stats)

    @app.route("/api/vessels")
    def api_vessels():
        """API endpoint untuk kapal aktif."""
        vessels = db_manager.get_active_vessels(minutes=30)
        return jsonify(vessels)

    @app.route("/api/alerts")
    def api_alerts():
        """API endpoint untuk alert terbaru."""
        alerts = db_manager.get_recent_alerts(limit=50)
        return jsonify(alerts)

    @app.route("/api/alerts/count")
    def api_alert_count():
        """API endpoint untuk jumlah alert per level."""
        counts = db_manager.get_alert_count_by_level()
        return jsonify(counts)

    # ============================================================
    # SocketIO Events
    # ============================================================

    @socketio.on("connect")
    def handle_connect():
        logger.info("🖥️ Dashboard client connected")

    @socketio.on("disconnect")
    def handle_disconnect():
        logger.info("🖥️ Dashboard client disconnected")

    @socketio.on("request_stats")
    def handle_request_stats():
        stats = db_manager.get_stats()
        socketio.emit("stats_update", stats)

    @socketio.on("request_vessels")
    def handle_request_vessels():
        vessels = db_manager.get_active_vessels(minutes=30)
        socketio.emit("vessels_update", vessels)

    return app, socketio


def run_dashboard(app, socketio):
    """Menjalankan Flask dashboard."""
    logger.info(
        "🌐 Dashboard starting at http://%s:%d",
        DASHBOARD_HOST, DASHBOARD_PORT
    )
    socketio.run(
        app,
        host=DASHBOARD_HOST,
        port=DASHBOARD_PORT,
        debug=False,
        use_reloader=False
    )
