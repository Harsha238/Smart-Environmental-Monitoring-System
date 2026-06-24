"""
ml_prediction.py
------------------------------------------------------------------------------
Machine Learning module for the Smart Environmental Monitoring & Analysis
System -- predicts FUTURE Air Quality Index (AQI) values from historical
temperature, humidity, and AQI sensor readings.

Pipeline:
    1. Load data             (MySQL database OR local sample_data.csv)
    2. Preprocess              (calendar features, lag features, rolling stats)
    3. Time-based train/test split (no shuffling -- this is a time series)
    4. Train models             (Linear Regression baseline + Random Forest)
    5. Evaluate                  (MAE, RMSE, R2)
    6. Visualize results          (saved as PNGs to ml_outputs/)
    7. Persist the best model     (joblib .pkl)
    8. Forecast future AQI         (walk-forward multi-step forecast)

Run directly:
    python ml_prediction.py                          # offline demo using sample_data.csv
    python ml_prediction.py --source db                # train on live MySQL data
    python ml_prediction.py --forecast-steps 24         # forecast next 24 readings
------------------------------------------------------------------------------
"""

import os
import logging
import argparse
from datetime import timedelta
from typing import Tuple, Optional

import numpy as np
import pandas as pd
import joblib

import matplotlib
matplotlib.use("Agg")  # headless backend -- safe for servers with no display
import matplotlib.pyplot as plt

from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("ml_prediction")

OUTPUT_DIR = "ml_outputs"
MODEL_PATH = os.path.join(OUTPUT_DIR, "aqi_predictor_model.pkl")
SCALER_PATH = os.path.join(OUTPUT_DIR, "aqi_scaler.pkl")
READING_INTERVAL_MINUTES = 10  # matches the interval used to build sample_data.csv

FEATURE_COLUMNS = [
    "temperature", "humidity", "aqi",
    "hour", "day_of_week", "is_weekend",
    "aqi_lag_1", "aqi_lag_2", "aqi_lag_3",
    "aqi_rolling_mean_6", "temp_rolling_mean_6",
]
TARGET_COLUMN = "aqi_next"


# ----------------------------------------------------------------------------
# 1. Data loading
# ----------------------------------------------------------------------------
def load_data(source: str = "csv", csv_path: str = "sample_data.csv") -> pd.DataFrame:
    """Load sensor readings from MySQL ('db') or the local CSV ('csv', default)."""
    if source == "db":
        import database as db_module
        rows = db_module.get_historical_data(limit=100000)
        if not rows:
            raise RuntimeError("No data returned from MySQL. Is the database populated?")
        df = pd.DataFrame(rows)
        df.rename(columns={"recorded_at": "timestamp"}, inplace=True)
    else:
        if not os.path.exists(csv_path):
            raise FileNotFoundError(f"Sample dataset not found at '{csv_path}'.")
        df = pd.read_csv(csv_path)

    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df.sort_values("timestamp", inplace=True)
    df.reset_index(drop=True, inplace=True)
    logger.info("Loaded %d rows from source='%s'", len(df), source)
    return df


# ----------------------------------------------------------------------------
# 2. Preprocessing / feature engineering
# ----------------------------------------------------------------------------
def preprocess(df: pd.DataFrame) -> pd.DataFrame:
    """
    Build the supervised-learning feature set:
        - Calendar features  : hour, day_of_week, is_weekend
        - Lag features        : aqi_lag_1 / 2 / 3 (previous readings)
        - Rolling statistics  : aqi_rolling_mean_6, temp_rolling_mean_6
        - Target               : aqi_next (the AQI value of the NEXT reading)
    """
    data = df.copy()

    # Handle missing sensor values (simulated dropout) via forward-fill
    data[["temperature", "humidity", "aqi"]] = data[["temperature", "humidity", "aqi"]].ffill()
    data.dropna(subset=["temperature", "humidity", "aqi"], inplace=True)

    data["hour"] = data["timestamp"].dt.hour
    data["day_of_week"] = data["timestamp"].dt.dayofweek
    data["is_weekend"] = (data["day_of_week"] >= 5).astype(int)

    for lag in (1, 2, 3):
        data[f"aqi_lag_{lag}"] = data["aqi"].shift(lag)

    data["aqi_rolling_mean_6"] = data["aqi"].rolling(window=6).mean()
    data["temp_rolling_mean_6"] = data["temperature"].rolling(window=6).mean()

    # Target = AQI of the NEXT reading (what the model must predict)
    data["aqi_next"] = data["aqi"].shift(-1)

    data.dropna(inplace=True)
    data.reset_index(drop=True, inplace=True)
    logger.info("Preprocessing complete: %d usable rows after feature engineering.", len(data))
    return data


