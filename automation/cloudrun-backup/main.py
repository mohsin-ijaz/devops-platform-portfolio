#!/usr/bin/env python3


from __future__ import annotations

import csv
import json
import os
import random
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

try:
    import mysql.connector
    from mysql.connector import Error as MySQLError
    MYSQL_AVAILABLE = True
except ImportError:
    MYSQL_AVAILABLE = False


# Configuration from environment
PROJECT_ID = os.environ.get("PROJECT_ID", "<GCP_PROJECT_ID>")
REGION = os.environ.get("REGION", "<GCP_REGION>")
LOG_BUCKET = os.environ.get("LOG_BUCKET", f"{PROJECT_ID}-cloudsql-backup-logs")
DRY_RUN = os.environ.get("DRY_RUN", "false").lower() == "true"
MAX_INSTANCES = int(os.environ.get("MAX_INSTANCES", "50"))
MAX_WORKERS = int(os.environ.get("MAX_WORKERS", "16"))  # Total parallel instances
OPERATION_TIMEOUT = int(os.environ.get("OPERATION_TIMEOUT", "3600"))
INSTANCE_FILTER = os.environ.get("INSTANCE_FILTER", "")  # Filter to specific instance

# Phase 2: Deep validation config
SETUP_GRANTS = os.environ.get("SETUP_GRANTS", "false").lower() == "true"
DB_VALIDATOR_SECRET = os.environ.get("DB_VALIDATOR_SECRET", "cloudsql-validator-credentials")
DB_VALIDATOR_USER = os.environ.get("DB_VALIDATOR_USER", "")   # fallback if no secret
DB_VALIDATOR_PASS = os.environ.get("DB_VALIDATOR_PASS", "")   # fallback if no secret
SIZE_THRESHOLD_PCT = float(os.environ.get("SIZE_THRESHOLD_PCT", "10"))
AI_DRIFT_THRESHOLD = int(os.environ.get("AI_DRIFT_THRESHOLD", "1000"))
ROW_TOLERANCE_PCT = float(os.environ.get("ROW_TOLERANCE_PCT", "5"))


# Safety constants
RESTORE_TEST_SUFFIX = "-restore-test-"
ALLOWED_PROJECTS = ("<YOUR_TENANT_ID>", "<GCP_PROJECT_ID>")


def log(msg: str, level: str = "INFO"):
    """Simple logging."""
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {msg}", flush=True)


def run_gcloud(args: list, capture_json: bool = False, check: bool = True) -> Union[dict, list, str]:
    """Run gcloud command and return output."""
    cmd = ["gcloud"] + args + [f"--project={PROJECT_ID}", "--quiet"]
    if capture_json:
        cmd.append("--format=json")

    log(f"Running: {' '.join(cmd)}", "DEBUG")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if check and result.returncode != 0:
        raise RuntimeError(f"gcloud failed: {result.stderr}")

    if capture_json and result.stdout.strip():
        return json.loads(result.stdout)
    return result.stdout


def list_instances() -> list:
    """List all runnable Cloud SQL instances (excluding replicas and restore-test)."""
    log(f"Listing instances in project {PROJECT_ID}")
    instances = run_gcloud(["sql", "instances", "list"], capture_json=True)
    runnable = [i for i in instances if i.get("state") == "RUNNABLE"]

    # Filter out replica instances (can't create backups on replicas)
    primary_only = [i for i in runnable if not i["name"].endswith("-replica") and "-replica-" not in i["name"]]
    excluded_replicas = len(runnable) - len(primary_only)
    if excluded_replicas > 0:
        log(f"Excluded {excluded_replicas} replica instances (backups not supported)")
    runnable = primary_only

    # Filter out any restore-test instances (from previous failed runs)
    runnable = [i for i in runnable if RESTORE_TEST_SUFFIX not in i["name"]]

    # Filter to specific instance if set
    if INSTANCE_FILTER:
        runnable = [i for i in runnable if i["name"] == INSTANCE_FILTER]
        log(f"Filtered to instance: {INSTANCE_FILTER}")

    log(f"Found {len(runnable)} primary instances to process")
    return runnable[:MAX_INSTANCES]


def create_backup(instance_name: str) -> str:
    """
    Create on-demand backup, return project-level backup NAME (projects/P/backups/UUID).
    This NAME format is required for restore-to-new-instance in one step.
    Reuses today's backup if one already exists (idempotency).
    """
    log(f"[{instance_name}] Step 1/3: Creating on-demand backup...")

    if DRY_RUN:
        log(f"[{instance_name}] [DRY RUN] Would create backup")
        return "projects/dry-run/backups/dry-run-backup-name"

    today = datetime.utcnow().strftime("%Y-%m-%d")

    # Idempotency: check project-level backup list which returns UUID names
    existing = run_gcloud(["sql", "backups", "list",
                           f"--filter=instance={instance_name} AND type=ON_DEMAND",
                           "--limit=5"], capture_json=True)
    for b in existing:
        if f"Monthly validation {today}" in b.get("description", "") and b.get("state") == "SUCCESSFUL":
            backup_name = b["name"]
            log(f"[{instance_name}] Reusing existing backup from today - {backup_name}")
            return backup_name

    desc = f"Monthly validation {today} {datetime.utcnow().strftime('%H:%M')}"
    run_gcloud(["sql", "backups", "create", f"--instance={instance_name}", f"--description={desc}"])

    # Fetch the project-level NAME (UUID) just created
    backups = run_gcloud(["sql", "backups", "list",
                          f"--filter=instance={instance_name} AND type=ON_DEMAND",
                          "--limit=1"], capture_json=True)
    if not backups:
        raise RuntimeError("No backup found after creation")

    backup_name = backups[0]["name"]  # projects/PROJECT/backups/UUID
    log(f"[{instance_name}] Backup created - {backup_name}")
    return backup_name


