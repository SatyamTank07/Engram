"""Tests for person API endpoints (routers/persons.py)."""

import io
from unittest.mock import patch, AsyncMock, MagicMock

import pytest


# ===================================================================
# Helper: mock graph_db for all person route tests
# ===================================================================
@pytest.fixture
def mock_graph_db():
    """Patch graph_db with async mocks for all CRUD operations."""
    with patch("app.routers.persons.graph_db") as mock:
        mock.create_person_node = AsyncMock()
        mock.get_person_node = AsyncMock()
        mock.list_person_nodes = AsyncMock()
        mock.update_person_node = AsyncMock()
        mock.delete_person_node = AsyncMock()
        mock.get_person_nodes_batch = AsyncMock()
        yield mock


@pytest.fixture
def sample_person():
    """A sample person dict as returned by graph_db."""
    return {
        "id": "person-123",
        "user_id": None,  # will be set per test
        "name": "Alice",
        "aliases": ["Ali"],
        "contacts": {"email": "alice@test.com"},
        "short_bio": "Engineer",
        "trust_score": "0.8",
        "first_seen": "2025-01-01T00:00:00+00:00",
        "last_seen": "2025-01-01T00:00:00+00:00",
    }


# ===================================================================
# POST /api/v1/persons — create person
# ===================================================================
class TestCreatePerson:
    def test_create_success(self, authenticated_client, mock_graph_db):
        client, user = authenticated_client
        mock_graph_db.create_person_node.return_value = {
            "id": "new-person-id",
            "user_id": str(user.id),
            "name": "Bob",
            "aliases": [],
            "contacts": {},
            "short_bio": "",
            "trust_score": "0.0",
        }

        resp = client.post("/api/v1/persons", json={"name": "Bob"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Bob"
        mock_graph_db.create_person_node.assert_called_once()

    def test_create_with_all_fields(self, authenticated_client, mock_graph_db):
        client, user = authenticated_client
        mock_graph_db.create_person_node.return_value = {
            "id": "p-1",
            "user_id": str(user.id),
            "name": "Charlie",
            "aliases": ["Chuck"],
            "contacts": {"phone": "555-0100"},
            "short_bio": "Designer",
            "trust_score": "0.9",
        }

        resp = client.post("/api/v1/persons", json={
            "name": "Charlie",
            "aliases": ["Chuck"],
            "contacts": {"phone": "555-0100"},
            "short_bio": "Designer",
            "trust_score": 0.9,
        })
        assert resp.status_code == 201
        assert resp.json()["aliases"] == ["Chuck"]

    def test_create_missing_name(self, authenticated_client, mock_graph_db):
        client, _ = authenticated_client
        resp = client.post("/api/v1/persons", json={})
        assert resp.status_code == 422

    def test_create_unauthenticated(self, client, mock_graph_db):
        resp = client.post("/api/v1/persons", json={"name": "Nobody"})
        assert resp.status_code == 401


# ===================================================================
# GET /api/v1/persons — list persons
# ===================================================================
class TestListPersons:
    def test_list_success(self, authenticated_client, mock_graph_db):
        client, user = authenticated_client
        mock_graph_db.list_person_nodes.return_value = [
            {"id": "p-1", "name": "Alice"},
            {"id": "p-2", "name": "Bob"},
        ]

        resp = client.get("/api/v1/persons")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

    def test_list_empty(self, authenticated_client, mock_graph_db):
        client, _ = authenticated_client
        mock_graph_db.list_person_nodes.return_value = []

        resp = client.get("/api/v1/persons")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_unauthenticated(self, client, mock_graph_db):
        resp = client.get("/api/v1/persons")
        assert resp.status_code == 401


# ===================================================================
# GET /api/v1/persons/{person_id} — get person
# ===================================================================
class TestGetPerson:
    def test_get_success(self, authenticated_client, mock_graph_db, sample_person):
        client, user = authenticated_client
        sample_person["user_id"] = str(user.id)
        mock_graph_db.get_person_node.return_value = sample_person

        resp = client.get("/api/v1/persons/person-123")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Alice"

    def test_get_not_found(self, authenticated_client, mock_graph_db):
        client, _ = authenticated_client
        mock_graph_db.get_person_node.return_value = None

        resp = client.get("/api/v1/persons/nonexistent")
        assert resp.status_code == 404

    def test_get_other_users_person_forbidden(self, authenticated_client, mock_graph_db, sample_person):
        client, _ = authenticated_client
        sample_person["user_id"] = "other-user-id"
        mock_graph_db.get_person_node.return_value = sample_person

        resp = client.get("/api/v1/persons/person-123")
        assert resp.status_code == 403

    def test_get_unauthenticated(self, client, mock_graph_db):
        resp = client.get("/api/v1/persons/person-123")
        assert resp.status_code == 401


# ===================================================================
# PUT /api/v1/persons/{person_id} — update person
# ===================================================================
class TestUpdatePerson:
    def test_update_success(self, authenticated_client, mock_graph_db, sample_person):
        client, user = authenticated_client
        sample_person["user_id"] = str(user.id)
        mock_graph_db.get_person_node.return_value = sample_person
        mock_graph_db.update_person_node.return_value = {
            **sample_person, "name": "Alice Updated"
        }

        resp = client.put("/api/v1/persons/person-123", json={"name": "Alice Updated"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "Alice Updated"

    def test_update_not_found(self, authenticated_client, mock_graph_db):
        client, _ = authenticated_client
        mock_graph_db.get_person_node.return_value = None

        resp = client.put("/api/v1/persons/nonexistent", json={"name": "X"})
        assert resp.status_code == 404

    def test_update_other_users_person_forbidden(self, authenticated_client, mock_graph_db, sample_person):
        client, _ = authenticated_client
        sample_person["user_id"] = "other-user-id"
        mock_graph_db.get_person_node.return_value = sample_person

        resp = client.put("/api/v1/persons/person-123", json={"name": "X"})
        assert resp.status_code == 403

    def test_update_unauthenticated(self, client, mock_graph_db):
        resp = client.put("/api/v1/persons/person-123", json={"name": "X"})
        assert resp.status_code == 401


# ===================================================================
# DELETE /api/v1/persons/{person_id} — delete person
# ===================================================================
class TestDeletePerson:
    def test_delete_success(self, authenticated_client, mock_graph_db, sample_person):
        client, user = authenticated_client
        sample_person["user_id"] = str(user.id)
        mock_graph_db.get_person_node.return_value = sample_person
        mock_graph_db.delete_person_node.return_value = True

        resp = client.delete("/api/v1/persons/person-123")
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

    def test_delete_not_found(self, authenticated_client, mock_graph_db):
        client, _ = authenticated_client
        mock_graph_db.get_person_node.return_value = None

        resp = client.delete("/api/v1/persons/nonexistent")
        assert resp.status_code == 404

    def test_delete_other_users_person_forbidden(self, authenticated_client, mock_graph_db, sample_person):
        client, _ = authenticated_client
        sample_person["user_id"] = "other-user-id"
        mock_graph_db.get_person_node.return_value = sample_person

        resp = client.delete("/api/v1/persons/person-123")
        assert resp.status_code == 403

    def test_delete_unauthenticated(self, client, mock_graph_db):
        resp = client.delete("/api/v1/persons/person-123")
        assert resp.status_code == 401


# ===================================================================
# POST /api/v1/persons/search — semantic search
# ===================================================================
class TestSemanticSearch:
    @patch("app.embedding_service.generate_text_embedding")
    @patch("app.vector_db.semantic_search")
    def test_search_success(self, mock_search, mock_emb, authenticated_client, mock_graph_db):
        client, user = authenticated_client
        mock_emb.return_value = [0.1] * 1536
        mock_search.return_value = [
            {"person_id": "p-1", "similarity_score": 0.92},
        ]
        mock_graph_db.get_person_nodes_batch.return_value = {
            "p-1": {"id": "p-1", "name": "Alice", "short_bio": "Engineer"}
        }

        resp = client.post("/api/v1/persons/search", json={"query": "engineer at google"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["name"] == "Alice"
        assert data[0]["similarity_score"] == 0.92

    @patch("app.embedding_service.generate_text_embedding")
    @patch("app.vector_db.semantic_search")
    def test_search_no_results(self, mock_search, mock_emb, authenticated_client, mock_graph_db):
        client, _ = authenticated_client
        mock_emb.return_value = [0.1] * 1536
        mock_search.return_value = []
        mock_graph_db.get_person_nodes_batch.return_value = {}

        resp = client.post("/api/v1/persons/search", json={"query": "nobody"})
        assert resp.status_code == 200
        assert resp.json() == []

    def test_search_empty_query(self, authenticated_client, mock_graph_db):
        client, _ = authenticated_client
        resp = client.post("/api/v1/persons/search", json={"query": ""})
        assert resp.status_code == 422

    def test_search_unauthenticated(self, client, mock_graph_db):
        resp = client.post("/api/v1/persons/search", json={"query": "test"})
        assert resp.status_code == 401


# ===================================================================
# POST /api/v1/persons/identify — face identification
# ===================================================================
class TestIdentifyPerson:
    @patch("app.routers.persons.face_service")
    def test_identify_success(self, mock_fs, authenticated_client, mock_graph_db):
        client, user = authenticated_client
        mock_fs.identify_faces_in_image = AsyncMock(return_value={
            "faces_detected": 1,
            "faces": [{
                "face_index": 0,
                "bbox": [10, 20, 30, 40],
                "det_score": 0.95,
                "match_status": "matched",
                "matches": [{"id": "p-1", "name": "Alice", "confidence_score": 0.91}],
            }],
        })

        # Create a fake JPEG file
        fake_jpeg = io.BytesIO(b"\xff\xd8\xff\xe0fake_jpeg_data")
        resp = client.post(
            "/api/v1/persons/identify",
            files={"file": ("photo.jpg", fake_jpeg, "image/jpeg")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["faces_detected"] == 1

    def test_identify_unsupported_file_type(self, authenticated_client, mock_graph_db):
        client, _ = authenticated_client
        fake_file = io.BytesIO(b"not_an_image")
        resp = client.post(
            "/api/v1/persons/identify",
            files={"file": ("doc.pdf", fake_file, "application/pdf")},
        )
        assert resp.status_code == 400
        data = resp.json()
        # Error may be in "detail" (dict or string) or "error" wrapper
        detail = data.get("detail") or data.get("error", {})
        if isinstance(detail, dict):
            assert detail.get("code") == "UNSUPPORTED_FILE_TYPE"
        else:
            assert "UNSUPPORTED_FILE_TYPE" in str(detail) or "Unsupported" in str(detail)

    def test_identify_unauthenticated(self, client, mock_graph_db):
        fake_file = io.BytesIO(b"fake")
        resp = client.post(
            "/api/v1/persons/identify",
            files={"file": ("photo.jpg", fake_file, "image/jpeg")},
        )
        assert resp.status_code == 401


# ===================================================================
# POST /api/v1/persons/{person_id}/face — upload face
# ===================================================================
class TestUploadPersonFace:
    @patch("app.routers.persons.face_service")
    @patch("app.routers.persons.vector_db")
    @patch("aiofiles.open")
    @patch("aiofiles.os.remove", new_callable=AsyncMock)
    def test_upload_face_success(
        self, mock_remove, mock_aioopen, mock_vdb, mock_fs,
        authenticated_client, mock_graph_db, sample_person
    ):
        client, user = authenticated_client
        sample_person["user_id"] = str(user.id)
        mock_graph_db.get_person_node.return_value = sample_person
        mock_graph_db.update_person_node.return_value = sample_person

        mock_fs.generate_face_embedding.return_value = [0.1] * 512
        mock_vdb.upsert_face_embedding.return_value = None

        # Mock aiofiles.open context manager
        mock_file = MagicMock()
        mock_file.__aenter__ = AsyncMock(return_value=mock_file)
        mock_file.__aexit__ = AsyncMock(return_value=False)
        mock_file.write = AsyncMock()
        mock_aioopen.return_value = mock_file

        fake_jpeg = io.BytesIO(b"\xff\xd8\xff\xe0fake_jpeg")
        resp = client.post(
            "/api/v1/persons/person-123/face",
            files={"file": ("face.jpg", fake_jpeg, "image/jpeg")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["person_id"] == "person-123"
        assert "face_image_url" in data

    def test_upload_face_unsupported_type(self, authenticated_client, mock_graph_db):
        client, _ = authenticated_client
        fake_file = io.BytesIO(b"fake")
        resp = client.post(
            "/api/v1/persons/person-123/face",
            files={"file": ("face.bmp", fake_file, "image/bmp")},
        )
        assert resp.status_code == 400

    def test_upload_face_person_not_found(self, authenticated_client, mock_graph_db):
        client, _ = authenticated_client
        mock_graph_db.get_person_node.return_value = None

        fake_jpeg = io.BytesIO(b"\xff\xd8\xff\xe0fake")
        resp = client.post(
            "/api/v1/persons/nonexistent/face",
            files={"file": ("face.jpg", fake_jpeg, "image/jpeg")},
        )
        assert resp.status_code == 404

    def test_upload_face_other_users_person(self, authenticated_client, mock_graph_db, sample_person):
        client, _ = authenticated_client
        sample_person["user_id"] = "other-user-id"
        mock_graph_db.get_person_node.return_value = sample_person

        fake_jpeg = io.BytesIO(b"\xff\xd8\xff\xe0fake")
        resp = client.post(
            "/api/v1/persons/person-123/face",
            files={"file": ("face.jpg", fake_jpeg, "image/jpeg")},
        )
        assert resp.status_code == 404

    def test_upload_face_unauthenticated(self, client, mock_graph_db):
        fake_file = io.BytesIO(b"fake")
        resp = client.post(
            "/api/v1/persons/person-123/face",
            files={"file": ("face.jpg", fake_file, "image/jpeg")},
        )
        assert resp.status_code == 401
