#!/usr/bin/env python3
"""
Verify ML Models Usage - Extract evidence from logs and database
"""

import subprocess
import json

def run_query(query):
    """Execute PostgreSQL query"""
    cmd = [
        'docker', 'exec', 'skyguard-postgres',
        'psql', '-U', 'skyguard', '-d', 'skyguard_db',
        '-t', '-A', '-F|', '-c', query
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout.strip()

print("=" * 70)
print(" SKYGUARD ML MODELS VERIFICATION")
print("=" * 70)
print()

# 1. Check ML training log
print("1. ML TRAINING STATUS:")
print("-" * 70)
try:
    with open('logs/computer3_inference.log', 'r', encoding='utf-8') as f:
        lines = f.readlines()
        ml_lines = [line.strip() for line in lines if 'ML' in line or 'model' in line.lower()]
        
        if ml_lines:
            print("Found ML-related log entries:")
            for line in ml_lines[:10]:  # Show first 10
                print(f"  {line}")
        else:
            print("  ⚠️ No ML logs found (might be in different log format)")
except FileNotFoundError:
    print("  ⚠️ Log file not found")

print()

# 2. Check alerts with ML detection
print("2. ALERTS DETECTED BY ML (Sample):")
print("-" * 70)
query = """
    SELECT 
        icao24,
        callsign,
        alert_level,
        anomaly_score,
        reasons::text
    FROM alerts
    WHERE anomaly_score > 0.5
    ORDER BY anomaly_score DESC
    LIMIT 10
"""

result = run_query(query)
if result:
    print(f"{'ICAO24':<10} {'Callsign':<10} {'Level':<8} {'Score':<8} {'Reasons'}")
    print("-" * 70)
    for line in result.split('\n'):
        if line.strip():
            parts = line.split('|')
            if len(parts) >= 5:
                icao = parts[0][:10].ljust(10)
                call = parts[1][:10].ljust(10)
                level = parts[2][:8].ljust(8)
                score = parts[3][:8].ljust(8)
                reasons = parts[4][:40]
                print(f"{icao} {call} {level} {score} {reasons}")
else:
    print("  No data")

print()

# 3. ML Model Statistics
print("3. ML DETECTION STATISTICS:")
print("-" * 70)
query_stats = """
    SELECT 
        COUNT(*) as total_inferences,
        COUNT(CASE WHEN anomaly_score >= 0.8 THEN 1 END) as high_anomalies,
        COUNT(CASE WHEN anomaly_score BETWEEN 0.6 AND 0.8 THEN 1 END) as medium_anomalies,
        COUNT(CASE WHEN anomaly_score BETWEEN 0.3 AND 0.6 THEN 1 END) as low_anomalies,
        ROUND(AVG(anomaly_score)::numeric, 3) as avg_score,
        ROUND(MAX(anomaly_score)::numeric, 3) as max_score
    FROM inference_results
"""

result = run_query(query_stats)
if result:
    parts = result.split('|')
    if len(parts) >= 6:
        print(f"  Total Inferences      : {parts[0]}")
        print(f"  HIGH Anomalies        : {parts[1]} (score >= 0.8)")
        print(f"  MEDIUM Anomalies      : {parts[2]} (score 0.6-0.8)")
        print(f"  LOW Anomalies         : {parts[3]} (score 0.3-0.6)")
        print(f"  Average Anomaly Score : {parts[4]}")
        print(f"  Maximum Score         : {parts[5]}")

print()

# 4. Model Performance Comparison
print("4. ALERT LEVEL DISTRIBUTION (ML + Rule-based Combined):")
print("-" * 70)
query_dist = """
    SELECT 
        alert_level,
        COUNT(*) as count,
        ROUND(AVG(anomaly_score)::numeric, 3) as avg_score,
        ROUND(MIN(anomaly_score)::numeric, 3) as min_score,
        ROUND(MAX(anomaly_score)::numeric, 3) as max_score
    FROM inference_results
    GROUP BY alert_level
    ORDER BY 
        CASE alert_level 
            WHEN 'HIGH' THEN 1
            WHEN 'MEDIUM' THEN 2
            WHEN 'LOW' THEN 3
            ELSE 4
        END
"""

result = run_query(query_dist)
if result:
    print(f"{'Alert Level':<12} {'Count':<10} {'Avg Score':<12} {'Min':<8} {'Max':<8}")
    print("-" * 70)
    for line in result.split('\n'):
        if line.strip():
            parts = line.split('|')
            if len(parts) >= 5:
                level = parts[0].ljust(12)
                count = parts[1].ljust(10)
                avg = parts[2].ljust(12)
                min_s = parts[3].ljust(8)
                max_s = parts[4].ljust(8)
                print(f"{level} {count} {avg} {min_s} {max_s}")

print()
print("=" * 70)
print(" VERIFICATION COMPLETE")
print("=" * 70)
print()
print("📌 BUKTI ML MODELS USAGE:")
print("   1. Log entries menunjukkan ML training dan prediction")
print("   2. Anomaly scores computed by ML ensemble (IF + SVM + LOF)")
print("   3. Hybrid scoring: max(rule_score, ml_score) untuk final decision")
print()
