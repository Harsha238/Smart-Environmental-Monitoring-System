# 🌍 Smart Environmental Monitoring & Analysis System

An end-to-end **IoT, Data Analytics, and Machine Learning** project that simulates an **ESP32** with **DHT11** and **MQ135** sensors, streams environmental data to a **Flask REST API**, stores readings in **MySQL**, predicts **Air Quality Index (AQI)** using **scikit-learn**, and visualizes insights through an interactive **Power BI** dashboard.

---

# 📌 Overview

This project demonstrates a complete environmental monitoring pipeline, from sensor data collection to predictive analytics and business intelligence visualization.

```
ESP32 Sensor Simulation
        │
        ▼
Flask REST API
        │
        ▼
MySQL Database
        │
        ▼
Analytics & Machine Learning
        │
        ▼
Power BI Dashboard
```

---

# ✨ Features

* 📡 ESP32 sensor simulation using DHT11 and MQ135
* 🌡️ Real-time temperature, humidity, and AQI monitoring
* 🔌 RESTful API built with Flask
* 🗄️ MySQL database integration
* 📊 Environmental analytics and trend analysis
* 🚨 Automated anomaly detection
* 🤖 AQI prediction using Machine Learning
* 📈 Interactive Power BI dashboard

---

# 🛠️ Tech Stack

* Python
* Flask
* MySQL
* Pandas
* NumPy
* Scikit-learn
* Power BI
* ESP32 (Simulated)
* DHT11
* MQ135

---

# 📁 Project Structure

```text
Smart_Environmental_Monitoring/
│── sensor_simulator.py
│── app.py
│── analytics.py
│── database.py
│── ml_prediction.py
│── schema.sql
│── sample_data.csv
│── requirements.txt
│── powerbi/
└── README.md
```

---

# 🚀 Installation

### Clone Repository

```bash
git clone https://github.com/Harsha238/Smart-Environmental-Monitoring.git
cd Smart-Environmental-Monitoring
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Configure Database

```bash
mysql -u root -p < schema.sql
```

Update the `.env` file with your MySQL credentials.

### Run the Flask API

```bash
python app.py
```

### Start the Sensor Simulator

```bash
python sensor_simulator.py
```

### Train the Machine Learning Model

```bash
python ml_prediction.py
```

---

# 📡 API Endpoints

| Method | Endpoint                   | Description             |
| ------ | -------------------------- | ----------------------- |
| GET    | `/api/health`              | API health check        |
| POST   | `/api/readings`            | Add sensor data         |
| GET    | `/api/readings/latest`     | Latest readings         |
| GET    | `/api/readings/history`    | Historical data         |
| GET    | `/api/analytics/summary`   | Environmental analytics |
| GET    | `/api/analytics/anomalies` | Recent alerts           |

---

# 📊 Dashboard

The Power BI dashboard provides:

* KPI Cards
* Temperature Trends
* Humidity Trends
* AQI Analysis
* Environmental Health Score
* Alert Monitoring
* Heatmaps
* Monthly Analytics

---

# 🤖 Machine Learning

The project compares multiple regression models to forecast future AQI values.

Models include:

* Random Forest Regressor
* Linear Regression

Evaluation Metrics:

* R² Score
* MAE
* RMSE

---

# 🔮 Future Improvements

* Real ESP32 hardware deployment
* MQTT integration
* Cloud deployment
* Email and SMS alerts
* Docker support
* LSTM-based AQI forecasting
* Mobile application integration

---

# 👩‍💻 Author

**K. Sai Harshitha**

---

⭐ If you found this project useful, consider giving it a star on GitHub.