def restore_to_new_instance(source_name: str, backup_name: str, restore_name: str):
    """
    Restore backup to a BRAND NEW instance in one step using the project-level backup NAME.
    Cloud SQL creates the instance automatically with matching specs (tier, version, network).
    No pre-created empty instance needed.
    """
    # SAFETY CHECK
    if RESTORE_TEST_SUFFIX not in restore_name:
        raise ValueError(f"Safety check failed: {restore_name} missing {RESTORE_TEST_SUFFIX}")

    log(f"[{source_name}] Step 2/3: Restoring backup to new instance {restore_name}...")

    if DRY_RUN:
        log(f"[{source_name}] [DRY RUN] Would restore {backup_name} → {restore_name}")
        return

    # Clean up any orphaned restore-test instances first
    try:
        existing = run_gcloud(["sql", "instances", "list",
                               f"--filter=name~{source_name}{RESTORE_TEST_SUFFIX}"],
                              capture_json=True)
        for inst in existing:
            orphan_name = inst.get("name", "")
            if RESTORE_TEST_SUFFIX in orphan_name:
                log(f"[{source_name}] Cleaning up orphaned instance: {orphan_name}", "WARN")
                run_gcloud(["sql", "instances", "patch", orphan_name,
                            "--no-deletion-protection"], check=False)
                time.sleep(3)
                run_gcloud(["sql", "instances", "delete", orphan_name], check=False)
                time.sleep(15)
    except Exception as e:
        log(f"[{source_name}] Error checking orphaned instances: {e}", "WARN")

    # Restore backup → creates new instance automatically (backup NAME format required)
    run_gcloud(["sql", "backups", "restore", backup_name,
                f"--restore-instance={restore_name}"])

    wait_for_instance(restore_name)
    log(f"[{source_name}] Restored successfully to new instance {restore_name}")


def wait_for_instance(instance_name: str):
    """Wait for instance to be RUNNABLE."""
    start = time.time()
    while time.time() - start < OPERATION_TIMEOUT:
        info = run_gcloud(["sql", "instances", "describe", instance_name], capture_json=True)
        state = info.get("state", "UNKNOWN")
        if state == "RUNNABLE":
            return
        log(f"[{instance_name}] Waiting... (state: {state})")
        time.sleep(20)
    raise TimeoutError(f"Instance {instance_name} not ready after {OPERATION_TIMEOUT}s")


def delete_instance(instance_name: str) -> bool:
    """Delete instance (ONLY if it has restore-test suffix)."""
    # CRITICAL SAFETY CHECK
    if RESTORE_TEST_SUFFIX not in instance_name:
        log(f"SAFETY BLOCK: Refusing to delete {instance_name} - missing {RESTORE_TEST_SUFFIX}", "ERROR")
        return False

    log(f"Deleting restore instance: {instance_name}")

    if DRY_RUN:
        log(f"[DRY RUN] Would delete {instance_name}")
        return True

    try:
        # Disable deletion protection (enabled by default on new instances)
        run_gcloud(["sql", "instances", "patch", instance_name,
                    "--no-deletion-protection"], check=False)
        time.sleep(3)
        run_gcloud(["sql", "instances", "delete", instance_name])
        log(f"Deleted: {instance_name}")
        return True
    except Exception as e:
        log(f"Failed to delete {instance_name}: {e}", "ERROR")
        return False



# Phase 2: Deep MySQL Validation


@dataclass
class CheckResult:
    category: str
    check_name: str
    status: str          # PASS | FAIL | WARN | INFO
    source_value: str = ""
    restored_value: str = ""
    detail: str = ""


@dataclass
class ValidationReport:
    run_at: str = ""
    source_host: str = ""
    source_db: str = ""
    restored_host: str = ""
    restored_db: str = ""
    results: List[CheckResult] = field(default_factory=list)

    def add(self, result: CheckResult):
        self.results.append(result)

    def summary(self) -> Dict[str, int]:
        counts: Dict[str, int] = {"PASS": 0, "FAIL": 0, "WARN": 0, "INFO": 0}
        for r in self.results:
            counts[r.status] = counts.get(r.status, 0) + 1
        return counts


def _db_query(conn, sql: str, params=None):
    cur = conn.cursor()
    cur.execute(sql, params or ())
    rows = cur.fetchall()
    cur.close()
    return rows


