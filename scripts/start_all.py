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
    3: {
        "name": "Computer 3 — Inference",
        "cmd": [sys.executable, "-m", "computer3_inference.main"],
    },
    4: {
        "name": "Computer 4 — Backend API",
        "cmd": [sys.executable, "-m", "uvicorn", "computer4_dashboard.api:app", "--host", "0.0.0.0", "--port", "8000"],
    },
    5: {
        "name": "Computer 4 — React UI",
        "cmd": ["npm.cmd" if os.name == "nt" else "npm", "run", "dev", "--prefix", "computer4_dashboard/frontend", "--", "--host"],
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
        "--component", "-c", type=int, choices=[1, 2, 3, 4, 5, 6, 7],
        help="Start only a specific computer (1-7). Default: start all."
    )
    args = parser.parse_args()

    # Project root is the parent directory of the scripts folder
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(project_root)

    # -------------------------------------------------------------------------
    # TAILSCALE / DISTRIBUTED SETUP
    # -------------------------------------------------------------------------
    # Parse a root .env file to find CENTRAL_NODE_IP and auto-configure everything
    env_path = os.path.join(project_root, ".env")
    central_ip = "localhost"
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if line.startswith("CENTRAL_NODE_IP="):
                    central_ip = line.split("=", 1)[1].strip()
                    break
    
    if central_ip != "localhost":
        print(f"🌐 [Tailscale Mode] Central Node IP detected: {central_ip}")
        os.environ["KAFKA_BOOTSTRAP_SERVERS"] = f"{central_ip}:9093" # or 9092 depending on setup
        os.environ["POSTGRES_HOST"] = central_ip
        os.environ["DEBEZIUM_CONNECT_URL"] = f"http://{central_ip}:8083"
        
        # Auto-update React Frontend .env
        frontend_env_path = os.path.join(project_root, "computer4_dashboard", "frontend", ".env")
        try:
            with open(frontend_env_path, "w") as f:
                f.write(f"VITE_API_BASE_URL=http://{central_ip}:8000\n")
        except Exception as e:
            print(f"⚠️ Could not update frontend .env: {e}")
    else:
        print("🏠 [Local Mode] Running all components locally.")
    # -------------------------------------------------------------------------

    banner = """
╔══════════════════════════════════════════════════════════════╗
║  SKYGUARD — Distributed Pipeline Launcher                  ║
╚══════════════════════════════════════════════════════════════╝
"""
    print(banner)

    if args.component:
        components_to_start = {args.component: COMPONENTS[args.component]}
    else:
        components_to_start = COMPONENTS

    processes = {}

    print("🚀 Starting components...")
    print()

    for comp_id, config in components_to_start.items():
        print(f"  [{comp_id}] Starting {config['name']}...")
        try:
            proc = subprocess.Popen(
                config["cmd"],
                cwd=project_root,
                # stdout=subprocess.DEVNULL,  # Uncomment to hide output
                # stderr=subprocess.DEVNULL,  # Uncomment to hide errors
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
