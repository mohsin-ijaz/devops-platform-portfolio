"""
Builds the feature matrix for model training from raw metric time series.
Rolling stats, lag features, derived ratios, temporal encoding — the works.
RobustScaler at the end because infra metrics are always skewed.
"""

import logging
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import RobustScaler

log = logging.getLogger(__name__)


class FeatureEngineer:

    def __init__(self, config_path: str = "config/features.yaml"):
        with open(config_path) as f:
            cfg = yaml.safe_load(f)
        self.cfg = cfg["engineering"]
        self.windows = self.cfg["rolling_windows"]       # [5, 15, 60, 360] minutes
        self.step_minutes = 5                             # matches extraction step
    def add_rolling_features(self, df: pd.DataFrame, metric_cols: list[str]) -> pd.DataFrame:
        """Rolling mean/std/min/max at each configured window size."""
        df = df.sort_values("timestamp")
        new_cols = {}

        for col in metric_cols:
            if col not in df.columns:
                continue
            series = df[col]

            for window_min in self.windows:
    
                n = max(1, window_min // self.step_minutes)
                prefix = f"{col}_r{window_min}m"

                if "mean" in self.cfg["per_window"]:
                    new_cols[f"{prefix}_mean"] = series.rolling(n, min_periods=1).mean()
                if "std" in self.cfg["per_window"]:
                    new_cols[f"{prefix}_std"] = series.rolling(n, min_periods=1).std().fillna(0)
                if "max" in self.cfg["per_window"]:
                    new_cols[f"{prefix}_max"] = series.rolling(n, min_periods=1).max()
                if "min" in self.cfg["per_window"]:
                    new_cols[f"{prefix}_min"] = series.rolling(n, min_periods=1).min()

        return pd.concat([df, pd.DataFrame(new_cols, index=df.index)], axis=1)

    def add_lag_features(self, df: pd.DataFrame, metric_cols: list[str]) -> pd.DataFrame:
        """Lag features so the model sees recent history, not just current value."""
        new_cols = {}
        for col in metric_cols:
            if col not in df.columns:
                continue
            for lag in [1, 6, 12]:
                new_cols[f"{col}_lag{lag}"] = df[col].shift(lag)
        return pd.concat([df, pd.DataFrame(new_cols, index=df.index)], axis=1)

    def add_diff_features(self, df: pd.DataFrame, metric_cols: list[str]) -> pd.DataFrame:
        """First-order diffs — helps catch things like restart acceleration."""
        new_cols = {}
        for col in metric_cols:
            if col not in df.columns:
                continue
            new_cols[f"{col}_diff1"] = df[col].diff(1)
            new_cols[f"{col}_diff6"] = df[col].diff(6)   # 30-min change
        return pd.concat([df, pd.DataFrame(new_cols, index=df.index)], axis=1)

    def add_derived_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Derived features — ratios and composites that tend to be better signals than raw values."""
        eps = 1e-9

        # error spike: ratio of current rate to its rolling average, anything >> 1 is worth flagging
        if "error_rate" in df.columns and "error_rate_r60m_mean" in df.columns:
            df["error_spike_ratio"] = (
                df["error_rate"] / (df["error_rate_r60m_mean"] + eps)
            ).clip(0, 100)

        # tail ratio — high p99/p50 means something is holding a small % of requests for way too long
        if "p99_latency_ms" in df.columns and "p50_latency_ms" in df.columns:
            df["latency_tail_ratio"] = (
                df["p99_latency_ms"] / (df["p50_latency_ms"] + eps)
            ).clip(0, 50)

        # rough z-score for CPU — catches sustained elevation better than raw usage
        if "cpu_usage" in df.columns and "cpu_usage_r60m_std" in df.columns:
            df["cpu_zscore"] = (
                (df["cpu_usage"] - df.get("cpu_usage_r60m_mean", 0))
                / (df["cpu_usage_r60m_std"] + eps)
            ).clip(-10, 10)

        # how close are we to the highest memory we've seen in the last 6 hours
        if "memory_usage_bytes" in df.columns and "memory_usage_bytes_r360m_max" in df.columns:
            df["memory_pressure"] = (
                df["memory_usage_bytes"] / (df["memory_usage_bytes_r360m_max"] + eps)
            ).clip(0, 1)

        # restart velocity — if this is climbing we usually want to know before the pod crashes
        if "pod_restarts" in df.columns:
            df["restart_velocity"] = df["pod_restarts"].diff(6).fillna(0).clip(0, 100)

        # week-over-week traffic ratio — 2016 steps = 7 days at 5min resolution
        if "request_rate" in df.columns:
            df["request_rate_wow"] = df["request_rate"].shift(2016)  # week-over-week
            df["traffic_wow_ratio"] = (
                df["request_rate"] / (df["request_rate_wow"] + eps)
            ).clip(0, 20)

        return df

    def add_temporal_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Temporal features. Sine/cosine encoding avoids the midnight discontinuity problem."""
        ts = pd.to_datetime(df["timestamp"])
        df["hour_of_day"] = ts.dt.hour
        df["day_of_week"] = ts.dt.dayofweek           # 0=Monday, 6=Sunday
        df["is_business_hours"] = (
            (ts.dt.hour >= 9) & (ts.dt.hour < 18) &
            (ts.dt.dayofweek < 5)
        ).astype(int)
        df["is_weekend"] = (ts.dt.dayofweek >= 5).astype(int)

        # sin/cos so hour 23 and hour 0 are close together, not far apart
        df["hour_sin"] = np.sin(2 * np.pi * ts.dt.hour / 24)
        df["hour_cos"] = np.cos(2 * np.pi * ts.dt.hour / 24)
        df["dow_sin"] = np.sin(2 * np.pi * ts.dt.dayofweek / 7)
        df["dow_cos"] = np.cos(2 * np.pi * ts.dt.dayofweek / 7)

        return df
    def clean(self, df: pd.DataFrame, feature_cols: list[str]) -> pd.DataFrame:
        """Nuke Inf/-Inf, impute NaNs with median. Called before scaling."""
        df = df.replace([np.inf, -np.inf], np.nan)


        imputer = SimpleImputer(strategy="median")
        df[feature_cols] = imputer.fit_transform(df[feature_cols])

        return df

    def fit_scaler(self, df: pd.DataFrame, feature_cols: list[str]) -> RobustScaler:
        scaler = RobustScaler(quantile_range=(5, 95))
        scaler.fit(df[feature_cols])
        return scaler
    def run(
        self,
        input_path: Path,
        output_path: Path,
        entity_cols: list[str] = None,
    ) -> tuple[pd.DataFrame, list[str], RobustScaler]:
        """Run everything and return (df, feature_cols, scaler). Scaler is returned so we can reuse it at inference."""
        log.info(f"Loading feature matrix from {input_path}")
        df = pd.read_parquet(input_path)
        log.info(f"  Shape: {df.shape}")

        meta_cols = ["timestamp"] + (entity_cols or [])
        raw_metric_cols = [c for c in df.columns if c not in meta_cols]

        log.info(f"Engineering features from {len(raw_metric_cols)} raw metrics...")

        # group by entity so rolling windows stay within one service's data
        entity_keys = entity_cols or []
        if entity_keys:
            groups = []
            for _, group in df.groupby(entity_keys):
                group = group.copy().reset_index(drop=True)
                group = self.add_rolling_features(group, raw_metric_cols)
                group = self.add_lag_features(group, raw_metric_cols)
                group = self.add_diff_features(group, raw_metric_cols)
                group = self.add_derived_features(group)
                group = self.add_temporal_features(group)
                groups.append(group)
            df = pd.concat(groups, ignore_index=True)
        else:
            df = self.add_rolling_features(df, raw_metric_cols)
            df = self.add_lag_features(df, raw_metric_cols)
            df = self.add_diff_features(df, raw_metric_cols)
            df = self.add_derived_features(df)
            df = self.add_temporal_features(df)

        feature_cols = [c for c in df.columns if c not in meta_cols]
        log.info(f"  Total features after engineering: {len(feature_cols)}")

        # drop rows where too much is still NaN (start of each entity's series)
        df = df.dropna(thresh=int(len(feature_cols) * 0.7))

        # Clean and scale
        df = self.clean(df, feature_cols)
        scaler = self.fit_scaler(df, feature_cols)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(output_path, index=False, compression="snappy")
        log.info(f"  Engineered features → {output_path}")
        log.info(f"  Final shape: {df.shape}")

        return df, feature_cols, scaler
