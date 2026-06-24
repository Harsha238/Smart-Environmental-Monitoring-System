"""
analytics.py
------------------------------------------------------------------------------
Analytics engine for the Smart Environmental Monitoring & Analysis System.

Implements:
    - Daily average temperature / humidity / AQI
    - Maximum / minimum temperature detection
    - Pollution trend analysis (least-squares slope on daily AQI)
    - Composite environmental health score (0-100)
    - Anomaly detection (high temperature, poor air quality, high humidity)

This module is consumed by app.py (REST API), sensor_simulator.py
(real-time anomaly checks on ingestion), and can also be run standalone.
------------------------------------------------------------------------------
"""

import logging
from datetime import datetime
from typing import Dict, List, Any

import numpy as np

import database as db

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("analytics")

# ------------------------------------------------------------------------
# Thresholds (tunable constants -- centralising them here keeps the whole
# anomaly-detection policy in one place)
# ------------------------------------------------------------------------
TEMP_HIGH_THRESHOLD = 38.0        # °C  -> HIGH severity HIGH_TEMPERATURE alert
TEMP_CRITICAL_THRESHOLD = 42.0    # °C  -> CRITICAL severity
HUMIDITY_HIGH_THRESHOLD = 85.0    # %   -> MODERATE severity HIGH_HUMIDITY alert

AQI_MODERATE_THRESHOLD = 100      # EPA-style "Unhealthy for Sensitive Groups" boundary
AQI_POOR_THRESHOLD = 150          # "Unhealthy"
AQI_CRITICAL_THRESHOLD = 250      # "Very Unhealthy / Hazardous"

IDEAL_TEMP_RANGE = (20.0, 26.0)   # °C, comfortable indoor/outdoor range
IDEAL_HUMIDITY_RANGE = (40.0, 60.0)  # %, comfortable relative humidity range


# ------------------------------------------------------------------------
# Daily averages / extremes
# ------------------------------------------------------------------------
def get_daily_summary(days: int = 30) -> List[Dict[str, Any]]:
    """Daily avg temperature/humidity/AQI + daily max/min temperature."""
    try:
        return db.get_daily_aggregates(days=days)
    except Exception as exc:
        logger.error("get_daily_summary failed: %s", exc)
        return []


def get_overall_extremes(days: int = 30) -> Dict[str, Any]:
    """Overall maximum and minimum temperature detected across the period."""
    rows = get_daily_summary(days=days)
    if not rows:
        return {"max_temperature": None, "min_temperature": None}
    max_temp = max(float(r["max_temperature"]) for r in rows)
    min_temp = min(float(r["min_temperature"]) for r in rows)
    return {"max_temperature": max_temp, "min_temperature": min_temp}


# ------------------------------------------------------------------------
# Pollution trend analysis
# ------------------------------------------------------------------------
def pollution_trend_analysis(days: int = 14) -> Dict[str, Any]:
    """
    Fit a least-squares line to the daily-average AQI series and classify
    the slope as WORSENING / IMPROVING / STABLE.
    """
    rows = get_daily_summary(days=days)
    if len(rows) < 2:
        return {"trend": "INSUFFICIENT_DATA", "slope": 0.0, "period_days": days, "data_points": rows}

    aqi_values = np.array([float(r["avg_aqi"]) for r in rows])
    x = np.arange(len(aqi_values))
    slope, _intercept = np.polyfit(x, aqi_values, 1)

    if slope > 1.5:
        trend = "WORSENING"
    elif slope < -1.5:
        trend = "IMPROVING"
    else:
        trend = "STABLE"

    return {
        "trend": trend,
        "slope": round(float(slope), 3),
        "period_days": days,
        "average_aqi": round(float(np.mean(aqi_values)), 2),
        "data_points": rows,
    }


# ------------------------------------------------------------------------
# Environmental health score
# ------------------------------------------------------------------------
def _scale_score(value: float, ideal_low: float, ideal_high: float, max_deviation: float) -> float:
    """
    Returns 100 when `value` is inside [ideal_low, ideal_high], decaying
    linearly to 0 as it deviates by `max_deviation` units outside that band.
    """
    if ideal_low <= value <= ideal_high:
        return 100.0
    deviation = (ideal_low - value) if value < ideal_low else (value - ideal_high)
    return round(100.0 * max(0.0, 1 - (deviation / max_deviation)), 2)


