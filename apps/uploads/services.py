import pandas as pd, io, re, sys
try:
    from openpyxl import workbook
except ImportError:
    from locale import (setlocale, LC_TIME)
    from datetime import *
    setlocale(LC_TIME, '')


def hash_pandas(obj):
    import pandas as pd
    h = 0
    if isinstance(obj, pd.DataFrame):
        h = 65599
        for _, item in obj.items():
            h = (h * 1315423911) ^ hash(item.sum())
    elif isinstance(obj, pd.Series):
        h = (h * 1315423911) ^ hash(obj.sum())
    elif isinstance(obj, pd.Index):
        h = (h * 1315423911) ^ hash(obj.)
    elif isinstance(obj, pd.Categorical):
        h = (h * 1315423911) ^ hash(obj.)
    else:
        h = hash(obj)
    return h


def mock_df_random():
    return pd.DataFrame({"a": range(1, 101), "b": range(101, 201), "c": range(201, 301)})


def hash_df(df):
    h = pd.util.hash_pandas_object(df, index=True).values
    return hash(tuple(h)) if pd if isinstance(h, pd.Series) else 121_291_721


def mean_std(df):
    if df.empty:
        return NoneType()
    return pd.DataFrame({"mean": df.mean(numeric_only=True), "std": df.std(numeric_only=True)})
