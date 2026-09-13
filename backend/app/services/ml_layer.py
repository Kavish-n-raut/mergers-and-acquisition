from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, mean_squared_error
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

MODEL_DIR = Path(__file__).resolve().parents[2] / "runtime_artifacts" / "ml"
MODEL_DIR.mkdir(parents=True, exist_ok=True)


class MLError(ValueError):
    pass


def _safe_float(value: Any) -> float:
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def build_feature_frame(financials_a: pd.DataFrame, financials_b: pd.DataFrame, market_context: dict[str, Any] | None = None) -> pd.DataFrame:
    if financials_a.empty or financials_b.empty:
        raise MLError("Both companies need at least one financial row to build ML features.")

    latest_a = financials_a.sort_values("Year").iloc[-1]
    latest_b = financials_b.sort_values("Year").iloc[-1]

    revenue_a = _safe_float(latest_a.get("Revenue"))
    revenue_b = _safe_float(latest_b.get("Revenue"))
    cogs_a = _safe_float(latest_a.get("COGS"))
    cogs_b = _safe_float(latest_b.get("COGS"))
    opex_a = _safe_float(latest_a.get("Operating_Expenses"))
    opex_b = _safe_float(latest_b.get("Operating_Expenses"))

    revenue_growth_a = _safe_float(financials_a["Revenue"].pct_change().dropna().mean())
    revenue_growth_b = _safe_float(financials_b["Revenue"].pct_change().dropna().mean())
    margin_a = 0.0 if revenue_a == 0 else (revenue_a - cogs_a - opex_a) / revenue_a
    margin_b = 0.0 if revenue_b == 0 else (revenue_b - cogs_b - opex_b) / revenue_b

    features = {
        "revenue_a": revenue_a,
        "revenue_b": revenue_b,
        "margin_a": margin_a,
        "margin_b": margin_b,
        "growth_a": revenue_growth_a,
        "growth_b": revenue_growth_b,
        "size_ratio": revenue_b / revenue_a if revenue_a else 0.0,
        "margin_gap": margin_b - margin_a,
        "combined_revenue": revenue_a + revenue_b,
        "market_context_signal": 0.0,
    }

    if market_context:
        features["market_context_signal"] = float(
            sum(1 for item in market_context.get("filings_signal", []) if item) + sum(1 for item in market_context.get("acquisition_signal", []) if item)
        )

    return pd.DataFrame([features])


def train_models(training_frame: pd.DataFrame, labels: pd.Series) -> dict[str, Any]:
    X = training_frame.copy()
    y_success = labels["success"].astype(int)
    y_synergy = labels["synergy"].astype(float)
    y_risk = labels["risk"].astype(int)

    success_model = Pipeline([
        ("scaler", StandardScaler()),
        ("clf", LogisticRegression(max_iter=2000, random_state=42)),
    ])
    success_model.fit(X, y_success)

    risk_model = RandomForestClassifier(n_estimators=120, random_state=42)
    risk_model.fit(X, y_risk)

    synergy_model = RandomForestRegressor(n_estimators=150, random_state=42)
    synergy_model.fit(X, y_synergy)

    report = classification_report(y_success, success_model.predict(X), output_dict=True, zero_division=0)
    mse = mean_squared_error(y_synergy, synergy_model.predict(X))

    return {
        "success_model": success_model,
        "risk_model": risk_model,
        "synergy_model": synergy_model,
        "metrics": {
            "success_accuracy": float(report.get("accuracy", 0.0)),
            "synergy_mse": float(mse),
        },
    }


def save_models(models: dict[str, Any]) -> None:
    for name, model in models.items():
        if name in {"success_model", "risk_model", "synergy_model"}:
            joblib.dump(model, MODEL_DIR / f"{name}.joblib")
    if "metrics" in models:
        with (MODEL_DIR / "training_metrics.json").open("w", encoding="utf-8") as handle:
            json.dump(models["metrics"], handle, indent=2)


def load_models() -> dict[str, Any]:
    models: dict[str, Any] = {}
    for name in ["success_model", "risk_model", "synergy_model"]:
        path = MODEL_DIR / f"{name}.joblib"
        if path.exists():
            models[name] = joblib.load(path)
    metrics_path = MODEL_DIR / "training_metrics.json"
    if metrics_path.exists():
        with metrics_path.open("r", encoding="utf-8") as handle:
            models["metrics"] = json.load(handle)
    return models


