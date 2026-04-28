"""
Combines IF and LSTM scores into a single anomaly signal.
IF is better at point anomalies (sudden spikes), LSTM is better at temporal patterns
(gradual drift, correlated changes). LSTM gets the higher weight by default — in
practice most production incidents look like drift, not spikes.
"""

import logging
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import yaml

from .isolation_forest import IsolationForestDetector
from .lstm_autoencoder import LSTMAutoencoder

log = logging.getLogger(__name__)


class AnomalyEnsemble:

    def __init__(self, config_path: str = "config/features.yaml"):
        with open(config_path) as f:
            cfg = yaml.safe_load(f)

        self.if_config = cfg["models"]["isolation_forest"]
        self.lstm_config = cfg["models"]["lstm_autoencoder"]
        self.ensemble_config = cfg["models"]["ensemble"]

        self.if_weight = self.ensemble_config["weights"]["isolation_forest"]
        self.lstm_weight = self.ensemble_config["weights"]["lstm_autoencoder"]
        self.alert_threshold = self.ensemble_config["alert_threshold"]

        self.iso_forest = IsolationForestDetector(self.if_config)
        self.lstm_ae = LSTMAutoencoder(self.lstm_config)
        self.scaler = None
        self.feature_cols: list[str] = []
    def train(
        self,
        df: pd.DataFrame,
        feature_cols: list[str],
        scaler,
        checkpoint_dir: Path = None,
        labels: Optional[pd.Series] = None,
    ) -> dict:
        """Train both models. Labels are optional — only used to tune the threshold if we have incident data."""
        self.feature_cols = feature_cols
        self.scaler = scaler

        log.info("=" * 60)
        log.info("Training Ensemble Anomaly Detector")
        log.info(f"  Samples:  {len(df):,}")
        log.info(f"  Features: {len(feature_cols)}")
        log.info(f"  Weights:  IF={self.if_weight}, LSTM={self.lstm_weight}")
        log.info("=" * 60)

        # Scale features
        df_scaled = df.copy()
        df_scaled[feature_cols] = self.scaler.transform(df[feature_cols])

        # Train Isolation Forest
        log.info("\n[1/2] Training Isolation Forest...")
        if_metrics = self.iso_forest.train(df_scaled, feature_cols, labels)
        log.info(f"  Score p95: {if_metrics['score_p95']:.4f}")
        if "roc_auc" in if_metrics:
            log.info(f"  ROC-AUC:   {if_metrics['roc_auc']:.4f}")

        # Train LSTM Autoencoder
        log.info("\n[2/2] Training LSTM Autoencoder...")
        lstm_ckpt = checkpoint_dir / "lstm" if checkpoint_dir else None
        lstm_metrics = self.lstm_ae.train(df_scaled, feature_cols,
                                          checkpoint_dir=lstm_ckpt)
        log.info(f"  Val Loss:  {lstm_metrics['final_val_loss']:.6f}")
        log.info(f"  Threshold: {lstm_metrics['threshold']:.6f}")

        log.info("\nTraining complete.")
        return {
            "isolation_forest": if_metrics,
            "lstm_autoencoder": lstm_metrics,
            "n_features": len(feature_cols),
            "alert_threshold": self.alert_threshold,
        }
    def predict(self, df: pd.DataFrame) -> pd.DataFrame:
        """Score a batch. Returns ensemble_score, is_anomaly, severity, and contributing features."""
        df_scaled = df.copy()
        df_scaled[self.feature_cols] = self.scaler.transform(df[self.feature_cols])


        if_result = self.iso_forest.predict(df_scaled)
        lstm_result = self.lstm_ae.predict(df_scaled)


        result = df[["timestamp"]].copy() if "timestamp" in df.columns else pd.DataFrame(index=df.index)

        result["if_score"] = if_result["if_score_normalised"].values
        result["lstm_score"] = self._align_lstm_scores(
            df, lstm_result, score_col="lstm_score"
        )
        result["lstm_score"] = result["lstm_score"].fillna(result["if_score"])


        result["ensemble_score"] = (
            self.if_weight * result["if_score"] +
            self.lstm_weight * result["lstm_score"]
        )

        result["is_anomaly"] = result["ensemble_score"] > self.alert_threshold
        result["severity"] = result["ensemble_score"].apply(self._score_to_severity)


        anomaly_mask = result["is_anomaly"]
        if anomaly_mask.any():
            contributions = self.iso_forest.get_feature_contributions(
                df_scaled[anomaly_mask], top_n=5
            )
            result.loc[anomaly_mask, "top_features"] = contributions.values
        result["top_features"] = result.get("top_features", "").fillna("")

        return result

    def _align_lstm_scores(
        self,
        df: pd.DataFrame,
        lstm_result: pd.DataFrame,
        score_col: str = "lstm_score",
    ) -> pd.Series:
        """LSTM scores land on sequence end-points — join back to the original df by timestamp."""
        if "timestamp" not in df.columns or "timestamp" not in lstm_result.columns:
            return pd.Series(0.0, index=df.index)

        score_map = lstm_result.set_index("timestamp")[score_col]
        return df["timestamp"].map(score_map).fillna(0.0)

    def _score_to_severity(self, score: float) -> str:
        if score >= 0.90:
            return "critical"
        elif score >= 0.80:
            return "high"
        elif score >= self.alert_threshold:
            return "medium"
        else:
            return "normal"
    def save(self, model_dir: Path):
        model_dir.mkdir(parents=True, exist_ok=True)

        import json, pickle
        self.iso_forest.save(model_dir / "isolation_forest.pkl")
        self.lstm_ae.save(model_dir / "lstm_autoencoder")
        pickle.dump(self.scaler, open(model_dir / "scaler.pkl", "wb"))
        (model_dir / "feature_cols.json").write_text(json.dumps(self.feature_cols))
        (model_dir / "config.json").write_text(json.dumps({
            "if_weight": self.if_weight,
            "lstm_weight": self.lstm_weight,
            "alert_threshold": self.alert_threshold,
        }))
        log.info(f"Ensemble saved → {model_dir}")

    @classmethod
    def load(cls, model_dir: Path, config_path: str = "config/features.yaml") -> "AnomalyEnsemble":
        import json, pickle
        ensemble = cls(config_path)
        ensemble.iso_forest = IsolationForestDetector.load(
            model_dir / "isolation_forest.pkl", ensemble.if_config
        )
        ensemble.lstm_ae = LSTMAutoencoder.load(
            model_dir / "lstm_autoencoder", ensemble.lstm_config
        )
        ensemble.scaler = pickle.load(open(model_dir / "scaler.pkl", "rb"))
        ensemble.feature_cols = json.loads((model_dir / "feature_cols.json").read_text())

        saved_cfg = json.loads((model_dir / "config.json").read_text())
        ensemble.if_weight = saved_cfg["if_weight"]
        ensemble.lstm_weight = saved_cfg["lstm_weight"]
        ensemble.alert_threshold = saved_cfg["alert_threshold"]

        log.info(f"Ensemble loaded from {model_dir}")
        return ensemble
