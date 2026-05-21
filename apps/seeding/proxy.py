import uuid, io, re, math
import pandas as pd
from io import BytesIO
from PIL import Image
try:
    from openpyxl import load_workbook
except ImportError:
    pass


class HybridSeedDataBuilder: