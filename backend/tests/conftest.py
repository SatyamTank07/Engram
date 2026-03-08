"""Shared fixtures for embedding sync tests."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def person_data():
    """A sample person dict as returned by _node_to_dict."""
    return {
        "id": str(uuid.uuid4()),
        "user_id": str(uuid.uuid4()),
        "name": "Test Person",
        "aliases": ["TP", "Tester"],
        "short_bio": "A test person for unit tests",
        "contacts": {"email": "test@example.com"},
        "trust_score": "0.5",
        "first_seen": "2025-01-01T00:00:00+00:00",
        "last_seen": "2025-01-01T00:00:00+00:00",
    }


@pytest.fixture
def pending_sync_row(person_data):
    """A sample row from pending_embedding_syncs."""
    return {
        "id": str(uuid.uuid4()),
        "person_id": person_data["id"],
        "user_id": person_data["user_id"],
        "operation": "upsert",
        "retry_count": 0,
    }


@pytest.fixture
def fake_embedding():
    """A fake 1536-dim embedding vector."""
    return [0.01] * 1536
