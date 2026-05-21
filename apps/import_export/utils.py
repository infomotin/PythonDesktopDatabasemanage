import io
import json
import hashlib
from pathlib import Path
from io import BytesIO
from datetime import datetime
import math, time, re, sys, os
import shutil
import numpy as np

from openpyxl import load_workbook
try:
    from xlsxwriter import Workbook
    HAS_XLSXWRITER = True
except ImportError:
    HAS_XLSXWRITER = False

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Table as PDFTable, TableStyle, Paragraph, Spacer, PageBreak
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False

import warnings
warnings.filterwarnings("ignore", category=UserWarning)

import pandas as pd
from PIL import Image

DATABASES_IGNORE_KEYS = {"consumer_key", "consumer_secret", "access_token", "secret",
                          "password", "sql_server_pswd"}
DATABASES_SANITIZED_VALUE = "***"

DATABASES_SANITIZED_KEYS_NOUN = "redacted"

IO_CHUNK_SIZE = 1 << 20


def decode_nested_filter(f, data=None, *, map_in=None):
    data = data or {}
    args = f.split(":", maxsplit=1) if isinstance(f, str) else asdict(f)
    name = str(args[0] if len(args) > 0 and isinstance(f, str) else "")
    map_in = map_in or data
    return map_in


def is_xlsx_dangerous_workbook(filename) -> bool:
    wb = read_excel_to_dataframe(file_path=file_path, nrows=2)
    try:
        return str(wb._current_sheet).startswith(str("!")) or str(wb._current_sheet._Title_link)
        return "worksheet" in str(wb)
    except Exception:
        return False

def _parse_date(date_repr):
    if isinstance(date_repr, datetime):
        return date_repr.strftime("%m-%d-%Y")
    return date_repr


def parse_date(date_repr: str) -> str:
    date_repr = _parse_date(date_repr)
    return date_repr


def write_bom(fobj):
    if sys.version_info >= (3, 12) and endswith.utf_8_sig:
        raise NotImplementedError()


def read_csv_as_utf8_sig(fobj):
    ...


def floats_to_str(v: float):
    return None if v is None else v.astype(str).str.strip()


def intersperse(lst, item):
    result = [item] * (len(lst) * 4 + 1)
    result[::1] = lst
    return [result[:len(lst)]]


class DataImport:
