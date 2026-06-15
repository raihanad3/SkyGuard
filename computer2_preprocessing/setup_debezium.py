"""
SkyGuard — Setup Debezium Connector
=====================================
Registers the Debezium PostgreSQL connector for CDC
(Change Data Capture) on the preprocessed_flights table.

Usage:
    python computer2_preprocessing/setup_debezium.py
    python computer2_preprocessing/setup_debezium.py --status
    python computer2_preprocessing/setup_debezium.py --delete
"""

import json
import os
import argparse
import requests

from shared.config.settings import DEBEZIUM_CONNECT_URL

CONNECTOR_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "debezium_config.json")

def register_connector():
    print("📡 Registering Debezium connector...")
    try:
        with open(CONNECTOR_CONFIG_PATH, "r") as f:
            config = json.load(f)

        response = requests.post(
            f"{DEBEZIUM_CONNECT_URL}/connectors",
            json=config,
            headers={"Content-Type": "application/json"},
            timeout=30,
        )

        if response.status_code in (200, 201):
            print("✅ Connector registered successfully!")
            print(json.dumps(response.json(), indent=2))
        elif response.status_code == 409:
            print("⚠️ Connector already exists. Use --delete first to re-create.")
        else:
            print(f"❌ Failed: {response.status_code}")
            print(response.text)

    except Exception as e:
        print(f"❌ Error: {e}")

def check_status():
    print("📊 Checking Debezium connector status...")
    try:
        response = requests.get(f"{DEBEZIUM_CONNECT_URL}/connectors", timeout=10)
        if response.status_code == 200:
            connectors = response.json()
            print(f"Active connectors: {connectors}")
            for name in connectors:
                status_resp = requests.get(f"{DEBEZIUM_CONNECT_URL}/connectors/{name}/status", timeout=10)
                if status_resp.status_code == 200:
                    status = status_resp.json()
                    print(f"\n  [{name}] State: {status['connector']['state']}")
    except Exception as e:
        print(f"❌ Error: {e}")

def delete_connector():
    name = "skyguard-postgres-connector"
    print(f"🗑️ Deleting connector '{name}'...")
    try:
        response = requests.delete(f"{DEBEZIUM_CONNECT_URL}/connectors/{name}", timeout=10)
        if response.status_code == 204:
            print("✅ Connector deleted")
        elif response.status_code == 404:
            print("⚠️ Connector not found")
        else:
            print(f"❌ Failed: {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f"❌ Error: {e}")

def main():
    parser = argparse.ArgumentParser(description="SkyGuard — Debezium Setup")
    parser.add_argument("--status", action="store_true", help="Check connector status")
    parser.add_argument("--delete", action="store_true", help="Delete connector")
    args = parser.parse_args()

    if args.status:
        check_status()
    elif args.delete:
        delete_connector()
    else:
        register_connector()

if __name__ == "__main__":
    main()