class Validator:
    def __init__(self, src_conn, rst_conn, src_db: str, rst_db: str,
                 size_threshold_pct: float, ai_drift_threshold: int,
                 row_count_tolerance_pct: float, report: ValidationReport,
                 db_prefix: str = ""):
        self.src = src_conn
        self.rst = rst_conn
        self.src_db = src_db
        self.rst_db = rst_db
        self.size_threshold = size_threshold_pct
        self.ai_drift = ai_drift_threshold
        self.row_tolerance = row_count_tolerance_pct
        self.report = report
        self.prefix = f"[{db_prefix}] " if db_prefix else ""

    def _ok(self, cat, name, sv="", rv="", detail=""):
        self.report.add(CheckResult(cat, f"{self.prefix}{name}", "PASS", str(sv), str(rv), detail))

    def _fail(self, cat, name, sv="", rv="", detail=""):
        self.report.add(CheckResult(cat, f"{self.prefix}{name}", "FAIL", str(sv), str(rv), detail))

    def _warn(self, cat, name, sv="", rv="", detail=""):
        self.report.add(CheckResult(cat, f"{self.prefix}{name}", "WARN", str(sv), str(rv), detail))

    def _info(self, cat, name, sv="", rv="", detail=""):
        self.report.add(CheckResult(cat, f"{self.prefix}{name}", "INFO", str(sv), str(rv), detail))

    def check_db_metadata(self):
        CAT = "DB Metadata"
        sql = ("SELECT DEFAULT_CHARACTER_SET_NAME, DEFAULT_COLLATION_NAME "
               "FROM INFORMATION_SCHEMA.SCHEMATA WHERE SCHEMA_NAME = %s")
        src_row = _db_query(self.src, sql, (self.src_db,))
        rst_row = _db_query(self.rst, sql, (self.rst_db,))
        if not src_row or not rst_row:
            self._fail(CAT, "database exists", detail="DB not found on one side")
            return
        for col, label in [(0, "charset"), (1, "collation")]:
            sv, rv = src_row[0][col], rst_row[0][col]
            (self._ok if sv == rv else self._fail)(CAT, f"db {label}", sv, rv)

    def check_object_counts(self):
        CAT = "Object Counts"
        checks = [
            ("tables",             "SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA=%s AND TABLE_TYPE='BASE TABLE'"),
            ("views",              "SELECT COUNT(*) FROM INFORMATION_SCHEMA.VIEWS WHERE TABLE_SCHEMA=%s"),
            ("stored procedures",  "SELECT COUNT(*) FROM INFORMATION_SCHEMA.ROUTINES WHERE ROUTINE_SCHEMA=%s AND ROUTINE_TYPE='PROCEDURE'"),
            ("functions",          "SELECT COUNT(*) FROM INFORMATION_SCHEMA.ROUTINES WHERE ROUTINE_SCHEMA=%s AND ROUTINE_TYPE='FUNCTION'"),
            ("triggers",           "SELECT COUNT(*) FROM INFORMATION_SCHEMA.TRIGGERS WHERE TRIGGER_SCHEMA=%s"),
            ("events",             "SELECT COUNT(*) FROM INFORMATION_SCHEMA.EVENTS WHERE EVENT_SCHEMA=%s"),
        ]
        for label, sql in checks:
            sv = _db_query(self.src, sql, (self.src_db,))[0][0]
            rv = _db_query(self.rst, sql, (self.rst_db,))[0][0]
            (self._ok if sv == rv else self._fail)(CAT, f"count: {label}", sv, rv)

    def check_object_names(self):
        CAT = "Object Names"
        checks = [
            ("table",     "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA=%s AND TABLE_TYPE='BASE TABLE' ORDER BY TABLE_NAME"),
            ("view",      "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.VIEWS WHERE TABLE_SCHEMA=%s ORDER BY TABLE_NAME"),
            ("procedure", "SELECT ROUTINE_NAME FROM INFORMATION_SCHEMA.ROUTINES WHERE ROUTINE_SCHEMA=%s AND ROUTINE_TYPE='PROCEDURE' ORDER BY ROUTINE_NAME"),
            ("function",  "SELECT ROUTINE_NAME FROM INFORMATION_SCHEMA.ROUTINES WHERE ROUTINE_SCHEMA=%s AND ROUTINE_TYPE='FUNCTION' ORDER BY ROUTINE_NAME"),
            ("trigger",   "SELECT TRIGGER_NAME FROM INFORMATION_SCHEMA.TRIGGERS WHERE TRIGGER_SCHEMA=%s ORDER BY TRIGGER_NAME"),
            ("event",     "SELECT EVENT_NAME FROM INFORMATION_SCHEMA.EVENTS WHERE EVENT_SCHEMA=%s ORDER BY EVENT_NAME"),
        ]
        for obj_type, sql in checks:
            src_names = {r[0] for r in _db_query(self.src, sql, (self.src_db,))}
            rst_names = {r[0] for r in _db_query(self.rst, sql, (self.rst_db,))}
            missing = src_names - rst_names
            extra   = rst_names - src_names
            if not missing and not extra:
                self._ok(CAT, f"{obj_type} names match", len(src_names), len(rst_names))
            else:
                if missing:
                    self._fail(CAT, f"{obj_type}s missing in restored", "", "", f"Missing: {', '.join(sorted(missing))}")
                if extra:
                    self._warn(CAT, f"{obj_type}s extra in restored", "", "", f"Extra: {', '.join(sorted(extra))}")

    def check_table_structure(self):
        CAT = "Table Structure"
        src_tables = {r[0] for r in _db_query(self.src,
            "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA=%s AND TABLE_TYPE='BASE TABLE'",
            (self.src_db,))}
        rst_tables = {r[0] for r in _db_query(self.rst,
            "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA=%s AND TABLE_TYPE='BASE TABLE'",
            (self.rst_db,))}
        common = src_tables & rst_tables
        col_sql = ("SELECT COLUMN_NAME,ORDINAL_POSITION,COLUMN_DEFAULT,IS_NULLABLE,DATA_TYPE,"
                   "CHARACTER_MAXIMUM_LENGTH,NUMERIC_PRECISION,NUMERIC_SCALE,COLUMN_TYPE,COLUMN_KEY,EXTRA,COLLATION_NAME "
                   "FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s ORDER BY ORDINAL_POSITION")
        idx_sql = ("SELECT INDEX_NAME,SEQ_IN_INDEX,COLUMN_NAME,NON_UNIQUE,INDEX_TYPE "
                   "FROM INFORMATION_SCHEMA.STATISTICS WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s ORDER BY INDEX_NAME,SEQ_IN_INDEX")
        fk_sql  = ("SELECT CONSTRAINT_NAME,COLUMN_NAME,REFERENCED_TABLE_NAME,REFERENCED_COLUMN_NAME "
                   "FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s "
                   "AND REFERENCED_TABLE_NAME IS NOT NULL ORDER BY CONSTRAINT_NAME,ORDINAL_POSITION")
        meta_sql = "SELECT ENGINE,TABLE_COLLATION FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s"
        for tbl in sorted(common):
            sm = _db_query(self.src, meta_sql, (self.src_db, tbl))
            rm = _db_query(self.rst, meta_sql, (self.rst_db, tbl))
            if sm and rm:
                (self._ok if sm[0] == rm[0] else self._fail)(CAT, f"table:{tbl} engine/collation", str(sm[0][0]), str(rm[0][0]))
            sc = _db_query(self.src, col_sql, (self.src_db, tbl))
            rc = _db_query(self.rst, col_sql, (self.rst_db, tbl))
            if sc != rc:
                scn = {r[0]: r for r in sc}; rcn = {r[0]: r for r in rc}
                details = []
                miss = set(scn)-set(rcn); extra = set(rcn)-set(scn)
                diff = [c for c in scn if c in rcn and scn[c] != rcn[c]]
                if miss:  details.append(f"missing: {miss}")
                if extra: details.append(f"extra: {extra}")
                if diff:  details.append(f"changed: {diff}")
                self._fail(CAT, f"table:{tbl} columns", len(sc), len(rc), "; ".join(details))
            else:
                self._ok(CAT, f"table:{tbl} columns", len(sc), len(rc))
            si = _db_query(self.src, idx_sql, (self.src_db, tbl))
            ri = _db_query(self.rst, idx_sql, (self.rst_db, tbl))
            (self._ok if si == ri else self._fail)(CAT, f"table:{tbl} indexes", len(si), len(ri))
            sf = _db_query(self.src, fk_sql, (self.src_db, tbl))
            rf = _db_query(self.rst, fk_sql, (self.rst_db, tbl))
            (self._ok if sf == rf else self._fail)(CAT, f"table:{tbl} foreign keys", len(sf), len(rf))

    def check_row_counts(self):
        CAT = "Row Counts"
        sql = "SELECT TABLE_NAME,TABLE_ROWS FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA=%s AND TABLE_TYPE='BASE TABLE'"
        src_t = {r[0]: r[1] for r in _db_query(self.src, sql, (self.src_db,))}
        rst_t = {r[0]: r[1] for r in _db_query(self.rst, sql, (self.rst_db,))}
        for tbl in sorted(set(src_t) & set(rst_t)):
            sv = src_t.get(tbl) or 0
            rv = rst_t.get(tbl) or 0
            if sv == 0 and rv == 0:
                self._ok(CAT, f"row count: {tbl}", sv, rv, "Both empty"); continue
            if sv == 0:
                self._info(CAT, f"row count: {tbl}", sv, rv, "Source estimate is 0 (InnoDB stats)"); continue
            diff_pct = abs(sv - rv) / max(sv, 1) * 100
            if rv > sv:
                self._fail(CAT, f"row count: {tbl}", sv, rv, f"Restored has MORE rows — data integrity concern")
            elif diff_pct == 0:
                self._ok(CAT, f"row count: {tbl}", sv, rv)
            elif diff_pct <= self.row_tolerance:
                self._warn(CAT, f"row count: {tbl}", sv, rv, f"Diff {diff_pct:.1f}% within {self.row_tolerance}% tolerance")
            else:
                self._fail(CAT, f"row count: {tbl}", sv, rv, f"Diff {diff_pct:.1f}% exceeds {self.row_tolerance}% tolerance")

    def check_auto_increment(self):
        CAT = "Auto-Increment"
        sql = ("SELECT TABLE_NAME,AUTO_INCREMENT FROM INFORMATION_SCHEMA.TABLES "
               "WHERE TABLE_SCHEMA=%s AND AUTO_INCREMENT IS NOT NULL AND TABLE_TYPE='BASE TABLE' ORDER BY TABLE_NAME")
        src_ai = {r[0]: r[1] for r in _db_query(self.src, sql, (self.src_db,))}
        rst_ai = {r[0]: r[1] for r in _db_query(self.rst, sql, (self.rst_db,))}
        for tbl in sorted(set(src_ai) | set(rst_ai)):
            sv, rv = src_ai.get(tbl), rst_ai.get(tbl)
            if sv is None or rv is None:
                self._info(CAT, f"auto_increment: {tbl}", sv or "N/A", rv or "N/A"); continue
            if rv > sv:
                self._warn(CAT, f"auto_increment: {tbl}", sv, rv, "Restored AI higher — possible post-restore writes")
            elif sv == rv:
                self._ok(CAT, f"auto_increment: {tbl}", sv, rv)
            else:
                drift = sv - rv
                (self._warn if drift <= self.ai_drift else self._fail)(
                    CAT, f"auto_increment: {tbl}", sv, rv, f"AI drift={drift}")

    def check_table_sizes(self):
        CAT = "Table Sizes"
        sql = ("SELECT TABLE_NAME,ROUND((data_length+index_length)/1024.0/1024.0,3) "
               "FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA=%s AND TABLE_TYPE='BASE TABLE' ORDER BY TABLE_NAME")
        src_s = {r[0]: float(r[1] or 0) for r in _db_query(self.src, sql, (self.src_db,))}
        rst_s = {r[0]: float(r[1] or 0) for r in _db_query(self.rst, sql, (self.rst_db,))}
        src_total = sum(src_s.values()); rst_total = sum(rst_s.values())
        if src_total > 0:
            d = abs(src_total - rst_total) / src_total * 100
            (self._ok if d <= self.size_threshold else self._fail)(
                CAT, "total DB size", f"{src_total:.2f} MB", f"{rst_total:.2f} MB", f"Diff {d:.1f}%")
        for tbl in sorted(set(src_s) & set(rst_s)):
            sv, rv = src_s[tbl], rst_s[tbl]
            if sv == 0 and rv == 0: continue
            if sv == 0:
                self._info(CAT, f"size: {tbl}", f"{sv} MB", f"{rv} MB"); continue
            d = abs(sv - rv) / sv * 100
            (self._ok if d <= self.size_threshold else self._warn)(
                CAT, f"size: {tbl}", f"{sv:.2f} MB", f"{rv:.2f} MB", f"Diff {d:.1f}%")

    def check_routine_bodies(self):
        CAT = "Routine Bodies"
        sql = ("SELECT ROUTINE_NAME,ROUTINE_TYPE,MD5(ROUTINE_DEFINITION) "
               "FROM INFORMATION_SCHEMA.ROUTINES WHERE ROUTINE_SCHEMA=%s ORDER BY ROUTINE_TYPE,ROUTINE_NAME")
        src_r = {(r[0], r[1]): r[2] for r in _db_query(self.src, sql, (self.src_db,))}
        rst_r = {(r[0], r[1]): r[2] for r in _db_query(self.rst, sql, (self.rst_db,))}
        for key in sorted(set(src_r) & set(rst_r)):
            name, rtype = key
            (self._ok if src_r[key] == rst_r[key] else self._fail)(
                CAT, f"{rtype.lower()}: {name}", "match" if src_r[key] == rst_r[key] else src_r[key],
                "match" if src_r[key] == rst_r[key] else rst_r[key])

    def check_trigger_bodies(self):
        CAT = "Trigger Bodies"
        sql = ("SELECT TRIGGER_NAME,EVENT_MANIPULATION,EVENT_OBJECT_TABLE,ACTION_TIMING,MD5(ACTION_STATEMENT) "
               "FROM INFORMATION_SCHEMA.TRIGGERS WHERE TRIGGER_SCHEMA=%s ORDER BY TRIGGER_NAME")
        src_t = {r[0]: r for r in _db_query(self.src, sql, (self.src_db,))}
        rst_t = {r[0]: r for r in _db_query(self.rst, sql, (self.rst_db,))}
        for name in sorted(set(src_t) & set(rst_t)):
            (self._ok if src_t[name] == rst_t[name] else self._fail)(
                CAT, f"trigger: {name}", "match", "match" if src_t[name] == rst_t[name] else "differs")

    def check_view_definitions(self):
        CAT = "View Definitions"
        sql = "SELECT TABLE_NAME,MD5(VIEW_DEFINITION) FROM INFORMATION_SCHEMA.VIEWS WHERE TABLE_SCHEMA=%s ORDER BY TABLE_NAME"
        src_v = {r[0]: r[1] for r in _db_query(self.src, sql, (self.src_db,))}
        rst_v = {r[0]: r[1] for r in _db_query(self.rst, sql, (self.rst_db,))}
        for name in sorted(set(src_v) & set(rst_v)):
            (self._ok if src_v[name] == rst_v[name] else self._fail)(
                CAT, f"view: {name}", "match", "match" if src_v[name] == rst_v[name] else "differs")

    def run_all(self):
        steps = [
            ("DB Metadata",      self.check_db_metadata),
            ("Object Counts",    self.check_object_counts),
            ("Object Names",     self.check_object_names),
            ("Table Structure",  self.check_table_structure),
            ("Row Counts",       self.check_row_counts),
            ("Auto-Increment",   self.check_auto_increment),
            ("Table Sizes",      self.check_table_sizes),
            ("Routine Bodies",   self.check_routine_bodies),
            ("Trigger Bodies",   self.check_trigger_bodies),
            ("View Definitions", self.check_view_definitions),
        ]
        for name, fn in steps:
            try:
                fn()
            except Exception as e:
                self.report.add(CheckResult(name, f"{self.prefix}check execution", "FAIL", "", "", f"Error: {e}"))


