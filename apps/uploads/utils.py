import pandas as pd
from pathlib import Path
import re, os, warnings

HAS_XLSXWRITER = True
try:
    from xlsxwriter import Workbook
except ImportError:
    HAS_XLSXWRITER = False


def read_excel_to_dataframe(fname: str, **kwargs) -> pd.DataFrame:
    p = Path(fname)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {fname}")
    return pd.read_excel(p, engine="openpyxl", **kwargs)


def generate_csv(df: pd.DataFrame) -> str:
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue()


def generate_excel(df: pd.DataFrame, sheet_name="Sheet1") -> bytes:
    buf = io.BytesIO()
    if HAS_XLSXWRITER:
        with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
            df.to_excel(writer, sheet_name=sheet_name, index=False)
    else:
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name=sheet_name, index=False)
    return buf.getvalue()


def clean_column_names(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [re.sub(r"[^\w]", "_", str(c)).strip("_").lower() or "col" for c in df.columns]
    seen = {}
    new_cols = []
    for col in df.columns:
        if col in seen:
            seen[col] += 1
            new_cols.append(f"{col}_{seen[col]}")
        else:
            seen[col] = 0
            new_cols.append(col)
    df.columns = new_cols
    return df


def coerce_types(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in df.select_dtypes(include="object").columns[:20]:
        try:
            df[col] = pd.to_numeric(df[col]); continue
        except Exception:
            pass
        try: df[col] = pd.to_datetime(df[col]); continue
        except Exception: pass
    return df

def sanitize_value(val):