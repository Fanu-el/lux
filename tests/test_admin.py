"""Tests for admin endpoints including analytics."""

from unittest.mock import AsyncMock, patch

import pytest

from app.models.chat import ChatMessage, ChatMessageRole, ChatMessageStatus, ChatSession
from app.models.role import RoleKey
from tests.conftest import auth_headers, make_user


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_session(db, user):
    session = ChatSession(user_id=user.id, title="Test")
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def make_message(db, session, role=ChatMessageRole.USER, status=ChatMessageStatus.COMPLETED, content="hi"):
    msg = ChatMessage(session_id=session.id, role=role, content=content, status=status)
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


# ---------------------------------------------------------------------------
# Access control
# ---------------------------------------------------------------------------

class TestAdminAccess:
    def test_regular_user_cannot_access_admin(self, client, db):
        user = make_user(db, email="regular@example.com")
        resp = client.get("/admin/chats", headers=auth_headers(user))
        assert resp.status_code == 403

    def test_super_admin_can_access_admin(self, client, db):
        admin = make_user(db, email="admin@example.com", role_key=RoleKey.SUPER_ADMIN)
        resp = client.get("/admin/chats", headers=auth_headers(admin))
        assert resp.status_code == 200

    def test_unauthenticated_cannot_access_admin(self, client, db):
        resp = client.get("/admin/chats")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /admin/analytics
# ---------------------------------------------------------------------------

class TestAnalytics:
    def test_analytics_returns_correct_counts(self, client, db):
        admin = make_user(db, email="analytics_admin@example.com", role_key=RoleKey.SUPER_ADMIN)
        user = make_user(db, email="analytics_user@example.com")

        session = make_session(db, user)
        make_message(db, session, role=ChatMessageRole.USER)
        make_message(db, session, role=ChatMessageRole.ASSISTANT, status=ChatMessageStatus.COMPLETED)
        make_message(db, session, role=ChatMessageRole.ASSISTANT, status=ChatMessageStatus.FAILED)

        resp = client.get("/admin/analytics", headers=auth_headers(admin))
        assert resp.status_code == 200
        data = resp.json()["data"]

        assert data["total_chat_sessions"] >= 1
        assert data["total_messages"] >= 3
        assert data["active_users"] >= 2  # admin + user are both ACTIVE
        assert data["failed_ai_calls"] >= 1

    def test_analytics_zero_state(self, client, db):
        admin = make_user(db, email="zero_admin@example.com", role_key=RoleKey.SUPER_ADMIN)
        resp = client.get("/admin/analytics", headers=auth_headers(admin))
        assert resp.status_code == 200
        data = resp.json()["data"]
        # All counts are non-negative integers
        for key in ("total_chat_sessions", "total_messages", "active_users", "failed_ai_calls"):
            assert isinstance(data[key], int)
            assert data[key] >= 0

    def test_analytics_regular_user_forbidden(self, client, db):
        user = make_user(db, email="analytics_noauth@example.com")
        resp = client.get("/admin/analytics", headers=auth_headers(user))
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# GET /admin/chats
# ---------------------------------------------------------------------------

class TestAdminChats:
    def test_list_all_chats(self, client, db):
        admin = make_user(db, email="chats_admin@example.com", role_key=RoleKey.SUPER_ADMIN)
        u1 = make_user(db, email="chats_u1@example.com")
        u2 = make_user(db, email="chats_u2@example.com")
        make_session(db, u1)
        make_session(db, u2)

        resp = client.get("/admin/chats", headers=auth_headers(admin))
        assert resp.status_code == 200
        assert len(resp.json()["data"]) >= 2

    def test_get_single_chat(self, client, db):
        admin = make_user(db, email="singlechat_admin@example.com", role_key=RoleKey.SUPER_ADMIN)
        user = make_user(db, email="singlechat_user@example.com")
        session = make_session(db, user)

        resp = client.get(f"/admin/chats/{session.id}", headers=auth_headers(admin))
        assert resp.status_code == 200
        assert resp.json()["data"]["id"] == session.id

    def test_get_nonexistent_chat_404(self, client, db):
        admin = make_user(db, email="notfound_admin@example.com", role_key=RoleKey.SUPER_ADMIN)
        resp = client.get("/admin/chats/nonexistent-id", headers=auth_headers(admin))
        assert resp.status_code == 404
