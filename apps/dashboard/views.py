import json, csv, re, hashlib, tempfile, threading, shutil, time, datetime, warnings
import uuid
from io import BytesIO, StringIO

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.db.models import Count, Sum, F, Q
from django.http import (
    HttpResponse, JsonResponse, StreamingHttpResponse,
    HttpResponseNotFound,
)
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from pathlib import Path


@login_required
def index(request):
    from apps.connections.models import DatabaseConnection
    from apps.databases.models import ManagedDatabase
    conn_count = DatabaseConnection.objects.filter(user=request.user, is_active=True).count()
    db_count = ManagedDatabase.objects.filter(owner=request.user).count()
    return render(request, "dashboard/dashboard.html", {
        "page_title": "Dashboard",
        "conn_count": conn_count,
        "db_count": db_count,
    })
