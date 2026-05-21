"""Index Recommendation Engine — analyses slow queries and generates
database-specific index DDL suggestions."""

import re
from collections import Counter

from django.db import models
from django.utils import timezone


ENGINE_INDEX_MAP = {
    "mysql": {
        "default": "BTREE",
        "types": {"btree": "USING BTREE", "hash": "USING HASH", "fulltext": "FULLTEXT"},
    },
    "mariadb": {
        "default": "BTREE",
        "types": {"btree": "USING BTREE", "hash": "USING HASH", "fulltext": "FULLTEXT"},
    },
    "postgresql": {
        "default": "BTREE",
        "types": {"btree": "USING BTREE", "hash": "USING HASH",
                  "gin": "USING GIN", "gist": "USING GIST",
                  "brin": "USING BRIN"},
    },
    "cockroachdb": {
        "default": "BTREE",
        "types": {"btree": "USING BTREE", "hash": "USING HASH", "inverted": "INVERTED"},
    },
    "sqlserver": {
        "default": "CLUSTERED",
        "types": {"clustered": "CLUSTERED", "nonclustered": "NONCLUSTERED"},
    },
    "oracle": {
        "default": "BTREE",
        "types": {"btree": "", "bitmap": "BITMAP"},
    },
}


def _extract_where_columns(sql: str) -> list:
    """Extract column names from WHERE clauses."""
    upper = sql.upper()
    m = re.search(r'\bWHERE\b(.+?)(?:GROUP BY|ORDER BY|LIMIT|\Z)', upper, re.DOTALL)
    if not m:
        return []
    clause = m.group(1)
    cols = re.findall(r'(\b\w+)\.(\w+)\s*(?:=|<>|!=|>|<|>=|<=|\s+IN\s+|\s+LIKE\s+|\s+IS\s+)', clause)
    unique = []
    seen = set()
    for tbl, col in cols:
        key = f"{tbl.lower()}.{col.lower()}"
        if key not in seen:
            seen.add(key)
            unique.append(col)
    return unique


def _extract_order_by_columns(sql: str) -> list:
    m = re.search(r'\bORDER BY\b(.+?)(?:LIMIT|\Z)', sql, re.IGNORECASE | re.DOTALL)
    if not m:
        return []
    return re.findall(r'(\w+)', m.group(1))


def _extract_group_by_columns(sql: str) -> list:
    m = re.search(r'\bGROUP BY\b(.+?)(?:ORDER BY|LIMIT|\Z)', sql, re.IGNORECASE | re.DOTALL)
    if not m:
        return []
    return re.findall(r'(\w+)', m.group(1))


def _extract_join_columns(sql: str) -> list:
    joins = re.findall(r'\bJOIN\s+\w+\s+(?:ON|USING)\s+(?:.+?)(\w+)\.(\w+)', sql, re.IGNORECASE)
    return [col for _, col in joins]


def _guess_index_type(engine: str, columns: list, where_cols: list) -> str:
    engine = engine.lower()
    if engine in ("postgresql", "cockroachdb"):
        # GiST for pattern-matching columns, GIN for array/jsonb, BTREE default
        if any(c.lower() in ("tags", "data", "payload", "json", "meta") for c in columns):
            return "GIN"
        return "BTREE"
    elif engine in ("mysql", "mariadb"):
        if len(columns) > 5:
            return "FULLTEXT"
        return "BTREE"
    elif engine == "sqlserver":
        return "NONCLUSTERED"
    elif engine == "oracle":
        return "BTREE"
    return "BTREE"


def generate_recommendations(
    user,
    engine: str,
    database_name: str,
    slow_metrics: list,
    existing_indexes: dict = None,
    threshold_ms: float = 500.0,
) -> list:
    """Return a list of unsaved IndexRecommendation objects."""
    existing_indexes = existing_indexes or {}
    recs = []
    table_counter: Counter = Counter()

    for metric in slow_metrics:
        sql = metric.raw_sql
        where_cols = _extract_where_columns(sql)
        order_cols = _extract_order_by_columns(sql)
        group_cols = _extract_group_by_columns(sql)
        join_cols = _extract_join_columns(sql)

        # store table candidates from join columns
        all_cols = list(dict.fromkeys(where_cols + order_cols + group_cols + join_cols))

        # naive table name extraction from FROM/JOIN
        table_matches = re.findall(r'FROM\s+(\w+)', sql, re.IGNORECASE)
        join_matches = re.findall(r'\bJOIN\s+(\w+)', sql, re.IGNORECASE)
        tables = list(dict.fromkeys(table_matches + join_matches))

        if not tables or not all_cols:
            continue

        for table in tables:
            key = f"{database_name}.{table}"
            existing = set(existing_indexes.get(key, []))

            # compose candidate column set
            candidate_cols = []
            for c in all_cols:
                if c.lower() not in existing:
                    candidate_cols.append(c)
                if len(candidate_cols) >= 3:
                    break

            if not candidate_cols:
                continue

            if table.lower() in table_counter:
                continue
            table_counter[table.lower()] += 1

            idx_type = _guess_index_type(engine, candidate_cols, where_cols)
            type_map = ENGINE_INDEX_MAP.get(engine.lower(), {}).get("types", {})
            idx_hint = type_map.get(idx_type.lower(), "")

            col_list = ", ".join(f"`{c}`" for c in candidate_cols)
            ddl = f"CREATE INDEX idx_{table}_{'_'.join(candidate_cols[:2])} ON `{table}` ({col_list}){idx_hint};"

            score = min(100, int(
                (60 if where_cols else 0)
                + (20 if order_cols else 0)
                + (10 if join_cols else 0)
                + 10
            ))
            improvement = min(95, score * 0.95)

            rationale_parts = []
            if where_cols:
                rationale_parts.append(f"Columns used in WHERE: {', '.join(where_cols)}")
            if order_cols:
                rationale_parts.append(f"ORDER BY on: {', '.join(order_cols)}")
            if join_cols:
                rationale_parts.append(f"JOIN columns: {', '.join(join_cols)}")

            recs.append(IndexRecommendation(
                user=user,
                database_engine=engine,
                database_name=database_name,
                table_name=table,
                column_names=candidate_cols,
                index_type=idx_type,
                suggested_ddl=ddl,
                rationale="; ".join(rationale_parts) if rationale_parts else f"Columns "
                                                                                  "appear frequently in "
                                                                                  "query predicates.",
                score=score,
                estimated_improvement_pct=improvement,
                based_on_slow_queries=len(slow_metrics),
                priority="high" if score >= 70 else "medium",
            ))

    recs.sort(key=lambda r: -r.score)
    return recs
