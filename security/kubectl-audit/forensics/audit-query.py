#!/usr/bin/env python3
"""
Forensic query tool for the k8s audit log index in Elasticsearch.
Built for post-incident investigation — reconstruct what a user did,
find all the exec events on a pod, dump everything in an incident window.

  ./audit-query.py --user john.doe --hours 24
  ./audit-query.py --pod my-pod --namespace production --days 30
  ./audit-query.py --start "2024-01-15T08:00:00Z" --end "2024-01-15T11:00:00Z"
  ./audit-query.py --secrets-access --days 7
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from elasticsearch import Elasticsearch
from tabulate import tabulate
ELASTICSEARCH_HOST = os.environ.get("ELASTICSEARCH_HOST", "http://localhost:9200")
ELASTICSEARCH_USER = os.environ.get("ELASTICSEARCH_USER", "elastic")
ELASTICSEARCH_PASS = os.environ.get("ELASTICSEARCH_PASSWORD", "")
AUDIT_INDEX = os.environ.get("AUDIT_INDEX", "k8s-audit-*")
def get_client():
    return Elasticsearch(
        ELASTICSEARCH_HOST,
        basic_auth=(ELASTICSEARCH_USER, ELASTICSEARCH_PASS),
        verify_certs=True,
        request_timeout=30,
    )
def build_time_filter(start_ts, end_ts):
    return {
        "range": {
            "@timestamp": {
                "gte": start_ts.isoformat(),
                "lte": end_ts.isoformat(),
            }
        }
    }


def search_audit(es, query, size=500, sort_field="@timestamp"):
    resp = es.search(
        index=AUDIT_INDEX,
        body={
            "query": query,
            "size": size,
            "sort": [{sort_field: {"order": "asc"}}],
            "_source": [
                "@timestamp", "verb", "user.username", "user.groups",
                "sourceIPs", "objectRef.resource", "objectRef.namespace",
                "objectRef.name", "objectRef.subresource",
                "responseStatus.code", "audit.risk_tier",
                "audit.alert_type", "userAgent", "cluster"
            ],
        },
    )
    return resp["hits"]["hits"]
def format_event(hit):
    src = hit["_source"]
    obj = src.get("objectRef", {})
    resource = obj.get("resource", "")
    if obj.get("subresource"):
        resource = f"{resource}/{obj['subresource']}"
    ns = obj.get("namespace", "-")
    name = obj.get("name", "-")
    return {
        "timestamp": src.get("@timestamp", "")[:19],
        "verb": src.get("verb", ""),
        "user": src.get("user", {}).get("username", "-"),
        "resource": resource,
        "namespace": ns,
        "name": name,
        "status": src.get("responseStatus", {}).get("code", "-"),
        "risk": src.get("audit", {}).get("risk_tier", "-"),
        "source_ip": (src.get("sourceIPs") or ["-"])[0],
    }


def print_table(events, title=""):
    if title:
        print(f"\n{'='*70}")
        print(f"  {title}")
        print(f"{'='*70}")
    if not events:
        print("  No events found.")
        return
    rows = [format_event(e) for e in events]
    headers = ["Timestamp", "Verb", "User", "Resource", "Namespace", "Name", "Status", "Risk", "Source IP"]
    print(tabulate(
        [[r["timestamp"], r["verb"], r["user"], r["resource"],
          r["namespace"], r["name"], r["status"], r["risk"], r["source_ip"]]
         for r in rows],
        headers=headers,
        tablefmt="simple",
    ))
    print(f"\n  Total: {len(rows)} events")
def user_timeline(es, username, start_ts, end_ts):
    """Full timeline for one user. Useful for insider investigations or access reviews."""
    query = {
        "bool": {
            "must": [
                build_time_filter(start_ts, end_ts),
                {"term": {"user.username": username}},
            ],
            "must_not": [
                {"terms": {"verb": ["watch"]}},
            ],
        }
    }
    events = search_audit(es, query, size=1000)
    print_table(events, f"Timeline for user: {username}")


    from collections import Counter
    summary = Counter(
        f"{format_event(e)['verb']} {format_event(e)['resource']}"
        for e in events
    )
    print(f"\n  Summary:")
    for action, count in summary.most_common(20):
        print(f"    {count:4d}x  {action}")


def critical_events(es, start_ts, end_ts, namespace=None):
    """High and critical events only — good starting point for any investigation."""
    must = [
        build_time_filter(start_ts, end_ts),
        {"terms": {"audit.risk_tier": ["critical", "high"]}},
        {"bool": {"must_not": [{"prefix": {"user.username": "system:"}}]}},
    ]
    if namespace:
        must.append({"term": {"objectRef.namespace": namespace}})
    events = search_audit(es, {"bool": {"must": must}}, size=500)
    title = f"Critical/High risk events"
    if namespace:
        title += f" in namespace: {namespace}"
    print_table(events, title)


def secrets_access(es, start_ts, end_ts):
    """Who read secrets in this window. Run this for quarterly access reviews."""
    query = {
        "bool": {
            "must": [
                build_time_filter(start_ts, end_ts),
                {"term": {"objectRef.resource": "secrets"}},
                {"bool": {"must_not": [{"prefix": {"user.username": "system:"}}]}},
            ]
        }
    }
    events = search_audit(es, query, size=1000)
    print_table(events, "Secret access by human users")

    # break it down by user so you can spot the outlier
    from collections import Counter
    by_user = Counter(
        hit["_source"].get("user", {}).get("username", "?")
        for hit in events
    )
    print(f"\n  Secret access by user:")
    for user, count in by_user.most_common():
        print(f"    {count:4d}x  {user}")


def pod_forensics(es, pod_name, namespace, start_ts, end_ts):
    """Everything touching a specific pod — who created it, who exec'd in, any deletes."""
    query = {
        "bool": {
            "must": [
                build_time_filter(start_ts, end_ts),
                {"term": {"objectRef.name": pod_name}},
                {"term": {"objectRef.namespace": namespace}},
            ]
        }
    }
    events = search_audit(es, query, size=500)
    print_table(events, f"Pod forensics: {namespace}/{pod_name}")

    # exec events are the most forensically interesting — flag them separately
    exec_events = [
        e for e in events
        if e["_source"].get("objectRef", {}).get("subresource") == "exec"
    ]
    if exec_events:
        print(f"\n  ⚠️  EXEC EVENTS ({len(exec_events)}):")
        print_table(exec_events, "Container exec events")


