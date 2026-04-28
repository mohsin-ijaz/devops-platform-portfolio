"""
LSTM Autoencoder for temporal anomaly detection.
Learns to reconstruct normal 3-hour patterns. At inference, high reconstruction
error means the model couldn't explain the pattern from what it learned — that's the anomaly.

Better than IF for things like gradual drift and correlated metric movements
(e.g. memory climbing for 2 hours before an OOM). Slower to train and predict
but the temporal context is worth it.
"""

import logging
import os
from pathlib import Path

import numpy as np
import pandas as pd

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")  # Suppress TF build warnings

import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers, Model
from tensorflow.keras.callbacks import (
    EarlyStopping, ModelCheckpoint, ReduceLROnPlateau
)

log = logging.getLogger(__name__)


class LSTMAutoencoder:

    def __init__(self, config: dict):
        self.cfg = config
        self.model: Model | None = None
        self.feature_cols: list[str] = []
        self.sequence_length: int = config.get("sequence_length", 36)
        self.threshold: float = 0.0
        self.threshold_percentile: float = 95.0
    def build_model(self, n_features: int) -> Model:
        """Encoder-bottleneck-decoder. Input and output shape are identical — the reconstruction diff is the signal."""
        seq_len = self.sequence_length
        encoding_dim = self.cfg.get("encoding_dim", 32)
        lstm_units = self.cfg.get("lstm_units", [128, 64])
        dropout = self.cfg.get("dropout", 0.2)
        inputs = keras.Input(shape=(seq_len, n_features), name="input")

        # First LSTM layer — return sequences for stacking
        x = layers.LSTM(lstm_units[0], return_sequences=True, name="enc_lstm_1")(inputs)
        x = layers.Dropout(dropout)(x)

        # Second LSTM layer — returns only last hidden state (bottleneck entry)
        x = layers.LSTM(lstm_units[1], return_sequences=False, name="enc_lstm_2")(x)
        x = layers.Dropout(dropout)(x)

        # Dense bottleneck — compressed representation
        encoded = layers.Dense(encoding_dim, activation="relu", name="bottleneck")(x)
        # RepeatVector restores the time dimension from the bottleneck
        x = layers.RepeatVector(seq_len, name="repeat")(encoded)

        x = layers.LSTM(lstm_units[1], return_sequences=True, name="dec_lstm_1")(x)
        x = layers.Dropout(dropout)(x)

        x = layers.LSTM(lstm_units[0], return_sequences=True, name="dec_lstm_2")(x)
        x = layers.Dropout(dropout)(x)

        # Reconstruct all features at each timestep
        outputs = layers.TimeDistributed(
            layers.Dense(n_features, activation="linear"),
            name="reconstruction"
        )(x)

        model = Model(inputs, outputs, name="lstm_autoencoder")
        return model
    def create_sequences(
        self,
        df: pd.DataFrame,
        feature_cols: list[str],
        step: int = 1,
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        Slice the flat matrix into overlapping (seq_len, n_features) windows.
        Grouped per entity so we don't create sequences that span different services.
        """
        seq_len = self.sequence_length
        all_X = []
        all_ts = []

        entity_cols = [c for c in df.columns
                       if c in ["namespace", "pod", "destination_service_name"]
                       and c not in feature_cols]

        if entity_cols:
            groups = df.groupby(entity_cols)
        else:
            groups = [("all", df)]

        for _, group in groups:
            group = group.sort_values("timestamp")
            values = group[feature_cols].values
            timestamps = group["timestamp"].values if "timestamp" in group.columns else None

            n = len(values)
            if n < seq_len:
                continue

            for i in range(0, n - seq_len + 1, step):
                all_X.append(values[i:i + seq_len])
                if timestamps is not None:
                    all_ts.append(timestamps[i + seq_len - 1])

        return np.array(all_X, dtype=np.float32), np.array(all_ts)
    def train(
        self,
        df: pd.DataFrame,
        feature_cols: list[str],
        validation_split: float = 0.15,
        checkpoint_dir: Path = None,
    ) -> dict:
        """Train the autoencoder to reconstruct normal patterns. Threshold is set from the p95 training error."""
        self.feature_cols = feature_cols
        n_features = len(feature_cols)

        log.info(f"Building LSTM Autoencoder: seq_len={self.sequence_length}, features={n_features}")
        self.model = self.build_model(n_features)

        lr = self.cfg.get("learning_rate", 0.001)
        self.model.compile(
            optimizer=keras.optimizers.Adam(learning_rate=lr),
            loss="mse",
            metrics=["mae"],
        )
        self.model.summary(print_fn=log.info)

        log.info("Creating sequences...")
        X, _ = self.create_sequences(df, feature_cols, step=3)
        log.info(f"  Sequence shape: {X.shape}")

        if len(X) < 100:
            raise ValueError(f"Not enough sequences ({len(X)}) — need at least 100")


        idx = np.random.permutation(len(X))
        X = X[idx]

        callbacks = [
            EarlyStopping(
                monitor="val_loss",
                patience=self.cfg.get("patience", 10),
                restore_best_weights=True,
                verbose=1,
            ),
            ReduceLROnPlateau(
                monitor="val_loss",
                factor=0.5,
                patience=5,
                min_lr=1e-6,
                verbose=1,
            ),
        ]

        if checkpoint_dir:
            checkpoint_dir.mkdir(parents=True, exist_ok=True)
            callbacks.append(ModelCheckpoint(
                filepath=str(checkpoint_dir / "lstm_ae_best.keras"),
                monitor="val_loss",
                save_best_only=True,
                verbose=1,
            ))

        history = self.model.fit(
            X, X,  # autoencoder: target is the input itself
            epochs=self.cfg.get("epochs", 50),
            batch_size=self.cfg.get("batch_size", 128),
            validation_split=validation_split,
            callbacks=callbacks,
            shuffle=True,
            verbose=1,
        )

        # set threshold from training errors — anything above p95 we flag
        train_errors = self._compute_reconstruction_errors(X)
        self.threshold = float(np.percentile(train_errors, self.threshold_percentile))
        log.info(f"  Anomaly threshold (p{self.threshold_percentile:.0f}): {self.threshold:.6f}")

        return {
            "n_sequences": len(X),
            "n_features": n_features,
            "final_loss": float(history.history["loss"][-1]),
            "final_val_loss": float(history.history["val_loss"][-1]),
            "epochs_trained": len(history.history["loss"]),
            "threshold": self.threshold,
        }
    def predict(self, df: pd.DataFrame) -> pd.DataFrame:
        """Score new data. Returns per-timestamp reconstruction error and anomaly flag."""
        if self.model is None:
            raise RuntimeError("Model not trained. Call train() first.")

        X, timestamps = self.create_sequences(df, self.feature_cols, step=1)
        if len(X) == 0:
            return pd.DataFrame(columns=["timestamp", "lstm_score", "lstm_anomaly"])

        errors = self._compute_reconstruction_errors(X)
        normalised = self._normalise_scores(errors)

        result = pd.DataFrame({
            "timestamp": timestamps,
            "lstm_score_raw": errors,
            "lstm_score": normalised,
            "lstm_anomaly": errors > self.threshold,
        })

        # Per-feature reconstruction error — useful for explaining which metric is anomalous
        X_pred = self.model.predict(X, verbose=0)
        per_feature_error = np.mean(np.abs(X - X_pred), axis=1)  # (n_seq, n_features)
        for i, feat in enumerate(self.feature_cols[:10]):  # Top 10 features only
            result[f"lstm_err_{feat}"] = per_feature_error[:, i]

        return result

    def _compute_reconstruction_errors(self, X: np.ndarray) -> np.ndarray:
        """Mean absolute error across the whole sequence — higher = harder to reconstruct = more anomalous."""
        X_pred = self.model.predict(X, verbose=0, batch_size=256)
        errors = np.mean(np.abs(X - X_pred), axis=(1, 2))
        return errors

    def _normalise_scores(self, errors: np.ndarray) -> np.ndarray:
        e_min, e_max = errors.min(), errors.max()
        if e_max == e_min:
            return np.zeros_like(errors)
        return (errors - e_min) / (e_max - e_min)
    def save(self, model_dir: Path):
        model_dir.mkdir(parents=True, exist_ok=True)
        self.model.save(model_dir / "lstm_ae.keras")
        np.save(model_dir / "threshold.npy", np.array([self.threshold]))
        import json
        (model_dir / "feature_cols.json").write_text(json.dumps(self.feature_cols))
        log.info(f"LSTM Autoencoder saved → {model_dir}")

    @classmethod
    def load(cls, model_dir: Path, config: dict = None) -> "LSTMAutoencoder":
        import json
        detector = cls(config or {})
        detector.model = keras.models.load_model(model_dir / "lstm_ae.keras")
        detector.threshold = float(np.load(model_dir / "threshold.npy")[0])
        detector.feature_cols = json.loads((model_dir / "feature_cols.json").read_text())
        return detector
