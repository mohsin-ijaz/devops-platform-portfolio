"""
FastAPI scoring service — wraps the ensemble and exposes it over HTTP.
Grafana calls this to enrich dashboards, Alertmanager can call it to add
anomaly context to alerts before they page someone.

POST /score         batch scoring
GET  /health        liveness
GET  /model/info    threshold + feature count
"""

import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

import numpy as np
import pandas as pd
import uvicorn
import yaml
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.gzip import GZipMiddleware
from pydantic import BaseModel, Field

# Prometheus metrics
from prometheus_client import Counter, Histogram, Gauge, make_asgi_app

sys.path.insert(0, str(Path(__file__).parent.parent))
from models.ensemble import AnomalyEnsemble

log = logging.getLogger(__name__)
SCORE_REQUESTS = Counter("anomaly_score_requests_total", "Total scoring requests")
ANOMALIES_DETECTED = Counter("anomaly_detections_total", "Total anomalies detected",
                             ["severity", "namespace"])
SCORE_LATENCY = Histogram("anomaly_score_duration_seconds", "Scoring latency",
                          buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 5.0])
MODEL_LOAD_TIME = Gauge("anomaly_model_load_seconds", "Time taken to load model")
CURRENT_THRESHOLD = Gauge("anomaly_alert_threshold", "Current alert threshold")
class TelemetryPoint(BaseModel):
    timestamp: str
    namespace: str
    service: str = ""
    pod: str = ""
    # all optional — missing values get imputed from the feature engineering scaler
    cpu_usage: float | None = None
    memory_usage_bytes: float | None = None
    request_rate: float | None = None
    error_rate: float | None = None
    p50_latency_ms: float | None = None
    p99_latency_ms: float | None = None
    pod_restarts: float | None = None

    class Config:
        extra = "allow"   # Accept any additional metric fields


class ScoreRequest(BaseModel):
    observations: list[TelemetryPoint] = Field(..., min_length=1, max_length=10000)
    explain: bool = False


class AnomalyResult(BaseModel):
    timestamp: str
    namespace: str
    service: str
    ensemble_score: float
    is_anomaly: bool
    severity: str
    if_score: float
    lstm_score: float
    top_features: list[str] = []


class ScoreResponse(BaseModel):
    results: list[AnomalyResult]
    n_anomalies: int
    processing_ms: float
    model_version: str
MODEL_DIR = Path(os.environ.get("MODEL_DIR", "models/latest"))
CONFIG_PATH = os.environ.get("CONFIG_PATH", "config/features.yaml")
ensemble: AnomalyEnsemble | None = None
model_metadata: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load the model at startup — LSTM can take ~60s, hence the long startup probe."""
    global ensemble, model_metadata
    log.info(f"Loading model from {MODEL_DIR}...")
    t0 = time.time()
    try:
        ensemble = AnomalyEnsemble.load(MODEL_DIR, CONFIG_PATH)
        load_time = time.time() - t0
        MODEL_LOAD_TIME.set(load_time)
        CURRENT_THRESHOLD.set(ensemble.alert_threshold)

        import json
        meta_path = MODEL_DIR / "training_metadata.json"
        if meta_path.exists():
            model_metadata = json.loads(meta_path.read_text())
        model_metadata["load_time_s"] = load_time

        log.info(f"Model loaded in {load_time:.2f}s")
        log.info(f"  Features: {len(ensemble.feature_cols)}")
        log.info(f"  Alert threshold: {ensemble.alert_threshold}")
    except Exception as e:
        log.error(f"Failed to load model: {e}")
        raise

    yield

    log.info("Shutting down scorer")


app = FastAPI(
    title="Infrastructure Anomaly Detection API",
    description="Real-time anomaly scoring using Isolation Forest + LSTM Autoencoder ensemble",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.mount("/metrics", make_asgi_app())
@app.get("/health")
async def health():
    if ensemble is None:
        raise HTTPException(503, "Model not loaded")
    return {"status": "ok", "model_loaded": True}


@app.get("/model/info")
async def model_info():
    return {
        "n_features": len(ensemble.feature_cols) if ensemble else 0,
        "alert_threshold": ensemble.alert_threshold if ensemble else None,
        "if_weight": ensemble.if_weight if ensemble else None,
        "lstm_weight": ensemble.lstm_weight if ensemble else None,
        **model_metadata,
    }


@app.post("/score", response_model=ScoreResponse)
async def score(request: ScoreRequest):
    if ensemble is None:
        raise HTTPException(503, "Model not loaded")

    SCORE_REQUESTS.inc()
    t0 = time.time()


    df = pd.DataFrame([obs.model_dump() for obs in request.observations])
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)


    with SCORE_LATENCY.time():
        try:
            result_df = ensemble.predict(df)
        except Exception as e:
            log.error(f"Scoring failed: {e}")
            raise HTTPException(500, f"Scoring error: {e}")


    results = []
    for i, row in result_df.iterrows():
        orig = request.observations[i] if i < len(request.observations) else request.observations[0]
        is_anomaly = bool(row.get("is_anomaly", False))
        severity = str(row.get("severity", "normal"))
        ns = getattr(orig, "namespace", "unknown")

        if is_anomaly:
            ANOMALIES_DETECTED.labels(severity=severity, namespace=ns).inc()

        top_features = row.get("top_features", "")
        if isinstance(top_features, str) and top_features:
            top_features = top_features.split(",")
        elif not isinstance(top_features, list):
            top_features = []

        results.append(AnomalyResult(
            timestamp=str(row.get("timestamp", orig.timestamp)),
            namespace=ns,
            service=getattr(orig, "service", ""),
            ensemble_score=float(row.get("ensemble_score", 0)),
            is_anomaly=is_anomaly,
            severity=severity,
            if_score=float(row.get("if_score", 0)),
            lstm_score=float(row.get("lstm_score", 0)),
            top_features=top_features,
        ))

    processing_ms = (time.time() - t0) * 1000
    n_anomalies = sum(1 for r in results if r.is_anomaly)

    return ScoreResponse(
        results=results,
        n_anomalies=n_anomalies,
        processing_ms=round(processing_ms, 2),
        model_version=model_metadata.get("trained_at", "unknown"),
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    uvicorn.run(
        "scorer:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8080)),
        workers=int(os.environ.get("WORKERS", 2)),
        log_level="info",
    )
