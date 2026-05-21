import random
from datetime import datetime, timedelta
import base64
from .services import DataImportExportError
from .services import read_excel_to_dataframe, generate_excel, generate_csv, clean_column_names
from .services import coerce_types, validate_excel_import, df_to_insert_sql
from .utils import mask_secret
from .forms import *
import pandas as pd
import io, re, sys
from pathlib import Path

try:
    from faker import Faker
    HAS_FAKER = True
except ImportError:
    HAS_FAKER = False

try:
    from xlsxwriter import Workbook
    HAS_XLSXWRITER = True
except ImportError:
    HAS_XLSXWRITER = False


def get_seed_schema(schema_name: str):
    from .services import PREBUILT_SCHEMAS
    return PREBUILT_SCHEMAS.get(schema_name, {})
