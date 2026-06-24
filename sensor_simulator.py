"""
sensor_simulator.py
------------------------------------------------------------------------------
Simulates an ESP32 microcontroller fitted with:
    - DHT11 temperature & humidity sensor
    - MQ135 air-quality sensor (AQI)

Generates one realistic reading every 10 seconds and pushes it either:
    1) Through the Flask REST API via HTTP POST   (--mode api, default)
    2) Directly into MySQL via database.py         (--mode db)

This mirrors how real ESP32 firmware (e.g. Arduino C++ using WiFiClient /
HTTPClient) would publish telemetry to a backend server, while remaining
fully runnable on a laptop with no physical hardware attached.

Usage:
    python sensor_simulator.py                       # API mode, runs forever
    python sensor_simulator.py --mode db              # write straight to MySQL
    python sensor_simulator.py --iterations 20         # generate 20 readings then stop
    python sensor_simulator.py --interval 2 --iterations 10   # fast demo mode
------------------------------------------------------------------------------
"""

import argparse
import logging
import math
import random
import time
from datetime import datetime
from typing import Dict, Any, Optional

import requests

import database as db

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("sensor_simulator")

DEVICE_ID = "ESP32_NODE_01"
API_URL = "http://127.0.0.1:5000/api/readings"
READ_INTERVAL_SECONDS = 10


class EnvironmentSimulator:
    """
    Stateful generator that produces believable temperature, humidity and
    AQI values:
        - Temperature follows a daily sinusoidal cycle (cool at night,
          warm in the afternoon) plus small sensor noise.
        - Humidity is loosely inversely correlated with temperature.
        - AQI follows a mean-reverting random walk with occasional
          "pollution spike" events, so the anomaly-detection logic in
          analytics.py has real anomalies to catch.
    """

    def __init__(self):
        self._last_aqi = 60.0
        self._spike_remaining = 0
        self._base_humidity = 55.0

    def read_temperature(self) -> float:
        """Simulate DHT11 temperature output."""
        now = datetime.now()
        hour = now.hour + now.minute / 60.0
        # Daily cycle: trough ~3-4AM, peak ~3PM
        daily_cycle = 27 + 6 * math.sin(((hour - 9) / 24) * 2 * math.pi)
        noise = random.uniform(-0.6, 0.6)
        temperature = round(daily_cycle + noise, 2)
        return max(10.0, min(48.0, temperature))

    def read_humidity(self, temperature: float) -> float:
        """Simulate DHT11 humidity output, loosely inverse to temperature."""
        inverse_component = (28 - temperature) * 0.8
        drift = random.uniform(-2.0, 2.0)
        target = 58 + inverse_component
        self._base_humidity = self._base_humidity * 0.85 + target * 0.15 + drift
        self._base_humidity = max(20.0, min(95.0, self._base_humidity))
        return round(self._base_humidity, 2)

    def read_aqi(self) -> int:
        """
        Simulate MQ135 AQI output as a mean-reverting random walk with
        occasional pollution spike events (e.g. nearby traffic, burning).
        """
        if self._spike_remaining <= 0 and random.random() < 0.03:
            self._spike_remaining = random.randint(3, 8)  # spike lasts 3-8 cycles

        if self._spike_remaining > 0:
            target = random.uniform(180, 320)
            self._spike_remaining -= 1
        else:
            target = 60.0

        step = (target - self._last_aqi) * 0.25 + random.uniform(-5, 5)
        new_aqi = max(5.0, min(500.0, self._last_aqi + step))
        self._last_aqi = new_aqi
        return int(round(new_aqi))

    def generate_reading(self) -> Dict[str, Any]:
        """Produce one full sensor reading dict, as the ESP32 firmware would."""
        temperature = self.read_temperature()
        humidity = self.read_humidity(temperature)
        aqi = self.read_aqi()
        return {
            "device_id": DEVICE_ID,
            "temperature": temperature,
            "humidity": humidity,
            "aqi": aqi,
            "timestamp": datetime.now().isoformat(),
        }


# ------------------------------------------------------------------------
# Transport layer: REST API or direct DB write
# ------------------------------------------------------------------------
def send_via_api(reading: Dict[str, Any]) -> bool:
    """POST the reading to the Flask REST API. Returns True on success."""
    try:
        response = requests.post(API_URL, json=reading, timeout=5)
        response.raise_for_status()
        body = response.json()
        anomaly_note = f" | anomalies={body.get('anomalies_detected', 0)}" if isinstance(body, dict) else ""
        logger.info(
            "API OK [%s] temp=%.2f°C hum=%.2f%% aqi=%s%s",
            response.status_code, reading["temperature"], reading["humidity"], reading["aqi"], anomaly_note,
        )
        return True
    except requests.exceptions.RequestException as exc:
        logger.warning("API unreachable (%s). Falling back to direct DB insert.", exc)
        return False


def send_via_db(reading: Dict[str, Any]) -> bool:
    """Insert the reading directly into MySQL, bypassing the API."""
    try:
        reading_id = db.insert_reading(
            temperature=reading["temperature"],
            humidity=reading["humidity"],
            aqi=reading["aqi"],
            device_id=reading["device_id"],
        )
        return reading_id is not None
    except Exception as exc:  # noqa: BLE001 - simulator must never crash the loop
        logger.error("Direct DB insert failed: %s", exc)
        return False


# ------------------------------------------------------------------------
# Main simulation loop
# ------------------------------------------------------------------------
def run_simulation(mode: str, interval: int, iterations: Optional[int]) -> None:
    simulator = EnvironmentSimulator()
    logger.info("Starting Smart Environmental Monitoring simulator | mode=%s interval=%ss", mode, interval)

    count = 0
    while iterations is None or count < iterations:
        reading = simulator.generate_reading()

        if mode == "api":
            if not send_via_api(reading):
                send_via_db(reading)
        else:
            send_via_db(reading)

        count += 1
        if iterations is None or count < iterations:
            time.sleep(interval)

    logger.info("Simulation finished after %d reading(s).", count)


def main():
    parser = argparse.ArgumentParser(description="ESP32 + DHT11 + MQ135 environmental sensor simulator")
    parser.add_argument("--mode", choices=["api", "db"], default="api",
                         help="Send readings via the Flask REST API (default) or directly to MySQL")
    parser.add_argument("--interval", type=int, default=READ_INTERVAL_SECONDS,
                         help="Seconds between readings (default: 10, matching real DHT11 polling rate)")
    parser.add_argument("--iterations", type=int, default=None,
                         help="Number of readings to generate before stopping (default: run forever)")
    args = parser.parse_args()

    try:
        run_simulation(args.mode, args.interval, args.iterations)
    except KeyboardInterrupt:
        logger.info("Simulator stopped by user (Ctrl+C).")


if __name__ == "__main__":
    main()
