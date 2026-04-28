"""
Pulls 6 months of metrics from Prometheus/Mimir for anomaly detection training.
Extracts in weekly chunks because Prometheus chokes on large range queries,
writes straight to parquet so we don't OOM on big clusters.

  python extract_telemetry.py --config config/features.yaml --output data/raw/
  python extract_telemetry.py --start 2024-01-01 --end 2024-07-01
"""

import argparse
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests
import yaml
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("telemetry_extractor")
def make_session(token: str = None) -> requests.Session:
    """Session with retry — mostly needed for the 429s we get on large extractions."""
    session = requests.Session()
    retry = Retry(
        total=5,
        backoff_factor=2,
        status_forcelist=[429, 500, 502, 503, 504],
        respect_retry_after_header=True,
    )
    session.mount("http://", HTTPAdapter(max_retries=retry))
    session.mount("https://", HTTPAdapter(max_retries=retry))
    if token:
        session.headers["Authorization"] = f"Bearer {token}"
    session.headers["X-Scope-OrgID"] = os.environ.get("MIMIR_TENANT_ID", "default")
    return session
def query_range_chunk(
    session: requests.Session,
    prometheus_url: str,
    query: str,
    start: datetime,
    end: datetime,
    step: str,
    timeout: int = 120,
) -> pd.DataFrame:
    """Single range_query call. Raises on non-success status."""
    resp = session.get(
        f"{prometheus_url}/api/v1/query_range",
        params={
            "query": query,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "step": step,
        },
        timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json()

    if data["status"] != "success":
        raise ValueError(f"Prometheus error: {data.get('error', 'unknown')}")

    rows = []
    for series in data["data"]["result"]:
        labels = series["metric"]
        for ts, val in series["values"]:
            row = {
                "timestamp": datetime.fromtimestamp(float(ts), tz=timezone.utc),
                "value": float(val) if val != "NaN" else None,
            }
            row.update(labels)
            rows.append(row)

    return pd.DataFrame(rows)


def query_range_full(
    session: requests.Session,
    prometheus_url: str,
    query: str,
    start: datetime,
    end: datetime,
    step: str = "5m",
    chunk_days: int = 7,
    timeout: int = 120,
) -> pd.DataFrame:
    """
    Split the date range into weekly chunks and concat results.
    Prometheus caps at ~11k samples per query so we can't do 6 months in one shot.
    """
    chunks = []
    current = start
    step_seconds = _parse_step_seconds(step)
    total_chunks = int((end - start).total_seconds() / (chunk_days * 86400)) + 1

    log.info(f"Extracting in {total_chunks} chunks of {chunk_days} days each")

    while current < end:
        chunk_end = min(current + timedelta(days=chunk_days), end)
        try:
            df = query_range_chunk(session, prometheus_url, query,
                                   current, chunk_end, step, timeout)
            chunks.append(df)
            log.debug(f"  Chunk {current.date()} → {chunk_end.date()}: {len(df)} rows")
        except Exception as e:
            log.warning(f"  Failed chunk {current.date()}: {e} — skipping")

        current = chunk_end
        time.sleep(0.1)

    if not chunks:
        return pd.DataFrame()
    return pd.concat(chunks, ignore_index=True)


def _parse_step_seconds(step: str) -> int:
    """Parse step string to seconds."""
    multipliers = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    return int(step[:-1]) * multipliers.get(step[-1], 1)
class TelemetryExtractor:

    def __init__(self, config_path: str):
        with open(config_path) as f:
            self.config = yaml.safe_load(f)

        self.prometheus_url = os.environ.get(
            "MIMIR_URL",
            self.config["extraction"]["prometheus_url"]
        ).rstrip("/")
        self.step = self.config["extraction"]["step"]
        self.timeout = self.config["extraction"].get("timeout_seconds", 120)

        token = os.environ.get("MIMIR_TOKEN")
        self.session = make_session(token)

    def extract_metric(
        self,
        metric_cfg: dict,
        start: datetime,
        end: datetime,
        output_dir: Path,
    ) -> Path:
        """Pull one metric and dump to parquet. Skips if the file already exists."""
        name = metric_cfg["name"]
        query = metric_cfg["query"].strip()
        out_path = output_dir / f"{name}.parquet"

        if out_path.exists():
            log.info(f"  {name}: already exists, skipping")
            return out_path

        log.info(f"  Extracting: {name}")
        df = query_range_full(
            self.session, self.prometheus_url, query,
            start, end, self.step
        )

        if df.empty:
            log.warning(f"  {name}: no data returned")
            df.to_parquet(out_path, index=False)
            return out_path

        df["metric_name"] = name
        df["unit"] = metric_cfg.get("unit", "unknown")
        df = df.dropna(subset=["value"])
        df.to_parquet(out_path, index=False, compression="snappy")
        log.info(f"  {name}: {len(df):,} rows → {out_path}")
        return out_path

    def extract_all(
        self,
        output_dir: Path,
        start: datetime,
        end: datetime,
        workers: int = 4,
    ) -> dict[str, Path]:
        """Extract everything in parallel. Returns dict of metric_name -> parquet path."""
        output_dir.mkdir(parents=True, exist_ok=True)
        metrics = self.config["metrics"]
        results = {}

        log.info(f"Extracting {len(metrics)} metrics: {start.date()} → {end.date()}")
        log.info(f"Using {workers} parallel workers")

        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(self.extract_metric, m, start, end, output_dir): m["name"]
                for m in metrics
            }
            for future in as_completed(futures):
                name = futures[future]
                try:
                    path = future.result()
                    results[name] = path
                except Exception as e:
                    log.error(f"Failed to extract {name}: {e}")

        log.info(f"Extraction complete: {len(results)}/{len(metrics)} metrics")
        return results

    def build_feature_matrix(self, raw_dir: Path, output_path: Path) -> pd.DataFrame:
        """Merge individual metric parquets into one wide matrix — one row per (timestamp, entity)."""
        log.info("Building feature matrix from raw metrics...")
        dfs = []

        for parquet_file in sorted(raw_dir.glob("*.parquet")):
            df = pd.read_parquet(parquet_file)
            if df.empty:
                continue
            metric_name = df["metric_name"].iloc[0]

            # pick up to 2 label columns to use as the entity key
            entity_cols = []
            for col in ["namespace", "pod", "destination_service_name", "persistentvolumeclaim"]:
                if col in df.columns:
                    entity_cols.append(col)
            entity_cols = entity_cols[:2]

            if not entity_cols:
                log.warning(f"  {metric_name}: no entity columns found, skipping")
                continue

            pivot = df.pivot_table(
                index=["timestamp"] + entity_cols,
                values="value",
                aggfunc="mean",
            ).reset_index()
            pivot.rename(columns={"value": metric_name}, inplace=True)
            dfs.append(pivot)

        if not dfs:
            raise ValueError("No metrics extracted — check Prometheus connectivity")

        log.info(f"  Merging {len(dfs)} metric tables...")
        result = dfs[0]
        for df in dfs[1:]:
            entity_cols = [c for c in df.columns if c in result.columns
                           and c != df.columns[-1]]
            result = result.merge(df, on=entity_cols, how="outer")

        result.sort_values(["timestamp"] + entity_cols[:1], inplace=True)
        result.to_parquet(output_path, index=False, compression="snappy")
        log.info(f"Feature matrix: {result.shape} → {output_path}")
        return result
def main():
    parser = argparse.ArgumentParser(description="Extract telemetry for anomaly detection training")
    parser.add_argument("--config", default="config/features.yaml")
    parser.add_argument("--output", default="data/raw")
    parser.add_argument("--matrix", default="data/feature_matrix.parquet")
    parser.add_argument("--start", help="Start date YYYY-MM-DD (default: 6 months ago)")
    parser.add_argument("--end", help="End date YYYY-MM-DD (default: today)")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    now = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    end_ts = (
        datetime.fromisoformat(args.end).replace(tzinfo=timezone.utc)
        if args.end else now
    )
    start_ts = (
        datetime.fromisoformat(args.start).replace(tzinfo=timezone.utc)
        if args.start else end_ts - timedelta(days=180)
    )

    extractor = TelemetryExtractor(args.config)
    raw_dir = Path(args.output)
    extractor.extract_all(raw_dir, start_ts, end_ts, workers=args.workers)
    extractor.build_feature_matrix(raw_dir, Path(args.matrix))
    log.info("Done — ready for feature engineering")


if __name__ == "__main__":
    main()
