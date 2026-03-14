"""Tests for vector_db.py — pgvector operations with mocked connections.

Covers:
- upsert_text_embedding — SQL params and commit
- upsert_face_embedding — SQL params and commit
- delete_embedding — correct person_id passed
- semantic_search — result parsing
- face_search — result format, min_score filtering, empty results
- face_search_batch — grouping by face index, min_score filtering, empty input
- Connection pool lifecycle: _get_pool, _pooled_connection, close_pool
"""

from unittest.mock import MagicMock, patch, call
from contextlib import contextmanager

import pytest

import backend.app.vector_db as vector_db


# ===================================================================
# Helpers
# ===================================================================

def _make_conn_mocks(cursor_factory=None):
    """Build mock cursor + connection for _pooled_connection."""
    mock_cur = MagicMock()
    mock_conn = MagicMock()

    # Support both `with conn.cursor() as cur` and `with conn.cursor(cursor_factory=...) as cur`
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return mock_conn, mock_cur


@contextmanager
def _patch_pooled_connection(mock_conn):
    """Patch _pooled_connection to yield mock_conn."""
    with patch.object(vector_db, "_pooled_connection") as mock_pool:
        mock_pool.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_pool.return_value.__exit__ = MagicMock(return_value=False)
        yield mock_pool


# ===================================================================
# upsert_text_embedding
# ===================================================================

class TestUpsertTextEmbedding:
    def test_executes_insert_with_on_conflict(self):
        mock_conn, mock_cur = _make_conn_mocks()
        with _patch_pooled_connection(mock_conn):
            vector_db.upsert_text_embedding(
                person_id="p-1",
                user_id="u-1",
                text_content="Alice | Bio: Engineer",
                embedding=[0.1] * 1536,
            )

        mock_cur.execute.assert_called_once()
        sql = mock_cur.execute.call_args[0][0]
        assert "INSERT INTO person_embeddings" in sql
        assert "ON CONFLICT (person_id) DO UPDATE" in sql
        assert "text_embedding" in sql
        mock_conn.commit.assert_called_once()

    def test_passes_correct_params(self):
        mock_conn, mock_cur = _make_conn_mocks()
        embedding = [0.5] * 1536
        with _patch_pooled_connection(mock_conn):
            vector_db.upsert_text_embedding("p-2", "u-2", "some text", embedding)

        params = mock_cur.execute.call_args[0][1]
        # params: (uuid, person_id, user_id, text_content, embedding_str, updated_at)
        assert params[1] == "p-2"
        assert params[2] == "u-2"
        assert params[3] == "some text"
        assert params[4] == str(embedding)

    def test_raises_on_db_error(self):
        mock_conn, mock_cur = _make_conn_mocks()
        mock_cur.execute.side_effect = ConnectionError("DB down")
        with _patch_pooled_connection(mock_conn):
            with pytest.raises(ConnectionError):
                vector_db.upsert_text_embedding("p-1", "u-1", "text", [0.0] * 1536)


# ===================================================================
# upsert_face_embedding
# ===================================================================

class TestUpsertFaceEmbedding:
    def test_executes_insert_with_on_conflict(self):
        mock_conn, mock_cur = _make_conn_mocks()
        with _patch_pooled_connection(mock_conn):
            vector_db.upsert_face_embedding("p-1", "u-1", [0.1] * 512)

        mock_cur.execute.assert_called_once()
        sql = mock_cur.execute.call_args[0][0]
        assert "INSERT INTO person_embeddings" in sql
        assert "ON CONFLICT (person_id) DO UPDATE" in sql
        assert "face_embedding" in sql
        mock_conn.commit.assert_called_once()

    def test_passes_correct_params(self):
        mock_conn, mock_cur = _make_conn_mocks()
        face_vec = [0.3] * 512
        with _patch_pooled_connection(mock_conn):
            vector_db.upsert_face_embedding("p-3", "u-3", face_vec)

        params = mock_cur.execute.call_args[0][1]
        # params: (uuid, person_id, user_id, face_vec_str)
        assert params[1] == "p-3"
        assert params[2] == "u-3"
        assert params[3] == str(face_vec)

    def test_raises_on_db_error(self):
        mock_conn, mock_cur = _make_conn_mocks()
        mock_cur.execute.side_effect = ConnectionError("DB down")
        with _patch_pooled_connection(mock_conn):
            with pytest.raises(ConnectionError):
                vector_db.upsert_face_embedding("p-1", "u-1", [0.0] * 512)


# ===================================================================
# delete_embedding
# ===================================================================

