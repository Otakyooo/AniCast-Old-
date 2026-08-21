import ipaddress
import socket
import time
from dataclasses import dataclass
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .models import Source
from .playback import source_url_allowed


class NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


@dataclass(frozen=True)
class HealthResult:
    is_healthy: bool
    http_status: int | None
    latency_ms: int
    error: str = ""


def validate_public_destination(source: Source, resolver=socket.getaddrinfo) -> None:
    if not source_url_allowed(source):
        raise ValueError("URL не соответствует HTTPS allowlist провайдера")
    hostname = urlparse(source.url).hostname
    if not hostname:
        raise ValueError("URL не содержит hostname")
    addresses = {item[4][0] for item in resolver(hostname, 443, type=socket.SOCK_STREAM)}
    if not addresses:
        raise ValueError("DNS не вернул адрес")
    if any(not ipaddress.ip_address(address).is_global for address in addresses):
        raise ValueError("DNS указывает на private или reserved адрес")


def check_source(source: Source, *, resolver=socket.getaddrinfo, opener=None) -> HealthResult:
    started = time.monotonic()
    try:
        validate_public_destination(source, resolver)
        client = opener or build_opener(NoRedirectHandler())
        req = Request(source.url, method="HEAD", headers={"User-Agent": "AniCast-Health/1.0"})
        try:
            response = client.open(req, timeout=10)
            status = response.status
            response.close()
        except HTTPError as error:
            status = error.code
            if 300 <= status < 400:
                raise ValueError("Redirect запрещён") from error
            if status not in {401, 403, 405}:
                raise
        healthy = 200 <= status < 300 or status in {401, 403, 405}
        return HealthResult(healthy, status, round((time.monotonic() - started) * 1000), "" if healthy else f"HTTP {status}")
    except Exception as error:
        return HealthResult(False, getattr(error, "code", None), round((time.monotonic() - started) * 1000), str(error)[:500])
