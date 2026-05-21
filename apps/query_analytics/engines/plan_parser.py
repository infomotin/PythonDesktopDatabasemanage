"""
query_analytics.engines.plan_parser
-------------------------------------
Parses raw EXPLAIN / EXPLAIN ANALYZE text from PostgreSQL and MySQL,
and produces a structured JSON plan consumed by the UI and the
index/optimisation engines.
"""
from __future__ import annotations

import re
import json
from typing import Any, Dict, List


# ---------------------------------------------------------------------------
# PostgreSQL parser
# ---------------------------------------------------------------------------
def parse_postgres_plan(raw: str) -> Dict[str, Any]:
    """
    Accepts the *text* tabular output of ``EXPLAIN (ANALYZE, COSTS, VERBOSE, BUFFERS)``
    and turns it into the canonical plan JSON.
    """
    lines = raw.strip().splitlines()
    plan_lines = [l for l in lines if l.strip() and not l.startswith("-")]
    steps: List[Dict[str, Any]] = []
    for line in plan_lines:
        step: Dict[str, Any] = {"raw": line}

        # ── operation (left-indented token) ─────────────────────────
        op_match = re.match(r"(\s*)(\w[\w\s\(\)]+)", line)
        if op_match:
            step["operation"] = op_match.group(2).strip()
            step["depth"] = len(op_match.group(1))

        # ── cost `cost=x..y` ────────────────────────────────────────
        cost_m = re.search(r"cost=([\d.]+)\.\.([\d.]+)", line)
        if cost_m:
            step["cost_start"] = float(cost_m.group(1))
            step["cost_end"]   = float(cost_m.group(2))

        # ── width ──────────────────────────────────────────────────
        width_m = re.search(r"width=([\d.]+)", line)
        if width_m:
            step["width"] = float(width_m.group(1))

        # ── actual rows / loops ─────────────────────────────────────
        rows_m = re.search(r"rows=(\d+)\s+loops=(\d+)", line)
        if rows_m:
            step["actual_rows"] = int(rows_m.group(1))
            step["loops"]      = int(rows_m.group(2))

        # ── actual time `actual time=x..y` ──────────────────────────
        atime_m = re.search(r"actual time=([\d.]+)\.\.([\d.]+)", line)
        if atime_m:
            step["actual_time_ms"] = [float(atime_m.group(1)), float(atime_m.group(2))]

        # ── trigger ────────────────────────────────────────────────
        if "(Trigger)" in line:
            step["has_trigger"] = True

        steps.append(step)

    top = steps[0] if steps else {}
    return {
        "engine": "postgresql",
        "top_operation": top.get("operation", ""),
        "steps": steps,
        "total_cost": top.get("cost_end", 0),
        "actual_time_ms": top.get("actual_time_ms", [0, 0]),
    }


# ---------------------------------------------------------------------------
# MySQL parser
# ---------------------------------------------------------------------------
def parse_mysql_plan(raw: str) -> Dict[str, Any]:
    """
    Accepts the tabular output of ``EXPLAIN`` / ``EXPLAIN EXTENDED`` for MySQL.
    """
    lines = raw.strip().splitlines()
    steps: List[Dict[str, Any]] = []

    # Locate header row
    header_idx = None
    for i, ln in enumerate(lines):
        if "id" in ln and "select_type" in ln and "table" in ln:
            header_idx = i
            break
    if header_idx is None:
        return {"engine": "mysql", "steps": [], "total_cost": 0}

    separators = ("id", "select_type", "table", "partitions", "type", "possible_keys",
                  "key", "key_len", "ref", "rows", "filtered", "Extra")
    col_widths = []
    if header_idx + 1 < len(lines):
        sep_line = lines[header_idx + 1]
        col_widths = [len(m.group()) for m in re.finditer(r"-+", sep_line)]

    data_lines = lines[header_idx + 1:]
    for ln in data_lines:
        if not ln.strip() or set(ln.strip()) <= {"-", " "}:
            continue
        step: Dict[str, Any] = {"raw": ln}

        def _field(idx):
            if idx < len(col_widths):
                start = sum(col_widths[:idx]) + idx
                end   = start + col_widths[idx]
                return ln[start:end].strip()
            return ""

        step["id"]           = _field(0)
        step["select_type"]  = _field(1)
        step["table"]        = _field(2)
        step["partitions"]   = _field(3)
        step["access_type"]  = _field(4)
        step["possible_keys"]= _field(5)
        step["key_used"]     = _field(6)
        step["key_len"]      = _field(7)
        step["ref"]          = _field(8)
        step["rows_est"]     = _field(9)
        step["filtered"]     = _field(10)
        step["extra"]        = _field(11)
        step["has_index"]    = bool(step["key_used"])
        steps.append(step)

    rows_est_sum = sum(int(s["rows_est"]) for s in steps if s.get("rows_est", "").isdigit())
    return {
        "engine": "mysql",
        "steps": steps,
        "total_cost": float(rows_est_sum),
        "estimated_rows": rows_est_sum,
        "used_indexes": [s["key_used"] for s in steps if s.get("key_used")],
    }


# ---------------------------------------------------------------------------
# Oracle parser (simple token extraction)
# ---------------------------------------------------------------------------
def parse_oracle_plan(raw: str) -> Dict[str, Any]:
    steps: List[Dict[str, Any]] = []
    for line in raw.strip().splitlines():
        if not line.strip():
            continue
        steps.append({"operation": line.strip(), "raw": line})
    return {
        "engine": "oracle",
        "steps": steps,
        "total_cost": 0,
    }


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------
_ENGINE_PARSERS = {
    "postgresql": parse_postgres_plan,
    "cockroachdb": parse_postgres_plan,
    "mysql":      parse_mysql_plan,
    "mariadb":    parse_mysql_plan,
    "oracle":     parse_oracle_plan,
    "sqlite":     parse_mysql_plan,          # SQLite EXPLAIN is one-row
}


def parse(raw_plan: str, engine: str) -> Dict[str, Any]:
    parser = _ENGINE_PARSERS.get(engine.lower(), lambda r: {"raw": r, "steps": []})
    return parser(raw_plan)


def to_json(raw_plan: str, engine: str) -> str:
    return json.dumps(parse(raw_plan, engine))