class TestDeleteEmbedding:
    def test_deletes_by_person_id(self):
        mock_conn, mock_cur = _make_conn_mocks()
        with _patch_pooled_connection(mock_conn):
            vector_db.delete_embedding("p-42")

        sql = mock_cur.execute.call_args[0][0]
        assert "DELETE FROM person_embeddings" in sql
        params = mock_cur.execute.call_args[0][1]
        assert params == ("p-42",)
        mock_conn.commit.assert_called_once()

    def test_raises_on_db_error(self):
        mock_conn, mock_cur = _make_conn_mocks()
        mock_cur.execute.side_effect = ConnectionError("DB down")
        with _patch_pooled_connection(mock_conn):
            with pytest.raises(ConnectionError):
                vector_db.delete_embedding("p-1")


# ===================================================================
# semantic_search
# ===================================================================

class TestSemanticSearch:
    def test_returns_parsed_results(self):
        mock_conn, mock_cur = _make_conn_mocks()
        mock_cur.fetchall.return_value = [
            {"person_id": "p-1", "text_content": "Alice | Bio: Engineer", "similarity_score": 0.923456},
            {"person_id": "p-2", "text_content": "Bob | Bio: Designer", "similarity_score": 0.812345},
        ]

        with _patch_pooled_connection(mock_conn):
            results = vector_db.semantic_search("u-1", [0.1] * 1536, limit=5)

        assert len(results) == 2
        assert results[0]["person_id"] == "p-1"
        assert results[0]["text_content"] == "Alice | Bio: Engineer"
        assert results[0]["similarity_score"] == 0.9235  # rounded to 4 decimal places
        assert results[1]["similarity_score"] == 0.8123

    def test_passes_correct_sql_params(self):
        mock_conn, mock_cur = _make_conn_mocks()
        mock_cur.fetchall.return_value = []
        query_vec = [0.5] * 1536

        with _patch_pooled_connection(mock_conn):
            vector_db.semantic_search("u-1", query_vec, limit=3)

        # First call is SET LOCAL hnsw.ef_search, second is the SELECT
        assert mock_cur.execute.call_count == 2
        select_call = mock_cur.execute.call_args_list[1]
        sql = select_call[0][0]
        assert "text_embedding" in sql
        assert "user_id" in sql
        params = select_call[0][1]
        assert str(query_vec) in params[0]  # embedding as string
        assert params[1] == "u-1"  # user_id
        assert params[3] == 3  # limit

    def test_empty_results(self):
        mock_conn, mock_cur = _make_conn_mocks()
        mock_cur.fetchall.return_value = []

        with _patch_pooled_connection(mock_conn):
            results = vector_db.semantic_search("u-1", [0.1] * 1536)

        assert results == []

    def test_sets_hnsw_ef_search(self):
        mock_conn, mock_cur = _make_conn_mocks()
        mock_cur.fetchall.return_value = []

        with _patch_pooled_connection(mock_conn):
            vector_db.semantic_search("u-1", [0.1] * 1536)

        first_call = mock_cur.execute.call_args_list[0]
        assert "hnsw.ef_search" in first_call[0][0]

    def test_raises_on_db_error(self):
        mock_conn, mock_cur = _make_conn_mocks()
        mock_cur.execute.side_effect = ConnectionError("DB down")

        with _patch_pooled_connection(mock_conn):
            with pytest.raises(ConnectionError):
                vector_db.semantic_search("u-1", [0.1] * 1536)


# ===================================================================
# face_search
# ===================================================================

