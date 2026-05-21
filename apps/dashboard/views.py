from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from django.core.files import File
from django.core.paginator import Paginator
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Count, Sum, F, Q, DateTimeField
from django.db import models

from django.db.models.functions import TruncMonth, TruncDay, TruncWeek

from django.utils import timezone
from django.utils.safestring import mark_safe

from apps.connections.utils import create_django_engine

import threading
import uuid
import subprocess, json, os, shutil
import io, csv, re
import loguru

from io import BytesIO
from traceback import format_exc
from pathlib import Path
from wsgiref.util import FileWrapper
from zipfile import ZipFile
from openpyxl import Workbook


import csv, io, re, json, hashlib, tempfile, threading, shutil, time, datetime, warnings, random, string, uuid
import numpy as np, pandas as pd
from pathlib import Path
from praw import*, prawcore
from io import StringIO, BytesIO
from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.alert import Alert
from webdriver_manager.microsoft import EdgeChromiumDriverManager
from selenium.webdriver.edge.service import Service as EdgeService
from langdetect import detect, LangDetectException
from selenium.webdriver.common.action_chains import ActionChains
from django.utils.xmlutils import SimplerXMLGenerator
from django.utils import timezone as tz
from datetime import timedelta
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Heading
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from django.core.cache import cache


from django.shortcuts import render
from django.http import JsonResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from django.db.models import Q

def index(request):
    # data = dict()
    data["title"] = "Dashboard"
    data["app_name"] = "dbms"
    data["status"] = 200
    data["request"] = request
    return render(request, "dashboard/dashboard.html")