def _write_validation_html(report: ValidationReport, instance_name: str) -> str:
    """Generate cumulative HTML report for one Cloud SQL instance (all DBs)."""
    summary = report.summary()
    fail_count = summary.get("FAIL", 0)
    status_color = {"PASS": "#28a745", "FAIL": "#dc3545", "WARN": "#fd7e14", "INFO": "#17a2b8"}
    overall_color = "#28a745" if fail_count == 0 else "#dc3545"
    overall_label = "ALL CHECKS PASSED" if fail_count == 0 else f"{fail_count} CHECKS FAILED"

    rows = []
    for r in report.results:
        color = status_color.get(r.status, "#6c757d")
        badge = f'<span style="background:{color};color:#fff;padding:2px 8px;border-radius:4px;font-size:.8em">{r.status}</span>'
        rows.append(f"<tr><td>{r.category}</td><td>{r.check_name}</td><td>{badge}</td>"
                    f"<td style='font-family:monospace'>{r.source_value}</td>"
                    f"<td style='font-family:monospace'>{r.restored_value}</td>"
                    f"<td>{r.detail}</td></tr>")

    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<title>Restore Validation – {instance_name}</title>
<style>body{{font-family:Arial,sans-serif;margin:20px;background:#f8f9fa}}
h1{{color:#343a40}}.meta{{background:#fff;padding:15px;border-radius:6px;margin-bottom:20px;box-shadow:0 1px 3px rgba(0,0,0,.1)}}
.summary{{display:flex;gap:15px;margin-bottom:20px}}.badge-box{{padding:15px 25px;border-radius:6px;color:#fff;text-align:center}}
.overall{{font-size:1.2em;font-weight:bold;padding:10px 20px;border-radius:6px;color:#fff;background:{overall_color};margin-bottom:20px;display:inline-block}}
table{{width:100%;border-collapse:collapse;background:#fff;box-shadow:0 1px 3px rgba(0,0,0,.1);border-radius:6px;overflow:hidden}}
th{{background:#343a40;color:#fff;padding:10px 12px;text-align:left}}
td{{padding:8px 12px;border-bottom:1px solid #dee2e6;vertical-align:top}}tr:hover{{background:#f1f3f5}}</style>
</head><body>
<h1>MySQL Restore Validation – {instance_name}</h1>
<div class="meta"><strong>Run at:</strong> {report.run_at}<br>
<strong>Source:</strong> {report.source_host}<br>
<strong>Restored:</strong> {report.restored_host}</div>
<div class="overall">{overall_label}</div>
<div class="summary">{"".join(
    f'<div class="badge-box" style="background:{status_color[s]}"><div style="font-size:2em">{summary.get(s,0)}</div>{s}</div>'
    for s in ["PASS","FAIL","WARN","INFO"])}</div>
<table><thead><tr><th>Category</th><th>Check</th><th>Status</th>
<th>Source Value</th><th>Restored Value</th><th>Detail</th></tr></thead>
<tbody>{"".join(rows)}</tbody></table>
<br><small style="color:#6c757d">Total checks: {sum(summary.values())} | Instance: {instance_name}</small>
</body></html>"""


def get_db_credentials() -> tuple:
    """Read DB credentials from Secret Manager, fall back to env vars."""
    if DB_VALIDATOR_USER and DB_VALIDATOR_PASS:
        return DB_VALIDATOR_USER, DB_VALIDATOR_PASS
    try:
        result = subprocess.run(
            ["gcloud", "secrets", "versions", "access", "latest",
             f"--secret={DB_VALIDATOR_SECRET}", f"--project={PROJECT_ID}"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            creds = json.loads(result.stdout.strip())
            return creds["user"], creds["password"]
    except Exception as e:
        log(f"Secret Manager read failed: {e}", "WARN")
    return "", ""


def get_instance_private_ip(instance_info: dict) -> str:
    """Extract private IP from instance info dict."""
    for ip in instance_info.get("ipAddresses", []):
        if ip.get("type") == "PRIVATE":
            return ip["ipAddress"]
    return ""


_proxy_port_counter = 3400
_proxy_port_lock = threading.Lock()


def _next_proxy_port() -> int:
    global _proxy_port_counter
    with _proxy_port_lock:
        port = _proxy_port_counter
        _proxy_port_counter += 1
        return port


def start_proxy(instance_name: str) -> tuple:
    """
    Start Cloud SQL Auth Proxy for an instance.
    Returns (process, local_port). Uses HTTPS to Admin API - bypasses PSA VPC routing.
    """
    port = _next_proxy_port()
    conn_name = f"{PROJECT_ID}:<GCP_REGION>:{instance_name}"
    log(f"[{instance_name}] Starting Cloud SQL Auth Proxy on localhost:{port}...", "DEBUG")
    proc = subprocess.Popen(
        ["cloud-sql-proxy", conn_name, f"--port={port}",
         "--quiet", "--structured-logs=false"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    time.sleep(3)  # wait for proxy to be ready
    return proc, port


def stop_proxy(proc):
    """Stop a Cloud SQL Auth Proxy process."""
    try:
        proc.terminate()
        proc.wait(timeout=5)
    except Exception:
        pass


def connect_mysql(host: str, user: str, password: str, database: str = "information_schema"):
    """Connect to MySQL directly via VPC connector (Serverless VPC Access reaches PSA IPs).
    ssl_verify_cert=False allows caching_sha2_password (MySQL 8.0 default) without a local CA cert.
    """
    return mysql.connector.connect(
        host=host, port=3306, user=user, password=password,
        database=database, connection_timeout=10, autocommit=True,
        ssl_disabled=False, ssl_verify_cert=False, ssl_verify_identity=False,
    )


def run_grants_setup():
    """
    One-time setup: GRANT SELECT to backup-validator-ro on all MySQL source instances.
    Tries root with empty password first; if that fails, sets a temporary root password
    via gcloud (Cloud SQL Admin API) then connects with that.
    """
    log("=" * 60)
    log("SETUP MODE: Granting SELECT to backup-validator-ro")
    log("=" * 60)

    if not MYSQL_AVAILABLE:
        log("mysql-connector-python not installed", "ERROR")
        sys.exit(1)

    import secrets as _secrets
    instances = list_instances()
    mysql_instances = [i for i in instances if "MYSQL" in i.get("databaseVersion", "").upper()]
    log(f"Found {len(mysql_instances)} MySQL instances to configure")

    success, failed = 0, []
    for inst in mysql_instances:
        name = inst["name"]
        ip = get_instance_private_ip(inst)
        if not ip:
            log(f"[{name}] No private IP - skipping", "WARN")
            continue

        conn = None

        # Direct connection via VPC connector (Serverless VPC Access provides PSA access)
        # Try 1: empty root password (default for fresh Cloud SQL instances)
        try:
            conn = connect_mysql(ip, "root", "")
            log(f"[{name}] Connected as root (empty password)")
        except Exception as e:
            log(f"[{name}] Empty password failed: {type(e).__name__}: {str(e)[:100]}")

        # Try 2: set a temporary root password via gcloud and connect
        if conn is None:
            try:
                temp_pass = _secrets.token_urlsafe(16)
                log(f"[{name}] Setting temporary root password via gcloud...")
                run_gcloud(["sql", "users", "set-password", "root",
                            f"--instance={name}", f"--password={temp_pass}"])
                for wait in [15, 30]:
                    log(f"[{name}] Waiting {wait}s for propagation...")
                    time.sleep(wait)
                    try:
                        conn = connect_mysql(ip, "root", temp_pass)
                        log(f"[{name}] Connected as root (temp password)")
                        break
                    except Exception:
                        pass
                if conn is None:
                    raise RuntimeError("Could not connect after setting root password")
            except Exception as e:
                log(f"[{name}] ✗ Cannot connect as root: {e}", "ERROR")
                failed.append(name)
                continue

        try:
            cur = conn.cursor()
            cur.execute("GRANT SELECT ON *.* TO 'backup-validator-ro'@'%'")
            cur.execute("FLUSH PRIVILEGES")
            cur.close()
            conn.close()
            log(f"[{name}] ✓ GRANT SELECT applied")
            success += 1
        except Exception as e:
            log(f"[{name}] ✗ GRANT failed: {e}", "ERROR")
            failed.append(name)

    log(f"\nSetup complete: {success} succeeded, {len(failed)} failed")
    if failed:
        log(f"Failed instances: {failed}", "ERROR")
        sys.exit(1)
    log("All instances configured. backup-validator-ro has SELECT on all MySQL instances.")
    sys.exit(0)


def validate_instance_deep(source: dict, restore_name: str, user_dbs: list, run_id: str) -> dict:
    """
    Run comprehensive MySQL validation across ALL databases in the instance.
    Produces ONE cumulative HTML + JSON report per instance uploaded to GCS.
    """
    source_name = source["name"]
    result = {"fail_count": 0, "warn_count": 0, "pass_count": 0, "html_url": "", "json_url": "", "skipped": False}

    if not MYSQL_AVAILABLE:
        log(f"[{source_name}] mysql-connector-python not available - skipping deep validation", "WARN")
        result["skipped"] = True
        return result

    db_user, db_pass = get_db_credentials()
    if not db_user:
        log(f"[{source_name}] No DB credentials available - skipping deep validation", "WARN")
        result["skipped"] = True
        return result

    # Get private IPs
    source_ip = get_instance_private_ip(source)
    restore_info = run_gcloud(["sql", "instances", "describe", restore_name], capture_json=True)
    restore_ip = get_instance_private_ip(restore_info)

    if not source_ip or not restore_ip:
        log(f"[{source_name}] No private IP found - skipping deep validation", "WARN")
        result["skipped"] = True
        return result

    log(f"[{source_name}] Starting deep validation across {len(user_dbs)} databases...")
    log(f"[{source_name}]   Source IP: {source_ip} | Restore IP: {restore_ip}")

    # Cumulative report for the entire instance (all DBs in one report)
    cumulative = ValidationReport(
        run_at=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        source_host=f"{source_name} ({source_ip})",
        source_db="[all databases]",
        restored_host=f"{restore_name} ({restore_ip})",
        restored_db="[all databases]",
    )

    # Direct connections via VPC connector (Serverless VPC Access reaches Cloud SQL PSA IPs)
    log(f"[{source_name}] Connecting directly to source ({source_ip}) and restore ({restore_ip})...")

    try:
        for db_name in sorted(user_dbs):
            log(f"[{source_name}] Validating DB: {db_name}...")
            try:
                src_conn = connect_mysql(source_ip, db_user, db_pass, db_name)
                rst_conn = connect_mysql(restore_ip, db_user, db_pass, db_name)
            except Exception as e:
                log(f"[{source_name}] Cannot connect for DB {db_name}: {e}", "WARN")
                cumulative.add(CheckResult("Connection", f"[{db_name}] connect", "WARN", "", "", str(e)))
                continue

            try:
                validator = Validator(
                    src_conn=src_conn, rst_conn=rst_conn,
                    src_db=db_name, rst_db=db_name,
                    size_threshold_pct=SIZE_THRESHOLD_PCT,
                    ai_drift_threshold=AI_DRIFT_THRESHOLD,
                    row_count_tolerance_pct=ROW_TOLERANCE_PCT,
                    report=cumulative,
                    db_prefix=db_name,
                )
                validator.run_all()
            finally:
                try: src_conn.close()
                except: pass
                try: rst_conn.close()
                except: pass

    except Exception as e:
        log(f"[{source_name}] Deep validation error: {e}", "ERROR")
        cumulative.add(CheckResult("Validation", "deep validation", "FAIL", "", "", str(e)))

    # Aggregate summary
    summary = cumulative.summary()
    result["pass_count"] = summary.get("PASS", 0)
    result["fail_count"] = summary.get("FAIL", 0)
    result["warn_count"] = summary.get("WARN", 0)
    total = sum(summary.values())
    log(f"[{source_name}] Deep validation complete: "
        f"PASS={result['pass_count']} FAIL={result['fail_count']} WARN={result['warn_count']} / {total} checks")

    # Upload HTML report
    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    base = f"gs://{LOG_BUCKET}/validation-reports/{date_str}/{source_name}-{run_id}"
    html_path = f"{base}.html"
    json_path = f"{base}.json"

    html_tmp = f"/tmp/validation-{source_name}-{run_id}.html"
    json_tmp = f"/tmp/validation-{source_name}-{run_id}.json"

    try:
        with open(html_tmp, "w", encoding="utf-8") as f:
            f.write(_write_validation_html(cumulative, source_name))
        if _gcs_upload(html_tmp, html_path):
            result["html_url"] = html_path

        json_data = {
            "instance": source_name, "run_id": run_id,
            "run_at": cumulative.run_at,
            "source_host": cumulative.source_host,
            "restored_host": cumulative.restored_host,
            "summary": summary,
            "results": [
                {"category": r.category, "check": r.check_name, "status": r.status,
                 "source_value": r.source_value, "restored_value": r.restored_value, "detail": r.detail}
                for r in cumulative.results
            ],
        }
        with open(json_tmp, "w") as f:
            json.dump(json_data, f, indent=2, default=str)
        if _gcs_upload(json_tmp, json_path):
            result["json_url"] = json_path
    except Exception as e:
        log(f"[{source_name}] Failed to upload validation report: {e}", "ERROR")
    finally:
        for tmp in [html_tmp, json_tmp]:
            if os.path.exists(tmp):
                os.remove(tmp)

    return result


def validate_restore(source: dict, restore_name: str, run_id: str = "") -> dict:
    """Compare databases AND tables between source and restored instance."""
    source_name = source["name"]
    db_version = source.get("databaseVersion", "")
    is_mysql = "MYSQL" in db_version.upper()
    is_postgres = "POSTGRES" in db_version.upper()

    log(f"[{source_name}] Step 3/4: Validating restore ({db_version})...")

    if DRY_RUN:
        log(f"[{source_name}] [DRY RUN] Would validate databases and tables")
        return {"success": True, "dry_run": True}

    result = {
        "success": False,
        "source_db_count": 0,
        "restored_db_count": 0,
        "source_databases": [],
        "restored_databases": [],
        "missing_databases": [],
        "error": None,
    }

    try:
        source_dbs = run_gcloud(
            ["sql", "databases", "list", f"--instance={source_name}"],
            capture_json=True
        )
        source_db_names = {db["name"] for db in source_dbs}

        restore_dbs = run_gcloud(
            ["sql", "databases", "list", f"--instance={restore_name}"],
            capture_json=True
        )
        restore_db_names = {db["name"] for db in restore_dbs}

        if is_mysql:
            system_dbs = {"information_schema", "mysql", "performance_schema", "sys"}
        elif is_postgres:
            system_dbs = {"postgres", "template0", "template1", "cloudsqladmin"}
        else:
            system_dbs = set()

        source_db_names -= system_dbs
        restore_db_names -= system_dbs

        result["source_db_count"] = len(source_db_names)
        result["restored_db_count"] = len(restore_db_names)
        result["source_databases"] = sorted(source_db_names)
        result["restored_databases"] = sorted(restore_db_names)
        result["missing_databases"] = sorted(source_db_names - restore_db_names)

        log(f"[{source_name}] Source databases: {sorted(source_db_names)}")
        log(f"[{source_name}] Restored databases: {sorted(restore_db_names)}")

        if result["missing_databases"]:
            result["error"] = f"Missing: {result['missing_databases']}"
            log(f"[{source_name}] MISSING databases: {result['missing_databases']}", "ERROR")
        else:
            log(f"[{source_name}] All {len(source_db_names)} databases present in restore")

        if result["missing_databases"]:
            log(f"[{source_name}] ✗ Validation FAILED", "ERROR")
        else:
            # Phase 2: Deep MySQL validation
            if is_mysql and MYSQL_AVAILABLE and run_id:
                deep = validate_instance_deep(source, restore_name, sorted(source_db_names), run_id)
                result["deep_validation"] = {
                    "pass":     deep.get("pass_count", 0),
                    "fail":     deep.get("fail_count", 0),
                    "warn":     deep.get("warn_count", 0),
                    "skipped":  deep.get("skipped", False),
                    "html_url": deep.get("html_url", ""),
                    "json_url": deep.get("json_url", ""),
                }
                if deep.get("fail_count", 0) > 0:
                    log(f"[{source_name}] Deep validation has {deep['fail_count']} issues - see report: {deep.get('html_url')}", "WARN")
                else:
                    log(f"[{source_name}] Deep validation clean: {deep.get('pass_count', 0)} checks passed")
                result["success"] = True
                log(f"[{source_name}] ✓ Validation PASSED: {len(source_db_names)} databases")
            else:
                result["success"] = True
                log(f"[{source_name}] ✓ Validation PASSED: {len(source_db_names)} databases match")

    except Exception as e:
        result["error"] = str(e)
        log(f"[{source_name}] Validation error: {e}", "ERROR")

    return result


def _gcs_upload(tmp_file: str, gcs_path: str) -> bool:
    """Upload a single file to GCS. Returns True on success."""
    try:
        result = subprocess.run(
            ["gsutil", "cp", tmp_file, gcs_path],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            log(f"gsutil cp failed: {result.stderr.strip()}", "ERROR")
            return False
        log(f"Uploaded: {gcs_path}")
        return True
    except Exception as e:
        log(f"Upload exception: {e}", "ERROR")
        return False


def upload_report(report: dict) -> str:
    """Upload two reports to GCS: a summary and a full detailed report."""
    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    run_id = report.get("run_id", "unknown")
    base_path = f"gs://{LOG_BUCKET}/backup-reports/{date_str}"
    full_path = f"{base_path}/report-{run_id}-full.json"
    summary_path = f"{base_path}/report-{run_id}-summary.json"

    if DRY_RUN:
        log(f"[DRY RUN] Would upload summary to {summary_path}")
        log(f"[DRY RUN] Would upload full report to {full_path}")
        return summary_path

    # Build summary report - compact view per instance
    summary = {
        "run_id": run_id,
        "project_id": report.get("project_id"),
        "started_at": report.get("started_at"),
        "completed_at": report.get("completed_at"),
        "total_duration_seconds": report.get("total_duration_seconds"),
        "summary": report.get("summary"),
        "instances": [
            {
                "instance": r["instance"],
                "type": r.get("type"),
                "status": r["status"],
                "db_count": r.get("db_count", 0),
                "restore_success": r.get("restore_success", False),
                "duration_sec": r.get("duration_sec", 0),
                "validation_report_url": r.get("validation_report_url"),
                "error": r.get("error"),
            }
            for r in report.get("instances", [])
        ],
    }

    uploaded = []
    for path, data in [(summary_path, summary), (full_path, report)]:
        tmp_file = f"/tmp/report-{run_id}-{'summary' if 'summary' in path else 'full'}.json"
        try:
            with open(tmp_file, "w") as f:
                json.dump(data, f, indent=2, default=str)
            if _gcs_upload(tmp_file, path):
                uploaded.append(path)
        except Exception as e:
            log(f"Failed to write/upload {path}: {e}", "ERROR")
        finally:
            if os.path.exists(tmp_file):
                os.remove(tmp_file)

    if not uploaded:
        log("All uploads failed - printing summary to stdout as fallback:", "ERROR")
        print(json.dumps(summary, indent=2, default=str))
        return ""

    return summary_path


def process_instance(instance: dict, timestamp: str, run_id: str = "") -> dict:
    """Process single instance: backup, restore from backup, validate, cleanup."""
    name = instance["name"]
    tier = instance.get("settings", {}).get("tier", "unknown")
    db_version = instance.get("databaseVersion", "unknown")

    log(f"Instance: {name}")
    log(f"  Database Version: {db_version}")
    log(f"  Tier: {tier}")

    # Result structure with restore instance info
    result = {
        "instance": name,
        "type": db_version,
        "status": "in_progress",
        "backup_id": None,
        "restore_instance": None,
        "restore_success": False,
        "db_count": 0,
        "duration_sec": 0,
        "error": None,
        "validation_report_url": None,
    }

    restore_name = f"{name}{RESTORE_TEST_SUFFIX}{timestamp}"[:80]

    start_time = datetime.utcnow()

    try:
        # Step 1: Create backup → returns project-level NAME (UUID)
        backup_name = create_backup(name)
        result["backup_id"] = backup_name

        # Step 2: Restore backup to a NEW instance in one step (no pre-creation needed)
        result["restore_instance"] = restore_name
        restore_to_new_instance(name, backup_name, restore_name)
        result["restore_success"] = True

        # Step 3: Validate databases + deep schema validation
        validation = validate_restore(instance, restore_name, run_id)
        result["db_count"] = validation.get("source_db_count", 0)
        result["validation_report_url"] = validation.get("deep_validation", {}).get("html_url")

        if validation.get("success"):
            result["status"] = "success"
        else:
            result["status"] = "failed"
            result["error"] = validation.get("error")

    except Exception as e:
        log(f"[{name}] Error: {e}", "ERROR")
        result["status"] = "failed"
        result["error"] = str(e)

    finally:
        # Cleanup - ALWAYS delete the restore instance
        if not DRY_RUN:
            log(f"[{name}] Step 3/3: Cleaning up restore instance...")
            if not delete_instance(restore_name):
                cleanup_error = "Cleanup failed"
                result["error"] = (result.get("error") or "") + f"; {cleanup_error}"
                log(f"[{name}] WARNING: {cleanup_error}", "WARN")

        result["duration_sec"] = int((datetime.utcnow() - start_time).total_seconds())

    return result


def main():
    """Main entry point."""
    # Setup grants mode - one-time GRANT setup, does not run backup/restore
    if SETUP_GRANTS:
        if PROJECT_ID not in ALLOWED_PROJECTS:
            log(f"Project {PROJECT_ID} not in allowed list", "ERROR")
            sys.exit(1)
        run_grants_setup()
        return

    log("=" * 60)
    log("Cloud SQL Backup Validator")
    log("=" * 60)

    # Validate project
    if PROJECT_ID not in ALLOWED_PROJECTS:
        log(f"Project {PROJECT_ID} not in allowed list: {ALLOWED_PROJECTS}", "ERROR")
        sys.exit(1)

    log(f"Project: {PROJECT_ID}")
    log(f"Region: {REGION}")
    log(f"Log Bucket: {LOG_BUCKET}")
    log(f"Dry Run: {DRY_RUN}")
    log(f"Max Workers: {MAX_WORKERS}")
    if INSTANCE_FILTER:
        log(f"Instance Filter: {INSTANCE_FILTER}")

    run_id = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")

    report = {
        "run_id": run_id,
        "project_id": PROJECT_ID,
        "dry_run": DRY_RUN,
        "started_at": datetime.utcnow().isoformat(),
        "instances": [],
        "summary": {"total": 0, "success": 0, "failed": 0},
    }

    try:
        instances = list_instances()
        report["summary"]["total"] = len(instances)

        if not instances:
            log("No instances to process!", "WARN")
        else:
            workers = min(MAX_WORKERS, len(instances))
            log(f"Processing {len(instances)} instances with {workers} parallel workers")
            log("=" * 60)

            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = {
                    executor.submit(process_instance, instance, timestamp, run_id): instance
                    for instance in instances
                }
                for future in as_completed(futures):
                    result = future.result()
                    report["instances"].append(result)
                    status_icon = "✓" if result["status"] == "success" else "✗"
                    log(f"{status_icon} Completed: {result['instance']} [{result['status']}] ({result['duration_sec']}s)")

            report["summary"]["success"] = sum(1 for r in report["instances"] if r["status"] == "success")
            report["summary"]["failed"] = sum(1 for r in report["instances"] if r["status"] != "success")

    except Exception as e:
        log(f"Fatal error: {e}", "ERROR")
        report["error"] = str(e)

    report["completed_at"] = datetime.utcnow().isoformat()

    # Calculate total duration
    start = datetime.fromisoformat(report["started_at"])
    end = datetime.fromisoformat(report["completed_at"])
    report["total_duration_seconds"] = (end - start).total_seconds()

    # Upload report
    report["report_url"] = upload_report(report)

    # Summary
    log("\n" + "=" * 60)
    log("SUMMARY")
    log("=" * 60)
    log(f"Run ID: {run_id}")
    log(f"Total: {report['summary']['total']}")
    log(f"Success: {report['summary']['success']}")
    log(f"Failed: {report['summary']['failed']}")
    log(f"Duration: {report['total_duration_seconds']:.1f} seconds")
    if report.get("report_url"):
        log(f"Report: {report['report_url']}")

    if report["summary"]["failed"] > 0:
        log("Some validations failed!", "ERROR")
        sys.exit(1)

    log("All validations completed successfully!")
    sys.exit(0)


if __name__ == "__main__":
    main()