def build_demo_training_data() -> tuple[pd.DataFrame, pd.Series]:
    rows = []
    scenarios = [
        (100, 80, 0.18, 0.22, 0.12, 0.15, 0.8, 1),
        (90, 110, 0.16, 0.19, 0.08, 0.1, 1.22, 2),
        (140, 160, 0.21, 0.24, 0.16, 0.17, 1.14, 3),
        (70, 90, 0.11, 0.14, 0.04, 0.06, 1.29, 0),
        (210, 120, 0.23, 0.2, 0.19, 0.12, 0.57, 2),
        (80, 75, 0.12, 0.13, 0.07, 0.05, 0.94, 1),
        (130, 200, 0.20, 0.18, 0.10, 0.09, 1.54, 1),
        (180, 170, 0.24, 0.25, 0.15, 0.16, 0.94, 3),
        (95, 85, 0.15, 0.17, 0.06, 0.08, 0.89, 2),
        (220, 240, 0.22, 0.20, 0.14, 0.12, 1.09, 0),
        (60, 140, 0.10, 0.19, 0.03, 0.11, 2.33, 0),
        (170, 160, 0.23, 0.24, 0.13, 0.14, 0.94, 3),
        (110, 190, 0.17, 0.18, 0.08, 0.10, 1.73, 1),
        (240, 150, 0.25, 0.16, 0.18, 0.07, 0.63, 2),
        (75, 95, 0.12, 0.16, 0.05, 0.09, 1.27, 2),
        (250, 300, 0.26, 0.27, 0.20, 0.21, 1.20, 3),
        (40, 70, 0.08, 0.11, 0.01, 0.03, 1.75, 0),
        (150, 310, 0.19, 0.21, 0.11, 0.13, 2.07, 1),
        (300, 120, 0.28, 0.15, 0.22, 0.06, 0.40, 2),
        (85, 160, 0.14, 0.20, 0.07, 0.12, 1.88, 1),
        (210, 260, 0.24, 0.23, 0.16, 0.15, 1.24, 2),
        (120, 135, 0.18, 0.18, 0.09, 0.09, 1.12, 2),
        (320, 180, 0.27, 0.17, 0.19, 0.08, 0.56, 3),
        (55, 90, 0.09, 0.12, 0.02, 0.04, 1.64, 0),
        (145, 225, 0.20, 0.22, 0.10, 0.14, 1.55, 2),
    ]

    for revenue_a, revenue_b, margin_a, margin_b, growth_a, growth_b, size_ratio, market_context_signal in scenarios:
        success = 1 if (margin_b - margin_a) > 0.01 and size_ratio < 1.3 and market_context_signal >= 1 else 0
        risk = 1 if (size_ratio > 1.2 and market_context_signal < 2) or (growth_a < 0.05 and margin_a < 0.14) else 0
        synergy = 1_500_000 + (market_context_signal * 250_000) + ((margin_b - margin_a) * 5_000_000) + (abs(growth_a - growth_b) * 1_500_000)
        rows.append({
            "revenue_a": revenue_a,
            "revenue_b": revenue_b,
            "margin_a": margin_a,
            "margin_b": margin_b,
            "growth_a": growth_a,
            "growth_b": growth_b,
            "size_ratio": size_ratio,
            "margin_gap": margin_b - margin_a,
            "combined_revenue": revenue_a + revenue_b,
            "market_context_signal": market_context_signal,
            "success": success,
            "risk": risk,
            "synergy": synergy,
        })

    frame = pd.DataFrame(rows)
    labels = frame[["success", "risk", "synergy"]]
    features = frame.drop(columns=["success", "risk", "synergy"])
    return features, labels


def ensure_models_exist() -> dict[str, Any]:
    models = load_models()
    if models and "metrics" in models:
        return models
    training_frame, labels = build_demo_training_data()
    trained = train_models(training_frame, labels)
    save_models(trained)
    return trained


def predict_deal_intelligence(financials_a: pd.DataFrame, financials_b: pd.DataFrame, market_context: dict[str, Any] | None = None) -> dict[str, Any]:
    models = ensure_models_exist()
    features = build_feature_frame(financials_a, financials_b, market_context)
    success_prob = float(models["success_model"].predict_proba(features)[0, 1])
    success_label = int(success_prob >= 0.6)
    risk_label = int(models["risk_model"].predict(features)[0])
    synergy_forecast = float(models["synergy_model"].predict(features)[0])

    return {
        "deal_success_probability": round(success_prob, 3),
        "deal_success_label": "Likely Success" if success_label else "High Risk",
        "risk_classification": "High" if risk_label else "Low",
        "synergy_forecast": round(synergy_forecast, 2),
        "features": features.to_dict(orient="records")[0],
    }