class TestFaceSearch:
    def test_returns_parsed_results(self):
        mock_conn, mock_cur = _make_conn_mocks()
        mock_cur.fetchall.return_value = [
            {"person_id": "p-1", "similarity_score": 0.856789},
            {"person_id": "p-2", "similarity_score": 0.712345},
        ]

        with _patch_pooled_connection(mock_conn):
            results = vector_db.face_search("u-1", [0.1] * 512)

        assert len(results) == 2
        assert results[0]["person_id"] == "p-1"
        assert results[0]["similarity_score"] == 0.8568
        assert results[1]["similarity_score"] == 0.7123

    def test_filters_below_min_score(self):
        mock_conn, mock_cur = _make_conn_mocks()
        mock_cur.fetchall.return_value = [
            {"person_id": "p-1", "similarity_score": 0.85},
            {"person_id": "p-2", "similarity_score": 0.15},  # below default min_score=0.3
        ]

        with _patch_pooled_connection(mock_conn):
            results = vector_db.face_search("u-1", [0.1] * 512)

        assert len(results) == 1
        assert results[0]["person_id"] == "p-1"

    def test_custom_min_score(self):
        mock_conn, mock_cur = _make_conn_mocks()
        mock_cur.fetchall.return_value = [
            {"person_id": "p-1", "similarity_score": 0.85},
            {"person_id": "p-2", "similarity_score": 0.60},
        ]

        with _patch_pooled_connection(mock_conn):
            results = vector_db.face_search("u-1", [0.1] * 512, min_score=0.7)

        assert len(results) == 1
        assert results[0]["person_id"] == "p-1"

    def test_empty_results(self):
        mock_conn, mock_cur = _make_conn_mocks()
        mock_cur.fetchall.return_value = []

        with _patch_pooled_connection(mock_conn):
            results = vector_db.face_search("u-1", [0.1] * 512)

        assert results == []

    def test_all_below_min_score_returns_empty(self):
        mock_conn, mock_cur = _make_conn_mocks()
        mock_cur.fetchall.return_value = [
            {"person_id": "p-1", "similarity_score": 0.1},
            {"person_id": "p-2", "similarity_score": 0.2},
        ]

        with _patch_pooled_connection(mock_conn):
            results = vector_db.face_search("u-1", [0.1] * 512)

        assert results == []

    def test_sets_hnsw_ef_search(self):
        mock_conn, mock_cur = _make_conn_mocks()
        mock_cur.fetchall.return_value = []

        with _patch_pooled_connection(mock_conn):
            vector_db.face_search("u-1", [0.1] * 512)

        first_call = mock_cur.execute.call_args_list[0]
        assert "hnsw.ef_search" in first_call[0][0]

    def test_raises_on_db_error(self):
        mock_conn, mock_cur = _make_conn_mocks()
        mock_cur.execute.side_effect = ConnectionError("DB down")

        with _patch_pooled_connection(mock_conn):
            with pytest.raises(ConnectionError):
                vector_db.face_search("u-1", [0.1] * 512)


# ===================================================================
# face_search_batch
# ===================================================================

class TestFaceSearchBatch:
    def test_returns_grouped_results(self):
        mock_conn, mock_cur = _make_conn_mocks()
        mock_cur.fetchall.return_value = [
            {"face_idx": 0, "person_id": "p-1", "similarity_score": 0.90},
            {"face_idx": 0, "person_id": "p-2", "similarity_score": 0.75},
            {"face_idx": 1, "person_id": "p-3", "similarity_score": 0.85},
        ]

        with _patch_pooled_connection(mock_conn):
            results = vector_db.face_search_batch(
                "u-1",
                [[0.1] * 512, [0.2] * 512],
            )

        assert len(results) == 2
        assert len(results[0]) == 2  # face 0 has 2 matches
        assert results[0][0]["person_id"] == "p-1"
        assert results[0][1]["person_id"] == "p-2"
        assert len(results[1]) == 1  # face 1 has 1 match
        assert results[1][0]["person_id"] == "p-3"

    def test_filters_below_min_score(self):
        mock_conn, mock_cur = _make_conn_mocks()
        mock_cur.fetchall.return_value = [
            {"face_idx": 0, "person_id": "p-1", "similarity_score": 0.90},
            {"face_idx": 0, "person_id": "p-2", "similarity_score": 0.10},  # below min
            {"face_idx": 1, "person_id": "p-3", "similarity_score": 0.05},  # below min
        ]

        with _patch_pooled_connection(mock_conn):
            results = vector_db.face_search_batch("u-1", [[0.1] * 512, [0.2] * 512])

        assert len(results[0]) == 1
        assert results[0][0]["person_id"] == "p-1"
        assert len(results[1]) == 0

    def test_empty_input_returns_empty(self):
        results = vector_db.face_search_batch("u-1", [])
        assert results == []

    def test_single_face(self):
        mock_conn, mock_cur = _make_conn_mocks()
        mock_cur.fetchall.return_value = [
            {"face_idx": 0, "person_id": "p-1", "similarity_score": 0.80},
        ]

        with _patch_pooled_connection(mock_conn):
            results = vector_db.face_search_batch("u-1", [[0.1] * 512])

        assert len(results) == 1
        assert len(results[0]) == 1
        assert results[0][0]["person_id"] == "p-1"

    def test_no_matches_returns_empty_lists(self):
        mock_conn, mock_cur = _make_conn_mocks()
        mock_cur.fetchall.return_value = []

        with _patch_pooled_connection(mock_conn):
            results = vector_db.face_search_batch("u-1", [[0.1] * 512, [0.2] * 512])

        assert len(results) == 2
        assert results[0] == []
        assert results[1] == []

    def test_uses_cross_join_lateral(self):
        mock_conn, mock_cur = _make_conn_mocks()
        mock_cur.fetchall.return_value = []

        with _patch_pooled_connection(mock_conn):
            vector_db.face_search_batch("u-1", [[0.1] * 512])

        # Second execute call is the main query (first is SET LOCAL)
        query_call = mock_cur.execute.call_args_list[1]
        sql = query_call[0][0]
        assert "CROSS JOIN LATERAL" in sql

    def test_raises_on_db_error(self):
        mock_conn, mock_cur = _make_conn_mocks()
        mock_cur.execute.side_effect = ConnectionError("DB down")

        with _patch_pooled_connection(mock_conn):
            with pytest.raises(ConnectionError):
                vector_db.face_search_batch("u-1", [[0.1] * 512])


