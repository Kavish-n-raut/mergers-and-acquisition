"""Authentication: stdlib HS256 JWT + PBKDF2 password hashing + demo user store.

No third-party JWT/crypto dependency — HS256 signing and PBKDF2-SHA256 hashing
use only the standard library. This replaces the previous "trusted x-user-role
header" model with verifiable Bearer tokens whose role claim is signed.

Demo users (one per role) share ``settings.demo_password`` and are intended for
local/MVP use only. A production deployment must back this with a real user
store and rotate ``JWT_SECRET`` out of source control.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from functools import lru_cache
from typing import Any

from app.core.config import get_settings

DEMO_USERNAMES_BY_ROLE = ("analyst", "associate", "vp", "director", "md", "admin")


class AuthError(Exception):
    """Raised for any authentication/token failure."""


# --- Password hashing (PBKDF2-SHA256) -----------------------------------------

def hash_password(password: str, *, salt: bytes | None = None, iterations: int = 200_000) -> str:
    salt = salt or os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iterations, salt_hex, hash_hex = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iterations))
        return hmac.compare_digest(dk.hex(), hash_hex)
    except Exception:
        return False


# --- JWT (HS256) --------------------------------------------------------------

def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(segment: str) -> bytes:
    padding = "=" * (-len(segment) % 4)
    return base64.urlsafe_b64decode(segment + padding)


def create_access_token(username: str, role: str, *, secret: str | None = None, expires_minutes: int | None = None) -> str:
    settings = get_settings()
    secret = secret or settings.jwt_secret
    expires_minutes = settings.jwt_expire_minutes if expires_minutes is None else expires_minutes

    header = {"alg": "HS256", "typ": "JWT"}
    now = int(time.time())
    payload = {"sub": username, "role": role, "iat": now, "exp": now + expires_minutes * 60}

    signing_input = (
        _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
        + "."
        + _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    )
    signature = hmac.new(secret.encode("utf-8"), signing_input.encode("ascii"), hashlib.sha256).digest()
    return signing_input + "." + _b64url_encode(signature)


def decode_access_token(token: str, *, secret: str | None = None) -> dict[str, Any]:
    settings = get_settings()
    secret = secret or settings.jwt_secret
    try:
        header_seg, payload_seg, signature_seg = token.split(".")
    except ValueError as exc:
        raise AuthError("Malformed token.") from exc

    signing_input = f"{header_seg}.{payload_seg}"
    expected = hmac.new(secret.encode("utf-8"), signing_input.encode("ascii"), hashlib.sha256).digest()
    if not hmac.compare_digest(expected, _b64url_decode(signature_seg)):
        raise AuthError("Invalid token signature.")

    try:
        payload = json.loads(_b64url_decode(payload_seg))
    except Exception as exc:
        raise AuthError("Invalid token payload.") from exc

    if int(payload.get("exp", 0)) < int(time.time()):
        raise AuthError("Token expired.")
    return payload


# --- Demo user store ----------------------------------------------------------

# Each demo account's password is "<username>@100" (e.g. director -> director@100).
def demo_password_for(username: str) -> str:
    return f"{username.lower()}@100"


@lru_cache(maxsize=1)
def _demo_users() -> dict[str, dict[str, str]]:
    return {
        role: {"role": role, "password_hash": hash_password(demo_password_for(role))}
        for role in DEMO_USERNAMES_BY_ROLE
    }


def authenticate(username: str, password: str) -> str | None:
    """Return the user's role if credentials are valid, else None."""
    user = _demo_users().get(username.lower())
    if user is None:
        return None
    if not verify_password(password, user["password_hash"]):
        return None
    return user["role"]
