"""
Isolation Forest for multivariate point anomaly detection.
Works well here because infra metrics are never Gaussian, we have lots of features,
and it's fast enough for near-real-time scoring. The contamination param is roughly
tuned to our historical incident rate (~2% of 5-minute windows are genuinely anomalous).
"""

import logging
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.inspection import permutation_importance
from sklearn.metrics import average_precision_score, roc_auc_score

log = logging.getLogger(__name__)


class IsolationForestDetector:

    def __init__(self, config: dict):
        self.cfg = config
        self.model: IsolationForest | None = None
        self.feature_cols: list[str] = []
        self.threshold: float = -0.1   # Default, tuned during training
        self.feature_importance: pd.Series | None = None

    def build(self) -> IsolationForest:
        return IsolationForest(
            n_estimators=self.cfg.get("n_estimators", 200),
            contamination=self.cfg.get("contamination", 0.02),
            max_features=self.cfg.get("max_features", 0.8),
            max_samples=self.cfg.get("max_samples", "auto"),
            random_state=self.cfg.get("random_state", 42),
            n_jobs=self.cfg.get("n_jobs", -1),
            warm_start=False,
        )

    def train(
        self,
        df: pd.DataFrame,
        feature_cols: list[str],
        labels: pd.Series = None,
    ) -> dict:
        """Train on the feature matrix. Labels are optional — used for threshold tuning if we have them."""
        self.feature_cols = feature_cols
        X = df[feature_cols].values

        log.info(f"Training Isolation Forest on {X.shape[0]:,} samples × {X.shape[1]} features")
        self.model = self.build()
        self.model.fit(X)

        # IF returns lower scores for anomalies — negate so higher = worse
        raw_scores = self.model.score_samples(X)
        self.scores_train = -raw_scores

        metrics = self._compute_metrics(labels)

        if labels is not None:
            self.threshold = self._tune_threshold(self.scores_train, labels)
        else:
            contamination = self.cfg.get("contamination", 0.02)
            self.threshold = np.percentile(self.scores_train, (1 - contamination) * 100)
            log.info(f"  Unsupervised threshold: {self.threshold:.4f} "
                     f"(top {contamination*100:.0f}% flagged as anomalies)")

        return metrics

    def predict(self, df: pd.DataFrame) -> pd.DataFrame:
        """Score rows and return if_score, if_anomaly, if_score_normalised."""
        if self.model is None:
            raise RuntimeError("Model not trained. Call train() first.")

        X = df[self.feature_cols].values
        raw_scores = self.model.score_samples(X)
        scores = -raw_scores

        result = df[["timestamp"]].copy() if "timestamp" in df.columns else pd.DataFrame(index=df.index)
        result["if_score"] = scores
        result["if_anomaly"] = scores > self.threshold
        result["if_score_normalised"] = self._normalise_scores(scores)

        return result

    def get_feature_contributions(
        self,
        df: pd.DataFrame,
        top_n: int = 5,
    ) -> pd.DataFrame:
        """
        Which features are driving the anomaly score for each flagged sample.
        Perturbation approach — replace each feature with its median, see how much the score drops.
        It's approximate but fast enough to run inline.
        """
        X = df[self.feature_cols].values
        medians = np.median(X, axis=0)
        base_scores = -self.model.score_samples(X)
        contributions = []

        for i in range(len(X)):
            if base_scores[i] <= self.threshold:
                contributions.append([])
                continue

            feat_impact = {}
            x_orig = X[i].copy()
            for j, feat_name in enumerate(self.feature_cols):
                x_perturbed = x_orig.copy()
                x_perturbed[j] = medians[j]
                score_perturbed = -self.model.score_samples([x_perturbed])[0]
                feat_impact[feat_name] = base_scores[i] - score_perturbed

            # Sort: biggest score drop when feature removed = most responsible
            top_feats = sorted(feat_impact.items(), key=lambda x: x[1], reverse=True)[:top_n]
            contributions.append([f"{name}({delta:+.3f})" for name, delta in top_feats])

        return pd.Series(contributions, index=df.index, name="if_top_features")

    def _tune_threshold(self, scores: np.ndarray, labels: pd.Series) -> float:
        """Sweep percentiles to find the threshold with best F1. Requires labelled incidents."""
        from sklearn.metrics import f1_score
        best_threshold, best_f1 = 0.0, 0.0
        for pct in np.arange(90, 100, 0.5):
            t = np.percentile(scores, pct)
            preds = (scores > t).astype(int)
            f1 = f1_score(labels, preds, zero_division=0)
            if f1 > best_f1:
                best_f1, best_threshold = f1, t
        log.info(f"  Tuned threshold: {best_threshold:.4f} (F1={best_f1:.3f})")
        return best_threshold

    def _normalise_scores(self, scores: np.ndarray) -> np.ndarray:
        """Normalise to [0,1] so IF and LSTM scores are on the same scale."""
        s_min, s_max = scores.min(), scores.max()
        if s_max == s_min:
            return np.zeros_like(scores)
        return (scores - s_min) / (s_max - s_min)

    def _compute_metrics(self, labels: pd.Series = None) -> dict:
        metrics = {
            "n_samples": len(self.scores_train),
            "score_mean": float(np.mean(self.scores_train)),
            "score_std": float(np.std(self.scores_train)),
            "score_p95": float(np.percentile(self.scores_train, 95)),
            "score_p99": float(np.percentile(self.scores_train, 99)),
        }
        if labels is not None:
            try:
                metrics["roc_auc"] = float(roc_auc_score(labels, self.scores_train))
                metrics["avg_precision"] = float(average_precision_score(labels, self.scores_train))
            except Exception:
                pass
        return metrics

    def save(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump({
                "model": self.model,
                "feature_cols": self.feature_cols,
                "threshold": self.threshold,
            }, f)
        log.info(f"Isolation Forest saved → {path}")

    @classmethod
    def load(cls, path: Path, config: dict = None) -> "IsolationForestDetector":
        with open(path, "rb") as f:
            state = pickle.load(f)
        detector = cls(config or {})
        detector.model = state["model"]
        detector.feature_cols = state["feature_cols"]
        detector.threshold = state["threshold"]
        return detector