# ----------------------------------------------------------------------------
# 3. Time-based train/test split
# ----------------------------------------------------------------------------
def time_based_split(data: pd.DataFrame, test_size: float = 0.2):
    """
    Splits chronologically (no shuffling) so the test set is strictly
    "in the future" relative to the training set -- the correct approach
    for time-series data, unlike a random sklearn train_test_split.
    """
    split_idx = int(len(data) * (1 - test_size))
    train_df = data.iloc[:split_idx]
    test_df = data.iloc[split_idx:]

    X_train, y_train = train_df[FEATURE_COLUMNS], train_df[TARGET_COLUMN]
    X_test, y_test = test_df[FEATURE_COLUMNS], test_df[TARGET_COLUMN]
    return X_train, X_test, y_train, y_test, train_df, test_df


# ----------------------------------------------------------------------------
# 4 & 5. Train models + evaluate
# ----------------------------------------------------------------------------
def train_and_evaluate(X_train, X_test, y_train, y_test):
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    models = {
        "LinearRegression": LinearRegression(),
        "RandomForest": RandomForestRegressor(n_estimators=200, max_depth=10, random_state=42, n_jobs=-1),
    }

    results, predictions = {}, {}

    for name, model in models.items():
        model.fit(X_train_scaled, y_train)
        y_pred = model.predict(X_test_scaled)

        mae = mean_absolute_error(y_test, y_pred)
        rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))
        r2 = r2_score(y_test, y_pred)

        results[name] = {"MAE": round(mae, 3), "RMSE": round(rmse, 3), "R2": round(r2, 4)}
        predictions[name] = y_pred
        logger.info("[%s] MAE=%.3f  RMSE=%.3f  R2=%.4f", name, mae, rmse, r2)

    best_model_name = min(results, key=lambda n: results[n]["MAE"])
    logger.info("Best model selected: %s", best_model_name)

    return {
        "models": models,
        "scaler": scaler,
        "results": results,
        "predictions": predictions,
        "best_model_name": best_model_name,
        "best_model": models[best_model_name],
    }


# ----------------------------------------------------------------------------
# 6. Visualization
# ----------------------------------------------------------------------------
def plot_actual_vs_predicted(test_df, y_test, predictions, best_model_name):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    plt.figure(figsize=(12, 5))
    plt.plot(test_df["timestamp"], y_test.values, label="Actual AQI", linewidth=1.8)
    plt.plot(test_df["timestamp"], predictions[best_model_name],
              label=f"Predicted AQI ({best_model_name})", linewidth=1.4, linestyle="--")
    plt.title("Actual vs Predicted AQI (Test Set)")
    plt.xlabel("Timestamp")
    plt.ylabel("AQI")
    plt.legend()
    plt.xticks(rotation=30)
    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "actual_vs_predicted_aqi.png")
    plt.savefig(path, dpi=150)
    plt.close()
    logger.info("Saved plot: %s", path)


def plot_feature_importance(model, feature_names):
    if not hasattr(model, "feature_importances_"):
        return
    importances = model.feature_importances_
    order = np.argsort(importances)

    plt.figure(figsize=(9, 6))
    plt.barh(np.array(feature_names)[order], importances[order], color="#2e86ab")
    plt.title("Random Forest Feature Importance for AQI Prediction")
    plt.xlabel("Importance")
    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "feature_importance.png")
    plt.savefig(path, dpi=150)
    plt.close()
    logger.info("Saved plot: %s", path)


def plot_model_comparison(results):
    names = list(results.keys())
    mae_values = [results[n]["MAE"] for n in names]

    plt.figure(figsize=(6, 5))
    plt.bar(names, mae_values, color=["#a8dadc", "#1d3557"])
    plt.title("Model Comparison -- Mean Absolute Error (lower is better)")
    plt.ylabel("MAE")
    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "model_comparison_mae.png")
    plt.savefig(path, dpi=150)
    plt.close()
    logger.info("Saved plot: %s", path)


def plot_forecast(history_df: pd.DataFrame, forecast_df: pd.DataFrame, lookback: int = 50):
    plt.figure(figsize=(12, 5))
    recent_history = history_df.tail(lookback)
    plt.plot(recent_history["timestamp"], recent_history["aqi"], label="Historical AQI")
    plt.plot(forecast_df["timestamp"], forecast_df["predicted_aqi"], label="Forecasted AQI",
              linestyle="--", marker="o", markersize=3)
    plt.axvline(x=history_df["timestamp"].iloc[-1], color="gray", linestyle=":", label="Forecast start")
    plt.title("Future AQI Forecast")
    plt.xlabel("Timestamp")
    plt.ylabel("AQI")
    plt.legend()
    plt.xticks(rotation=30)
    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "future_aqi_forecast.png")
    plt.savefig(path, dpi=150)
    plt.close()
    logger.info("Saved plot: %s", path)


