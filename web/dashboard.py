# flask dashboard - web server
import logging
import os
from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO

from core.config import DASHBOARD_HOST, DASHBOARD_PORT

logger = logging.getLogger("skyguard")


def create_dashboard(db_manager):
    # setup flask app
    base_dir = os.path.dirname(os.path.abspath(__file__))
    template_folder = os.path.join(base_dir, 'templates')
    static_folder = os.path.join(base_dir, 'static')
    
    app = Flask(__name__, 
                template_folder=template_folder,
                static_folder=static_folder)
    app.config["SECRET_KEY"] = "skyguard-indonesia-2026"

    socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

    @app.route("/")
    def index():
        # halaman utama
        return render_template("index.html")

    @app.route("/api/stats")
    def api_stats():
        # api stats
        stats = db_manager.get_stats()
        return jsonify(stats)

    @app.route("/api/flights")
    def api_flights():
        # api flights aktif
        flights = db_manager.get_active_flights(minutes=30)
        return jsonify(flights)

    @app.route("/api/alerts")
    def api_alerts():
        # api alerts
        alerts = db_manager.get_recent_alerts(limit=50)
        return jsonify(alerts)

    @app.route("/api/alerts/count")
    def api_alert_count():
        # jumlah alert per level
        counts = db_manager.get_alert_count_by_level()
        return jsonify(counts)

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

    @socketio.on("request_flights")
    def handle_request_flights():
        flights = db_manager.get_active_flights(minutes=30)
        socketio.emit("flights_update", flights)

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
