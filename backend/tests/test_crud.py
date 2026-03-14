"""Tests for CRUD operations (crud.py).

Uses an in-memory SQLite database via the `db` fixture from conftest.
"""

import uuid

import pytest

from app import crud, database


# ===================================================================
# User CRUD
# ===================================================================
class TestUserCrud:
    def test_create_user(self, db):
        user = crud.create_user(db, phone="1234567890", password="secret123")
        assert user.phone == "1234567890"
        assert user.password_hash != "secret123"  # must be hashed
        assert user.id is not None

    def test_create_user_hashes_password(self, db):
        user = crud.create_user(db, phone="1234567890", password="mypassword")
        assert user.password_hash.startswith("$2b$")

    def test_create_user_duplicate_phone_raises(self, db):
        crud.create_user(db, phone="1234567890", password="pass1")
        with pytest.raises(Exception):
            crud.create_user(db, phone="1234567890", password="pass2")

    def test_get_user_by_phone_found(self, db):
        crud.create_user(db, phone="9876543210", password="pass")
        user = crud.get_user_by_phone(db, "9876543210")
        assert user is not None
        assert user.phone == "9876543210"

    def test_get_user_by_phone_not_found(self, db):
        result = crud.get_user_by_phone(db, "0000000000")
        assert result is None

    def test_get_user_by_id_found(self, db):
        created = crud.create_user(db, phone="5555555555", password="pass")
        found = crud.get_user_by_id(db, str(created.id))
        assert found is not None
        assert found.phone == "5555555555"

    def test_get_user_by_id_not_found(self, db):
        result = crud.get_user_by_id(db, str(uuid.uuid4()))
        assert result is None


# ===================================================================
# Session CRUD
# ===================================================================
class TestSessionCrud:
    @pytest.fixture
    def user(self, db):
        """Create a test user for session tests."""
        return crud.create_user(db, phone="1111111111", password="pass")

    def test_create_session_default_title(self, db, user):
        session = crud.create_session(db, user_id=str(user.id))
        assert session.title == "New Chat"
        assert session.user_id == user.id

    def test_create_session_custom_title(self, db, user):
        session = crud.create_session(db, user_id=str(user.id), title="My Chat")
        assert session.title == "My Chat"

    def test_get_user_sessions_returns_ordered(self, db, user):
        crud.create_session(db, user_id=str(user.id), title="First")
        crud.create_session(db, user_id=str(user.id), title="Second")
        sessions = crud.get_user_sessions(db, str(user.id))
        assert len(sessions) == 2
        # Most recent first (desc order)
        assert sessions[0].title == "Second"

    def test_get_user_sessions_empty(self, db, user):
        sessions = crud.get_user_sessions(db, str(user.id))
        assert sessions == []

    def test_get_user_sessions_isolation(self, db):
        """User A's sessions should not appear for User B."""
        user_a = crud.create_user(db, phone="2222222222", password="pass")
        user_b = crud.create_user(db, phone="3333333333", password="pass")
        crud.create_session(db, user_id=str(user_a.id), title="A's Chat")

        b_sessions = crud.get_user_sessions(db, str(user_b.id))
        assert b_sessions == []

    def test_get_session_found(self, db, user):
        created = crud.create_session(db, user_id=str(user.id), title="Find Me")
        found = crud.get_session(db, str(created.id))
        assert found is not None
        assert found.title == "Find Me"

    def test_get_session_not_found(self, db):
        result = crud.get_session(db, str(uuid.uuid4()))
        assert result is None

    def test_update_session_title(self, db, user):
        session = crud.create_session(db, user_id=str(user.id), title="Old Title")
        crud.update_session_title(db, str(session.id), "New Title")
        updated = crud.get_session(db, str(session.id))
        assert updated.title == "New Title"

    def test_update_session_title_truncates_long_title(self, db, user):
        session = crud.create_session(db, user_id=str(user.id))
        long_title = "A" * 300
        crud.update_session_title(db, str(session.id), long_title)
        updated = crud.get_session(db, str(session.id))
        assert len(updated.title) == 255

    def test_update_session_title_nonexistent_session(self, db):
        # Should not raise — just a no-op
        crud.update_session_title(db, str(uuid.uuid4()), "No Effect")

    def test_delete_session(self, db, user):
        session = crud.create_session(db, user_id=str(user.id))
        crud.delete_session(db, str(session.id))
        assert crud.get_session(db, str(session.id)) is None

    def test_delete_session_nonexistent(self, db):
        # Should not raise
        crud.delete_session(db, str(uuid.uuid4()))

    def test_delete_session_cascades_messages(self, db, user):
        session = crud.create_session(db, user_id=str(user.id))
        crud.save_message(db, str(session.id), "user", "hello")
        crud.save_message(db, str(session.id), "assistant", "hi there")

        crud.delete_session(db, str(session.id))
        messages = crud.get_session_messages(db, str(session.id))
        assert messages == []


# ===================================================================
# Message CRUD
# ===================================================================
class TestMessageCrud:
    @pytest.fixture
    def session(self, db):
        """Create a test user + session for message tests."""
        user = crud.create_user(db, phone="4444444444", password="pass")
        return crud.create_session(db, user_id=str(user.id))

    def test_save_message_user_role(self, db, session):
        msg = crud.save_message(db, str(session.id), "user", "Hello!")
        assert msg.role == "user"
        assert msg.content == "Hello!"
        assert msg.session_id == session.id
        assert msg.id is not None

    def test_save_message_assistant_role(self, db, session):
        msg = crud.save_message(db, str(session.id), "assistant", "Hi there!")
        assert msg.role == "assistant"
        assert msg.content == "Hi there!"

    def test_save_message_with_image_url(self, db, session):
        msg = crud.save_message(
            db, str(session.id), "user", "Look at this",
            image_url="/uploads/chat/image.jpg",
        )
        assert msg.image_url == "/uploads/chat/image.jpg"

    def test_save_message_without_image_url(self, db, session):
        msg = crud.save_message(db, str(session.id), "user", "No image")
        assert msg.image_url is None

    def test_get_session_messages_ordered_by_timestamp(self, db, session):
        crud.save_message(db, str(session.id), "user", "First")
        crud.save_message(db, str(session.id), "assistant", "Second")
        crud.save_message(db, str(session.id), "user", "Third")

        messages = crud.get_session_messages(db, str(session.id))
        assert len(messages) == 3
        assert messages[0].content == "First"
        assert messages[1].content == "Second"
        assert messages[2].content == "Third"

    def test_get_session_messages_empty(self, db, session):
        messages = crud.get_session_messages(db, str(session.id))
        assert messages == []

    def test_get_session_messages_isolation(self, db):
        """Messages from session A should not appear in session B."""
        user = crud.create_user(db, phone="6666666666", password="pass")
        session_a = crud.create_session(db, user_id=str(user.id), title="A")
        session_b = crud.create_session(db, user_id=str(user.id), title="B")

        crud.save_message(db, str(session_a.id), "user", "Only in A")
        messages_b = crud.get_session_messages(db, str(session_b.id))
        assert messages_b == []
