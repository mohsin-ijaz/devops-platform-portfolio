#!/usr/bin/env python3
"""
Scan Kubernetes ConfigMaps and Secrets for database endpoints across namespaces.

- Includes keys that look DB-related (e.g., mysql, database, db_host, db_endpoint, url, host, endpoint, rds, cloudsql).
- Excludes anything MongoDB-related (keys containing mongo/mongodb or values with mongodb://).
- Parses values to detect:
  - mysql:// and jdbc:mysql:// URLs (credentials redacted)
  - Go DSN user:pass@tcp(host:port)/db (redacted, normalized to mysql://host:port/db)
  - AWS RDS hostnames (*<RDS_ENDPOINT>[:port])
  - Private IPs (10.x, 172.16-31.x, 192.168.x) with optional ports (e.g., Cloud SQL private IP)

Output: CSV by default (use --format tsv for TSV). Columns -> namespace, kind, resource, application, key, match_reason, value_or_endpoint

Usage examples:
  KUBECONFIG=~/.kube/enterprise-uat-eks-local-16443 ./scan_db_endpoints.py   # writes ./db_endpoints_full.csv
  ./scan_db_endpoints.py --format tsv                                 # writes ./db_endpoints_full.tsv
  ./scan_db_endpoints.py --output - --format csv                      # print to stdout
  ./scan_db_endpoints.py --all-namespaces --format tsv -o file.tsv
"""

import argparse
import base64
import csv
import ipaddress
import json
import os
import re
import subprocess
import sys
from typing import Dict, Iterable, List, Optional, Tuple

# Patterns for parsing values
MYSQL_URL_RE = re.compile(r"(?i)(?:jdbc:)?mysql://(?:[^@/\s]+@)?(?P<host>[^/:?#\s,;]+)(?::(?P<port>\d+))?(?P<path>/[^\s,;]*)?")
GO_DSN_RE = re.compile(r"(?P<user>[A-Za-z0-9._%+-]+)(?::(?P<pw>[^@]*))?@tcp\((?P<hp>[^)]+)\)(?P<path>/[^\s,;]*)?")
RDS_HOST_RE = re.compile(r"(?P<host>[A-Za-z0-9.-]+\.rds\.amazonaws\.com)(?::(?P<port>\d+))?")
PRIVATE_IP_RE = re.compile(r"\b(?P<ip>(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}))(?:[:](?P<port>\d{2,5}))?\b")
HOST_PORT_PATH_RE = re.compile(r"\b(?P<host>[A-Za-z0-9._-]+)(?::(?P<port>\d{2,5}))?(/[^\s,;]*)?\b")

# Key filters
KEY_EXCLUDE_TERMS = [
    "password", "passwd", "pwd", "secret", "token", "access_key", "private_key", "certificate",
    "mongo", "mongodb"
]

# if key contains any of these, we consider it DB-related without additional hints
KEY_STRONG_POSITIVE = ["mysql", "jdbc", "dsn", "rds", "cloudsql"]

# if key contains any of these AND also contains one of the hints below, consider DB-related
KEY_WEAK_POSITIVE = ["db", "database", "sql"]
KEY_ENDPOINT_HINTS = ["host", "hostname", "endpoint", "addr", "address", "url", "uri", "conn", "connection", "server"]


def run_kubectl_json(kinds: str, all_namespaces: bool) -> Dict:
    cmd = ["kubectl", "get", kinds, "-o", "json"]
    if all_namespaces:
        cmd.insert(2, "-A")
    try:
        res = subprocess.run(cmd, check=True, capture_output=True, text=True, env=os.environ.copy())
    except subprocess.CalledProcessError as e:
        sys.stderr.write(f"Error running {' '.join(cmd)}\nSTDERR: {e.stderr}\n")
        raise
    return json.loads(res.stdout)


def is_private_ip(host: str) -> bool:
    try:
        ip = ipaddress.ip_address(host)
        return ip.is_private
    except ValueError:
        return False


def sanitize_value(val: str) -> str:
    # redact credentials and keep value readable
    s = val.replace("\n", " ")
    # redact credentials in mysql/jdbc URLs
    s = re.sub(r"(?i)(mysql://)[^:/\s]+:[^@/\s]*@", r"\1****:****@", s)
    # redact credentials in DSN
    s = re.sub(r"([A-Za-z0-9._%+-]+):[^@]*@tcp\(", r"\1:****@tcp(", s)
    # redact common password kv pairs
    s = re.sub(r"(?i)(password|passwd|pwd)=([^;&\s]+)", r"\1=****", s)
    return s


def key_is_relevant(key: str) -> bool:
    k = key.lower()
    if any(t in k for t in KEY_EXCLUDE_TERMS):
        return False
    if any(t in k for t in KEY_STRONG_POSITIVE):
        return True
    if any(t in k for t in KEY_WEAK_POSITIVE) and any(h in k for h in KEY_ENDPOINT_HINTS):
        return True
    return False


