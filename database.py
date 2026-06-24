"""
database.py
------------------------------------------------------------------------------
Database access layer for the Smart Environmental Monitoring & Analysis System.

Responsibilities:
    - Manage MySQL connections (env-based configuration, context managers)
    - Insert new sensor readings (called by the Flask API on ingestion)
    - Retrieve latest / historical readings
    - Create and retrieve anomaly alerts
    - Provide pre-aggregated daily statistics for the analytics engine

All public functions fail "softly" (return None / [] and log the error)
rather than crashing the calling process, since this module is used both
by a live Flask server and by offline scripts (ML training, simulator).
------------------------------------------------------------------------------
"""

import os
import logging
from contextlib import contextmanager
from datetime import datetime
from typing import Optional, List, Dict, Any

import mysql.connector
from mysql.connector import Error as MySQLError

try:
    from dotenv import load_dotenv
    load_dotenv()  # Loads variables from a local .env file, if present
except ImportError:
    pass  # python-dotenv is optional; environment variables still work without it

# ------------------------------------------------------------------------
# Configuration (override via environment variables or a .env file)
# ------------------------------------------------------------------------
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", "root"),
    "database": os.getenv("DB_NAME", "smart_env_monitoring"),
    "autocommit": False,
    "connection_timeout": 10,
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("database")


# ------------------------------------------------------------------------
# Connection handling
# ------------------------------------------------------------------------
@contextmanager
def get_connection():
    """
    Context manager that yields a live MySQL connection and guarantees
    it is closed afterwards, even if an exception is raised.
    """
    connection = None
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        yield connection
    except MySQLError as exc:
        logger.error("MySQL connection error: %s", exc)
        raise
    finally:
        if connection is not None and connection.is_connected():
            connection.close()


@contextmanager
def get_cursor(commit: bool = False):
    """
    Context manager that yields a dictionary cursor (rows returned as dicts)
    bound to a fresh connection. Commits on success if `commit=True`,
    rolls back automatically on any exception.
    """
    with get_connection() as connection:
        cursor = connection.cursor(dictionary=True)
        try:
            yield cursor
            if commit:
                connection.commit()
        except MySQLError as exc:
            connection.rollback()
            logger.error("Query failed, transaction rolled back: %s", exc)
            raise
        finally:
            cursor.close()


def test_connection() -> bool:
    """Quick health check used by /api/health and start-up diagnostics."""
    try:
        with get_connection() as conn:
            return conn.is_connected()
    except MySQLError:
        return False


# ------------------------------------------------------------------------
# Sensor readings
# ------------------------------------------------------------------------
def insert_reading(temperature: float, humidity: float, aqi: int,
                    device_id: str = "ESP32_NODE_01") -> Optional[int]:
    """
    Insert a new sensor reading.

    Returns:
        The auto-generated reading_id, or None if the insert failed.
    """
    query = """
        INSERT INTO sensor_readings (device_id, temperature, humidity, aqi, recorded_at)
        VALUES (%s, %s, %s, %s, %s)
    """
    try:
        with get_cursor(commit=True) as cursor:
            cursor.execute(query, (device_id, temperature, humidity, aqi, datetime.now()))
            reading_id = cursor.lastrowid
            logger.info(
                "Inserted reading #%s | temp=%.2f°C hum=%.2f%% aqi=%s",
                reading_id, temperature, humidity, aqi,
            )
            return reading_id
    except MySQLError as exc:
        logger.error("Failed to insert reading: %s", exc)
        return None


def get_latest_reading(limit: int = 1) -> List[Dict[str, Any]]:
    """Return the most recent `limit` readings, newest first."""
    query = """
        SELECT reading_id, device_id, temperature, humidity, aqi, recorded_at
        FROM sensor_readings
        ORDER BY recorded_at DESC
        LIMIT %s
    """
    try:
        with get_cursor() as cursor:
            cursor.execute(query, (limit,))
            return cursor.fetchall()
    except MySQLError as exc:
        logger.error("get_latest_reading failed: %s", exc)
        return []


