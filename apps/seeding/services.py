import random, string, datetime
from io import BytesIO
from pathlib import Path
import pandas as pd
from PIL import Image

try:
    from xlsxwriter import Workbook
    HAS_XLSXWRITER = True
except ImportError:
    HAS_XLSXWRITER = False

_demo_verbs = ["Analyze", "Create", "Optimize", "Generate", "Sync", "Export", "Import", "Process",
               "Transform", "Validate", "Stream", "Pipeline", "Orchestrate", "Provision"]
_demo_nouns = ["DataPipeline", "QueryJob", "SeedDataSet", "AnalyticsJob", "DBMigration", "CacheJob",
               "AuditLog", "FlowTask", "SchemaJob", "ModelPipeline"]

_dl = _demo_verbs
_dn = _demo_nouns

SCHEMA_PATTERNS = {
    "ecommerce": {