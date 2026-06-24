"""
app.py
------------------------------------------------------------------------------
Flask REST API for the Smart Environmental Monitoring & Analysis System.

Endpoints
---------
GET  /api/health                  -> Service + database health check
POST /api/readings                -> Ingest a new sensor reading (used by
                                      sensor_simulator.py); runs anomaly
                                      detection immediately on ingestion
GET  /api/readings/latest         -> Most recent reading(s)         ?limit=
GET  /api/readings/history        -> Historical readings            ?start_date=&end_date=&device_id=&limit=
GET  /api/analytics/summary       -> Full analytics summary          ?days=
GET  /api/analytics/anomalies     -> Recent alerts                  ?limit=

Run with:
    python app.py
    (or, for production)  flask --app app run --host=0.0.0.0 --port=5000
------------------------------------------------------------------------------
"""

import logging
from datetime import datetime

from flask import Flask, request, jsonify
from flask_cors import CORS

import database as db
import analytics

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("app")

app = Flask(__name__)
CORS(app)  # Allows browser-based dashboards / Power BI Web connector to query the API


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
def error_response(message: str, status_code: int = 400):
    return jsonify({"success": False, "error": message}), status_code


def clamp_int(raw, default, lo, hi):
    """Parse `raw` as int, clamp to [lo, hi]; fall back to `default` on bad input."""
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default, False
    return max(lo, min(value, hi)), True


# ----------------------------------------------------------------------------
# Health check
# ----------------------------------------------------------------------------
@app.route("/api/health", methods=["GET"])
def health_check():
    db_ok = db.test_connection()
    return jsonify({
        "success": True,
        "status": "online",
        "database_connected": db_ok,
        "timestamp": datetime.now().isoformat(),
    })


# ----------------------------------------------------------------------------
# Ingest a new sensor reading
# ----------------------------------------------------------------------------
@app.route("/api/readings", methods=["POST"])
def add_reading():
    payload = request.get_json(silent=True)
    if not payload:
        return error_response("Request body must be valid JSON.", 400)

    required_fields = {"temperature", "humidity", "aqi"}
    missing = required_fields - payload.keys()
    if missing:
        return error_response(f"Missing required field(s): {', '.join(sorted(missing))}", 400)

    try:
        temperature = float(payload["temperature"])
        humidity = float(payload["humidity"])
        aqi = int(round(float(payload["aqi"])))
        device_id = str(payload.get("device_id", "ESP32_NODE_01"))
    except (TypeError, ValueError):
        return error_response("temperature/humidity/aqi must be numeric.", 400)

    reading_id = db.insert_reading(temperature, humidity, aqi, device_id)
    if reading_id is None:
        return error_response("Failed to persist reading to the database.", 500)

    # Run anomaly detection immediately on ingestion
    reading_record = {"reading_id": reading_id, "temperature": temperature, "humidity": humidity, "aqi": aqi}
    anomalies = analytics.detect_anomalies(reading_record, persist=True)

    return jsonify({
        "success": True,
        "reading_id": reading_id,
        "anomalies_detected": len(anomalies),
        "anomalies": anomalies,
    }), 201


# ----------------------------------------------------------------------------
# Latest reading(s)
# ----------------------------------------------------------------------------
@app.route("/api/readings/latest", methods=["GET"])
def latest_readings():
    limit, ok = clamp_int(request.args.get("limit", 1), default=1, lo=1, hi=100)
    if not ok:
        return error_response("limit must be an integer.", 400)

    try:
        readings = db.get_latest_reading(limit=limit)
        return jsonify({"success": True, "count": len(readings), "data": readings})
    except Exception as exc:  # noqa: BLE001
        logger.error("latest_readings failed: %s", exc)
        return error_response("Could not retrieve latest readings.", 500)


# ----------------------------------------------------------------------------
# Historical data
# ----------------------------------------------------------------------------
@app.route("/api/readings/history", methods=["GET"])
def historical_data():
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    device_id = request.args.get("device_id")
    limit, ok = clamp_int(request.args.get("limit", 1000), default=1000, lo=1, hi=10000)
    if not ok:
        return error_response("limit must be an integer.", 400)

    try:
        rows = db.get_historical_data(start_date, end_date, device_id, limit)
        return jsonify({"success": True, "count": len(rows), "data": rows})
    except Exception as exc:  # noqa: BLE001
        logger.error("historical_data failed: %s", exc)
        return error_response("Could not retrieve historical data.", 500)


# ----------------------------------------------------------------------------
# Analytics summary
# ----------------------------------------------------------------------------
@app.route("/api/analytics/summary", methods=["GET"])
def analytics_summary():
    days, ok = clamp_int(request.args.get("days", 7), default=7, lo=1, hi=365)
    if not ok:
        return error_response("days must be an integer.", 400)

    try:
        summary = analytics.generate_analytics_summary(days=days)
        return jsonify({"success": True, "data": summary})
    except Exception as exc:  # noqa: BLE001
        logger.error("analytics_summary failed: %s", exc)
        return error_response("Could not generate analytics summary.", 500)


# ----------------------------------------------------------------------------
# Anomalies / alerts
# ----------------------------------------------------------------------------
@app.route("/api/analytics/anomalies", methods=["GET"])
def recent_anomalies():
    limit, ok = clamp_int(request.args.get("limit", 20), default=20, lo=1, hi=200)
    if not ok:
        return error_response("limit must be an integer.", 400)

    try:
        alerts = db.get_recent_alerts(limit=limit)
        return jsonify({"success": True, "count": len(alerts), "data": alerts})
    except Exception as exc:  # noqa: BLE001
        logger.error("recent_anomalies failed: %s", exc)
        return error_response("Could not retrieve anomalies.", 500)


# ----------------------------------------------------------------------------
# Error handlers
# ----------------------------------------------------------------------------
@app.errorhandler(404)
def not_found(_):
    return error_response("Endpoint not found.", 404)


@app.errorhandler(405)
def method_not_allowed(_):
    return error_response("Method not allowed on this endpoint.", 405)


if __name__ == "__main__":
    logger.info("Starting Smart Environmental Monitoring API on http://0.0.0.0:5000")
    app.run(host="0.0.0.0", port=5000, debug=True)