def incident_window(es, start_ts, end_ts):
    """Dump all human activity in a window. Start here when you don't know what happened."""
    query = {
        "bool": {
            "must": [
                build_time_filter(start_ts, end_ts),
                {"bool": {"must_not": [{"prefix": {"user.username": "system:"}}]}},
            ],
            "must_not": [
                {"terms": {"verb": ["watch", "list"]}},
            ],
        }
    }
    events = search_audit(es, query, size=2000)
    print_table(events, f"Incident window: {start_ts.isoformat()} → {end_ts.isoformat()}")
def parse_args():
    p = argparse.ArgumentParser(
        description="K8s Audit Log Forensic Query Tool — ISO 27001 A.16.1.7"
    )
    time_grp = p.add_mutually_exclusive_group()
    time_grp.add_argument("--hours", type=int, default=24, help="Look back N hours (default: 24)")
    time_grp.add_argument("--days", type=int, help="Look back N days")
    time_grp.add_argument("--start", help="Start timestamp (ISO 8601)")
    p.add_argument("--end", help="End timestamp (ISO 8601), default: now")

    # Investigation modes
    p.add_argument("--user", help="Show all activity by this username")
    p.add_argument("--pod", help="Forensic investigation of a specific pod")
    p.add_argument("--namespace", "-n", help="Filter by namespace")
    p.add_argument("--critical-only", action="store_true", help="Show only critical/high risk events")
    p.add_argument("--secrets-access", action="store_true", help="List all human secret access")
    p.add_argument("--incident", action="store_true", help="Full dump of all human activity in time window")

    p.add_argument("--output", choices=["table", "json"], default="table")
    return p.parse_args()


def main():
    args = parse_args()

    # Resolve time window
    now = datetime.now(timezone.utc)
    if args.start:
        start_ts = datetime.fromisoformat(args.start.replace("Z", "+00:00"))
    elif args.days:
        start_ts = now - timedelta(days=args.days)
    else:
        start_ts = now - timedelta(hours=args.hours)

    end_ts = datetime.fromisoformat(args.end.replace("Z", "+00:00")) if args.end else now

    print(f"\n  Querying: {AUDIT_INDEX}")
    print(f"  Window:   {start_ts.isoformat()} → {end_ts.isoformat()}")

    es = get_client()

    if args.user:
        user_timeline(es, args.user, start_ts, end_ts)
    elif args.secrets_access:
        secrets_access(es, start_ts, end_ts)
    elif args.pod:
        if not args.namespace:
            print("Error: --namespace required with --pod", file=sys.stderr)
            sys.exit(1)
        pod_forensics(es, args.pod, args.namespace, start_ts, end_ts)
    elif args.incident:
        incident_window(es, start_ts, end_ts)
    else:
        critical_events(es, start_ts, end_ts, namespace=args.namespace)


if __name__ == "__main__":
    main()
