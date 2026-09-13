from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, Header, HTTPException, Request, status

from app.core.auth import AuthError, decode_access_token
from app.core.config import get_settings

ROLE_ORDER = {
    "analyst": 1,
    "associate": 2,
    "vp": 3,
    "director": 4,
    "md": 5,
    "admin": 6,
}


def normalize_role(role: str | None) -> str:
    settings = get_settings()
    if not role:
        return settings.default_role.lower()
    return role.lower()


def role_rank(role: str) -> int:
    return ROLE_ORDER.get(role, 0)


def _role_from_bearer(authorization: str | None) -> str | None:
    """Extract and verify the role claim from an Authorization: Bearer <jwt> header.

    Returns None when no bearer token is present. Raises 401 when a token is
    present but invalid/expired."""
    if not authorization:
        return None
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    try:
        payload = decode_access_token(parts[1].strip())
    except AuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    return normalize_role(payload.get("role"))


def get_current_role(
    x_user_role: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
) -> str:
    settings = get_settings()

    # 1) A signed Bearer token always wins (its role claim is verifiable).
    role = _role_from_bearer(authorization)

    # 2) Otherwise fall back to the x-user-role header, unless auth is enforced.
    if role is None:
        if settings.auth_enforced:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required. Obtain a token from /api/v1/auth/login.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        role = normalize_role(x_user_role)

    if role not in ROLE_ORDER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Unknown role '{role}'. Valid roles: {', '.join(ROLE_ORDER)}",
        )
    return role


def require_role(min_role: str) -> Callable[[str], str]:
    required = normalize_role(min_role)
    if required not in ROLE_ORDER:
        raise ValueError(f"Invalid required role: {required}")

    def _checker(current_role: str = Depends(get_current_role)) -> str:
        if role_rank(current_role) < role_rank(required):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Requires role >= {required}.",
            )
        return current_role

    return _checker


def attach_role_to_request(request: Request, role: str) -> None:
    request.state.user_role = role

