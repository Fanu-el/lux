"""Tests for auth endpoints."""

from unittest.mock import AsyncMock, patch

import pytest

from tests.conftest import auth_headers, make_user


# ---------------------------------------------------------------------------
# POST /auth/login
# ---------------------------------------------------------------------------

class TestLogin:
    def test_login_success(self, client, db):
        make_user(db, email="login@example.com")
        resp = client.post("/auth/login", json={"email": "login@example.com", "password": "Password1!"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["is_error"] is False
        assert "access_token" in body["data"]

    def test_login_wrong_password(self, client, db):
        make_user(db, email="wrongpw@example.com")
        resp = client.post("/auth/login", json={"email": "wrongpw@example.com", "password": "WrongPassword1!"})
        assert resp.status_code == 401

    def test_login_unknown_email(self, client, db):
        resp = client.post("/auth/login", json={"email": "nobody@example.com", "password": "Password1!"})
        assert resp.status_code == 401

    def test_login_pending_user_blocked(self, client, db):
        from app.models.user import UserStatus
        make_user(db, email="pending@example.com", status=UserStatus.PENDING)
        resp = client.post("/auth/login", json={"email": "pending@example.com", "password": "Password1!"})
        assert resp.status_code == 403

    def test_login_banned_user_blocked(self, client, db):
        from app.models.user import UserStatus
        make_user(db, email="banned@example.com", status=UserStatus.BANNED)
        resp = client.post("/auth/login", json={"email": "banned@example.com", "password": "Password1!"})
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# GET /auth/me
# ---------------------------------------------------------------------------

class TestMe:
    def test_me_authenticated(self, client, db):
        user = make_user(db, email="me@example.com")
        resp = client.get("/auth/me", headers=auth_headers(user))
        assert resp.status_code == 200
        assert resp.json()["data"]["email"] == "me@example.com"

    def test_me_unauthenticated(self, client, db):
        resp = client.get("/auth/me")
        assert resp.status_code == 401

    def test_me_invalid_token(self, client, db):
        resp = client.get("/auth/me", headers={"Authorization": "Bearer not.a.token"})
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /auth/register
# ---------------------------------------------------------------------------

class TestRegister:
    def test_register_sends_verification(self, client, db):
        with patch("app.services.auth_service.send_email", new_callable=AsyncMock):
            resp = client.post(
                "/auth/register",
                json={"name": "New User", "email": "newuser@example.com", "password": "Password1!"},
            )
        assert resp.status_code == 201
        body = resp.json()
        assert body["is_error"] is False
        assert "message" in body["data"]

    def test_register_duplicate_email(self, client, db):
        make_user(db, email="dup@example.com")
        with patch("app.services.auth_service.send_email", new_callable=AsyncMock):
            resp = client.post(
                "/auth/register",
                json={"name": "Dup", "email": "dup@example.com", "password": "Password1!"},
            )
        assert resp.status_code == 409
