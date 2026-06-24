-- ============================================================================
-- Smart Environmental Monitoring & Analysis System
-- MySQL Database Schema
-- ============================================================================
-- Run with:  mysql -u root -p < schema.sql
-- ============================================================================

DROP DATABASE IF EXISTS smart_env_monitoring;
CREATE DATABASE smart_env_monitoring
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE smart_env_monitoring;

-- ----------------------------------------------------------------------------
-- Table: sensor_readings
-- Stores every reading pushed by the ESP32 (DHT11 + MQ135) every 10 seconds.
-- ----------------------------------------------------------------------------
CREATE TABLE sensor_readings (
    reading_id   BIGINT AUTO_INCREMENT PRIMARY KEY,
    device_id    VARCHAR(50)   NOT NULL DEFAULT 'ESP32_NODE_01',
    temperature  DECIMAL(5,2)  NOT NULL COMMENT 'Degrees Celsius (DHT11)',
    humidity     DECIMAL(5,2)  NOT NULL COMMENT 'Relative humidity %% (DHT11)',
    aqi          INT           NOT NULL COMMENT 'Air Quality Index (MQ135, EPA-style scale 0-500)',
    recorded_at  DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_recorded_at (recorded_at),
    INDEX idx_device (device_id),
    INDEX idx_device_time (device_id, recorded_at)
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- Table: alerts
-- Anomalies raised automatically by analytics.py on ingestion.
-- ----------------------------------------------------------------------------
CREATE TABLE alerts (
    alert_id     BIGINT AUTO_INCREMENT PRIMARY KEY,
    reading_id   BIGINT NOT NULL,
    alert_type   ENUM('HIGH_TEMPERATURE', 'POOR_AIR_QUALITY', 'HIGH_HUMIDITY') NOT NULL,
    severity     ENUM('LOW', 'MODERATE', 'HIGH', 'CRITICAL') NOT NULL,
    message      VARCHAR(255) NOT NULL,
    created_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_alert_reading FOREIGN KEY (reading_id)
        REFERENCES sensor_readings (reading_id) ON DELETE CASCADE,
    INDEX idx_created_at (created_at),
    INDEX idx_alert_type (alert_type)
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- Table: daily_analytics
-- Optional materialized cache so Power BI / dashboards can read pre-aggregated
-- daily figures without recomputing them on every query.
-- ----------------------------------------------------------------------------
CREATE TABLE daily_analytics (
    analytics_id     BIGINT AUTO_INCREMENT PRIMARY KEY,
    analysis_date    DATE NOT NULL UNIQUE,
    avg_temperature  DECIMAL(5,2),
    avg_humidity     DECIMAL(5,2),
    avg_aqi          DECIMAL(6,2),
    max_temperature  DECIMAL(5,2),
    min_temperature  DECIMAL(5,2),
    health_score     DECIMAL(5,2),
    created_at       DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- ============================================================================
-- SAMPLE DATASET
-- A small representative sample (use sample_data.csv + the loader snippet in
-- README.md to bulk-load the full 2000+ row dataset for analytics/ML/Power BI)
-- ============================================================================
INSERT INTO sensor_readings (device_id, temperature, humidity, aqi, recorded_at) VALUES
('ESP32_NODE_01', 24.10, 58.20, 62,  '2026-06-10 00:00:00'),
('ESP32_NODE_01', 23.80, 59.10, 58,  '2026-06-10 00:10:00'),
('ESP32_NODE_01', 23.40, 60.30, 55,  '2026-06-10 00:20:00'),
('ESP32_NODE_01', 22.90, 61.50, 130, '2026-06-10 00:30:00'),
('ESP32_NODE_01', 22.70, 62.00, 178, '2026-06-10 00:40:00'),
('ESP32_NODE_01', 22.50, 62.80, 205, '2026-06-10 00:50:00'),
('ESP32_NODE_01', 22.30, 63.40, 190, '2026-06-10 01:00:00'),
('ESP32_NODE_01', 22.10, 64.00, 140, '2026-06-10 01:10:00'),
('ESP32_NODE_01', 21.90, 64.50, 95,  '2026-06-10 01:20:00'),
('ESP32_NODE_01', 21.70, 65.10, 70,  '2026-06-10 01:30:00'),
('ESP32_NODE_01', 25.30, 56.00, 65,  '2026-06-10 09:00:00'),
('ESP32_NODE_01', 27.10, 52.40, 68,  '2026-06-10 12:00:00'),
('ESP32_NODE_01', 29.80, 47.30, 72,  '2026-06-10 14:00:00'),
('ESP32_NODE_01', 31.20, 44.10, 80,  '2026-06-10 15:00:00'),
('ESP32_NODE_01', 38.60, 41.00, 90,  '2026-06-10 15:30:00'),
('ESP32_NODE_01', 42.90, 38.50, 88,  '2026-06-10 15:40:00'),
('ESP32_NODE_01', 30.10, 46.00, 75,  '2026-06-10 16:30:00'),
('ESP32_NODE_01', 28.40, 49.20, 64,  '2026-06-10 18:00:00'),
('ESP32_NODE_01', 26.00, 53.60, 60,  '2026-06-10 20:00:00'),
('ESP32_NODE_01', 24.50, 57.00, 58,  '2026-06-10 22:00:00'),
('ESP32_NODE_01', 23.90, 58.40, 55,  '2026-06-11 00:00:00'),
('ESP32_NODE_01', 24.00, 58.10, 59,  '2026-06-11 02:00:00'),
('ESP32_NODE_01', 25.50, 55.80, 63,  '2026-06-11 08:00:00'),
('ESP32_NODE_01', 28.70, 50.10, 110, '2026-06-11 11:00:00'),
('ESP32_NODE_01', 30.40, 46.50, 160, '2026-06-11 13:00:00'),
('ESP32_NODE_01', 31.80, 44.80, 255, '2026-06-11 13:30:00'),
('ESP32_NODE_01', 32.10, 44.20, 270, '2026-06-11 13:40:00'),
('ESP32_NODE_01', 31.50, 45.10, 210, '2026-06-11 14:00:00'),
('ESP32_NODE_01', 29.90, 47.60, 130, '2026-06-11 15:00:00'),
('ESP32_NODE_01', 27.20, 52.00, 85,  '2026-06-11 17:00:00'),
('ESP32_NODE_01', 25.10, 56.50, 70,  '2026-06-11 19:00:00'),
('ESP32_NODE_01', 23.60, 60.00, 60,  '2026-06-11 21:00:00');

-- ============================================================================
-- ANALYTICAL QUERIES
-- The same logic implemented in analytics.py, expressed directly in SQL.
-- Useful for ad-hoc analysis, Power BI "SQL query" data source mode, and
-- validating the Python analytics engine's output.
-- ============================================================================

-- 1) Daily average temperature, humidity, AQI -------------------------------
SELECT
    DATE(recorded_at)              AS reading_date,
    ROUND(AVG(temperature), 2)     AS avg_temperature,
    ROUND(AVG(humidity), 2)        AS avg_humidity,
    ROUND(AVG(aqi), 2)             AS avg_aqi,
    COUNT(*)                       AS reading_count
FROM sensor_readings
GROUP BY DATE(recorded_at)
ORDER BY reading_date;

-- 2) Maximum & minimum temperature detected (overall) -----------------------
SELECT
    MAX(temperature) AS max_temperature_recorded,
    MIN(temperature) AS min_temperature_recorded
FROM sensor_readings;

-- 3) Maximum & minimum temperature per day -----------------------------------
SELECT
    DATE(recorded_at) AS reading_date,
    MAX(temperature)  AS max_temperature,
    MIN(temperature)  AS min_temperature