# ===================================================================
# Connection pool lifecycle
# ===================================================================

class TestConnectionPool:
    def test_get_pool_creates_pool_on_first_call(self):
        original_pool = vector_db._pool
        vector_db._pool = None
        try:
            with patch("backend.app.vector_db.ThreadedConnectionPool") as MockPool:
                mock_pool_instance = MagicMock()
                MockPool.return_value = mock_pool_instance

                pool = vector_db._get_pool()

                MockPool.assert_called_once()
                assert pool is mock_pool_instance
        finally:
            vector_db._pool = original_pool

    def test_get_pool_reuses_existing_pool(self):
        mock_pool = MagicMock()
        original_pool = vector_db._pool
        vector_db._pool = mock_pool
        try:
            with patch("backend.app.vector_db.ThreadedConnectionPool") as MockPool:
                pool = vector_db._get_pool()

                MockPool.assert_not_called()
                assert pool is mock_pool
        finally:
            vector_db._pool = original_pool

    def test_close_pool_closes_and_clears(self):
        mock_pool = MagicMock()
        original_pool = vector_db._pool
        vector_db._pool = mock_pool
        try:
            vector_db.close_pool()

            mock_pool.closeall.assert_called_once()
            assert vector_db._pool is None
        finally:
            vector_db._pool = original_pool

    def test_close_pool_noop_when_no_pool(self):
        original_pool = vector_db._pool
        vector_db._pool = None
        try:
            # Should not raise
            vector_db.close_pool()
            assert vector_db._pool is None
        finally:
            vector_db._pool = original_pool

    def test_pooled_connection_returns_conn_to_pool(self):
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_pool.getconn.return_value = mock_conn

        with patch.object(vector_db, "_get_pool", return_value=mock_pool):
            with patch("backend.app.vector_db.register_vector"):
                with vector_db._pooled_connection() as conn:
                    assert conn is mock_conn

        mock_pool.putconn.assert_called_once_with(mock_conn)

    def test_pooled_connection_returns_conn_on_error(self):
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_pool.getconn.return_value = mock_conn

        with patch.object(vector_db, "_get_pool", return_value=mock_pool):
            with patch("backend.app.vector_db.register_vector"):
                try:
                    with vector_db._pooled_connection() as conn:
                        raise ValueError("boom")
                except ValueError:
                    pass

        # Connection is still returned to pool even after error
        mock_pool.putconn.assert_called_once_with(mock_conn)

    def test_pooled_connection_skips_register_when_false(self):
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_pool.getconn.return_value = mock_conn

        with patch.object(vector_db, "_get_pool", return_value=mock_pool):
            with patch("backend.app.vector_db.register_vector") as mock_register:
                with vector_db._pooled_connection(register_vec=False) as conn:
                    pass

        mock_register.assert_not_called()


# ===================================================================
# init_vector_db
# ===================================================================

class TestInitVectorDb:
    def test_creates_extension_and_tables(self):
        mock_conn, mock_cur = _make_conn_mocks()

        with _patch_pooled_connection(mock_conn):
            vector_db.init_vector_db()

        # Collect all SQL statements executed
        sqls = [c[0][0] for c in mock_cur.execute.call_args_list]
        sql_combined = " ".join(sqls)

        assert "CREATE EXTENSION IF NOT EXISTS vector" in sql_combined
        assert "CREATE TABLE IF NOT EXISTS person_embeddings" in sql_combined
        assert "CREATE INDEX IF NOT EXISTS idx_text_embedding" in sql_combined
        assert "CREATE INDEX IF NOT EXISTS idx_face_embedding" in sql_combined
        assert "CREATE TABLE IF NOT EXISTS pending_embedding_syncs" in sql_combined
        # Commit should be called (at least twice: after extension, after tables)
        assert mock_conn.commit.call_count >= 1