def extract_endpoints(val: str) -> List[Tuple[str, str]]:
    """Return list of (match_reason, endpoint_or_url). Redacted where applicable.
    Excludes MongoDB patterns.
    """
    if "mongodb://" in val.lower():
        return []
    out: List[Tuple[str, str]] = []
    for m in MYSQL_URL_RE.finditer(val):
        host = m.group("host") or ""
        port = m.group("port") or ""
        path = m.group("path") or ""
        url = f"mysql://{host}{(':'+port) if port else ''}{path}"
        out.append(("mysql_url", url))
    for m in GO_DSN_RE.finditer(val):
        hp = m.group("hp") or ""
        path = m.group("path") or ""
        url = f"mysql://{hp}{path or ''}"
        out.append(("go_dsn", url))
    for m in RDS_HOST_RE.finditer(val):
        host = m.group("host")
        port = m.group("port") or ""
        out.append(("aws_rds", f"{host}{(':'+port) if port else ''}"))
    for m in PRIVATE_IP_RE.finditer(val):
        ip = m.group("ip")
        port = m.group("port") or ""
        if is_private_ip(ip):
            out.append(("private_ip", f"{ip}{(':'+port) if port else ''}"))
    # Generic host:port for common MySQL ports
    for m in HOST_PORT_PATH_RE.finditer(val):
        host = m.group("host")
        port = m.group("port") or ""
        path = m.group(3) or ""
        if port in ("3306", "3307"):
            out.append(("host_port", f"{host}:{port}{path}"))
    # de-duplicate while preserving order
    seen = set()
    uniq: List[Tuple[str, str]] = []
    for reason, value in out:
        key = (reason, value)
        if key not in seen:
            seen.add(key)
            uniq.append((reason, value))
    return uniq


def decode_secret_data(data: Dict[str, str]) -> Dict[str, str]:
    out = {}
    for k, v in (data or {}).items():
        try:
            out[k] = base64.b64decode(v).decode("utf-8", "ignore")
        except Exception:
            # Skip undecodable entries
            continue
    return out


def main():
    ap = argparse.ArgumentParser(description="Scan k8s ConfigMaps and Secrets for DB endpoints")
    ap.add_argument("--ns-prefix", default="enterprise-", help="Namespace prefix to include (default: enterprise-)")
    ap.add_argument("--all-namespaces", action="store_true", help="Scan all namespaces (overrides --ns-prefix)")
    ap.add_argument("--kinds", default="cm,secret", help="Comma-separated kinds to scan (cm,secret)")
    ap.add_argument("--format", "-f", choices=["csv", "tsv"], default="csv", help="Output format: csv or tsv (default: csv)")
    ap.add_argument("--output", "-o", default="", help="Output file path or '-' for stdout (default: ./db_endpoints_full.<csv|tsv>)")
    args = ap.parse_args()

    kinds = args.kinds
    data = run_kubectl_json(kinds, all_namespaces=True)

    rows: List[Tuple[str, str, str, str, str, str, str]] = []

    for it in data.get("items", []):
        md = it.get("metadata", {})
        ns = md.get("namespace", "")
        if not args.all_namespaces and not ns.startswith(args.ns_prefix):
            continue
        kind = it.get("kind", "")
        name = md.get("name", "")
        labels = md.get("labels") or {}
        app = (
            labels.get("app.kubernetes.io/name")
            or labels.get("app")
            or labels.get("app.kubernetes.io/instance")
            or name
        )

        # Collect key-value pairs
        kv: Dict[str, str] = {}
        if kind == "Secret":
            kv.update(decode_secret_data(it.get("data") or {}))
            # ignore binaryData
        else:
            kv.update((it.get("data") or {}))

        for key, val in kv.items():
            sval = str(val) if not isinstance(val, str) else val

            # value-based extraction first
            endpoints = extract_endpoints(sval)
            for reason, endpoint in endpoints:
                rows.append((ns, kind, name, app, key, reason, endpoint))

            # key-name based inclusion (only if no endpoints found), focusing on endpoint-like keys
            if not endpoints and key_is_relevant(key):
                sanitized = sanitize_value(sval)
                rows.append((ns, kind, name, app, key, "key_match", sanitized))

    # Sort results for readability
    rows.sort(key=lambda r: (r[0], r[3], r[1], r[2], r[4], r[5], r[6]))

    # Output
    header = ["namespace", "kind", "resource", "application", "key", "match_reason", "value_or_endpoint"]
    delim = "," if args.format == "csv" else "\t"

    if args.output == "-":
        w = csv.writer(sys.stdout, delimiter=delim)
        w.writerow(header)
        for r in rows:
            w.writerow(r)
    else:
        out_path = args.output or f"db_endpoints_full.{ 'csv' if args.format == 'csv' else 'tsv' }"
        with open(out_path, "w", newline="") as f:
            w = csv.writer(f, delimiter=delim)
            w.writerow(header)
            for r in rows:
                w.writerow(r)
        print(f"Wrote {len(rows)} rows to {out_path}")


if __name__ == "__main__":
    main()

