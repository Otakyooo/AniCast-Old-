from django.conf import settings
from rest_framework.permissions import SAFE_METHODS
from rest_framework.settings import api_settings
from rest_framework.throttling import AnonRateThrottle, SimpleRateThrottle, UserRateThrottle

from .security import constant_time_equals


INTERNAL_HEADER = "X-AniCast-Internal-Token"


def is_internal_safe_request(request) -> bool:
    expected = str(getattr(settings, "INTERNAL_API_TOKEN", ""))
    supplied = str(request.headers.get(INTERNAL_HEADER, ""))
    return (
        request.method in SAFE_METHODS
        and len(expected) >= 32
        and constant_time_equals(supplied, expected)
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


class AniCastUserRateThrottle(UserRateThrottle):
    """Per-account ceiling for authenticated traffic.

    ``AnonRateThrottle`` returns ``None`` for authenticated requests, so without
    this class a single cheap account could hammer the expensive personal
    endpoints (account summary, recommendations, continue-watching) unthrottled.
    The budget is deliberately loose: it bounds abuse without interfering with
    a normal session, which fires several parallel requests per page.

    Anonymous callers are left to :class:`AniCastAnonRateThrottle`, whose limit
    is stricter anyway, so they are not counted twice. Trusted SSR requests are
    exempt because they share the ``ssr`` bucket and are never attributable to
    one visitor.
    """

    scope = "user"

    def allow_request(self, request, view):
        if is_internal_safe_request(request):
            return True
        return super().allow_request(request, view)

    def get_cache_key(self, request, view):
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            return None
        return self.cache_format % {"scope": self.scope, "ident": user.pk}


class VisitRateThrottle(SimpleRateThrottle):
    """IP-scoped ceiling for the anonymous visit counter.

    ``/analytics/visit/`` is a plain Django view, so the DRF defaults never
    applied to it. Its own guards are advisory by design — the bot check reads
    the User-Agent and the dedupe check reads a client-held cookie — so a script
    with a browser UA and no cookie jar could inflate DailyVisitStat without
    bound while taking a row lock per request. The bucket is per client address
    and generous enough for shared NAT egress.
    """

    scope = "visit"

    @property
    def THROTTLE_RATES(self):  # noqa: N802 - overrides a DRF class attribute
        # DRF resolves the rate table once at class definition, which happens
        # before ``override_settings`` in tests can take effect. Reading it per
        # instance keeps the configured rate authoritative.
        return api_settings.DEFAULT_THROTTLE_RATES

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}
