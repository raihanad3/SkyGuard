"""
SKYGUARD — Main Orchestrator
Sistem Monitoring Penerbangan Real-time untuk Wilayah Udara Indonesia.

Menjalankan semua komponen secara concurrent:
1. OpenSky Data Collector (REST API polling)
2. Anomaly Detection (Rule-based)
3. Alert System (Console + Log + Dashboard)
4. Web Dashboard (Flask + SocketIO)
5. Model Trainer (Placeholder)

Usage:
    python main.py
"""

import os
import sys
import asyncio
import logging
import threading
import signal
from datetime import datetime

# Fix encoding untuk Windows console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    os.environ.setdefault("PYTHONUTF8", "1")

# Setup logging
from core.config import LOG_DIR, LOG_FILE


def setup_logging():
    """Konfigurasi logging sistem."""
    os.makedirs(LOG_DIR, exist_ok=True)

    root_logger = logging.getLogger("skyguard")
    root_logger.setLevel(logging.INFO)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S"
    )
    console_handler.setFormatter(console_fmt)
    root_logger.addHandler(console_handler)

    # File handler
    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(file_fmt)
    root_logger.addHandler(file_handler)

    return root_logger


def print_banner():
    """Tampilkan banner startup."""
    banner = """
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║   ███████╗██╗  ██╗██╗   ██╗ ██████╗ ██╗   ██╗ █████╗ ██████╗ ║
║   ██╔════╝██║ ██╔╝╚██╗ ██╔╝██╔════╝ ██║   ██║██╔══██╗██╔══██╗║
║   ███████╗█████╔╝  ╚████╔╝ ██║  ███╗██║   ██║███████║██████╔╝║
║   ╚════██║██╔═██╗   ╚██╔╝  ██║   ██║██║   ██║██╔══██║██╔══██╗║
║   ███████║██║  ██╗   ██║   ╚██████╔╝╚██████╔╝██║  ██║██║  ██║║
║   ╚══════╝╚═╝  ╚═╝   ╚═╝    ╚═════╝  ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝║
║                                                              ║
║   Indonesian Airspace Anomaly Detection System               ║
║   Real-time Flight Monitoring & Alert                        ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
    """
    print(banner)
    print(f"  📅 Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  📡 Data Source: OpenSky Network (FREE API)")
    print()


def main():
    """Entry point utama."""
    logger = setup_logging()
    print_banner()

    # Import komponen
    from core.database import DatabaseManager
    from modules.feature_engine import FeatureEngine
    from modules.anomaly_model import AnomalyDetector
    from modules.alert_system import AlertSystem
    from scrapers.opensky_collector import OpenSkyCollector
    from modules.model_trainer import ModelTrainer
    from web.dashboard import create_dashboard, run_dashboard

    # Inisialisasi komponen
    logger.info("🔧 Initializing components...")

    db = DatabaseManager()
    logger.info("  ✅ Database initialized")

    feature_engine = FeatureEngine(db)
    logger.info("  ✅ Feature engine initialized")

    detector = AnomalyDetector(feature_engine)
    logger.info("  ✅ Anomaly detector initialized")

    app, socketio = create_dashboard(db)
    logger.info("  ✅ Dashboard initialized")

    alert_system = AlertSystem(db, socketio)
    logger.info("  ✅ Alert system initialized")

    collector = OpenSkyCollector(db, detector, alert_system, socketio)
    logger.info("  ✅ OpenSky collector initialized")

    trainer = ModelTrainer(detector, db)
    logger.info("  ✅ Model trainer initialized")

    logger.info("")
    logger.info("🚀 All components ready! Starting services...")
    logger.info("")

    # Start services
    shutdown_event = threading.Event()

    def signal_handler(sig, frame):
        logger.info("\n🛑 Shutdown signal received...")
        collector.stop()
        trainer.stop()
        shutdown_event.set()

    signal.signal(signal.SIGINT, signal_handler)

    # Start collector in separate thread
    def run_collector_and_trainer():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def run_all():
            collector_task = asyncio.create_task(
                collector.start_streaming())
            trainer_initial = asyncio.create_task(
                trainer.initial_training_check())
            trainer_periodic = asyncio.create_task(
                trainer.start_periodic_training())

            await asyncio.gather(
                collector_task,
                trainer_initial,
                trainer_periodic,
                return_exceptions=True
            )

        try:
            loop.run_until_complete(run_all())
        except Exception as e:
            logger.error("Collector thread error: %s", e)
        finally:
            loop.close()

    collector_thread = threading.Thread(
        target=run_collector_and_trainer,
        daemon=True,
        name="opensky-collector"
    )
    collector_thread.start()
    logger.info("📡 OpenSky Collector started (background thread)")

    # Start Flask dashboard (blocking)
    logger.info("🌐 Starting web dashboard...")
    logger.info("   Open browser at: http://localhost:5000")
    logger.info("")
    logger.info("=" * 60)
    logger.info("   SKYGUARD is now ACTIVE")
    logger.info("   Monitoring Indonesian airspace...")
    logger.info("=" * 60)
    logger.info("")

    try:
        run_dashboard(app, socketio)
    except KeyboardInterrupt:
        logger.info("🛑 Dashboard stopped")
    finally:
        collector.stop()
        trainer.stop()
        logger.info("👋 SkyGuard shutdown complete")


if __name__ == "__main__":
    main()
