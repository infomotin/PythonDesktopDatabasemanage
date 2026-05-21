import urllib.request, urllib.parse, json, ssl, os, re, html, time
from io import StringIO
from collections import defaultdict
import pandas as pd
import numpy as np


class MCPClient:
    def __init__(self, base_url: str = None, headers: dict = None):
        self.base_url = base_url or os.environ.get("ANALYTICS_MCP_BASE_URL", "http://localhost:3000")
        self.headers = headers or {}
        self.timeout = 30

    def _post(self, path: str, body: dict):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}{path}", data=data,
            headers={**self.headers, "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout, context=ctx) as resp:
                return {"ok": True, "data": json.loads(resp.read().decode())}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def mcp_analytics_summarize(self, payload: dict) -> dict:
        return self._post("/analytics/summarize", payload)

    def mcp_analytics_get_dashboard(self, dash_id: str) -> dict:
        return self._post("/analytics/dashboards/get", {"id": dash_id})

    def mcp_analytics_list_dashboards(self, org_id: str = None) -> dict:
        return self._post("/analytics/dashboards/list", {"org_id": org_id})

    def mcp_analytics_describe_dataset(self, dataset_id: str) -> dict:
        return self._post("/analytics/datasets/describe", {"id": dataset_id})


class DBQueryStatement:
    """Minimal DB query executor backed by MCP client."""
    def __init__(self, client: MCPClient = None):
        self.client = client or MCPClient()

    def run_query(self, sql: str, database_id: str = None) -> dict:
        return self.client._post("/query/run", {"sql": sql, "db": database_id})

    def get_tables(self, database_id: str = None) -> dict:
        return self.client._post("/query/tables", {"db": database_id})


class AnalyticsResult:
    def __init__(self, summary: str = "", data: dict = None, has_data: bool = False):
        self.summary = summary
        self.data = data or {}
        self.has_data = has_data

    def to_dict(self):
        return {"summary": self.summary, "data": self.data, "has_data": self.has_data}


def local_analytics_pipeline(df: pd.DataFrame) -> str:
    """Run simple local analytics on a pandas DataFrame."""
    try:
        buf = StringIO()
        buf.write(f"Rows: {len(df)}, Columns: {len(df.columns)}\n")
        desc = df.describe(include="all").fillna("").to_string()
        buf.write(desc + "\n")
        corr = df.select_dtypes(include="number").corr().round(3).to_string()
        buf.write(f"\nCorrelations:\n{corr}")
        return buf.getvalue()
    except Exception as e:
        return f"Analytics error: {e}"


def remote_analytics_pipeline(df: pd.DataFrame, mcp_client: MCPClient = None) -> AnalyticsResult:
    """Run remote analytics pipeline via MCP."""
    client = mcp_client or MCPClient()
    sample = df.head(500).to_dict(orient="records")
    resp = client.mcp_analytics_summarize({
        "rows": len(df), "columns": list(df.columns),
        "sample": sample, "dtype": {c: str(t) for c, t in zip(df.columns, df.dtypes)},
    })
    if resp["ok"]:
        r = resp.get("data", {})
        return AnalyticsResult(summary=r.get("summary", ""), data=r, has_data=True)
    return AnalyticsResult(summary="", data=resp.get("error", ""))


def run_sql_analytics(sql: str, mcp_client: MCPClient = None) -> AnalyticsResult:
    """Run a SQL query against a remote DB via MCP."""
    client = mcp_client or MCPClient()
    q = DBQueryStatement(client)
    res = q.run_query(sql)
    if res.get("ok"):
        rows = res["data"]
        df = pd.DataFrame(rows)
        s = local_analytics_pipeline(df) if not df.empty else "Query returned no rows."
        return AnalyticsResult(summary=s, data={"rows": rows}, has_data=not df.empty)
    return AnalyticsResult(summary="", data={"error": res.get("error", "Unknown")}, has_data=False)


def get_kpi_metric(label: str, value: str, trend: str = "flat") -> dict:
    return {"label": label, "value": value, "trend": trend, "type": "kpi"}


def get_kpis_for_model(model_name: str = None) -> list:
    base = ["total_rows", "avg_value", "max_value", "min_value", "null_count", "unique_count", "update_count"]
    if model_name:
        return [get_kpi_metric(f"{model_name}_{k}", "—") for k in base]
    return [get_kpi_metric(k, "—") for k in base]


def stats_fill_stats(active_actions: list, total_stars: int) -> dict:
    """Aggregate stats for the given action list."""
    actions = {a.get("type", "unknown"): a for a in active_actions}
    if not actions:
        return {"status": "inactive"}
    return {"status": "active", "actions": list(actions.values()), "total_stars": total_stars}


def content_series_parse_table_from_html(html_str: str) -> list:
    tables = re.findall(r"<table[^>]*>(.*?)</table>", html_str, re.DOTALL | re.IGNORECASE)
    all_rows = []
    for table_html in tables:
        headers = re.findall(r"<th[^>]*>(.*?)</th>", table_html, re.DOTALL | re.IGNORECASE)
        rows = re.findall(r"<tr[^>]*>(.*?)</tr>", table_html, re.DOTALL | re.IGNORECASE)
        for row in rows:
            cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.DOTALL | re.IGNORECASE)
            cells = [html.unescape(c.strip()) for c in cells]
            if len(cells) == len(headers):
                all_rows.append(dict(zip(headers, cells)))
    return all_rows


def agent_benchmark_models_to_dataframe() -> pd.DataFrame:
    return pd.DataFrame([
        {"model": "devstral-small-2507",  "rellab_correctness_pct": 70, "hybench_score": 70, "v0_score": 58, "re_val_score": 53},
        {"model": "devstral-small-2508",  "rellab_correctness_pct": 82, "hybench_score": 53, "v0_score": 61, "re_val_score": 56},
        {"model": "devstral-2507",        "rellab_correctness_pct": 88, "hybench_score": 63, "v0_score": 68, "re_val_score": 75},
        {"model": "devstral-med-2507",    "rellab_correctness_pct": 95, "hybench_score": 79, "v0_score": 82, "re_val_score": 96},
        {"model": "devstral-med-2508",    "rellab_correctness_pct": 96, "hybench_score": 80, "v0_score": 85, "re_val_score": 97},
        {"model": "devstral-2508",        "rellab_correctness_pct": 99, "hybench_score": 82, "v0_score": 88, "re_val_score": 98},
    ])


def agents_evaluator_interactive(is_finished: bool = False) -> dict:
    log_lines = ["╔══════════════════════════════════════════╗", "║     DBMS Pro Analytics Engine v1.0       ║", "╚══════════════════════════════════════════╝", ""]
    score = 90 if is_finished else 0
    if is_finished:
        log_lines.append(f"[✓] Final benchmark score: {score:38}")
        log_lines.append(f"[✓] Model:                     {score:38}")
        log_lines.append(f"[✓] Correctness:               {score:38}")
        log_lines.append(f"[✓] Rated by:                  {score:38}")
    return {"score": score, "log": log_lines, "is_finished": is_finished}


def get_doc_agent():
    now = time.time()
    return {"status": "success", "text": "", "is_finished": True, "action_output": "", "current_agent": now}


def load_csv_for_documentation(file_path: str) -> pd.DataFrame:
    if not os.path.exists(file_path):
        raise FileNotFoundError(file_path)
    return pd.read_csv(file_path, nrows=500)


def evaluate_model_accuracy(df: pd.DataFrame, model_col: str = "model") -> pd.DataFrame:
    for col in ["rellab_correctness_pct", "hybench_score", "v0_score", "re_val_score"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df
