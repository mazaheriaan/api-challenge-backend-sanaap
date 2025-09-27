import json
import logging
import time

from django.contrib.auth import get_user_model
from django.http import HttpRequest, HttpResponse
from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin
# Translate 
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)
User = get_user_model()

class RequestLoggingMiddleware(MiddlewareMixin):
    def process_request(self, request: HttpRequest) -> None:
        request._start_time = time.time()

        log_data = {
            "timestamp": timezone.now().isoformat(),
            "method": request.method,
            "path": request.path,
            "user": (
                request.user.username if request.user.is_authenticated else "anonymous"
            ),
            "ip_address": self._get_client_ip(request),
            "user_agent": request.META.get("HTTP_USER_AGENT", ""),
        }

        if self._is_sensitive_operation(request):
            # Don't access request.body for multipart uploads to avoid consuming the stream
            if request.content_type and "multipart" not in request.content_type:
                try:
                    log_data["body_size"] = len(request.body) if request.body else 0
                except Exception:
                    log_data["body_size"] = "Unable to determine"
            else:
                log_data["body_size"] = request.META.get("CONTENT_LENGTH", 0)
            log_data["query_params"] = dict(request.GET)

        logger.info(f"API Request: {json.dumps(log_data)}")

    def process_response(
        self, request: HttpRequest, response: HttpResponse
    ) -> HttpResponse:
        # Calculate request duration
        if hasattr(request, "_start_time"):
            duration = time.time() - request._start_time
            response["X-Response-Time"] = f"{duration:.3f}s"

            log_data = {
                "timestamp": timezone.now().isoformat(),
                "method": request.method,
                "path": request.path,
                "status_code": response.status_code,
                "duration": duration,
                "user": (
                    request.user.username
                    if request.user.is_authenticated
                    else "anonymous"
                ),
            }

            # Log errors and slow requests
            if response.status_code >= 400 or duration > 1.0:
                logger.warning(f"API Response: {json.dumps(log_data)}")
            else:
                logger.debug(f"API Response: {json.dumps(log_data)}")

        return response

    def _get_client_ip(self, request: HttpRequest) -> str:
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "unknown")

    def _is_sensitive_operation(self, request: HttpRequest) -> bool:
        sensitive_paths = [
            "/api/documents/",
            "/api/auth/",
            "/api/users/",
            "/api/permissions/",
        ]
        sensitive_methods = ["POST", "PUT", "PATCH", "DELETE"]

        return (
            any(request.path.startswith(path) for path in sensitive_paths)
            and request.method in sensitive_methods
        )
