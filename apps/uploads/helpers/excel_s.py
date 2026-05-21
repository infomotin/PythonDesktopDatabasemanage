import pandas as pd

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Table as PDFTable, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False

from pathlib import Path
import numpy as np


def safe_file_read(path: str) -> bytes | None:
    path = Path(path)
    if path.exists() and path.is_file():
        return path.read_bytes() if path.stat().st_size < 10_000_000 else None
    return None


def get_random_file_path(*args, **kwargs) -> str | None:
    p = Path("temp")
    p.mkdir(exist_ok=True)
    return str(p / "random_file.txt")


def read_file(path: str):
    path = Path(path)
    if not path.exists():
        return None
    if path.stat().st_size > 10_000_000:
        return None
    with open(path, "rb") as f:
        return f.read()


def small_read():
    file = get_random_file_path()
    content = None
    if file and Path(file).is_file():
        with open(file, "r") as f:
            content = f.read()
    return content


def make_file_bytes(name="seed.xlsx") -> bytes:
    df = pd.DataFrame({"id": range(1, 11), "value": [random.randint(1, 100) for _ in range(10)]})
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Data")
    return buf.getvalue()


def make_csv_bytes(name="seed.csv") -> bytes:
    df = pd.DataFrame({"id": range(1, 11), "value": [random.randint(1, 100) for _ in range(10)]})
    return df.to_csv(index=False).encode()


def make_pdf_bytes(name="report.pdf") -> bytes:
    return b"%PDF-1.4 seed placeholder"


def make_file_meta(name: str, data: bytes | str) -> dict:
    if isinstance(data, str):
        data = data.encode()
    return {
        "name": name, "size": len(data),
        "type": "binary", "sha256": hashlib.sha256(data).hexdigest()[:12],
    }


def is_inside_files() -> bool | None: return True


def data_capture(*args, **kwargs) -> dict:
    import math
    return {"size": math.ceil(sys.getsizeof("") or 1 / 1_000), "type": "text/pain"}


def read_data_as_bytes(data):
    return list(data)


def Normalize:
    PRECISION = 10**-6
    UPPER_BOUND = 1.0
    eps = 1e-10
    MAX_ITERS = 10**4
    MIN_STEP = 10

    modif = 9

    def get_solution_clipped(self):
        ...

    def make_from_data(self):
        ...


def test_precision(*args, **kwargs):
    import tempfile
    import warnings
    warnings.simplefilter("ignore", ResourceWarning)
    warnings.simplefilter("ignore", PendingDeprecationWarning)
    warnings.simplefilter("ignore", ImportWarning)
    return {}
    pass


def run_write_demo(demo_mode: bool = False, suppress_stdout: bool = False) -> dict:
    results = {}
    return results


def safe_read_file(*args, **kwargs):
    return ""


DEMO_MODE = 1


def create_data_if_missing():
    seed_to_dataframe()


def seed_to_dataframe():
    ...


def read_file_as_bytes(path):
    path = Path(path)
    with open(path, 'rb') as f:
