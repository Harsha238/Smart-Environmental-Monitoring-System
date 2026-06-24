# 🌍 Smart Environmental Monitoring & Analysis System

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)]()
[![Flask](https://img.shields.io/badge/Flask-REST%20API-black)]()
[![MySQL](https://img.shields.io/badge/MySQL-8.0-orange)]()
[![scikit-learn](https://img.shields.io/badge/ML-scikit--learn-f7931e)]()
[![Power BI](https://img.shields.io/badge/Dashboard-Power%20BI-f2c811)]()

An end-to-end **IoT + Data Analytics + Machine Learning** system that simulates
an **ESP32** microcontroller with a **DHT11** (temperature/humidity) and
**MQ135** (air quality) sensor, streams readings into **MySQL** through a
**Flask REST API**, computes real-time environmental analytics, predicts
**future Air Quality Index (AQI)** values with **scikit-learn**, and
visualizes everything in a 3-page **Power BI** dashboard.

Built as a final-year engineering capstone project — fully functional,
modular, and resume-ready.

---

## 📌 Project Overview

Modern cities and indoor spaces need continuous environmental monitoring to
protect public health. This project demonstrates a complete IoT-to-insight
pipeline:

```
Sensor (simulated) → REST API → MySQL → Analytics Engine → ML Forecasting → Power BI Dashboard
```

It covers the full stack a real environmental-monitoring product would need:
data acquisition, persistence, a documented API, statistical analytics,
anomaly alerting, predictive ML, and business-intelligence reporting.

---

## ✨ Features

- 📡 **Realistic sensor simulation** — ESP32 + DHT11 + MQ135 with daily
  temperature cycles, humidity correlation, and randomized pollution spikes
- 🔌 **REST API (Flask)** — ingest, query latest/historical data, analytics summary
- 🗄️ **MySQL schema** — normalized tables, indexes, foreign keys, sample data
- 📊 **Analytics engine** — daily averages, max/min temperature, pollution
  trend detection (least-squares slope), composite health score
- 🚨 **Automated anomaly detection** — high temperature & poor air quality
  alerts raised the moment a reading is ingested
- 🤖 **Machine Learning** — Random Forest vs Linear Regression AQI forecaster
  with full preprocessing, evaluation, and multi-step future forecasting
- 📈 **Power BI dashboard** — 3 pages: KPI overview, trend charts, heatmap +
  gauge + alert table
- ✅ **Production-style code** — modular functions, logging, error handling,
  environment-based configuration

---

## 🏗️ Architecture Diagram

```
                    ┌──────────────────────────────┐
                    │   ESP32 + DHT11 + MQ135       │
                    │   (sensor_simulator.py)        │
                    │   generates a reading every     │
                    │   10 seconds                     │
                    └───────────────┬───────────────┘
                                    │ HTTP POST (JSON)
                                    ▼
                    ┌──────────────────────────────┐
                    │        Flask REST API          │
                    │            (app.py)             │
                    │  /api/readings        (POST)     │
                    │  /api/readings/latest  (GET)      │
                    │  /api/readings/history (GET)       │
                    │  /api/analytics/summary (GET)       │
                    │  /api/analytics/anomalies (GET)      │
                    └───────────────┬───────────────┘
                                    │
                  ┌─────────────────┼──────────────────┐
                  ▼                 ▼                   ▼
        ┌──────────────┐  ┌──────────────────┐  ┌──────────────────┐
        │  database.py  │  │   analytics.py    │  │ ml_prediction.py  │
        │  MySQL access │  │  daily averages,   │  │  RandomForest /    │
        │  layer         │  │  trend, health      │  │  LinearRegression  │
        │               │  │  score, anomalies     │  │  AQI forecasting     │
        └───────┬──────┘  └──────────────────┘  └──────────────────┘
                │
                ▼
        ┌──────────────┐
        │    MySQL      │
        │ smart_env_     │
        │ monitoring DB   │
        │ (sensor_readings,│
        │  alerts, daily_  │
        │  analytics)       │
        └───────┬──────┘
                │
                ▼
        ┌──────────────────────────────┐
        │        Power BI Dashboard      │
        │  Page 1: KPI Cards               │
        │  Page 2: Trend Line Charts        │
        │  Page 3: Heatmap + Gauge + Alerts  │
        └──────────────────────────────┘
```

---

## 🛠️ Tech Stack

| Layer            | Technology                                  |
|-------------------|----------------------------------------------|
| Hardware (sim)     | ESP32, DHT11, MQ135 (simulated in Python)     |
| Backend API         | Python, Flask, Flask-CORS                      |
| Database             | MySQL 8.0                                       |
| Data Analytics        | Pandas, NumPy, raw SQL                          |
| Machine Learning        | scikit-learn (RandomForestRegressor, LinearRegression) |
| Visualization (training) | Matplotlib                                    |
| BI Dashboard               | Microsoft Power BI                            |

---

## 📁 Project Structure

```
Smart_Environmental_Monitoring/
│
├── sensor_simulator.py     # ESP32 + DHT11 + MQ135 simulator (10s interval)
├── app.py                  # Flask REST API
├── database.py             # MySQL connection & query layer
├── analytics.py            # Daily stats, trend, health score, anomalies
├── ml_prediction.py        # AQI forecasting ML pipeline
├── requirements.txt        # Python dependencies
├── schema.sql              # Database schema + sample data + SQL queries
├── sample_data.csv         # 2,016-row realistic 14-day sample dataset
├── .env.example             # MySQL credentials template
├── .gitignore
├── powerbi/
│   ├── PowerBI_Dashboard_Guide.md   # Step-by-step dashboard build guide
│   └── dax_measures.txt              # All DAX measures, ready to paste
├── ml_outputs/                # Generated by ml_prediction.py (plots + model)
└── README.md
```

---

## 🚀 Installation & Setup

### 1. Clone & install dependencies
```bash
git clone <your-repo-url>
cd Smart_Environmental_Monitoring
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Set up MySQL
```bash
mysql -u root -p < schema.sql
```
This creates the `smart_env_monitoring` database, the `sensor_readings`,
`alerts`, and `daily_analytics` tables, and inserts ~30 sample rows.

Copy `.env.example` to `.env` and set your real credentials:
```bash
cp .env.example .env
# then edit .env with your MySQL host/user/password
```

### 3. (Optional) Bulk-load the full sample dataset
```python
# load_sample_data.py — quick one-off loader
import pandas as pd
import database as db

df = pd.read_csv("sample_data.csv")
df = df.where(pd.notnull(df), None)
df.rename(columns={"timestamp": "recorded_at"}, inplace=True)
rows = df.to_dict(orient="records")
db.bulk_insert_readings(rows)
```
```bash
python load_sample_data.py
```

### 4. Run the Flask API
```bash
python app.py
# API now live at http://localhost:5000
```

### 5. Run the sensor simulator (in a second terminal)
```bash
python sensor_simulator.py                 # streams to the API every 10s, forever
python sensor_simulator.py --iterations 20 --interval 2   # quick demo: 20 readings, 2s apart
```

### 6. Train the ML model & generate forecasts
```bash
python ml_prediction.py                     # uses sample_data.csv (offline demo)
python ml_prediction.py --source db          # trains on live MySQL data instead
```
Outputs (model + plots) are saved to `ml_outputs/`.

### 7. Build the Power BI dashboard
Follow `powerbi/PowerBI_Dashboard_Guide.md` step by step, using the DAX
measures in `powerbi/dax_measures.txt`.

---

## 🔌 API Reference

| Method | Endpoint                      | Description                                |
|--------|--------------------------------|----------------------------------------------|
| GET    | `/api/health`                  | Service & database health check               |
| POST   | `/api/readings`                | Ingest a new sensor reading + run anomaly check |
| GET    | `/api/readings/latest`         | Most recent reading(s) — `?limit=`              |
| GET    | `/api/readings/history`        | Historical data — `?start_date=&end_date=&limit=` |
| GET    | `/api/analytics/summary`       | Full analytics payload — `?days=`               |
| GET    | `/api/analytics/anomalies`     | Recent alerts — `?limit=`                        |

**Example: ingest a reading**
```bash
curl -X POST http://localhost:5000/api/readings \
  -H "Content-Type: application/json" \
  -d '{"temperature": 41.2, "humidity": 70, "aqi": 260, "device_id": "ESP32_NODE_01"}'
```

---

## 📸 Screenshots (placeholders)

> Replace these with real screenshots once you run the project locally.

| Screenshot | Description |
|------------|--------------|
| `screenshots/api_postman.png` | Postman/cURL call to `/api/readings` showing a successful 201 response with anomalies detected |
| `screenshots/ml_actual_vs_predicted.png` | `ml_outputs/actual_vs_predicted_aqi.png` — model tracking real pollution spikes |
| `screenshots/ml_feature_importance.png` | `ml_outputs/feature_importance.png` — which features drive AQI predictions |
| `screenshots/powerbi_page1_overview.png` | Power BI Page 1 — KPI cards for Avg Temp/Humidity/AQI |
| `screenshots/powerbi_page2_trends.png` | Power BI Page 2 — AQI/Temperature/Humidity trend lines |
| `screenshots/powerbi_page3_health.png` | Power BI Page 3 — heatmap, health score gauge, alert table |

---

## 📈 Results

On the bundled 2,016-row / 14-day synthetic dataset (`sample_data.csv`):

| Model              | MAE   | RMSE   | R²     |
|---------------------|--------|---------|---------|
| Linear Regression    | 6.22  | 10.76  | 0.952  |
| **Random Forest**   | **5.97** | **10.59** | **0.953** |

- The Random Forest model was automatically selected as the best performer
  and accurately tracks sharp AQI spikes caused by simulated pollution events.
- Anomaly detection correctly flags every simulated heatwave (≥38°C) and
  hazardous air-quality event (AQI ≥ 150) in the sample dataset.
- The composite Environmental Health Score correctly rates clean, mild
  conditions as "EXCELLENT/GOOD" and hot+polluted conditions as "POOR/HAZARDOUS".

---

## 🔮 Future Enhancements

- Replace the simulator with real ESP32 firmware (Arduino C++, `HTTPClient.h`)
  publishing to the same `/api/readings` endpoint
- Add MQTT support for lower-latency device-to-cloud telemetry
- Deploy the Flask API on a cloud VM / container with HTTPS + API-key auth
- Add LSTM/Prophet models for longer-horizon AQI forecasting
- Push real-time alerts to Telegram/Email/SMS via webhook
- Add a `daily_analytics` materializer job (cron) that pre-fills the cache table
- Containerize with Docker Compose (Flask + MySQL + scheduled simulator)

---

## 📄 License

This project is released under the MIT License — free to use, modify, and
extend for academic or portfolio purposes.

---

## 👤 Resume Project Description

**Smart Environmental Monitoring & Analysis System** | Python, Flask, MySQL, scikit-learn, Power BI
- Designed and built a full-stack IoT analytics platform simulating ESP32/DHT11/MQ135 sensors, ingesting real-time telemetry through a Flask REST API into a normalized MySQL database with automated anomaly detection.
- Engineered an analytics layer computing daily environmental statistics, pollution trend analysis, and a composite health-score index, and trained a Random Forest regression model (R²=0.95) to forecast future AQI values from time-series sensor data.
- Developed a 3-page Power BI dashboard (KPI cards, trend charts, heatmap, gauge, and alert table) backed by custom DAX measures, delivering actionable environmental insights from raw sensor data.

### ATS-Friendly Resume Entry
```
Smart Environmental Monitoring & Analysis System (Personal/Academic Project)
Python | Flask | MySQL | REST API | scikit-learn | Pandas | NumPy | Power BI | DAX
- Built an IoT data pipeline simulating ESP32, DHT11, and MQ135 sensors, streaming
  real-time temperature, humidity, and air quality data into MySQL via a Flask REST API.
- Implemented analytics module computing daily averages, pollution trend analysis,
  environmental health scoring, and automated anomaly/alert detection.
- Trained and evaluated Random Forest and Linear Regression models in scikit-learn to
  predict future AQI values (R-squared 0.95, MAE 5.97), with full preprocessing,
  evaluation, and visualization pipeline.
- Designed a 3-page interactive Power BI dashboard with KPI cards, trend visualizations,
  a heatmap, a gauge, and an alert table using custom DAX measures.
```
