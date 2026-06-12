-- ============================================================
-- SkyGuard — PostgreSQL Initial Schema
-- ============================================================
-- Runs automatically on first docker-compose up via
-- /docker-entrypoint-initdb.d/

-- ============================================================
-- 1. Raw Flights (from Computer 1 producer, stored by Computer 2)
-- ============================================================
CREATE TABLE IF NOT EXISTS raw_flights (
    id              BIGSERIAL PRIMARY KEY,
    icao24          VARCHAR(10)  NOT NULL,
    callsign        VARCHAR(20),
    origin_country  VARCHAR(100),
    time_position   BIGINT,
    last_contact     BIGINT,
    longitude       DOUBLE PRECISION,
    latitude        DOUBLE PRECISION,
    baro_altitude   DOUBLE PRECISION,
    on_ground       BOOLEAN DEFAULT FALSE,
    velocity        DOUBLE PRECISION,
    true_track      DOUBLE PRECISION,
    vertical_rate   DOUBLE PRECISION,
    sensors         TEXT,
    geo_altitude    DOUBLE PRECISION,
    squawk          VARCHAR(10),
    spi             BOOLEAN DEFAULT FALSE,
    position_source SMALLINT DEFAULT 0,
    received_at     TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE (icao24, received_at)
);

CREATE INDEX IF NOT EXISTS idx_raw_flights_icao24     ON raw_flights (icao24);
CREATE INDEX IF NOT EXISTS idx_raw_flights_received   ON raw_flights (received_at);


