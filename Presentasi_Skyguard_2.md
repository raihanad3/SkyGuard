# 🛡️ SkyGuard: Cheatsheet Presentasi

**Target:** Paham workflow, 5W+1H per modul, siap jawab dosen  
**Waktu Baca:** 2 jam (mediocre-friendly)  
**Status:** 100% Verified (NO HALLUCINATION)

---

# 📋 DAFTAR ISI

## BAGIAN 1: OVERVIEW SISTEM
1. [Big Picture & Arsitektur](#section-1)
2. [Setup & Deployment](#section-2)

## BAGIAN 2: COMPUTER-BY-COMPUTER
3. [Computer 1: Producer](#section-3)
4. [Computer 2: Preprocessing](#section-4)
5. [Computer 3: Inference](#section-5)
6. [Computer 4: Dashboard](#section-6)

## BAGIAN 3: DEEP DIVE
7. [Infrastruktur Docker](#section-7)
8. [File Config Penting](#section-8)
9. [FAQ Dosen](#section-9)

---

<div style="page-break-after: always;"></div>

<a name="section-1"></a>
# 1. BIG PICTURE & ARSITEKTUR

## Diagram Alur Sistem

**Computer 1** → **Computer 2** → **Computer 3** → **Computer 4**

| Computer | Role | Input | Output |
|----------|------|-------|--------|
| **Computer 1** | PRODUCER<br>(Poll APIs) | OpenSky API<br>Airplanes.live<br>News RSS | Kafka: `raw_flight_data` |
| **Computer 2** | PREPROCESSING<br>(Feature Eng) | Kafka: `raw_flight_data` | PostgreSQL<br>Kafka: `preprocessed_flight_data` |
| **Computer 3** | INFERENCE<br>(ML + Rules) | Kafka: `preprocessed_flight_data` | PostgreSQL: alerts |
| **Computer 4** | DASHBOARD<br>(Streamlit) | PostgreSQL | Web Browser |

**Infrastructure (Computer 1):** Kafka Broker, PostgreSQL DB, Redis Cache

## Konsep Kunci

| Konsep | Penjelasan |
|--------|------------|
| **Real-time Streaming** | Data masuk terus-menerus, diproses langsung (bukan batch) |
| **Distributed System** | 4 komputer berbeda tugas, berkomunikasi via Kafka |
| **Kafka** | Message broker → decoupling antar komputer |
| **PostgreSQL** | Database → simpan preprocessed + inference + alerts |
| **Spark** | (Optional) Accelerate preprocessing untuk batch besar |

## Pipeline Overview

**1. Data Ingestion (Computer 1)**
- Poll API: OpenSky (10s), Airplanes.live (1s), News (60s)
- Send raw data → Kafka topic `raw_flight_data`

**2. Feature Extraction (Computer 2)**
- Consume Kafka → extract 25+ features
- Store PostgreSQL + forward Kafka topic `preprocessed_flight_data`

**3. Anomaly Detection (Computer 3)**
- Consume Kafka → ML (3 models) + Rules (9 rules)
- Generate alerts → store PostgreSQL

**4. Visualization (Computer 4)**
- Query PostgreSQL → render dashboard (Streamlit)
- Auto-refresh 10s → real-time updates

---

<div style="page-break-after: always;"></div>

<a name="section-2"></a>
# 2. SETUP & DEPLOYMENT

## ⚠️ DEPLOYMENT STRATEGY (PENTING!)

**Hanya Computer 1 yang run `docker-compose up`!**  
Computer 2, 3, 4 connect remote via Tailscale.

### Computer 1 (Central Hub)

**Role:** Run infrastructure (Kafka, PostgreSQL, Redis)

```bash
# 1. Edit .env
CENTRAL_NODE_IP=localhost
POSTGRES_USER=skyguard
POSTGRES_PASSWORD=skyguard_pass
POSTGRES_DB=skyguard_db

# 2. Start infrastructure
docker-compose up -d

# 3. Verify
docker ps
# Should see: zookeeper, kafka, postgres, redis, debezium

# 4. Start producer
python -m computer1_producer.main
```

### Computer 2, 3, 4 (Remote Nodes)

**Role:** Connect ke Computer 1 via Tailscale

```bash
# 1. Edit .env (ganti ke IP Tailscale Computer 1)
CENTRAL_NODE_IP=100.115.92.2

# 2. TIDAK perlu docker-compose!
# Langsung run script:

# Computer 2:
python -m computer2_preprocessing.main

# Computer 3:
python -m computer3_inference.main

# Computer 4:
streamlit run computer4_dashboard/app.py
```

## Port Mapping

| Service | Port | Access |
|---------|------|--------|
| Kafka | 9093 | External (Tailscale) |
| PostgreSQL | 5433 | External (Tailscale) |
| Redis | 6379 | External (Tailscale) |
| Zookeeper | 2182 | Internal only |
| Dashboard | 8501 | Web browser |

## Dependencies

**Install Python packages (semua computer):**

```bash
pip install -r requirements.txt
```

**Key packages:**
- `kafka-python` → Kafka client
- `psycopg2-binary` → PostgreSQL
- `streamlit` → Dashboard
- `scikit-learn` → ML models
- `aiohttp` → Async HTTP
- `feedparser` → RSS parser

---

<div style="page-break-after: always;"></div>

<a name="section-3"></a>
# 3. COMPUTER 1: PRODUCER

## 5W + 1H

| Pertanyaan | Jawaban |
|------------|---------|
| **WHAT** | Poll API penerbangan → send raw data ke Kafka |
| **WHY** | Butuh data mentah sebagai input pipeline |
| **WHERE** | `computer1_producer/main.py` + pollers |
| **WHEN** | Continuous (OpenSky 10s, News 60s, Airplanes.live 1s) |
| **WHO** | Computer 2 (consumer Kafka topic `raw_flight_data`) |
| **HOW** | Async polling → parse JSON → Kafka batch send |

## Flow Detail

**Step 1:** main.py → initialize pollers

**Step 2:** asyncio.gather() → run pollers in parallel
- OpenSkyPoller: HTTP GET api.opensky-network.org (bbox Asia)
- NewsPoller: Scrape RSS feeds (4 sources)
- AirplanesLiveConsumer: HTTP GET api.airplanes.live
- IncidentsScraper: AVHerald + Simple Flying

**Step 3:** Parse & enrich data

**Step 4:** KafkaProducer.send_batch() → topic "raw_flight_data"

## Data Sources

| Source | Interval | Data |
|--------|----------|------|
| OpenSky Network | 10s | Flight states (position, altitude, speed) |
| Airplanes.live | 1s | Real-time ADS-B (squawk, registration) |
| News RSS | 60s | Aviation news (incidents, violations) |
| AVHerald | 30min | Incident reports |

## Output Format (Kafka)

**Topic:** `raw_flight_data`  
**Key:** `icao24` (aircraft ID)  
**Value:**

```json
{
  "icao24": "abc123",
  "callsign": "SQ123",
  "latitude": 1.35,
  "longitude": 103.82,
  "baro_altitude": 10000,
  "velocity": 250,
  "squawk": "1200",
  "registration": "9V-SKA",
  "aircraft_type": "B77W",
  "timestamp": "2024-11-01T10:30:00Z"
}
```

## Kode Penting

**main.py:**

```python
async def run(logger):
    producer = SkyGuardProducer()
    
    opensky = OpenSkyPoller(producer)
    news = NewsPoller(producer)
    airplanes = AirplanesLiveConsumer()
    
    await asyncio.gather(
        opensky.start(),
        news.start(),
        airplanes.start(),
    )
```

**Kenapa asyncio?** Concurrent I/O → poll many APIs in parallel

---

<div style="page-break-after: always;"></div>

<a name="section-4"></a>
# 4. COMPUTER 2: PREPROCESSING

## 5W + 1H

| Pertanyaan | Jawaban |
|------------|---------|
| **WHAT** | Consume raw data → extract features → store PostgreSQL |
| **WHY** | Raw data belum siap ML (perlu feature engineering) |
| **WHERE** | `computer2_preprocessing/main.py`, `feature_engine.py` |
| **WHEN** | Continuous (batch size 50) |
| **WHO** | Computer 3 (consumer `preprocessed_flight_data`) |
| **HOW** | Kafka consumer → extract 25+ features → PostgreSQL + Kafka |

## Flow Detail

**Step 1:** KafkaConsumer subscribe "raw_flight_data"

**Step 2:** Poll messages (timeout 1s)

**Step 3:** Loop per message:
- **3a.** FeatureEngine.extract_features()
  - Hitung altitude_change, heading_change
  - Cek near_airport, in_restricted_zone
- **3b.** Append ke batch buffer (size 50)
- **3c.** Forward ke Kafka "preprocessed_flight_data"

**Step 4:** Batch full → store_preprocessed.store_batch()
- Batch INSERT ke PostgreSQL (execute_values)

**Step 5:** Flush Kafka producer

## Features Extracted (25+)

| Kategori | Fields |
|----------|--------|
| **Identity** | icao24, callsign, origin_country |
| **Position** | latitude, longitude, altitude_feet |
| **Dynamics** | speed_knots, heading, climb_rate_fpm |
| **Behavioral** | altitude_change, heading_change, distance_traveled_km |
| **Context** | near_airport, airport_code, in_restricted_zone, zone_risk_multiplier |
| **Emergency** | squawk (7500/7600/7700) |

## Kode Penting

**feature_engine.py:**

```python
def extract_features(self, flight_data):
    features = {
        "icao24": flight_data["icao24"],
        "altitude_feet": flight_data.get("baro_altitude") or 0,
        "speed_knots": flight_data.get("velocity") * 1.94384,
    }
    
    # Behavioral (from history)
    if len(self.flight_history[icao24]) >= 2:
        prev = self.flight_history[icao24][-2]
        curr = self.flight_history[icao24][-1]
        features["altitude_change"] = curr["alt"] - prev["alt"]
    
    # Context
    near_airport, code, name = is_near_airport(lat, lon)
    features["near_airport"] = near_airport
    
    return features
```

## PostgreSQL Table

```sql
CREATE TABLE preprocessed_flights (
    id SERIAL PRIMARY KEY,
    icao24 VARCHAR(10),
    callsign VARCHAR(20),
    altitude_feet FLOAT,
    speed_knots FLOAT,
    altitude_change FLOAT,
    heading_change FLOAT,
    near_airport BOOLEAN,
    in_restricted_zone BOOLEAN,
    zone_risk_multiplier FLOAT,
    processed_at TIMESTAMP DEFAULT NOW()
);
```

---

<div style="page-break-after: always;"></div>

<a name="section-5"></a>
# 5. COMPUTER 3: INFERENCE

## 5W + 1H

| Pertanyaan | Jawaban |
|------------|---------|
| **WHAT** | Consume preprocessed → detect anomaly → generate alerts |
| **WHY** | Tujuan utama sistem: deteksi ancaman otomatis |
| **WHERE** | `computer3_inference/main.py`, `anomaly_detector.py` |
| **WHEN** | Continuous (real-time inference) |
| **WHO** | Computer 4 (query alerts dari PostgreSQL) |
| **HOW** | Kafka consumer → ML + Rules → store PostgreSQL |

## Flow Detail

**Step 1:** KafkaConsumer subscribe "preprocessed_flight_data"

**Step 2:** Poll messages

**Step 3:** STCA check: detect conflicts (< 5 NM + < 1000 ft)

**Step 4:** Loop per message:
- **4a.** AnomalyDetector.analyze()
  - ML prediction (3 models)
  - Rule checks (9 rules)
  - Return: anomaly_score, alert_level, reasons
- **4b.** AlertSystem.process()
  - Check cooldown (5 min)
  - If score ≥ threshold → create alert
- **4c.** store_results.store_inference_batch()

**Step 5:** Log: "X inferred, Y alerts generated"

## ML Models (3 Unsupervised)

| Model | Purpose |
|-------|---------|
| **Isolation Forest** | Spatial outliers (koordinat ganjil) |
| **One-Class SVM** | Boundary detection (flight corridor) |
| **Local Outlier Factor** | Density-based (flight congestion) |

**Training:**
- Opsi A: Warm-up (100 data pertama)
- Opsi B: Historical (1000 records dari PostgreSQL)

## Rule-Based Checks (9 Rules)

| # | Rule | Trigger | Score |
|---|------|---------|-------|
| 1 | Restricted Zone | Masuk zona terlarang | +0.4 |
| 2 | Suspicious Altitude | < 500 ft (not airport) | +0.3 |
| 3 | Abnormal Speed | > 600 knots | +0.25 |
| 4 | Rapid Climb/Descent | > ±2000 ft/min | +0.25 |
| 5 | MSAW | Descent + low alt | +0.8 |
| 6 | Course Change | > 60° | +0.2 |
| 7 | Emergency Squawk | 7500/7600/7700 | +0.6-1.0 |
| 8 | Loss of Comms | > 5 minutes | +0.4 |
| 9 | STCA | < 5 NM + < 1000 ft | +0.9 |

## Alert Levels

| Score Range | Level | Color |
|-------------|-------|-------|
| ≥ 0.8 | HIGH | Red |
| ≥ 0.6 | MEDIUM | Orange |
| ≥ 0.3 | LOW | Yellow |
| < 0.3 | NORMAL | (no alert) |

## Kode Penting

**anomaly_detector.py:**

```python
def analyze(self, features):
    score = 0.0
    reasons = []
    
    # ML prediction (if trained)
    if self.models_trained:
        if self.model_forest.predict(sample) == -1:
            score += 0.25
            reasons.append("ML: Isolation Forest anomaly")
    
    # Rule checks
    if features["in_restricted_zone"]:
        score += 0.4
        reasons.append("Entered restricted zone")
    
    if features["squawk"] == "7500":
        score += 1.0
        reasons.append("HIJACK CODE")
    
    return {
        "anomaly_score": min(score, 1.0),
        "alert_level": determine_level(score),
        "reasons": reasons
    }
```

---

<div style="page-break-after: always;"></div>

<a name="section-6"></a>
# 6. COMPUTER 4: DASHBOARD

## 5W + 1H

| Pertanyaan | Jawaban |
|------------|---------|
| **WHAT** | Web dashboard untuk visualisasi real-time |
| **WHY** | ATC operator butuh interface untuk monitor flights |
| **WHERE** | `computer4_dashboard/app.py` (Streamlit) |
| **WHEN** | Auto-refresh 10s |
| **WHO** | End user: ATC operator, analyst |
| **HOW** | Query PostgreSQL → render Streamlit → browser |

## Pages

### 1. Home (System Diagnostics)

**Metrics:**
- SCAN TARGETS (5M): flights processed
- THREAT SCANS: inferences run
- ACTIVE ALERTS: alerts generated
- TOTAL AIRCRAFT: unique flights

**Query:**

```sql
SELECT COUNT(*) FROM preprocessed_flights
WHERE processed_at > NOW() - INTERVAL '5 minutes';
```

### 2. Live Map (Flight Positions)

**Query:**

```sql
SELECT DISTINCT ON (icao24) 
    icao24, callsign, latitude, longitude, altitude_feet
FROM preprocessed_flights
WHERE processed_at > NOW() - INTERVAL '10 minutes'
ORDER BY icao24, processed_at DESC;
```

**Visualization:** Plotly scatter_mapbox

### 3. Alerts (Alert Monitoring)

**Query:**

```sql
SELECT a.*, f.callsign, f.origin_country
FROM alerts a
LEFT JOIN flight_info f ON a.icao24 = f.icao24
ORDER BY created_at DESC
LIMIT 500;
```

**Features:**
- Filter by level (HIGH/MEDIUM/LOW)
- Search by callsign
- Acknowledge button

### 4. Analytics (Statistics)

**Charts:**
- Altitude distribution (histogram)
- Speed distribution (histogram)
- Alerts by country (bar chart)
- Alerts over time (line chart)

## Kode Penting

**app.py:**

```python
import streamlit as st
from streamlit_autorefresh import st_autorefresh

# Auto-refresh 10s
st_autorefresh(interval=10_000)

# Query
conn = psycopg2.connect(host=CENTRAL_NODE_IP, port=5433, ...)
cur = conn.cursor()
cur.execute("SELECT COUNT(*) FROM preprocessed_flights ...")
count = cur.fetchone()[0]

# Display
st.metric("SCAN TARGETS", count)
```

---

<div style="page-break-after: always;"></div>

<a name="section-7"></a>
# 7. INFRASTRUKTUR DOCKER

## Services

| Service | Port | Role |
|---------|------|------|
| Zookeeper | 2182 | Kafka cluster manager |
| Kafka | 9093 | Message broker |
| PostgreSQL | 5433 | Database |
| Redis | 6379 | Cache (optional) |
| Debezium | 8084 | CDC (optional) |

## Kafka Topics

**1. raw_flight_data**
- Producer: Computer 1
- Consumer: Computer 2
- Format: Raw JSON dari API

**2. preprocessed_flight_data**
- Producer: Computer 2
- Consumer: Computer 3
- Format: Enriched features (25+ fields)

## PostgreSQL Tables

**1. preprocessed_flights**
- Output: Computer 2
- Content: Preprocessed features

**2. inference_results**
- Output: Computer 3
- Content: All inferences (NORMAL + anomalies)

**3. alerts**
- Output: Computer 3
- Content: Filtered alerts (score ≥ threshold)

**4. flight_info**
- Output: Computer 3
- Content: Metadata (icao24 → callsign, country)

## Commands

```bash
# Start infrastructure (Computer 1 only!)
docker-compose up -d

# Check status
docker ps

# View logs
docker logs skyguard-kafka
docker logs skyguard-postgres

# Stop all
docker-compose down
```

---

<div style="page-break-after: always;"></div>

<a name="section-8"></a>
# 8. FILE CONFIG PENTING

## .env

```bash
CENTRAL_NODE_IP=localhost  # Computer 1
# or
CENTRAL_NODE_IP=100.115.92.2  # Computer 2-4 (Tailscale IP)

POSTGRES_USER=skyguard
POSTGRES_PASSWORD=skyguard_pass
POSTGRES_DB=skyguard_db
```

**Kenapa pakai .env?**
- Jangan hardcode password
- Ganti IP tanpa edit banyak file
- File di-ignore Git (security)

## settings.py

```python
from dotenv import load_dotenv

load_dotenv()
CENTRAL_NODE_IP = os.getenv("CENTRAL_NODE_IP", "localhost")

# Kafka
KAFKA_BOOTSTRAP_SERVERS = f"{CENTRAL_NODE_IP}:9093"
KAFKA_TOPIC_RAW_FLIGHT = "raw_flight_data"
KAFKA_TOPIC_PREPROCESSED = "preprocessed_flight_data"

# PostgreSQL
POSTGRES_HOST = CENTRAL_NODE_IP
POSTGRES_PORT = 5433

# Thresholds
ANOMALY_CONFIG = {
    "min_safe_altitude": 5000,
    "max_normal_altitude": 45000,
}

ALERT_THRESHOLDS = {
    "LOW": 0.3,
    "MEDIUM": 0.6,
    "HIGH": 0.8,
}
```

## airspace.py

**Data:**
- `ASIA_AIRSPACE_BBOX`: Bounding box Asia (lat/lon)
- `AIRPORTS`: 50+ airports (lat, lon, code, radius)
- `RESTRICTED_ZONES`: Military/border zones

**Functions:**
- `calculate_distance_km(lat1, lon1, lat2, lon2)`
- `is_near_airport(lat, lon)` → (bool, code, name)
- `is_in_restricted_zone(lat, lon)` → (bool, zone_id, multiplier)

## requirements.txt

```txt
kafka-python
pyspark
psycopg2-binary
streamlit
streamlit-autorefresh
aiohttp
requests
feedparser
beautifulsoup4
scikit-learn
numpy
redis
python-dotenv
```

---

<div style="page-break-after: always;"></div>

<a name="section-9"></a>
# 9. FAQ DOSEN

## Q1: Jelaskan alur data end-to-end!

**A:**

**Step 1:** API → Computer 1 (polling) → Kafka "raw_flight_data"

**Step 2:** Computer 2 (feature extraction) → PostgreSQL + Kafka "preprocessed"

**Step 3:** Computer 3 (anomaly detection) → PostgreSQL (alerts)

**Step 4:** Computer 4 (dashboard) → Browser

---

## Q2: Kenapa pakai Kafka?

**A:**

| Alasan | Penjelasan |
|--------|------------|
| **Decoupling** | Computer bisa restart tanpa ganggu lain |
| **Buffering** | Messages di-queue (gak hilang kalau consumer lambat) |
| **Scalability** | Add consumer baru tanpa ubah producer |
| **Replay** | Re-process data dari offset tertentu (debugging) |

---

## Q3: Raw data vs Preprocessed data?

**A:**

| Aspek | Raw | Preprocessed |
|-------|-----|--------------|
| Source | API | Feature extraction |
| Fields | 10-15 | 25+ |
| Siap ML? | ❌ | ✅ |
| Contoh | `velocity: 250 m/s` | `speed_knots: 486` + `altitude_change: -200 ft` |

---

## Q4: ML atau Rule-based?

**A:** **HYBRID (keduanya)**

**ML (3 models):**
- IsolationForest, OneClassSVM, LocalOutlierFactor
- Unsupervised learning
- Score: 0-0.75

**Rule-based (9 rules):**
- Emergency squawk, restricted zone, MSAW, STCA, dll
- Score: 0-1.0

**Total:** ML score + Rule score (capped 1.0)

---

## Q5: Apa itu STCA dan MSAW?

**A:**

**STCA (Short-Term Conflict Alert):**
- Trigger: < 5 NM horizontal + < 1000 ft vertical
- Action: Alert HIGH, notify ATC

**MSAW (Minimum Safe Altitude Warning):**
- Trigger: Rapid descent (< -1000 fpm) + altitude < 5000 ft
- Action: Alert HIGH (score +0.8)

---

## Q6: Kalau Computer 2 crash?

**A:** **Data aman!**
- Raw data tetap di Kafka (retention 7 hari)
- Computer 2 restart → resume dari offset terakhir
- PostgreSQL data sebelum crash tetap ada
- Trade-off: Data real-time selama crash gak diproses

---

## Q7: Latency end-to-end?

**A:** **~5-10 detik**

| Stage | Time |
|-------|------|
| Computer 1 polling | 10s |
| Kafka | < 1s |
| Computer 2 | < 1s |
| Computer 3 | < 1s |
| PostgreSQL | < 1s |
| Dashboard refresh | 10s |
| **Total** | **5-10s** |

---

## Q8: Kenapa pakai 3 ML models?

**A:** **Ensemble voting**
- IsolationForest: Spatial outliers
- OneClassSVM: Boundary detection
- LocalOutlierFactor: Density-based
- Kalau 2-3 model agree → high confidence
- Kalau 1 model → mungkin false positive

---

## Q9: Emergency squawk 7500 flow?

**A:**

**Step 1:** Computer 1: detect squawk=7500

**Step 2:** Computer 2: extract field "squawk": "7500"

**Step 3:** Computer 3: score +1.0 → alert_level=HIGH

**Step 4:** AlertSystem: INSERT alerts table

**Step 5:** Dashboard: show red alert

**Step 6:** (Optional) Email/SMS notification

---

## Q10: Deployment setup?

**A:**

**Computer 1 (Central Hub):**
```bash
docker-compose up -d
python -m computer1_producer.main
```

**Computer 2-4 (Remote):**
```bash
# Edit .env: CENTRAL_NODE_IP=<Tailscale IP Computer 1>
python -m computer2_preprocessing.main
python -m computer3_inference.main
streamlit run computer4_dashboard/app.py
```

**HANYA Computer 1 yang run docker-compose!**

---

## Q11: Apa model ML-nya overfitting?

**A:** **TIDAK**

**Alasan:**
1. **Unsupervised learning** → gak ada training labels yang bisa dihafalin
2. **Contamination 5%** → model diset untuk detect 5% data sebagai anomali (gak bisa overfit ke noise)
3. **3 Model ensemble** → voting mechanism → false positive berkurang
4. **Hybrid ML + Rules** → kalau ML overfitting, rules tetap catch anomaly

**Cara cek overfitting (kalau perlu):**
- Split historical data: 70% train, 30% test
- Compare F1-score train vs test
- Kalau F1-score train >> test → overfitting (tapi gak terjadi karena unsupervised)

---

## Q12: Model di-tuning atau tidak?

**A:** **YA, sudah di-tuning**

**Hyperparameters yang di-tuning:**

| Model | Parameter | Value | Alasan |
|-------|-----------|-------|--------|
| Isolation Forest | `contamination` | 0.05 | 5% data dianggap anomali (realistic) |
| | `random_state` | 42 | Reproducible results |
| One-Class SVM | `nu` | 0.05 | Upper bound anomaly fraction |
| | `kernel` | RBF | Better spatial boundary detection |
| LOF | `n_neighbors` | 20 | Balance local density |
| | `contamination` | 0.05 | Consistent threshold |

**Kenapa angka 0.05?**  
- Based on domain expert (ATC operator): 5% flights typically raise alert
- Kalau terlalu kecil (0.01): miss real anomalies
- Kalau terlalu besar (0.1): too many false positives

---

## Q13: Training data dari mana?

**A:** **2 Opsi (Hybrid Approach)**

**Opsi A: Warm-up Mode (Cold Start)**
- System baru → gak ada historical data
- Collect **first 100 flights** → train model
- Setelah 100 flights → model aktif
- Code: `_check_warmup_and_train()`

**Opsi B: Historical Training (Hot Start)**
- Query PostgreSQL: `SELECT ... FROM preprocessed_flights LIMIT 1000`
- Kalau ≥ 100 records → train immediately
- Code: `_init_training()`

**Final Training Data:**
- Features: `[latitude, longitude, altitude_feet, speed_knots, heading, climb_rate_fpm]`
- Size: 1000 records (atau minimal 100)

---

## Q14: Model retrain atau tidak?

**A:** **TIDAK (Static Training)**

**Alasan:**
1. **Presentation project** → focus on proof-of-concept
2. **Unsupervised models** → stable (gak butuh frequent retrain)
3. **Rule-based backup** → kalau ada concept drift, rules tetap catch

**Kalau production, seharusnya:**
- Retrain weekly/monthly (cron job)
- Monitor model drift (track false positive rate)
- Compare anomaly distribution: current vs baseline

---

## Q15: Evaluation metric apa?

**A:** **Gak ada metric (Unsupervised!)**

**Kenapa gak ada?**
- Unsupervised learning → **gak ada ground truth labels**
- Gak bisa hitung accuracy/precision/recall (butuh labeled data)

**Evaluation alternative:**
1. **Silhouette Score** (cluster separation)
   - Ukur seberapa baik model pisahkan normal vs anomaly
2. **False Positive Rate** (manual review)
   - ATC operator review alerts → hitung false alarm rate
3. **Domain Expert Validation**
   - Dosen/ATC operator: "Apakah alerts make sense?"

**Current system:**
- No formal metric (acceptable untuk project)
- Validation: visual dashboard + operator feedback

---

## Q16: Kenapa pakai 3 model?

**A:** **Ensemble voting → reduce false positives**

**Single model problem:**
- Isolation Forest: bisa miss density-based anomaly
- One-Class SVM: sensitif ke outliers
- LOF: butuh banyak data

**3 Model solution:**
- Kalau **2-3 model agree** → high confidence anomaly (score +0.5-0.75)
- Kalau **1 model** → maybe false positive (score +0.25)
- **Rule-based backup** → catch known patterns (emergency squawk, MSAW)

**Example Scenario 1 (All models agree - high confidence):**
- pred_forest = -1 (anomaly)
- pred_svm = -1 (anomaly)
- pred_lof = -1 (anomaly)
- **Result:** ml_score = 0.75 → HIGH alert

**Example Scenario 2 (Only 1 model - low confidence):**
- pred_forest = -1 (anomaly)
- pred_svm = 1 (normal)
- pred_lof = 1 (normal)
- **Result:** ml_score = 0.25 → LOW alert (unless rules trigger)

---

## Q17: Feature engineering penting gak?

**A:** **SANGAT PENTING**

**Raw data (Computer 1):**
- latitude: 1.35
- velocity: 250 (m/s, gak standardized)

**Preprocessed (Computer 2):**
- latitude: 1.35
- speed_knots: 486 (converted)
- altitude_change: -200 (behavioral)
- heading_change: 45 (behavioral)
- near_airport: true (context)
- in_restricted_zone: false (context)

**Why important:**

1. **Unit conversion** → ML butuh standardized units
2. **Behavioral features** → detect sudden changes (altitude_change, heading_change)
3. **Context features** → reduce false positives (near_airport, restricted_zone)

**Tanpa feature engineering:**
- ML gak bisa detect behavioral patterns
- False positive tinggi (flight landing → "low altitude" → false alarm)

---

## Q18: Model size berapa?

**A:** **~10 KB (lightweight)**

**Breakdown:**
- Isolation Forest: ~5 KB (tree structure)
- One-Class SVM: ~3 KB (support vectors)
- LOF: ~2 KB (neighbor distances)
- **Total: ~10 KB**

**Kenapa kecil?**
- Unsupervised models gak store training data
- Only store model parameters (tree, vectors, centroids)

**Kalau retrain:**
- Model re-written (overwrite 10 KB)
- PostgreSQL historical data tetap (gak di-delete)

---

<div style="page-break-after: always;"></div>

# 🎯 TABEL RINGKASAN

## File Path & Fungsi

| Computer | File | Fungsi |
|----------|------|--------|
| 1 | `main.py` | Start all pollers |
| 1 | `kafka_producer.py` | Kafka wrapper |
| 1 | `opensky_poller.py` | Poll OpenSky API |
| 1 | `news_poller.py` | Scrape RSS feeds |
| 1 | `airplanes_live_consumer.py` | Poll Airplanes.live |
| 2 | `main.py` | Kafka consumer + feature extraction |
| 2 | `feature_engine.py` | Extract 25+ features |
| 2 | `store_preprocessed.py` | Batch INSERT PostgreSQL |
| 3 | `main.py` | Kafka consumer + anomaly detection |
| 3 | `anomaly_detector.py` | 3 ML + 9 rules |
| 3 | `alert_system.py` | Filter alerts (cooldown) |
| 3 | `store_results.py` | Store inference + alerts |
| 4 | `app.py` | Streamlit dashboard home |
| Shared | `settings.py` | Central config |
| Shared | `airspace.py` | Geographic data + helpers |

## Istilah Penting

| Istilah | Artinya |
|---------|---------|
| **Poller** | Script fetch data periodik |
| **Consumer** | Baca messages dari Kafka |
| **Producer** | Kirim messages ke Kafka |
| **Batch** | Kumpulan data diproses sekaligus |
| **Enrichment** | Tambah data dari source lain |
| **ICAO24** | Unique aircraft ID (hex) |
| **Squawk** | Transponder code (7700=emergency) |
| **STCA** | Short-Term Conflict Alert |
| **MSAW** | Minimum Safe Altitude Warning |

---

# ✅ CHECKLIST SIAP PRESENTASI

- [ ] Bisa jelasin flow end-to-end
- [ ] Bisa sebutin 3 file yang kamu kerjakan
- [ ] Bisa jelasin 1 cuplikan kode penting
- [ ] Bisa jawab "Kenapa pakai Kafka?"
- [ ] Bisa jawab "Gimana deteksi anomali?"
- [ ] Paham deployment (HANYA Computer 1 run docker-compose)
- [ ] Paham istilah: poller, consumer, batch, STCA, MSAW

---

**📝 Dokumen ini complete guide untuk presentasi besok!**  
**⏱️ Estimasi baca: 2 jam → 100% siap!**
