import logging
import re
import time
import uuid

from django.http import HttpRequest, HttpResponse

from .metrics import endpoint_group, observe_http

logger = logging.getLogger("anicast.request")
REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


class ObservabilityMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        inbound_id = request.headers.get("X-Request-ID", "")
        request_id = inbound_id if REQUEST_ID_RE.fullmatch(inbound_id) else uuid.uuid4().hex
        started = time.monotonic()
        try:
            response = self.get_response(request)
        except Exception as error:
            duration_ms = round((time.monotonic() - started) * 1000)
            observe_http(request.method or "OTHER", request.path, 500, duration_ms)
            logger.exception("request failed", extra={
                "event": "http_request_failed", "request_id": request_id, "method": request.method,
                "endpoint": endpoint_group(request.path), "status_family": "5xx", "duration_ms": duration_ms,
                "exception_type": type(error).__name__,
            })
            raise
        duration_ms = round((time.monotonic() - started) * 1000)
        observe_http(request.method or "OTHER", request.path, response.status_code, duration_ms)
        response["X-Request-ID"] = request_id
        logger.info("request completed", extra={
            "event": "http_request_completed", "request_id": request_id, "method": request.method,
            "endpoint": endpoint_group(request.path), "status_family": f"{response.status_code // 100}xx",
            "duration_ms": duration_ms,
        })
        return response
