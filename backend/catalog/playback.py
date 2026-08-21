from urllib.parse import urlparse

from django.utils import timezone

from .models import RightsGrant, Source


def source_url_allowed(source: Source) -> bool:
    if source.provider is None:
        return False
    parsed = urlparse(source.url)
    hostname = parsed.hostname
    allowed_hosts = {str(host).lower() for host in source.provider.allowed_hosts}
    return (
        parsed.scheme == "https"
        and hostname is not None
        and parsed.username is None
        and parsed.password is None
        and hostname.lower() in allowed_hosts
    )


def authorized_playback_source(source_id: int, *, now=None) -> Source | None:
    moment = now or timezone.now()
    source = Source.objects.select_related("provider").filter(
        pk=source_id,
        availability="available",
        provider__is_enabled=True,
    ).first()
    if source is None or not source_url_allowed(source):
        return None
    has_grant = RightsGrant.objects.filter(
        source=source,
        status=RightsGrant.Status.ACTIVE,
        valid_from__lte=moment,
        valid_until__gt=moment,
        approved_by__isnull=False,
        approved_at__isnull=False,
    ).exists()
    return source if has_grant else None
