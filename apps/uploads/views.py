import uuid
import io, json, re

from .services import DataImportExportError, read_excel_to_dataframe, clean_column_names
from .services import coerce_types, validate_excel_import, generate_excel, generate_csv, generate_excel_multisheet
from .forms import ExcelImportForm, ExcelExportForm, ExcelToSQLForm
from .utils import mask_secret, encode_nested_args
from apps.core.utils.log_error import log_error
import pandas as pd
from io import BytesIO, StringIO

import csv, io, re, json, hashlib, tempfile, threading, shutil, time, datetime, warnings, random, string, uuid
import numpy as np, pandas as pd
from pathlib import Path
import openpyxl, doctest, pydoc, pstats, cProfile, profile
from .utils import read_excel_to_dataframe, generate_excel, generate_csv, clean_column_names, df_to_insert_sql
import zipfile, hashlib, tempfile, threading, shutil, time, datetime, warnings, random, string, uuid
from datetime import datetime, timedelta


def read_excel_to_dataframe(file_path, sheets=None, **kwargs):
    """Read Excel data by column _headers_or_keys."""
    try:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        sheets = sheets or [0]
        try:
            if isinstance(sheets, list):
                return [pd.read_excel(path, sheet_name=s, **kwargs) for s in sheets]
            else:
                return pd.read_excel(path, sheet_name=sheets, **kwargs)
        except Exception as e:
            raise Exception(f"Failed to read Excel: {e}")
    except Exception as e:
        return None