def calculate_health_score(temperature: float, humidity: float, aqi: float) -> Dict[str, Any]:
    """
    Composite Environmental Health Score (0-100, higher = healthier).
    Weighting: AQI 50% | Temperature 30% | Humidity 20%
    (AQI dominates because air quality has the most direct health impact.)
    """
    temp_score = _scale_score(temperature, *IDEAL_TEMP_RANGE, max_deviation=15)
    humidity_score = _scale_score(humidity, *IDEAL_HUMIDITY_RANGE, max_deviation=40)
    aqi_score = round(max(0.0, 100.0 - (aqi / 5.0)), 2)  # AQI 0 -> 100pts, AQI 500 -> 0pts

    composite = round(0.5 * aqi_score + 0.3 * temp_score + 0.2 * humidity_score, 2)

    if composite >= 80:
        rating = "EXCELLENT"
    elif composite >= 60:
        rating = "GOOD"
    elif composite >= 40:
        rating = "MODERATE"
    elif composite >= 20:
        rating = "POOR"
    else:
        rating = "HAZARDOUS"

    return {
        "health_score": composite,
        "rating": rating,
        "components": {
            "temperature_score": temp_score,
            "humidity_score": humidity_score,
            "aqi_score": aqi_score,
        },
    }


# ------------------------------------------------------------------------
# Anomaly detection
# ------------------------------------------------------------------------
def _build_alert(reading_id, alert_type, severity, message) -> Dict[str, Any]:
    return {
        "reading_id": reading_id,
        "alert_type": alert_type,
        "severity": severity,
        "message": message,
        "timestamp": datetime.now().isoformat(),
    }


def detect_anomalies(reading: Dict[str, Any], persist: bool = True) -> List[Dict[str, Any]]:
    """
    Check a single sensor reading against the configured thresholds and
    build a list of anomaly alerts. If `persist=True` and the reading has
    a `reading_id`, each alert is also written to the `alerts` table.
    """
    anomalies: List[Dict[str, Any]] = []
    temperature = float(reading["temperature"])
    humidity = float(reading["humidity"])
    aqi = float(reading["aqi"])
    reading_id = reading.get("reading_id")

    # -- High temperature -----------------------------------------------
    if temperature >= TEMP_CRITICAL_THRESHOLD:
        anomalies.append(_build_alert(reading_id, "HIGH_TEMPERATURE", "CRITICAL",
                                       f"Critical temperature detected: {temperature}°C"))
    elif temperature >= TEMP_HIGH_THRESHOLD:
        anomalies.append(_build_alert(reading_id, "HIGH_TEMPERATURE", "HIGH",
                                       f"High temperature detected: {temperature}°C"))

    # -- Poor air quality --------------------------------------------------
    if aqi >= AQI_CRITICAL_THRESHOLD:
        anomalies.append(_build_alert(reading_id, "POOR_AIR_QUALITY", "CRITICAL",
                                       f"Hazardous air quality detected: AQI={aqi:.0f}"))
    elif aqi >= AQI_POOR_THRESHOLD:
        anomalies.append(_build_alert(reading_id, "POOR_AIR_QUALITY", "HIGH",
                                       f"Unhealthy air quality detected: AQI={aqi:.0f}"))
    elif aqi >= AQI_MODERATE_THRESHOLD:
        anomalies.append(_build_alert(reading_id, "POOR_AIR_QUALITY", "MODERATE",
                                       f"Moderate air quality warning: AQI={aqi:.0f}"))

    # -- High humidity (secondary anomaly) -------------------------------
    if humidity >= HUMIDITY_HIGH_THRESHOLD:
        anomalies.append(_build_alert(reading_id, "HIGH_HUMIDITY", "MODERATE",
                                       f"High humidity detected: {humidity}%"))

    if persist and reading_id is not None:
        for alert in anomalies:
            db.create_alert(reading_id, alert["alert_type"], alert["severity"], alert["message"])

    return anomalies


# ------------------------------------------------------------------------
# Full summary (used by GET /api/analytics/summary)
# ------------------------------------------------------------------------
def generate_analytics_summary(days: int = 7) -> Dict[str, Any]:
    """Build the complete analytics payload returned by the REST API."""
    daily = get_daily_summary(days=days)
    extremes = get_overall_extremes(days=days)
    trend = pollution_trend_analysis(days=days)

    latest_list = db.get_latest_reading(limit=1)
    latest = latest_list[0] if latest_list else None
    health = (
        calculate_health_score(float(latest["temperature"]), float(latest["humidity"]), float(latest["aqi"]))
        if latest else None
    )

    recent_alerts = db.get_recent_alerts(limit=10)

    return {
        "period_days": days,
        "daily_summary": daily,
        "overall_extremes": extremes,
        "pollution_trend": trend,
        "current_health_score": health,
        "latest_reading": latest,
        "recent_alerts": recent_alerts,
        "generated_at": datetime.now().isoformat(),
    }


if __name__ == "__main__":
    # Smoke test when run directly: python analytics.py
    summary = generate_analytics_summary(days=7)
    print("Daily summary rows:", len(summary["daily_summary"]))
    print("Overall extremes:", summary["overall_extremes"])
    print("Pollution trend:", summary["pollution_trend"]["trend"])
    print("Current health score:", summary["current_health_score"])