-- ============================================================
-- 2. Preprocessed Flights (Computer 2 Spark output)
--    Debezium watches this table for CDC → Kafka
-- ============================================================
CREATE TABLE IF NOT EXISTS preprocessed_flights (
    id                   BIGSERIAL PRIMARY KEY,
    icao24               VARCHAR(10)  NOT NULL,
    callsign             VARCHAR(20),
    origin_country       VARCHAR(100),
    latitude             DOUBLE PRECISION,
    longitude            DOUBLE PRECISION,

    -- converted features
    altitude_feet        DOUBLE PRECISION,
    speed_knots          DOUBLE PRECISION,
    heading              DOUBLE PRECISION,
    climb_rate_fpm       DOUBLE PRECISION,
    vertical_rate        DOUBLE PRECISION,
    on_ground            BOOLEAN DEFAULT FALSE,

    -- behavioral features
    altitude_change      DOUBLE PRECISION DEFAULT 0,
    heading_change       DOUBLE PRECISION DEFAULT 0,
    distance_traveled_km DOUBLE PRECISION DEFAULT 0,

    -- context features
    near_airport         BOOLEAN DEFAULT FALSE,
    airport_code         VARCHAR(10),
    airport_name         VARCHAR(100),
    in_restricted_zone   BOOLEAN DEFAULT FALSE,
    restricted_zone_id   VARCHAR(50),
    restricted_zone_name VARCHAR(100),
    zone_risk_multiplier DOUBLE PRECISION DEFAULT 1.0,

    -- metadata
    squawk               VARCHAR(10),
    last_contact         BIGINT,
    raw_timestamp        TEXT,
    processed_at         TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_prep_icao24      ON preprocessed_flights (icao24);
CREATE INDEX IF NOT EXISTS idx_prep_processed   ON preprocessed_flights (processed_at);


-- ============================================================
-- 3. Inference Results (Computer 3 output)
-- ============================================================
CREATE TABLE IF NOT EXISTS inference_results (
    id              BIGSERIAL PRIMARY KEY,
    icao24          VARCHAR(10)  NOT NULL,
    callsign        VARCHAR(20),
    origin_country  VARCHAR(100),
    latitude        DOUBLE PRECISION,
    longitude       DOUBLE PRECISION,
    altitude        DOUBLE PRECISION,
    speed           DOUBLE PRECISION,
    heading         DOUBLE PRECISION,
    vertical_rate   DOUBLE PRECISION,
    anomaly_score   DOUBLE PRECISION,
    alert_level     VARCHAR(10)  NOT NULL DEFAULT 'NORMAL',
    reasons         JSONB        DEFAULT '[]'::jsonb,
    zone_name       VARCHAR(100),
    squawk          VARCHAR(10),
    last_contact    BIGINT,
    inferred_at     TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_infer_icao24   ON inference_results (icao24);
CREATE INDEX IF NOT EXISTS idx_infer_level    ON inference_results (alert_level);
CREATE INDEX IF NOT EXISTS idx_infer_time     ON inference_results (inferred_at);


-- ============================================================
-- 4. Alerts (Computer 3 output — only non-NORMAL)
-- ============================================================
CREATE TABLE IF NOT EXISTS alerts (
    id              BIGSERIAL PRIMARY KEY,
    icao24          VARCHAR(10)  NOT NULL,
    callsign        VARCHAR(20),
    alert_level     VARCHAR(10)  NOT NULL,
    anomaly_score   DOUBLE PRECISION,
    latitude        DOUBLE PRECISION,
    longitude       DOUBLE PRECISION,
    altitude        DOUBLE PRECISION,
    speed           DOUBLE PRECISION,
    heading         DOUBLE PRECISION,
    reasons         JSONB        DEFAULT '[]'::jsonb,
    zone_name       VARCHAR(100),
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_alerts_icao24   ON alerts (icao24);
CREATE INDEX IF NOT EXISTS idx_alerts_level    ON alerts (alert_level);
CREATE INDEX IF NOT EXISTS idx_alerts_created  ON alerts (created_at);


-- ============================================================
-- 5. Flight Info (metadata — deduplicated)
-- ============================================================
CREATE TABLE IF NOT EXISTS flight_info (
    icao24          VARCHAR(10) PRIMARY KEY,
    callsign        VARCHAR(20),
    origin_country  VARCHAR(100),
    first_seen      TIMESTAMP WITH TIME ZONE,
    last_seen       TIMESTAMP WITH TIME ZONE,
    total_positions BIGINT DEFAULT 0
);


-- ============================================================
-- 6. News Intelligence (Computer 1 news producer output)
-- ============================================================
CREATE TABLE IF NOT EXISTS news_intelligence (
    id              BIGSERIAL PRIMARY KEY,
    category        VARCHAR(50),
    source          VARCHAR(100),
    title           TEXT,
    location        VARCHAR(200),
    flight_info     VARCHAR(200),
    threat_level    VARCHAR(10),
    sentiment       VARCHAR(20),
    confidence      DOUBLE PRECISION,
    coordinates     VARCHAR(50),
    published_at    TIMESTAMP WITH TIME ZONE,
    collected_at    TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_news_category ON news_intelligence (category);
CREATE INDEX IF NOT EXISTS idx_news_threat   ON news_intelligence (threat_level);


-- ============================================================
-- 7. Weather Zones (Computer 1 weather poller output)
-- ============================================================
CREATE TABLE IF NOT EXISTS weather_zones (
    id SERIAL PRIMARY KEY,
    firId VARCHAR(50),
    hazard VARCHAR(50),
    severity VARCHAR(50),
    validTimeFrom TIMESTAMP WITH TIME ZONE,
    validTimeTo TIMESTAMP WITH TIME ZONE,
    geometry JSONB,
    collected_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);


-- ============================================================
-- Publication for Debezium CDC
-- ============================================================
-- Debezium uses the PostgreSQL logical replication slot.
-- The publication tells PostgreSQL which tables to track.
CREATE PUBLICATION skyguard_publication FOR TABLE preprocessed_flights;

-- ============================================================
-- 8. Flight Routes (Origin/Destination Caching)
-- ============================================================
CREATE TABLE IF NOT EXISTS flight_routes (
    callsign VARCHAR(20) PRIMARY KEY,
    origin_airport_icao VARCHAR(10),
    destination_airport_icao VARCHAR(10),
    operator_icao VARCHAR(10),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
