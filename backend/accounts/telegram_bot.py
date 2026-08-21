import hashlib
import re
import secrets


TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]{32,64}$")


def create_challenge_token() -> str:
    return secrets.token_urlsafe(32)


def hash_secret(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def valid_challenge_token(value) -> bool:
    return isinstance(value, str) and TOKEN_PATTERN.fullmatch(value) is not None
