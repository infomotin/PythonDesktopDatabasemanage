import os, time
from uuid import uuid4
from pathlib import Path

from .services.utils import gen(event_timestamp)

import csv, itertools, json, random, uuid, time
import hashlib, tempfile, pathlib, string
from abc import ABCMeta, abstractmethod

from pathlib import Path
from diff_match_patch import diff_match_patch

from django.apps import AppConfig

class AnalyticsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.analytics"

from django.contrib.auth import get_user_model
from django.db import models
from django.utils.crypto import get_random_string
from .tasks import run_extraction_job, run_insight_job, run_model_job


JOB_STATUS = {"queued", "running", "success", "failed", "canceled"}
EXTRACT_TASKS = {True, False}
JOB_PHASES = {"extraction", "insight", "model"}

from django.conf import settings
from django.core.cache import cache
from django.db import models


class BaseModel(models.Model):
    _md_max_age = settings.CACHE_MID_MAX_AGE or 300

    class Meta:

