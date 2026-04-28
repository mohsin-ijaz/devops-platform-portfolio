"""
Runs the full training pipeline — extract, engineer, train, save.
Runs weekly as a CronJob so the model doesn't drift too far from current infra behaviour.

  python train.py --config config/features.yaml --output models/v1/
  python train.py --skip-extract   # reuse cached raw data, re-run features + train
  python train.py --start 2024-01-01 --end 2024-07-01
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("trainer")

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.extract_telemetry import TelemetryExtractor
from data.feature_engineering import FeatureEngineer
from models.ensemble import AnomalyEnsemble


def parse_args():
    p = argparse.ArgumentParser(description="Train anomaly detection ensemble")
    p.add_argument("--config", default="config/features.yaml")
    p.add_argument("--output", default="models/latest", help="Model output directory")
    p.add_argument("--data-dir", default="data", help="Raw data directory")
    p.add_argument("--start", help="Training start date YYYY-MM-DD")
    p.add_argument("--end", help="Training end date YYYY-MM-DD")
    p.add_argument("--skip-extract", action="store_true", help="Use cached raw data")
    p.add_argument("--skip-features", action="store_true", help="Use cached feature matrix")
    p.add_argument("--workers", type=int, default=4, help="Extraction parallelism")
    return p.parse_args()


def main():
    args = parse_args()
    config_path = args.config
    output_dir = Path(args.output)
    data_dir = Path(args.data_dir)

    now = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    end_ts = (
        datetime.fromisoformat(args.end).replace(tzinfo=timezone.utc)
        if args.end else now
    )
    start_ts = (
        datetime.fromisoformat(args.start).replace(tzinfo=timezone.utc)
        if args.start else end_ts - timedelta(days=180)
    )

    log.info("=" * 60)
    log.info("  Anomaly Detection Training Pipeline")
    log.info(f"  Training window: {start_ts.date()} → {end_ts.date()}")
    log.info(f"  Output: {output_dir}")
    log.info("=" * 60)

    raw_dir = data_dir / "raw"
    matrix_path = data_dir / "feature_matrix.parquet"
    engineered_path = data_dir / "features_engineered.parquet"

    if not args.skip_extract:
        log.info("\n[Step 1/3] Extracting telemetry from Prometheus/Mimir...")
        extractor = TelemetryExtractor(config_path)
        extractor.extract_all(raw_dir, start_ts, end_ts, workers=args.workers)
        extractor.build_feature_matrix(raw_dir, matrix_path)
    else:
        log.info("\n[Step 1/3] Skipping extraction — using cached data")
        if not matrix_path.exists():
            log.error(f"No cached data at {matrix_path}. Run without --skip-extract first.")
            sys.exit(1)

    if not args.skip_features:
        log.info("\n[Step 2/3] Engineering features...")
        engineer = FeatureEngineer(config_path)
        df, feature_cols, scaler = engineer.run(
            input_path=matrix_path,
            output_path=engineered_path,
            entity_cols=["namespace"],
        )
    else:
        log.info("\n[Step 2/3] Skipping feature engineering — using cached features")
        import pandas as pd, pickle
        df = pd.read_parquet(engineered_path)
        feature_cols = [c for c in df.columns if c not in ["timestamp", "namespace",
                                                             "pod", "destination_service_name"]]
        engineer = FeatureEngineer(config_path)
        scaler = engineer.fit_scaler(df, feature_cols)

    log.info(f"  Features ready: {len(df):,} samples × {len(feature_cols)} features")

    log.info("\n[Step 3/3] Training ensemble...")
    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_dir = output_dir / "checkpoints"

    ensemble = AnomalyEnsemble(config_path)
    metrics = ensemble.train(
        df=df,
        feature_cols=feature_cols,
        scaler=scaler,
        checkpoint_dir=checkpoint_dir,
    )
    ensemble.save(output_dir)


    training_meta = {
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "training_start": start_ts.isoformat(),
        "training_end": end_ts.isoformat(),
        "n_samples": int(len(df)),
        "n_features": int(len(feature_cols)),
        "metrics": metrics,
    }
    (output_dir / "training_metadata.json").write_text(
        json.dumps(training_meta, indent=2)
    )

    log.info("\n" + "=" * 60)
    log.info("  Training Complete")
    log.info(f"  Model saved: {output_dir}")
    log.info(f"  IF score p99:    {metrics['isolation_forest']['score_p99']:.4f}")
    log.info(f"  LSTM val loss:   {metrics['lstm_autoencoder']['final_val_loss']:.6f}")
    log.info(f"  Alert threshold: {metrics['alert_threshold']}")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
