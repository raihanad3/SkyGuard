"""
SkyGuard — Start All Components
=================================
Convenience script to start all 4 computer components
in separate processes from a single terminal.

Usage:
    python scripts/start_all.py
    python scripts/start_all.py --component 1   # Start only Computer 1
    python scripts/start_all.py --component 2   # Start only Computer 2
    python scripts/start_all.py --component 3   # Start only Computer 3
    python scripts/start_all.py --component 4   # Start only Computer 4
"""

import subprocess
import sys
import os
import signal
import argparse
import time


# Components configuration
COMPONENTS = {
    1: {
        "name": "Computer 1 — Producer",
        "cmd": [sys.executable, "-m", "computer1_producer.main"],
    },
    2: {
        "name": "Computer 2 — Preprocessing",
        "cmd": [sys.executable, "-m", "computer2_preprocessing.main"],
    },
    "2-hybrid": {
        "name": "Computer 2 — Preprocessing (HYBRID MODE)",
        "cmd": [sys.executable, "computer2_preprocessing/RUN_HYBRID.py"],
    },
    3: {
        "name": "Computer 3 — Inference",
        "cmd": [sys.executable, "-m", "computer3_inference.main"],
    },
    4: {
        "name": "Computer 4 — Backend API",
        "cmd": [sys.executable, "-m", "uvicorn", "computer4_dashboard.api:app", "--host", "0.0.0.0", "--port", "8001"],
    },
    5: {
        "name": "Computer 4 — React UI",
        "cmd": ["npm.cmd" if os.name == "nt" else "npm", "run", "dev", "--prefix", "computer4_dashboard/frontend"],
    },
    6: {
        "name": "Computer 1 — Weather Scraper",
        "cmd": [sys.executable, "-m", "computer1_producer.weather_poller"],
    },
    7: {
        "name": "Computer 1 — Route Resolver",
        "cmd": [sys.executable, "-m", "computer1_producer.route_resolver"],
    },
}


def main():
    parser = argparse.ArgumentParser(description="SkyGuard — Start Components")
    parser.add_argument(
        "--component", "-c", type=str,
        help="Start only a specific computer (1-7, or '2-hybrid'). Default: start all."
    )
    parser.add_argument(
        "--hybrid", action="store_true",
        help="Use hybrid mode for Computer 2 (NLP + time-windowing)"
    )
    args = parser.parse_args()

    # Project root is the current directory of this script
    project_root = os.path.dirname(os.path.abspath(__file__))
    os.chdir(project_root)

    banner = """
╔══════════════════════════════════════════════════════════════╗
║  SKYGUARD — Distributed Pipeline Launcher                  ║
╚══════════════════════════════════════════════════════════════╝
"""
    print(banner)

    if args.component:
        # jika user spesifik component, jalankan itu aja
        comp_key = args.component
        if isinstance(args.component, str) and args.component.isdigit():
            comp_key = int(args.component)
        components_to_start = {comp_key: COMPONENTS[comp_key]}
    else:
        # jalankan semua component
        components_to_start = {}
        for key in [1, 2, 3, 4, 5, 6, 7]:
            components_to_start[key] = COMPONENTS[key]
        
        # if hybrid mode, replace Computer 2 dengan hybrid version
        if args.hybrid:
            components_to_start[2] = COMPONENTS["2-hybrid"]
            print("🔬 HYBRID MODE ENABLED: Computer 2 will use NLP + Time-Windowing")
            print()

    processes = {}

    print("🚀 Starting components...")
    print()

    for comp_id, config in components_to_start.items():
        print(f"  [{comp_id}] Starting {config['name']}...")
        try:
            proc = subprocess.Popen(
                config["cmd"],
                cwd=project_root,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            processes[comp_id] = proc
            print(f"  [{comp_id}] ✅ PID {proc.pid}")
        except Exception as e:
            print(f"  [{comp_id}] ❌ Failed: {e}")

    print()
    print(f"📊 {len(processes)} components running")
    print("🛑 Press Ctrl+C to stop all")
    print()

    def shutdown(sig, frame):
        print("\n🛑 Shutting down all components...")
        for comp_id, proc in processes.items():
            print(f"  [{comp_id}] Stopping PID {proc.pid}...")
            proc.terminate()
        for comp_id, proc in processes.items():
            proc.wait(timeout=10)
            print(f"  [{comp_id}] ✅ Stopped")
        print("👋 All components stopped")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)

    # Wait for processes
    try:
        while True:
            for comp_id, proc in list(processes.items()):
                retcode = proc.poll()
                if retcode is not None:
                    print(f"  [{comp_id}] ⚠️ Exited with code {retcode}")
                    del processes[comp_id]

            if not processes:
                print("All components have stopped")
                break

            time.sleep(2)
    except KeyboardInterrupt:
        shutdown(None, None)


if __name__ == "__main__":
    main()
