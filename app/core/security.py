import base64
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException, status

from app.core.config import settings


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        310_000,
    )
    return (
        f"pbkdf2_sha256$310000$"
        f"{base64.b64encode(salt).decode()}$"
        f"{base64.b64encode(password_hash).decode()}"
    )


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iterations, salt, stored_hash = password_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        computed_hash = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            base64.b64decode(salt),
            int(iterations),
        )
        return hmac.compare_digest(computed_hash, base64.b64decode(stored_hash))
    except (ValueError, TypeError):
        return False


def create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:
    expire_at = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    payload = {"sub": subject, "exp": int(expire_at.timestamp())}
    return _encode_jwt(payload)


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        header, payload, signature = token.split(".")
        expected_signature = _sign(f"{header}.{payload}")
        if not hmac.compare_digest(signature, expected_signature):
            raise ValueError("Invalid signature")
        decoded_payload = json.loads(_base64url_decode(payload))
        if decoded_payload.get("exp", 0) < int(datetime.now(timezone.utc).timestamp()):
            raise ValueError("Token expired")
        return decoded_payload
    except (ValueError, json.JSONDecodeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def _encode_jwt(payload: dict[str, Any]) -> str:
    header = {"alg": settings.jwt_algorithm, "typ": "JWT"}
    encoded_header = _base64url_encode(json.dumps(header, separators=(",", ":")))
    encoded_payload = _base64url_encode(json.dumps(payload, separators=(",", ":")))
    signature = _sign(f"{encoded_header}.{encoded_payload}")
    return f"{encoded_header}.{encoded_payload}.{signature}"


def _sign(message: str) -> str:
    digest = hmac.new(
        settings.jwt_secret_key.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return _base64url_encode(digest)


def _base64url_encode(value: str | bytes) -> str:
    raw_value = value.encode("utf-8") if isinstance(value, str) else value
    return base64.urlsafe_b64encode(raw_value).rstrip(b"=").decode("utf-8")


def _base64url_decode(value: str) -> str:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}").decode("utf-8")

