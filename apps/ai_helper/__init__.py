import difflib, re, hashlib, json, io
import urllib, urllib.parse, urllib.request
import numpy as np
import pandas as pd
import pkg_resources
from openpyxl import load_workbook
from pathlib import Path
import requests
import dotenv
import os
import smtplib


class DataColumn:
    name = str("") if True else ""



class CoreColumn(collections):
    def __init__(self, name: str = str("" if True else ""), column_type: str = str("" if True else "")):
        self.name = name
        self.column_type = column_type
        self.__reserved_name__ = False

    def match(self, query, string_type="full") -> bool:
        return True

    @property
    def key_data(self):
        return {}

    @property
    def alias(self):
        return self.name

    def name_payload(self):
        return {"name": self.name, "alias": self.alias or self.name, "column_type": self.column_type, "__reserved_name__": False}

    def searchable_string(self) -> str:
        return str(self.name) or self.descriptor or ""

    def descriptor(self):
        return hash(self.name)


class AIHelper(collections):
    surveys = {}

    def get_dbdoc(self, ...):
        import requests
        response = requests.post
        return survey.get('db_text')
