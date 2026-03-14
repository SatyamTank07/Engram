"""Tests for chat API endpoints (routers/chat.py) — Phase 5."""

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app import crud


# ===================================================================
# POST /api/v1/chat — Synchronous chat
# ===================================================================
class TestChat:
    def test_chat_success(self, authenticated_client, db):
        """Successful chat returns user and assistant messages."""
        client, user = authenticated_client
        session = crud.create_session(db, user_id=str(user.id), title="Test Chat")
        db.flush()

        with patch("app.agent.get_agent_response", new_callable=AsyncMock) as mock_agent:
            mock_agent.return_value = "Hello from AI!"
            resp = client.post("/api/v1/chat", json={
                "session_id": str(session.id),
                "message": "Hi there",
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == str(session.id)
        assert data["user_message"]["role"] == "user"
        assert data["user_message"]["content"] == "Hi there"
        assert data["assistant_message"]["role"] == "assistant"
        assert data["assistant_message"]["content"] == "Hello from AI!"

    def test_chat_auto_title_on_first_message(self, authenticated_client, db):
        """First message in a session should auto-set the session title."""
        client, user = authenticated_client
        session = crud.create_session(db, user_id=str(user.id), title="New Chat")
        db.flush()

        with patch("app.agent.get_agent_response", new_callable=AsyncMock) as mock_agent:
            mock_agent.return_value = "Response"
            client.post("/api/v1/chat", json={
                "session_id": str(session.id),
                "message": "What is the meaning of life?",
            })

        # Verify title was updated
        db.expire_all()
        updated = crud.get_session(db, str(session.id))
        assert updated.title == "What is the meaning of life?"

    def test_chat_long_message_title_truncated(self, authenticated_client, db):
        """Long first messages should be truncated to 50 chars + '...'."""
        client, user = authenticated_client
        session = crud.create_session(db, user_id=str(user.id))
        db.flush()

        long_message = "A" * 100

        with patch("app.agent.get_agent_response", new_callable=AsyncMock) as mock_agent:
            mock_agent.return_value = "Response"
            client.post("/api/v1/chat", json={
                "session_id": str(session.id),
                "message": long_message,
            })

        db.expire_all()
        updated = crud.get_session(db, str(session.id))
        assert updated.title == "A" * 50 + "..."

    def test_chat_with_image_url(self, authenticated_client, db):
        """image_url should be passed through to the agent."""
        client, user = authenticated_client
        session = crud.create_session(db, user_id=str(user.id))
        db.flush()

        with patch("app.agent.get_agent_response", new_callable=AsyncMock) as mock_agent:
            mock_agent.return_value = "I see a face."
            resp = client.post("/api/v1/chat", json={
                "session_id": str(session.id),
                "message": "Who is this?",
                "image_url": "/uploads/chat/test.jpg",
            })

        assert resp.status_code == 200
        # Verify image_url was passed to agent
        mock_agent.assert_called_once()
        call_kwargs = mock_agent.call_args
        assert call_kwargs[0][2] == "/uploads/chat/test.jpg"  # positional arg for image_url

    def test_chat_session_not_found(self, authenticated_client):
        """Non-existent session should return 404."""
        client, _ = authenticated_client
        fake_id = str(uuid.uuid4())

        resp = client.post("/api/v1/chat", json={
            "session_id": fake_id,
            "message": "Hello",
        })
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "SESSION_NOT_FOUND"

    def test_chat_access_denied_other_user(self, client, db):
        """Chatting in another user's session should return 403."""
        user_a = crud.create_user(db, phone="5550000001", password="pass123")
        db.flush()
        session_a = crud.create_session(db, user_id=str(user_a.id))
        db.flush()

        # Login as user B
        crud.create_user(db, phone="5550000002", password="pass123")
        db.flush()
        client.post("/api/v1/auth/login", json={
            "phone": "5550000002",
            "password": "pass123",
        })

        resp = client.post("/api/v1/chat", json={
            "session_id": str(session_a.id),
            "message": "Snoop",
        })
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "ACCESS_DENIED"

    def test_chat_unauthenticated(self, client):
        """Unauthenticated requests should return 401."""
        resp = client.post("/api/v1/chat", json={
            "session_id": str(uuid.uuid4()),
            "message": "Hello",
        })
        assert resp.status_code == 401

    def test_chat_agent_error_returns_500(self, authenticated_client, db):
        """Agent failure should return 500 with CHAT_AGENT_ERROR code."""
        client, user = authenticated_client
        session = crud.create_session(db, user_id=str(user.id))
        db.flush()

        with patch("app.agent.get_agent_response", new_callable=AsyncMock) as mock_agent:
            mock_agent.side_effect = Exception("LLM crashed")
            resp = client.post("/api/v1/chat", json={
                "session_id": str(session.id),
                "message": "Hello",
            })

        assert resp.status_code == 500
        assert resp.json()["error"]["code"] == "CHAT_AGENT_ERROR"

    def test_chat_passes_user_id_to_agent(self, authenticated_client, db):
        """The authenticated user's ID should be passed to the agent."""
        client, user = authenticated_client
        session = crud.create_session(db, user_id=str(user.id))
        db.flush()

        with patch("app.agent.get_agent_response", new_callable=AsyncMock) as mock_agent:
            mock_agent.return_value = "OK"
            client.post("/api/v1/chat", json={
                "session_id": str(session.id),
                "message": "Hello",
            })

        mock_agent.assert_called_once()
        assert mock_agent.call_args.kwargs["user_id"] == str(user.id)

    def test_chat_passes_history(self, authenticated_client, db):
        """Existing messages should be passed as chat_history to the agent."""
        client, user = authenticated_client
        session = crud.create_session(db, user_id=str(user.id))
        db.flush()
        crud.save_message(db, str(session.id), "user", "First Q")
        crud.save_message(db, str(session.id), "assistant", "First A")
        db.flush()

        with patch("app.agent.get_agent_response", new_callable=AsyncMock) as mock_agent:
            mock_agent.return_value = "Second answer"
            client.post("/api/v1/chat", json={
                "session_id": str(session.id),
                "message": "Second Q",
            })

        call_args = mock_agent.call_args
        history = call_args[0][1]  # second positional arg = chat_history
        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[0]["content"] == "First Q"


# ===================================================================
# POST /api/v1/chat/stream — SSE streaming chat
# ===================================================================
class TestChatStream:
    def test_stream_unauthenticated(self, client):
        """Unauthenticated streaming should return 401."""
        resp = client.post("/api/v1/chat/stream", json={
            "session_id": str(uuid.uuid4()),
            "message": "Hello",
        })
        assert resp.status_code == 401

    def test_stream_session_not_found(self, authenticated_client):
        """Non-existent session should return 404 for stream endpoint."""
        client, _ = authenticated_client
        resp = client.post("/api/v1/chat/stream", json={
            "session_id": str(uuid.uuid4()),
            "message": "Hello",
        })
        assert resp.status_code == 404

    def test_stream_access_denied(self, client, db):
        """Streaming in another user's session should return 403."""
        user_a = crud.create_user(db, phone="5551110001", password="pass123")
        db.flush()
        session_a = crud.create_session(db, user_id=str(user_a.id))
        db.flush()

        crud.create_user(db, phone="5551110002", password="pass123")
        db.flush()
        client.post("/api/v1/auth/login", json={
            "phone": "5551110002",
            "password": "pass123",
        })

        resp = client.post("/api/v1/chat/stream", json={
            "session_id": str(session_a.id),
            "message": "Snoop",
        })
        assert resp.status_code == 403
