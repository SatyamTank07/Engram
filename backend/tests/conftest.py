"""Shared test fixtures."""

import os
import uuid
import pytest

# ---------------------------------------------------------------------------
# Ensure auth-critical env vars are set BEFORE any app module is imported.
# These must be set at process level because auth.py reads them at import time.
# ---------------------------------------------------------------------------
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests")
os.environ.setdefault("NEO4J_URI", "bolt://localhost:7687")
os.environ.setdefault("NEO4J_USER", "neo4j")
os.environ.setdefault("NEO4J_PASSWORD", "test")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-fake-key")

# Generate a proper Fernet key for tests
from cryptography.fernet import Fernet

os.environ.setdefault("TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())

# ---------------------------------------------------------------------------
# Now safe to import app modules
# ---------------------------------------------------------------------------
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.database import Base

# Use the container's PostgreSQL — already running and healthy.
# Tests use a separate "engram_test" database to avoid polluting prod data.
_PG_ADMIN_URL = os.environ.get(
    "DATABASE_URL", "postgresql://postgres:postgres@postgres:5432/engram"
)
_TEST_DB_NAME = "engram_test"
_TEST_DB_URL = _PG_ADMIN_URL.rsplit("/", 1)[0] + f"/{_TEST_DB_NAME}"


def _ensure_test_database():
    """Create the test database if it doesn't exist."""
    admin_engine = create_engine(_PG_ADMIN_URL, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :name"),
            {"name": _TEST_DB_NAME},
        ).scalar()
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{_TEST_DB_NAME}"'))
    admin_engine.dispose()


_ensure_test_database()


# ---------------------------------------------------------------------------
# Database fixtures (PostgreSQL test database)
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def db_engine():
    """Create engine connected to the test database; create all tables once."""
    engine = create_engine(_TEST_DB_URL, echo=False)
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def db(db_engine):
    """Provide a DB session that rolls back after each test for isolation."""
    connection = db_engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


# ---------------------------------------------------------------------------
# FastAPI TestClient fixtures (Phase 2+)
# ---------------------------------------------------------------------------
@pytest.fixture
def client(db):
    """FastAPI TestClient with the test DB session injected.

    Overrides the `get_db` dependency so every request in the test uses the
    same transactional session (which rolls back after the test).
    """
    from httpx import ASGITransport
    from app.main import app
    from app import database

    def _override_get_db():
        yield db

    app.dependency_overrides[database.get_db] = _override_get_db

    # Disable rate limiting in tests — all requests come from "testclient"
    # which shares one counter and quickly hits 5/min limits.
    from app.routers.deps import limiter
    limiter.enabled = False

    from starlette.testclient import TestClient
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c

    limiter.enabled = True
    app.dependency_overrides.clear()


@pytest.fixture
def authenticated_client(client, db):
    """TestClient with a pre-registered and logged-in user.

    Returns (client, user) tuple. The client has auth cookies set.
    """
    from app import crud

    # Create user directly in DB (faster than going through the API)
    user = crud.create_user(db, phone="9999999999", password="testpassword123")
    db.flush()  # ensure user.id is available

    # Login via API to get cookies set on the client
    resp = client.post("/api/v1/auth/login", json={
        "phone": "9999999999",
        "password": "testpassword123",
    })
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return client, user


# ---------------------------------------------------------------------------
# Embedding-sync fixtures
# ---------------------------------------------------------------------------
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
