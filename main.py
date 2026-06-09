"""
VESSEL GUARD — Main Orchestrator
Sistem Deteksi Kapal Anomali Real-time untuk Perairan Indonesia.

Menjalankan semua komponen secara concurrent:
1. AIS Data Collector (WebSocket stream)
2. Anomaly Detection (Rule-based + Isolation Forest)
3. Alert System (Console + Log + Dashboard)
4. Web Dashboard (Flask + SocketIO)
5. Model Trainer (Periodic retraining)

Usage:
    python main.py
    
Environment:
    AISSTREAM_API_KEY: API key dari aisstream.io (wajib)
"""

import os
import sys
import asyncio
import logging
import threading
import signal
from datetime import datetime

# Fix encoding untuk Windows console (emoji support)
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    os.environ.setdefault("PYTHONUTF8", "1")

# Setup logging sebelum import modul lain
from core.config import LOG_DIR, SYSTEM_LOG_FILE, AISSTREAM_API_KEY


def setup_logging():
    """Konfigurasi logging sistem."""
    os.makedirs(LOG_DIR, exist_ok=True)

    # Root logger
    root_logger = logging.getLogger("vessel_anomaly")
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
    file_handler = logging.FileHandler(
        SYSTEM_LOG_FILE, encoding="utf-8")
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
║   ██╗   ██╗███████╗███████╗███████╗███████╗██╗               ║
║   ██║   ██║██╔════╝██╔════╝██╔════╝██╔════╝██║               ║
║   ██║   ██║█████╗  ███████╗███████╗█████╗  ██║               ║
║   ╚██╗ ██╔╝██╔══╝  ╚════██║╚════██║██╔══╝  ██║               ║
║    ╚████╔╝ ███████╗███████║███████║███████╗███████╗           ║
║     ╚═══╝  ╚══════╝╚══════╝╚══════╝╚══════╝╚══════╝           ║
║                                                              ║
║         ██████╗ ██╗   ██╗ █████╗ ██████╗ ██████╗             ║
║        ██╔════╝ ██║   ██║██╔══██╗██╔══██╗██╔══██╗            ║
║        ██║  ███╗██║   ██║███████║██████╔╝██║  ██║            ║
║        ██║   ██║██║   ██║██╔══██║██╔══██╗██║  ██║            ║
║        ╚██████╔╝╚██████╔╝██║  ██║██║  ██║██████╔╝            ║
║         ╚═════╝  ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═════╝            ║
║                                                              ║
║   Indonesian Waters Anomaly Detection System                 ║
║   Real-time AIS Vessel Monitoring & Alert                    ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
    """
    print(banner)
    print(f"  📅 Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  🔑 API Key: {'*' * 8 + AISSTREAM_API_KEY[-4:] if len(AISSTREAM_API_KEY) > 4 else 'NOT SET'}")
    print()


def main():
    """Entry point utama."""
    logger = setup_logging()
    print_banner()

    # Validasi API key
    if AISSTREAM_API_KEY == "YOUR_API_KEY_HERE" or not AISSTREAM_API_KEY:
        logger.error("❌ API KEY BELUM DISET!")
        logger.error("   Silakan set environment variable AISSTREAM_API_KEY")
        logger.error("   atau edit nilai di config.py")
        logger.error("")
        logger.error("   Cara mendapatkan API key (GRATIS):")
        logger.error("   1. Buka https://aisstream.io")
        logger.error("   2. Login dengan GitHub")
        logger.error("   3. Copy API key yang diberikan")
        logger.error("")
        logger.error("   Cara menjalankan:")
        logger.error("   set AISSTREAM_API_KEY=your_key_here")
        logger.error("   python main.py")
        sys.exit(1)

    # Import komponen (setelah logging setup)
    from core.database import DatabaseManager
    from modules.feature_engine import FeatureEngine
    from modules.anomaly_model import AnomalyDetector
    from modules.alert_system import AlertSystem
    from scrapers.data_collector import DataCollector
    from modules.model_trainer import ModelTrainer
    from web.dashboard import create_dashboard, run_dashboard

    # Inisialisasi komponen
    logger.info("🔧 Initializing components...")

    # 1. Database
    db = DatabaseManager()
    logger.info("  ✅ Database initialized")

    # 2. Feature Engine
    feature_engine = FeatureEngine(db)
    logger.info("  ✅ Feature engine initialized")

    # 3. Anomaly Detector
    detector = AnomalyDetector(feature_engine)
    logger.info("  ✅ Anomaly detector initialized")

    # 4. Dashboard (Flask + SocketIO)
    app, socketio = create_dashboard(db)
    logger.info("  ✅ Dashboard initialized")

    # 5. Alert System
    alert_system = AlertSystem(db, socketio)
    logger.info("  ✅ Alert system initialized")

    # 6. Data Collector
    collector = DataCollector(db, detector, alert_system, socketio)
    logger.info("  ✅ Data collector initialized")

    # 7. Model Trainer
    trainer = ModelTrainer(detector, db)
    logger.info("  ✅ Model trainer initialized")

    logger.info("")
    logger.info("🚀 All components ready! Starting services...")
    logger.info("")

    # ================================================================
    # Start services
    # ================================================================

    # Graceful shutdown
    shutdown_event = threading.Event()

    def signal_handler(sig, frame):
        logger.info("\n🛑 Shutdown signal received...")
        collector.stop()
        trainer.stop()
        shutdown_event.set()

    signal.signal(signal.SIGINT, signal_handler)

    # Start AIS collector in a separate thread with its own event loop
    def run_collector_and_trainer():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def run_all():
            # Jalankan collector dan trainer secara concurrent
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

    # Start collector thread
    collector_thread = threading.Thread(
        target=run_collector_and_trainer,
        daemon=True,
        name="ais-collector"
    )
    collector_thread.start()
    logger.info("📡 AIS Data Collector started (background thread)")

    # Start Flask dashboard (blocking — on main thread)
    logger.info("🌐 Starting web dashboard...")
    logger.info("   Open browser at: http://localhost:5000")
    logger.info("")
    logger.info("=" * 60)
    logger.info("   VESSEL GUARD is now ACTIVE")
    logger.info("   Monitoring Indonesian waters for anomalies...")
    logger.info("=" * 60)
    logger.info("")

    try:
        run_dashboard(app, socketio)
    except KeyboardInterrupt:
        logger.info("🛑 Dashboard stopped")
    finally:
        collector.stop()
        trainer.stop()
        logger.info("👋 Vessel Guard shutdown complete")


if __name__ == "__main__":
    main()
