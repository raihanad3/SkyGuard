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
from core.config import LOG_DIR, SYSTEM_LOG_FILE, AISSTREAM_API_KEY, get_ship_type_name


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
    from scrapers.backup_ais_source import backup_source
    from core.config import INDONESIA_EEZ_BBOX
    from modules.realistic_vessel_generator import generator as vessel_generator

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
            
            # 🔄 Realistic simulation DISABLED - using real AIS data + historical data
            # simulation_task = asyncio.create_task(run_realistic_simulation())

            await asyncio.gather(
                collector_task,
                trainer_initial,
                trainer_periodic,
                # simulation_task,  # DISABLED
                return_exceptions=True
            )
        
        async def run_realistic_simulation():
            """🚢 Generate realistic vessel traffic for Indonesian waters."""
            logger.info("🚢 Starting realistic vessel simulation for Indonesian waters...")
            logger.info("   (Simulated data based on real shipping patterns)")
            
            await asyncio.sleep(3)  # Wait for system init
            
            # Generate initial fleet
            vessels = vessel_generator.generate_initial_vessels(count=30)
            
            # Insert initial vessels into DB and push to dashboard
            for vessel_data in vessels:
                db.insert_position(vessel_data)
                
                db.upsert_vessel_info({
                    "mmsi": vessel_data["mmsi"],
                    "ship_name": vessel_data["ship_name"],
                    "ship_type": vessel_data["ship_type"],
                    "ship_type_name": vessel_data["ship_type_name"],
                    "flag_country": vessel_data["flag_country"],
                })
                
                # Anomaly detection
                analysis = detector.analyze(vessel_data)
                
                # Process alert
                alert_system.process_alert(analysis)
                
                # Push to dashboard
                if socketio:
                    try:
                        socketio.emit("vessel_update", {
                            "mmsi": vessel_data["mmsi"],
                            "latitude": vessel_data["latitude"],
                            "longitude": vessel_data["longitude"],
                            "speed": vessel_data["speed"],
                            "course": vessel_data["course"],
                            "ship_name": vessel_data["ship_name"],
                            "flag_country": vessel_data["flag_country"],
                            "ship_type": vessel_data["ship_type_name"],
                            "alert_level": analysis["alert_level"],
                            "anomaly_score": analysis["anomaly_score"],
                        })
                    except Exception as e:
                        pass
            
            logger.info(f"✅ Initial fleet deployed: {len(vessels)} vessels")
            
            # Update positions every 30 seconds
            update_count = 0
            while True:
                try:
                    await asyncio.sleep(30)
                    
                    # Update all vessel positions
                    updated_vessels = vessel_generator.update_vessel_positions()
                    update_count += 1
                    
                    # Push updates to dashboard
                    for vessel_data in updated_vessels:
                        db.insert_position(vessel_data)
                        
                        # Re-analyze for anomalies
                        analysis = detector.analyze(vessel_data)
                        alert_system.process_alert(analysis)
                        
                        # Push to dashboard
                        if socketio:
                            try:
                                socketio.emit("vessel_update", {
                                    "mmsi": vessel_data["mmsi"],
                                    "latitude": vessel_data["latitude"],
                                    "longitude": vessel_data["longitude"],
                                    "speed": vessel_data["speed"],
                                    "course": vessel_data["course"],
                                    "ship_name": vessel_data["ship_name"],
                                    "flag_country": vessel_data["flag_country"],
                                    "ship_type": vessel_data["ship_type_name"],
                                    "alert_level": analysis["alert_level"],
                                    "anomaly_score": analysis["anomaly_score"],
                                })
                            except Exception as e:
                                pass
                    
                    # Every 5 minutes, add a suspicious vessel
                    if update_count % 10 == 0:
                        suspicious = vessel_generator.add_suspicious_vessel()
                        db.insert_position(suspicious)
                        db.upsert_vessel_info({
                            "mmsi": suspicious["mmsi"],
                            "ship_name": suspicious["ship_name"],
                            "ship_type": suspicious["ship_type"],
                            "ship_type_name": suspicious["ship_type_name"],
                            "flag_country": suspicious["flag_country"],
                        })
                    
                    if update_count % 20 == 0:
                        logger.info(f"📊 Simulation: {update_count} updates | {len(updated_vessels)} vessels active")
                    
                except Exception as e:
                    logger.error(f"❌ Simulation error: {type(e).__name__}: {e}")
                    await asyncio.sleep(30)

        async def run_backup_source():
            """🔄 Backup AIS source - fetch REAL data from alternative APIs."""
            logger.info("🔄 Backup source: Starting in 5 seconds...")
            await asyncio.sleep(5)  # Wait 5 seconds for system init
            
            logger.info("🔄 Fetching REAL vessels from backup APIs (VesselFinder/MyShipTracking/AISHub)...")
            
            fetch_count = 0
            success_count = 0
            
            while True:
                try:
                    # Fetch REAL vessels from backup APIs
                    vessels = await backup_source.get_vessels_in_area(INDONESIA_EEZ_BBOX[0])
                    
                    fetch_count += 1
                    
                    if vessels:
                        success_count += 1
                        logger.info(f"📡 Backup: Received {len(vessels)} REAL vessels (fetch #{fetch_count})")
                        
                        for vessel_data in vessels:
                            # Process real data (NO demo label)
                            db.insert_position(vessel_data)
                            
                            db.upsert_vessel_info({
                                "mmsi": vessel_data["mmsi"],
                                "ship_name": vessel_data["ship_name"],
                                "ship_type": vessel_data["ship_type"],
                                "ship_type_name": get_ship_type_name(vessel_data["ship_type"]),
                                "flag_country": vessel_data["flag_country"],
                            })
                            
                            # Anomaly detection
                            analysis = detector.analyze(vessel_data)
                            
                            # Process alert (ALL levels, sistem yang filter)
                            alert_system.process_alert(analysis)
                            
                            # Push to dashboard
                            if socketio:
                                try:
                                    socketio.emit("vessel_update", {
                                        "mmsi": vessel_data["mmsi"],
                                        "latitude": vessel_data["latitude"],
                                        "longitude": vessel_data["longitude"],
                                        "speed": vessel_data["speed"],
                                        "course": vessel_data["course"],
                                        "ship_name": vessel_data["ship_name"],
                                        "flag_country": vessel_data["flag_country"],
                                        "ship_type": get_ship_type_name(vessel_data["ship_type"]),
                                        "alert_level": analysis["alert_level"],
                                        "anomaly_score": analysis["anomaly_score"],
                                    })
                                except Exception as e:
                                    pass
                        
                        # Log stats every 5 successful fetches
                        if success_count % 5 == 0:
                            logger.info(f"📊 Backup stats: {success_count} successful / {fetch_count} total fetches")
                    else:
                        logger.warning(f"⚠️ Backup sources returned empty data (attempt #{fetch_count})")
                    
                    # Fetch every 30 seconds (real-time enough for free APIs)
                    await asyncio.sleep(30)
                    
                except Exception as e:
                    logger.error(f"❌ Backup source error: {type(e).__name__}: {e}")
                    await asyncio.sleep(60)

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
