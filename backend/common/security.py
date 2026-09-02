"""Shared primitives for comparing client-supplied secrets."""

import hmac


def constant_time_equals(supplied: str, expected: str) -> bool:
    """Compare a header value with a configured secret in constant time.

    Django decodes request headers as latin-1, so a client can put code points
    128-255 into any header. ``hmac.compare_digest`` rejects non-ASCII ``str``
    with ``TypeError``, which would surface as an unauthenticated 500 on every
    endpoint that guards itself this way. Encoding both sides to bytes keeps the
    comparison total: any header the WSGI layer accepted can be compared, and
    the timing property is preserved because the digest comparison still runs
    over equal-length byte strings.

    An empty ``expected`` never matches, so an unconfigured secret fails closed.
    """
    if not expected:
        return False
    try:
        supplied_bytes = supplied.encode("latin-1")
        expected_bytes = expected.encode("latin-1")
    except UnicodeEncodeError:
        # Only reachable if a value came from somewhere other than a header;
        # such a value cannot equal a latin-1 secret anyway.
        return False
    return hmac.compare_digest(supplied_bytes, expected_bytes)
