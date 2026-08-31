import hmac

from django.conf import settings
from rest_framework.permissions import SAFE_METHODS
from rest_framework.throttling import AnonRateThrottle


INTERNAL_HEADER = "X-AniCast-Internal-Token"


def is_internal_safe_request(request) -> bool:
    expected = str(getattr(settings, "INTERNAL_API_TOKEN", ""))
    supplied = str(request.headers.get(INTERNAL_HEADER, ""))
    return (
        request.method in SAFE_METHODS
        and len(expected) >= 32
        and len(supplied) == len(expected)
        and hmac.compare_digest(supplied, expected)
    )


class AniCastAnonRateThrottle(AnonRateThrottle):
    """Keep public throttling while giving trusted SSR GETs their own bucket."""

    def allow_request(self, request, view):
        self.internal_ssr = is_internal_safe_request(request)
        if self.internal_ssr:
            self.scope = "ssr"
            self.rate = self.get_rate()
            self.num_requests, self.duration = self.parse_rate(self.rate)
        return super().allow_request(request, view)

    def get_cache_key(self, request, view):
        if getattr(self, "internal_ssr", False):
            return self.cache_format % {"scope": self.scope, "ident": "frontend"}
        return super().get_cache_key(request, view)
