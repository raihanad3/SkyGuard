#!/usr/bin/env python3
"""
SkyGuard — Real-time Monitoring Script
Run in separate terminal tab
"""

import subprocess
import time
import os
from datetime import datetime

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def run_query(query):
    """Execute PostgreSQL query via docker"""
    cmd = [
        'docker', 'exec', 'skyguard-postgres',
        'psql', '-U', 'skyguard', '-d', 'skyguard_db',
        '-t', '-A', '-F|', '-c', query
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return result.stdout.strip()
    except Exception as e:
        return f"Error: {e}"

def main():
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║  SKYGUARD — Real-time Monitoring                            ║")
    print("║  Press Ctrl+C to stop                                       ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()
    input("Press Enter to start monitoring...")
    
    try:
        while True:
            clear_screen()
            
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print("═" * 65)
            print(f" SKYGUARD MONITORING — {timestamp}")
            print("═" * 65)
            print()
            
            # Database Stats
            print("📊 DATABASE RECORDS:")
            query_stats = """
                SELECT 'Raw Flights' as table_name, COUNT(*)::text FROM raw_flights
                UNION ALL
                SELECT 'Preprocessed', COUNT(*)::text FROM preprocessed_flights
                UNION ALL
                SELECT 'Inference', COUNT(*)::text FROM inference_results
                UNION ALL
                SELECT 'Alerts', COUNT(*)::text FROM alerts
                UNION ALL
                SELECT 'HIGH Alerts', COUNT(*)::text FROM alerts WHERE alert_level = 'HIGH'
                UNION ALL
                SELECT 'MEDIUM Alerts', COUNT(*)::text FROM alerts WHERE alert_level = 'MEDIUM'
                UNION ALL
                SELECT 'LOW Alerts', COUNT(*)::text FROM alerts WHERE alert_level = 'LOW'
            """
            
            result = run_query(query_stats)
            if result and not result.startswith("Error"):
                for line in result.split('\n'):
                    if '|' in line:
                        parts = line.split('|')
                        name = parts[0].ljust(20)
                        count = parts[1].rjust(10)
                        print(f"  {name} : {count}")
            else:
                print(f"  {result}")
            
            print()
            
            # Recent Activity
            print("🔥 RECENT ACTIVITY (Last 5 min):")
            query_recent = "SELECT COUNT(*)::text FROM inference_results WHERE inferred_at > NOW() - INTERVAL '5 minutes'"
            recent = run_query(query_recent)
            print(f"  Records processed: {recent}")
            
            print()
            
            # Latest HIGH Alert
            print("⚠️  LATEST HIGH ALERT:")
            query_alert = """
                SELECT icao24, callsign, anomaly_score::text, TO_CHAR(created_at, 'HH24:MI:SS')
                FROM alerts 
                WHERE alert_level = 'HIGH' 
                ORDER BY created_at DESC 
                LIMIT 1
            """
            
            alert = run_query(query_alert)
            if alert and not alert.startswith("Error") and alert.strip():
                parts = alert.split('|')
                if len(parts) >= 4:
                    print(f"  ICAO24    : {parts[0]}")
                    print(f"  Callsign  : {parts[1]}")
                    print(f"  Score     : {parts[2]}")
                    print(f"  Time      : {parts[3]}")
                else:
                    print("  No HIGH alerts yet")
            else:
                print("  No HIGH alerts yet")
            
            print()
            print("═" * 65)
            print("Refreshing in 5 seconds... (Ctrl+C to stop)")
            print()
            
            time.sleep(5)
            
    except KeyboardInterrupt:
        print("\n\n👋 Monitoring stopped")

if __name__ == "__main__":
    main()