def get_historical_data(start_date: Optional[str] = None,
                         end_date: Optional[str] = None,
                         device_id: Optional[str] = None,
                         limit: int = 1000) -> List[Dict[str, Any]]:
    """
    Return historical readings filtered by optional date range / device.
    Dates are expected in 'YYYY-MM-DD' format.
    """
    conditions, params = [], []

    if start_date:
        conditions.append("recorded_at >= %s")
        params.append(f"{start_date} 00:00:00")
    if end_date:
        conditions.append("recorded_at <= %s")
        params.append(f"{end_date} 23:59:59")
    if device_id:
        conditions.append("device_id = %s")
        params.append(device_id)

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    query = f"""
        SELECT reading_id, device_id, temperature, humidity, aqi, recorded_at
        FROM sensor_readings
        {where_clause}
        ORDER BY recorded_at ASC
        LIMIT %s
    """
    params.append(limit)

    try:
        with get_cursor() as cursor:
            cursor.execute(query, tuple(params))
            return cursor.fetchall()
    except MySQLError as exc:
        logger.error("get_historical_data failed: %s", exc)
        return []


def get_daily_aggregates(days: int = 30) -> List[Dict[str, Any]]:
    """
    Daily average temperature/humidity/AQI plus max/min temperature,
    used by analytics.get_daily_summary().
    """
    query = """
        SELECT
            DATE(recorded_at)            AS reading_date,
            ROUND(AVG(temperature), 2)   AS avg_temperature,
            ROUND(AVG(humidity), 2)      AS avg_humidity,
            ROUND(AVG(aqi), 2)           AS avg_aqi,
            MAX(temperature)             AS max_temperature,
            MIN(temperature)             AS min_temperature,
            COUNT(*)                     AS reading_count
        FROM sensor_readings
        WHERE recorded_at >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
        GROUP BY DATE(recorded_at)
        ORDER BY reading_date ASC
    """
    try:
        with get_cursor() as cursor:
            cursor.execute(query, (days,))
            return cursor.fetchall()
    except MySQLError as exc:
        logger.error("get_daily_aggregates failed: %s", exc)
        return []


# ------------------------------------------------------------------------
# Alerts
# ------------------------------------------------------------------------
def create_alert(reading_id: int, alert_type: str, severity: str, message: str) -> Optional[int]:
    """Persist an anomaly alert linked to the reading that triggered it."""
    query = """
        INSERT INTO alerts (reading_id, alert_type, severity, message, created_at)
        VALUES (%s, %s, %s, %s, %s)
    """
    try:
        with get_cursor(commit=True) as cursor:
            cursor.execute(query, (reading_id, alert_type, severity, message, datetime.now()))
            alert_id = cursor.lastrowid
            logger.warning("ALERT raised [%s/%s] (reading #%s): %s",
                            alert_type, severity, reading_id, message)
            return alert_id
    except MySQLError as exc:
        logger.error("Failed to create alert: %s", exc)
        return None


def get_recent_alerts(limit: int = 20) -> List[Dict[str, Any]]:
    """Return the most recent alerts, newest first, joined with reading data."""
    query = """
        SELECT a.alert_id, a.alert_type, a.severity, a.message, a.created_at,
               r.temperature, r.humidity, r.aqi, r.device_id
        FROM alerts a
        JOIN sensor_readings r ON a.reading_id = r.reading_id
        ORDER BY a.created_at DESC
        LIMIT %s
    """
    try:
        with get_cursor() as cursor:
            cursor.execute(query, (limit,))
            return cursor.fetchall()
    except MySQLError as exc:
        logger.error("get_recent_alerts failed: %s", exc)
        return []


# ------------------------------------------------------------------------
# Bulk loading helper (used to import sample_data.csv)
# ------------------------------------------------------------------------
def bulk_insert_readings(rows: List[Dict[str, Any]]) -> int:
    """
    Insert many readings in a single transaction. Each row dict must
    contain: device_id, temperature, humidity, aqi, recorded_at.
    Returns the number of rows successfully inserted.
    """
    query = """
        INSERT INTO sensor_readings (device_id, temperature, humidity, aqi, recorded_at)
        VALUES (%(device_id)s, %(temperature)s, %(humidity)s, %(aqi)s, %(recorded_at)s)
    """
    try:
        with get_cursor(commit=True) as cursor:
            cursor.executemany(query, rows)
            logger.info("Bulk inserted %d readings.", cursor.rowcount)
            return cursor.rowcount
    except MySQLError as exc:
        logger.error("bulk_insert_readings failed: %s", exc)
        return 0


if __name__ == "__main__":
    # Simple smoke test when run directly: python database.py
    if test_connection():
        print("✅ Successfully connected to MySQL:", DB_CONFIG["database"])
        latest = get_latest_reading(limit=5)
        print(f"Latest {len(latest)} readings:")
        for row in latest:
            print(" ", row)
    else:
        print("❌ Could not connect to MySQL. Check DB_HOST/DB_USER/DB_PASSWORD/DB_NAME.")
