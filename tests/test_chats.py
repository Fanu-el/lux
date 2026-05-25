"""Tests for chat session and message endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.conftest import auth_headers, make_user


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def create_session(client, headers, title="Test chat"):
    resp = client.post("/chats", json={"title": title}, headers=headers)
    assert resp.status_code == 201
    return resp.json()["data"]


# ---------------------------------------------------------------------------
# Chat session CRUD
# ---------------------------------------------------------------------------

class TestChatSessions:
    def test_create_session(self, client, db):
        user = make_user(db, email="cs1@example.com")
        resp = client.post("/chats", json={"title": "My chat"}, headers=auth_headers(user))
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["title"] == "My chat"
        assert data["user_id"] == user.id

    def test_create_session_default_title(self, client, db):
        user = make_user(db, email="cs2@example.com")
        resp = client.post("/chats", json={}, headers=auth_headers(user))
        assert resp.status_code == 201
        assert resp.json()["data"]["title"] == "New chat"

    def test_list_sessions(self, client, db):
        user = make_user(db, email="cs3@example.com")
        headers = auth_headers(user)
        create_session(client, headers, "A")
        create_session(client, headers, "B")
        resp = client.get("/chats", headers=headers)
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 2

    def test_list_sessions_isolated_per_user(self, client, db):
        u1 = make_user(db, email="cs4a@example.com")
        u2 = make_user(db, email="cs4b@example.com")
        create_session(client, auth_headers(u1), "U1 chat")
        resp = client.get("/chats", headers=auth_headers(u2))
        assert resp.json()["data"] == []

    def test_get_session(self, client, db):
        user = make_user(db, email="cs5@example.com")
        headers = auth_headers(user)
        session = create_session(client, headers)
        resp = client.get(f"/chats/{session['id']}", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["data"]["id"] == session["id"]

    def test_get_session_other_user_forbidden(self, client, db):
        u1 = make_user(db, email="cs6a@example.com")
        u2 = make_user(db, email="cs6b@example.com")
        session = create_session(client, auth_headers(u1))
        resp = client.get(f"/chats/{session['id']}", headers=auth_headers(u2))
        assert resp.status_code == 404

    def test_update_session_title(self, client, db):
        user = make_user(db, email="cs7@example.com")
        headers = auth_headers(user)
        session = create_session(client, headers)
        resp = client.patch(f"/chats/{session['id']}", json={"title": "Renamed"}, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["data"]["title"] == "Renamed"

    def test_delete_session(self, client, db):
        user = make_user(db, email="cs8@example.com")
        headers = auth_headers(user)
        session = create_session(client, headers)
        resp = client.delete(f"/chats/{session['id']}", headers=headers)
        assert resp.status_code == 200
        # Deleted session should no longer appear in list
        list_resp = client.get("/chats", headers=headers)
        ids = [s["id"] for s in list_resp.json()["data"]]
        assert session["id"] not in ids

    def test_unauthenticated_access_denied(self, client, db):
        resp = client.get("/chats")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Chat messages / exchange
# ---------------------------------------------------------------------------

FAKE_LLM_RESPONSE = MagicMock(
    content="Hello from Gemini!",
    model="gemini-2.5-flash",
    latency_ms=123,
    input_tokens=10,
    output_tokens=5,
    total_tokens=15,
)


class TestChatMessages:
    def _mock_llm(self):
        from app.services.llm_service import LLMResponse
        mock_response = LLMResponse(
            content="Hello from Gemini!",
            model="gemini/gemini-2.5-flash",
            latency_ms=123,
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
        )
        return patch(
            "app.services.chat_service.generate_assistant_reply",
            new_callable=AsyncMock,
            return_value=mock_response,
        )

    def test_send_message_returns_exchange(self, client, db):
        user = make_user(db, email="cm1@example.com")
        headers = auth_headers(user)
        session = create_session(client, headers)

        with self._mock_llm():
            resp = client.post(
                f"/chats/{session['id']}/messages",
                json={"content": "Hello!"},
                headers=headers,
            )

        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["user_message"]["content"] == "Hello!"
        assert data["assistant_message"]["content"] == "Hello from Gemini!"
        assert data["assistant_message"]["model"] == "gemini/gemini-2.5-flash"
        assert data["assistant_message"]["latency_ms"] == 123

    def test_send_message_auto_titles_session(self, client, db):
        user = make_user(db, email="cm2@example.com")
        headers = auth_headers(user)
        session = create_session(client, headers, title=None)
        assert session["title"] == "New chat"

        with self._mock_llm():
            client.post(
                f"/chats/{session['id']}/messages",
                json={"content": "What is the capital of France?"},
                headers=headers,
            )

        updated = client.get(f"/chats/{session['id']}", headers=headers).json()["data"]
        assert updated["title"] != "New chat"
        assert "France" in updated["title"]

    def test_list_messages(self, client, db):
        user = make_user(db, email="cm3@example.com")
        headers = auth_headers(user)
        session = create_session(client, headers)

        with self._mock_llm():
            client.post(f"/chats/{session['id']}/messages", json={"content": "Hi"}, headers=headers)

        resp = client.get(f"/chats/{session['id']}/messages", headers=headers)
        assert resp.status_code == 200
        messages = resp.json()["data"]
        assert len(messages) == 2  # user + assistant
        roles = {m["role"] for m in messages}
        assert roles == {"USER", "ASSISTANT"}

    def test_invalid_gemini_model_rejected(self, client, db):
        user = make_user(db, email="cm4@example.com")
        headers = {**auth_headers(user), "X-LLM-Model": "openai/gpt-99-fake"}
        session = create_session(client, headers)
        resp = client.post(
            f"/chats/{session['id']}/messages",
            json={"content": "Hi"},
            headers=headers,
        )
        assert resp.status_code == 400

    def test_send_message_to_other_users_session_forbidden(self, client, db):
        u1 = make_user(db, email="cm5a@example.com")
        u2 = make_user(db, email="cm5b@example.com")
        session = create_session(client, auth_headers(u1))
        with self._mock_llm():
            resp = client.post(
                f"/chats/{session['id']}/messages",
                json={"content": "Hi"},
                headers=auth_headers(u2),
            )
        assert resp.status_code == 404