# ----------------------------------------------------------------------------
# 7. Persist / load model
# ----------------------------------------------------------------------------
def save_model(model, scaler):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    joblib.dump(scaler, SCALER_PATH)
    logger.info("Model saved to %s", MODEL_PATH)
    logger.info("Scaler saved to %s", SCALER_PATH)


def load_saved_model() -> Tuple[Optional[object], Optional[object]]:
    if os.path.exists(MODEL_PATH) and os.path.exists(SCALER_PATH):
        return joblib.load(MODEL_PATH), joblib.load(SCALER_PATH)
    return None, None


# ----------------------------------------------------------------------------
# 8. Multi-step future forecasting (walk-forward)
# ----------------------------------------------------------------------------
def forecast_future_aqi(model, scaler, processed_df: pd.DataFrame, steps: int = 12) -> pd.DataFrame:
    """
    Walk-forward forecast of the next `steps` AQI readings: each predicted
    value is fed back in as the lag feature for the following step, since
    future ground truth is (by definition) not available yet.
    """
    history = processed_df.copy().reset_index(drop=True)
    last_timestamp = history["timestamp"].iloc[-1]
    forecasts = []

    recent_aqi = list(history["aqi"].tail(6))
    last_temp = float(history["temperature"].iloc[-1])
    last_humidity = float(history["humidity"].iloc[-1])

    for step in range(1, steps + 1):
        future_time = last_timestamp + timedelta(minutes=READING_INTERVAL_MINUTES * step)
        features = pd.DataFrame([{
            "temperature": last_temp,
            "humidity": last_humidity,
            "aqi": recent_aqi[-1],
            "hour": future_time.hour,
            "day_of_week": future_time.dayofweek,
            "is_weekend": int(future_time.dayofweek >= 5),
            "aqi_lag_1": recent_aqi[-1],
            "aqi_lag_2": recent_aqi[-2] if len(recent_aqi) >= 2 else recent_aqi[-1],
            "aqi_lag_3": recent_aqi[-3] if len(recent_aqi) >= 3 else recent_aqi[-1],
            "aqi_rolling_mean_6": float(np.mean(recent_aqi[-6:])),
            "temp_rolling_mean_6": last_temp,
        }])[FEATURE_COLUMNS]

        scaled = scaler.transform(features)
        predicted_aqi = max(0.0, float(model.predict(scaled)[0]))

        forecasts.append({"timestamp": future_time, "predicted_aqi": round(predicted_aqi, 2)})
        recent_aqi.append(predicted_aqi)

    return pd.DataFrame(forecasts)


# ----------------------------------------------------------------------------
# Main pipeline
# ----------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Train and evaluate the AQI prediction model.")
    parser.add_argument("--source", choices=["csv", "db"], default="csv",
                         help="Train on the local sample_data.csv (default) or live MySQL data")
    parser.add_argument("--csv-path", default="sample_data.csv")
    parser.add_argument("--forecast-steps", type=int, default=12,
                         help="Number of future readings to forecast (default: 12 -> next 2 hours)")
    args = parser.parse_args()

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    df = load_data(source=args.source, csv_path=args.csv_path)
    processed = preprocess(df)

    X_train, X_test, y_train, y_test, train_df, test_df = time_based_split(processed)
    outcome = train_and_evaluate(X_train, X_test, y_train, y_test)

    plot_actual_vs_predicted(test_df, y_test, outcome["predictions"], outcome["best_model_name"])
    plot_feature_importance(outcome["models"]["RandomForest"], FEATURE_COLUMNS)
    plot_model_comparison(outcome["results"])

    save_model(outcome["best_model"], outcome["scaler"])

    forecast_df = forecast_future_aqi(outcome["best_model"], outcome["scaler"], processed,
                                       steps=args.forecast_steps)
    plot_forecast(processed, forecast_df)

    print("\n" + "=" * 64)
    print("MODEL EVALUATION RESULTS")
    print("=" * 64)
    for name, metrics in outcome["results"].items():
        print(f"{name:>18}: MAE={metrics['MAE']:<8} RMSE={metrics['RMSE']:<8} R2={metrics['R2']}")
    print("=" * 64)
    print(f"Best model: {outcome['best_model_name']}")
    print(f"\nNext {args.forecast_steps} predicted AQI readings:")
    print(forecast_df.to_string(index=False))
    print(f"\nAll plots and the trained model were saved to: {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
