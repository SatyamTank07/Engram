"""Tests for session management API endpoints (routers/sessions.py)."""

import uuid

import pytest

from app import crud


# ===================================================================
# POST /api/v1/sessions — Create session
# ===================================================================
class TestCreateSession:
    def test_create_session_default_title(self, authenticated_client):
        client, _ = authenticated_client
        resp = client.post("/api/v1/sessions", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "New Chat"
        assert "id" in data

    def test_create_session_custom_title(self, authenticated_client):
        client, _ = authenticated_client
        resp = client.post("/api/v1/sessions", json={"title": "My Topic"})
        assert resp.status_code == 200
        assert resp.json()["title"] == "My Topic"

    def test_create_session_unauthenticated(self, client):
        resp = client.post("/api/v1/sessions", json={})
        assert resp.status_code == 401


# ===================================================================
# GET /api/v1/sessions — List sessions
# ===================================================================
class TestListSessions:
    def test_list_sessions_empty(self, authenticated_client):
        client, _ = authenticated_client
        resp = client.get("/api/v1/sessions")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_sessions_returns_created(self, authenticated_client):
        client, _ = authenticated_client
        client.post("/api/v1/sessions", json={"title": "Chat 1"})
        client.post("/api/v1/sessions", json={"title": "Chat 2"})

        resp = client.get("/api/v1/sessions")
        assert resp.status_code == 200
        sessions = resp.json()
        assert len(sessions) == 2
        # Most recent first
        assert sessions[0]["title"] == "Chat 2"
        assert sessions[1]["title"] == "Chat 1"

    def test_list_sessions_user_isolation(self, client, db):
        """User A's sessions should not appear for User B."""
        # Create User A and a session
        user_a = crud.create_user(db, phone="7777777770", password="pass123")
        db.flush()
        crud.create_session(db, user_id=str(user_a.id), title="A's Chat")
        db.flush()

        # Login as User B
        crud.create_user(db, phone="7777777771", password="pass123")
        db.flush()
        login_resp = client.post("/api/v1/auth/login", json={
            "phone": "7777777771",
            "password": "pass123",
        })
        assert login_resp.status_code == 200

        # User B should see no sessions
        resp = client.get("/api/v1/sessions")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_sessions_unauthenticated(self, client):
        resp = client.get("/api/v1/sessions")
        assert resp.status_code == 401


# ===================================================================
# GET /api/v1/sessions/{session_id}/messages
# ===================================================================
class TestGetSessionMessages:
    def test_get_messages_empty_session(self, authenticated_client, db):
        client, user = authenticated_client
        session = crud.create_session(db, user_id=str(user.id), title="Empty")
        db.flush()

        resp = client.get(f"/api/v1/sessions/{session.id}/messages")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_messages_with_content(self, authenticated_client, db):
        client, user = authenticated_client
        session = crud.create_session(db, user_id=str(user.id))
        db.flush()
        crud.save_message(db, str(session.id), "user", "Hello")
        crud.save_message(db, str(session.id), "assistant", "Hi there!")
        db.flush()

        resp = client.get(f"/api/v1/sessions/{session.id}/messages")
        assert resp.status_code == 200
        messages = resp.json()
        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Hello"
        assert messages[1]["role"] == "assistant"

    def test_get_messages_session_not_found(self, authenticated_client):
        client, _ = authenticated_client
        fake_id = str(uuid.uuid4())
        resp = client.get(f"/api/v1/sessions/{fake_id}/messages")
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "SESSION_NOT_FOUND"

    def test_get_messages_other_users_session(self, client, db):
        """Accessing another user's session should return 403."""
        # Create User A with a session
        user_a = crud.create_user(db, phone="8888888880", password="pass123")
        db.flush()
        session_a = crud.create_session(db, user_id=str(user_a.id), title="Private")
        db.flush()

        # Login as User B
        crud.create_user(db, phone="8888888881", password="pass123")
        db.flush()
        client.post("/api/v1/auth/login", json={
            "phone": "8888888881",
            "password": "pass123",
        })

        resp = client.get(f"/api/v1/sessions/{session_a.id}/messages")
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "ACCESS_DENIED"

    def test_get_messages_unauthenticated(self, client):
        fake_id = str(uuid.uuid4())
        resp = client.get(f"/api/v1/sessions/{fake_id}/messages")
        assert resp.status_code == 401


# ===================================================================
# DELETE /api/v1/sessions/{session_id}
# ===================================================================
class TestDeleteSession:
    def test_delete_session_success(self, authenticated_client, db):
        client, user = authenticated_client
        session = crud.create_session(db, user_id=str(user.id), title="ToDelete")
        db.flush()

        resp = client.delete(f"/api/v1/sessions/{session.id}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

        # Session should be gone
        list_resp = client.get("/api/v1/sessions")
        assert all(s["id"] != str(session.id) for s in list_resp.json())

    def test_delete_session_not_found(self, authenticated_client):
        client, _ = authenticated_client
        fake_id = str(uuid.uuid4())
        resp = client.delete(f"/api/v1/sessions/{fake_id}")
        assert resp.status_code == 404

    def test_delete_other_users_session(self, client, db):
        """Deleting another user's session should return 403."""
        user_a = crud.create_user(db, phone="6666666660", password="pass123")
        db.flush()
        session_a = crud.create_session(db, user_id=str(user_a.id))
        db.flush()

        # Login as User B
        crud.create_user(db, phone="6666666661", password="pass123")
        db.flush()
        client.post("/api/v1/auth/login", json={
            "phone": "6666666661",
            "password": "pass123",
        })

        resp = client.delete(f"/api/v1/sessions/{session_a.id}")
        assert resp.status_code == 403

    def test_delete_session_unauthenticated(self, client):
        fake_id = str(uuid.uuid4())
        resp = client.delete(f"/api/v1/sessions/{fake_id}")
        assert resp.status_code == 401