FROM sensor_readings
GROUP BY DATE(recorded_at)
ORDER BY reading_date;

-- 4) Pollution trend analysis (day-over-day AQI change) ----------------------
SELECT
    reading_date,
    avg_aqi,
    LAG(avg_aqi) OVER (ORDER BY reading_date) AS prev_day_avg_aqi,
    ROUND(avg_aqi - LAG(avg_aqi) OVER (ORDER BY reading_date), 2) AS aqi_change,
    CASE
        WHEN avg_aqi - LAG(avg_aqi) OVER (ORDER BY reading_date) > 5  THEN 'WORSENING'
        WHEN avg_aqi - LAG(avg_aqi) OVER (ORDER BY reading_date) < -5 THEN 'IMPROVING'
        ELSE 'STABLE'
    END AS trend
FROM (
    SELECT DATE(recorded_at) AS reading_date, ROUND(AVG(aqi), 2) AS avg_aqi
    FROM sensor_readings
    GROUP BY DATE(recorded_at)
) AS daily
ORDER BY reading_date;

-- 5) Poor air quality alert count by day -------------------------------------
SELECT
    DATE(recorded_at) AS reading_date,
    COUNT(*) AS poor_aqi_readings
FROM sensor_readings
WHERE aqi >= 150
GROUP BY DATE(recorded_at)
ORDER BY reading_date;

-- 6) High temperature alert events -------------------------------------------
SELECT reading_id, device_id, temperature, recorded_at
FROM sensor_readings
WHERE temperature >= 38.0
ORDER BY recorded_at;

-- 7) Environmental health score components (latest reading) -----------------
SELECT
    reading_id, temperature, humidity, aqi, recorded_at,
    ROUND(GREATEST(0, 100 - (aqi / 5)), 2) AS aqi_sub_score
FROM sensor_readings
ORDER BY recorded_at DESC
LIMIT 1;

-- 8) Alerts joined with their originating reading -----------------------------
SELECT
    a.alert_id, a.alert_type, a.severity, a.message, a.created_at,
    r.temperature, r.humidity, r.aqi
FROM alerts a
JOIN sensor_readings r ON a.reading_id = r.reading_id
ORDER BY a.created_at DESC
LIMIT 50;

-- 9) Hourly average AQI (useful for Power BI heatmap: hour x day matrix) ------
SELECT
    DATE(recorded_at)            AS reading_date,
    HOUR(recorded_at)            AS reading_hour,
    ROUND(AVG(aqi), 2)           AS avg_aqi
FROM sensor_readings
GROUP BY DATE(recorded_at), HOUR(recorded_at)
ORDER BY reading_date, reading_hour;

-- ============================================================================
-- BULK LOADING THE FULL SAMPLE DATASET (sample_data.csv)
-- ============================================================================
-- Option A: LOAD DATA (run from the MySQL client on the server hosting the file)
-- LOAD DATA LOCAL INFILE 'sample_data.csv'
-- INTO TABLE sensor_readings
-- FIELDS TERMINATED BY ',' ENCLOSED BY '"'
-- LINES TERMINATED BY '\n'
-- IGNORE 1 ROWS
-- (device_id, temperature, humidity, aqi, recorded_at);
--
-- Option B (recommended): use the Python loader shown in README.md, which
-- reads sample_data.csv with pandas and calls database.insert_reading() for
-- each row -- this also keeps timestamp parsing/validation consistent with
-- the rest of the codebase.
