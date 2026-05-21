"""
Django middleware: request logging + error forwarding.
"""

import time
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware:
    """Log every HTTP request with method, path, status, and duration."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start = time.time()
        response = self.get_response(request)
        duration_ms = (time.time() - start) * 1000
        try:
            ip = request.META.get("REMOTE_ADDR", "0.0.0.0")
            logger.info(
                "HTTP %s %s -> %s (%.1fms) [%s]",
                request.method, request.path, response.status_code,
                duration_ms, ip,
            )
        except Exception:
            pass
        return response


class ExceptionLoggingMiddleware:
    """Forward exceptions to the logger before the default 500 handler."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        logger.exception("Unhandled exception on %s: %s", request.path, exception)
        return None  # let Django handle the response
