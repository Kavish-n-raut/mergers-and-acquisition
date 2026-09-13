import time

import pytest
from fastapi.testclient import TestClient

from app.core.auth import (
    AuthError,
    authenticate,
    create_access_token,
    decode_access_token,
    demo_password_for,
    hash_password,
    verify_password,
)
from app.core.config import get_settings
from app.main import app


def test_password_hash_roundtrip():
    hashed = hash_password("s3cret")
    assert verify_password("s3cret", hashed)
    assert not verify_password("wrong", hashed)


def test_jwt_roundtrip_and_signature_tamper_rejected():
    token = create_access_token("md", "md")
    payload = decode_access_token(token)
    assert payload["sub"] == "md"
    assert payload["role"] == "md"

    tampered = token[:-2] + ("aa" if not token.endswith("aa") else "bb")
    with pytest.raises(AuthError):
        decode_access_token(tampered)


def test_jwt_expiry_rejected():
    token = create_access_token("vp", "vp", expires_minutes=-1)
    with pytest.raises(AuthError):
        decode_access_token(token)


def test_authenticate_demo_user():
    assert authenticate("md", "md@100") == "md"          # password is <username>@100
    assert authenticate("md", "nope") is None
    assert authenticate("md", demo_password_for("vp")) is None  # vp's password won't work for md
    assert authenticate("ghost", "ghost@100") is None


def test_login_endpoint_issues_usable_bearer_token():
    with TestClient(app) as c:
        resp = c.post("/api/v1/auth/login", json={"username": "vp", "password": "vp@100"})
        assert resp.status_code == 200
        token = resp.json()["access_token"]
        assert resp.json()["role"] == "vp"

        # A vp token can reach a vp-gated endpoint (M6 LBO)...
        ok = c.post(
            "/api/v1/modules/m6/lbo",
            headers={"Authorization": f"Bearer {token}"},
            json={"enterprise_value": 500.0, "ebitda": 100.0},
        )
        assert ok.status_code == 200

        # ...but the analyst token cannot (403).
        analyst_token = c.post("/api/v1/auth/login", json={"username": "analyst", "password": "analyst@100"}).json()["access_token"]
        denied = c.post(
            "/api/v1/modules/m6/lbo",
            headers={"Authorization": f"Bearer {analyst_token}"},
            json={"enterprise_value": 500.0, "ebitda": 100.0},
        )
        assert denied.status_code == 403


def test_login_rejects_bad_credentials():
    with TestClient(app) as c:
        resp = c.post("/api/v1/auth/login", json={"username": "md", "password": "definitely-wrong"})
        assert resp.status_code == 401


def test_invalid_bearer_token_is_401():
    with TestClient(app) as c:
        resp = c.get("/api/v1/auth/me", headers={"Authorization": "Bearer not.a.real.token"})
        assert resp.status_code == 401


def test_legacy_header_still_works_when_auth_not_enforced():
    # auth_enforced defaults to False, so x-user-role remains valid for dev/tests.
    with TestClient(app) as c:
        resp = c.get("/api/v1/auth/me", headers={"x-user-role": "director"})
        assert resp.status_code == 200
        assert resp.json()["role"] == "director"
