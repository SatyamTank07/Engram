"""
Tests for Neo4j <-> pgvector embedding sync consistency.

Covers:
- _sync_embedding queues on failure
- delete_person_node ordering (Neo4j first, then embedding)
- sync_worker retry logic, backoff, and edge cases
- vector_db pending sync CRUD helpers
"""

import asyncio
import sys
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

# Pre-import modules so patches work on lazy imports inside function bodies.
# We need these in sys.modules before graph_db / sync_worker do
# "from . import vector_db, embedding_service".
import backend.app.vector_db
import backend.app.embedding_service
import backend.app.graph_db
import backend.app.sync_worker


# ---------------------------------------------------------------------------
# 1. _sync_embedding — queues pending sync on failure
# ---------------------------------------------------------------------------


class TestSyncEmbedding:
    """Tests for graph_db._sync_embedding."""

    def test_successful_sync(self, person_data, fake_embedding):
        """Embedding is generated and upserted when everything works."""
        with (
            patch.object(backend.app.embedding_service, "generate_person_embedding",
                         return_value=("text", fake_embedding)) as mock_gen,
            patch.object(backend.app.vector_db, "upsert_text_embedding") as mock_upsert,
        ):
            backend.app.graph_db._sync_embedding(person_data)

            mock_gen.assert_called_once_with(
                name=person_data["name"],
                aliases=person_data["aliases"],
                short_bio=person_data["short_bio"],
                contacts=person_data["contacts"],
            )
            mock_upsert.assert_called_once_with(
                person_id=person_data["id"],
                user_id=person_data["user_id"],
                text_content="text",
                embedding=fake_embedding,
            )

    def test_queues_pending_on_embedding_failure(self, person_data):
        """When embedding generation fails, a pending sync is queued."""
        with (
            patch.object(backend.app.embedding_service, "generate_person_embedding",
                         side_effect=RuntimeError("OpenAI down")),
            patch.object(backend.app.vector_db, "insert_pending_sync") as mock_queue,
        ):
            backend.app.graph_db._sync_embedding(person_data)

            mock_queue.assert_called_once_with(
                person_id=person_data["id"],
                user_id=person_data["user_id"],
                operation="upsert",
            )

    def test_queues_pending_on_upsert_failure(self, person_data, fake_embedding):
        """When pgvector upsert fails, a pending sync is queued."""
        with (
            patch.object(backend.app.embedding_service, "generate_person_embedding",
                         return_value=("text", fake_embedding)),
            patch.object(backend.app.vector_db, "upsert_text_embedding",
                         side_effect=ConnectionError("DB unreachable")),
            patch.object(backend.app.vector_db, "insert_pending_sync") as mock_queue,
        ):
            backend.app.graph_db._sync_embedding(person_data)

            mock_queue.assert_called_once_with(
                person_id=person_data["id"],
                user_id=person_data["user_id"],
                operation="upsert",
            )

    def test_double_failure_does_not_raise(self, person_data):
        """If both embedding AND queue insertion fail, it logs but doesn't crash."""
        with (
            patch.object(backend.app.embedding_service, "generate_person_embedding",
                         side_effect=RuntimeError("fail")),
            patch.object(backend.app.vector_db, "insert_pending_sync",
                         side_effect=ConnectionError("queue fail")),
        ):
            # Should not raise
            backend.app.graph_db._sync_embedding(person_data)


# ---------------------------------------------------------------------------
# 2. delete_person_node — ordering and failure handling
# ---------------------------------------------------------------------------


class TestDeletePersonNode:
    """Tests for graph_db.delete_person_node."""

    def _make_neo4j_mocks(self, deleted_count=1):
        """Helper to build mock Neo4j driver/session/result."""
        mock_record = MagicMock()
        mock_record.__getitem__ = lambda self, key: deleted_count
        mock_record.__bool__ = lambda self: True

        mock_result = AsyncMock()
        mock_result.single.return_value = mock_record

        mock_session = AsyncMock()
        mock_session.run.return_value = mock_result
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_driver = MagicMock()
        mock_driver.session.return_value = mock_session
        return mock_driver, mock_session

    @pytest.mark.asyncio
    async def test_deletes_neo4j_first_then_embedding(self, person_data):
        """Neo4j node is deleted before the embedding cleanup."""
        call_order = []
        mock_driver, mock_session = self._make_neo4j_mocks(deleted_count=1)

        original_run = mock_session.run

        async def tracked_run(*args, **kwargs):
            call_order.append("neo4j_delete")
            return await original_run(*args, **kwargs)
        mock_session.run = tracked_run

        def tracked_delete_embedding(pid):
            call_order.append("delete_embedding")

        with (
            patch.object(backend.app.graph_db, "get_person_node",
                         new_callable=AsyncMock, return_value=person_data),
            patch.object(backend.app.graph_db, "_get_driver", return_value=mock_driver),
            patch.object(backend.app.vector_db, "delete_embedding",
                         side_effect=tracked_delete_embedding),
        ):
            result = await backend.app.graph_db.delete_person_node(person_data["id"])

            assert result is True
            assert call_order == ["neo4j_delete", "delete_embedding"]

    @pytest.mark.asyncio
    async def test_queues_pending_when_embedding_delete_fails(self, person_data):
        """If embedding deletion fails after Neo4j delete, it queues for retry."""
        mock_driver, _ = self._make_neo4j_mocks(deleted_count=1)

        with (
            patch.object(backend.app.graph_db, "get_person_node",
                         new_callable=AsyncMock, return_value=person_data),
            patch.object(backend.app.graph_db, "_get_driver", return_value=mock_driver),
            patch.object(backend.app.vector_db, "delete_embedding",
                         side_effect=ConnectionError("pg down")),
            patch.object(backend.app.vector_db, "insert_pending_sync") as mock_queue,
        ):
            result = await backend.app.graph_db.delete_person_node(person_data["id"])

            assert result is True
            mock_queue.assert_called_once_with(
                person_data["id"],
                person_data["user_id"],
                operation="delete",
            )

    @pytest.mark.asyncio
    async def test_no_embedding_cleanup_when_node_not_found(self):
        """If the Neo4j node doesn't exist, embedding cleanup is skipped."""
        mock_driver, _ = self._make_neo4j_mocks(deleted_count=0)

        with (
            patch.object(backend.app.graph_db, "get_person_node",
                         new_callable=AsyncMock, return_value=None),
            patch.object(backend.app.graph_db, "_get_driver", return_value=mock_driver),
            patch.object(backend.app.vector_db, "delete_embedding") as mock_del,
            patch.object(backend.app.vector_db, "insert_pending_sync") as mock_queue,
        ):
            result = await backend.app.graph_db.delete_person_node("nonexistent-id")

            mock_del.assert_not_called()
            mock_queue.assert_not_called()


# ---------------------------------------------------------------------------
# 3. sync_worker — retry logic, backoff, and edge cases
# ---------------------------------------------------------------------------


class TestSyncWorkerBackoff:
    """Tests for sync_worker._get_backoff."""

    def test_backoff_values(self):
        from backend.app.sync_worker import _get_backoff

        assert _get_backoff(0) == 30
        assert _get_backoff(1) == 60
        assert _get_backoff(2) == 120
        assert _get_backoff(3) == 240
        assert _get_backoff(4) == 480

    def test_backoff_clamps_at_max(self):
        from backend.app.sync_worker import _get_backoff

        assert _get_backoff(5) == 480
        assert _get_backoff(100) == 480


class TestProcessPendingSyncs:
    """Tests for sync_worker._process_pending_syncs."""

    @pytest.mark.asyncio
    async def test_no_pending_syncs_is_noop(self):
        """Worker does nothing when there are no pending syncs."""
        async def mock_threadpool(fn, *args, **kwargs):
            return fn(*args, **kwargs)

        with (
            patch.object(backend.app.vector_db, "get_pending_syncs", return_value=[]),
            patch.object(backend.app.sync_worker, "run_in_threadpool",
                         side_effect=mock_threadpool),
        ):
            await backend.app.sync_worker._process_pending_syncs()
            # No error, nothing processed

    @pytest.mark.asyncio
    async def test_successful_upsert_retry(self, person_data, pending_sync_row, fake_embedding):
        """Successful upsert retry deletes the pending record."""
        async def mock_threadpool(fn, *args, **kwargs):
            return fn(*args, **kwargs)

        with (
            patch.object(backend.app.vector_db, "get_pending_syncs",
                         return_value=[pending_sync_row]),
            patch.object(backend.app.vector_db, "upsert_text_embedding") as mock_upsert,
            patch.object(backend.app.vector_db, "delete_pending_sync") as mock_del,
            patch.object(backend.app.graph_db, "get_person_node",
                         new_callable=AsyncMock, return_value=person_data),
            patch.object(backend.app.embedding_service, "generate_person_embedding",
                         return_value=("text", fake_embedding)),
            patch.object(backend.app.sync_worker, "run_in_threadpool",
                         side_effect=mock_threadpool),
        ):
            await backend.app.sync_worker._process_pending_syncs()

            mock_upsert.assert_called_once()
            mock_del.assert_called_once_with(pending_sync_row["id"])

    @pytest.mark.asyncio
    async def test_successful_delete_retry(self, pending_sync_row):
        """Successful delete retry removes the pending record."""
        pending_sync_row["operation"] = "delete"

        async def mock_threadpool(fn, *args, **kwargs):
            return fn(*args, **kwargs)

        with (
            patch.object(backend.app.vector_db, "get_pending_syncs",
                         return_value=[pending_sync_row]),
            patch.object(backend.app.vector_db, "delete_embedding") as mock_del_emb,
            patch.object(backend.app.vector_db, "delete_pending_sync") as mock_del_sync,
            patch.object(backend.app.sync_worker, "run_in_threadpool",
                         side_effect=mock_threadpool),
        ):
            await backend.app.sync_worker._process_pending_syncs()

            mock_del_emb.assert_called_once_with(pending_sync_row["person_id"])
            mock_del_sync.assert_called_once_with(pending_sync_row["id"])

    @pytest.mark.asyncio
    async def test_failed_retry_updates_backoff(self, pending_sync_row, person_data):
        """Failed retry increments retry_count and sets backoff."""
        async def mock_threadpool(fn, *args, **kwargs):
            return fn(*args, **kwargs)

        with (
            patch.object(backend.app.vector_db, "get_pending_syncs",
                         return_value=[pending_sync_row]),
            patch.object(backend.app.vector_db, "update_pending_sync_retry") as mock_update,
            patch.object(backend.app.graph_db, "get_person_node",
                         new_callable=AsyncMock, return_value=person_data),
            patch.object(backend.app.embedding_service, "generate_person_embedding",
                         side_effect=RuntimeError("API error")),
            patch.object(backend.app.sync_worker, "run_in_threadpool",
                         side_effect=mock_threadpool),
        ):
            await backend.app.sync_worker._process_pending_syncs()

            mock_update.assert_called_once()
            args = mock_update.call_args[0]
            assert args[0] == pending_sync_row["id"]  # sync_id
            assert args[1] == 1  # new retry_count
            assert args[2] == 60  # backoff for retry_count=1
            assert "API error" in args[3]  # error message

    @pytest.mark.asyncio
    async def test_discards_sync_for_deleted_person(self, pending_sync_row):
        """If the person no longer exists in Neo4j, the sync is discarded."""
        async def mock_threadpool(fn, *args, **kwargs):
            return fn(*args, **kwargs)

        with (
            patch.object(backend.app.vector_db, "get_pending_syncs",
                         return_value=[pending_sync_row]),
            patch.object(backend.app.vector_db, "delete_pending_sync") as mock_del,
            patch.object(backend.app.vector_db, "upsert_text_embedding") as mock_upsert,
            patch.object(backend.app.graph_db, "get_person_node",
                         new_callable=AsyncMock, return_value=None),
            patch.object(backend.app.sync_worker, "run_in_threadpool",
                         side_effect=mock_threadpool),
        ):
            await backend.app.sync_worker._process_pending_syncs()

            mock_del.assert_called_once_with(pending_sync_row["id"])
            mock_upsert.assert_not_called()

    @pytest.mark.asyncio
    async def test_processes_multiple_syncs(self, person_data, fake_embedding):
        """Worker processes all pending syncs in a single poll."""
        rows = [
            {"id": str(uuid.uuid4()), "person_id": person_data["id"],
             "user_id": person_data["user_id"], "operation": "upsert", "retry_count": 0},
            {"id": str(uuid.uuid4()), "person_id": str(uuid.uuid4()),
             "user_id": person_data["user_id"], "operation": "delete", "retry_count": 2},
        ]

        async def mock_threadpool(fn, *args, **kwargs):
            return fn(*args, **kwargs)

        with (
            patch.object(backend.app.vector_db, "get_pending_syncs", return_value=rows),
            patch.object(backend.app.vector_db, "delete_pending_sync") as mock_del,
            patch.object(backend.app.vector_db, "delete_embedding"),
            patch.object(backend.app.vector_db, "upsert_text_embedding"),
            patch.object(backend.app.graph_db, "get_person_node",
                         new_callable=AsyncMock, return_value=person_data),
            patch.object(backend.app.embedding_service, "generate_person_embedding",
                         return_value=("text", fake_embedding)),
            patch.object(backend.app.sync_worker, "run_in_threadpool",
                         side_effect=mock_threadpool),
        ):
            await backend.app.sync_worker._process_pending_syncs()

            assert mock_del.call_count == 2


class TestRunSyncWorker:
    """Tests for sync_worker.run_sync_worker lifecycle."""

    @pytest.mark.asyncio
    async def test_worker_stops_on_cancellation(self):
        """Worker exits cleanly when the task is cancelled."""
        call_count = 0

        async def process_and_count():
            nonlocal call_count
            call_count += 1

        async def fake_sleep(seconds):
            raise asyncio.CancelledError()

        with (
            patch.object(backend.app.sync_worker, "_process_pending_syncs",
                         side_effect=process_and_count),
            patch("asyncio.sleep", side_effect=fake_sleep),
        ):
            task = asyncio.create_task(backend.app.sync_worker.run_sync_worker())
            await task

        assert call_count == 1

    @pytest.mark.asyncio
    async def test_worker_continues_after_unexpected_error(self):
        """Worker logs errors but keeps running."""
        iteration = 0

        async def flaky_process():
            nonlocal iteration
            iteration += 1
            if iteration == 1:
                raise ValueError("unexpected boom")

        async def fake_sleep(seconds):
            if iteration >= 2:
                raise asyncio.CancelledError()

        with (
            patch.object(backend.app.sync_worker, "_process_pending_syncs",
                         side_effect=flaky_process),
            patch("asyncio.sleep", side_effect=fake_sleep),
        ):
            task = asyncio.create_task(backend.app.sync_worker.run_sync_worker())
            await task

        assert iteration == 2  # Worker continued past the error


# ---------------------------------------------------------------------------
# 4. vector_db pending sync helpers — unit tests (mocked DB)
# ---------------------------------------------------------------------------


class TestVectorDbPendingSyncHelpers:
    """Tests for vector_db pending sync CRUD functions with mocked connections."""

    def _make_conn_mocks(self):
        """Helper: create mock cursor + connection for _pooled_connection."""
        mock_cur = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        return mock_conn, mock_cur

    def test_insert_pending_sync(self):
        """insert_pending_sync executes correct SQL."""
        mock_conn, mock_cur = self._make_conn_mocks()

        with patch.object(backend.app.vector_db, "_pooled_connection") as mock_pool:
            mock_pool.return_value.__enter__ = MagicMock(return_value=mock_conn)
            mock_pool.return_value.__exit__ = MagicMock(return_value=False)

            backend.app.vector_db.insert_pending_sync("person-1", "user-1", "upsert")

            mock_cur.execute.assert_called_once()
            sql = mock_cur.execute.call_args[0][0]
            assert "INSERT INTO pending_embedding_syncs" in sql
            assert "ON CONFLICT DO NOTHING" in sql
            mock_conn.commit.assert_called_once()

    def test_get_pending_syncs(self):
        """get_pending_syncs queries with correct WHERE clause."""
        mock_conn, mock_cur = self._make_conn_mocks()
        mock_cur.fetchall.return_value = [
            {"id": "s1", "person_id": "p1", "user_id": "u1",
             "operation": "upsert", "retry_count": 0}
        ]

        with patch.object(backend.app.vector_db, "_pooled_connection") as mock_pool:
            mock_pool.return_value.__enter__ = MagicMock(return_value=mock_conn)
            mock_pool.return_value.__exit__ = MagicMock(return_value=False)

            results = backend.app.vector_db.get_pending_syncs(limit=10)

            assert len(results) == 1
            assert results[0]["person_id"] == "p1"
            sql = mock_cur.execute.call_args[0][0]
            assert "retry_count < max_retries" in sql
            assert "next_retry_at <= NOW()" in sql

    def test_delete_pending_sync(self):
        """delete_pending_sync deletes by id."""
        mock_conn, mock_cur = self._make_conn_mocks()

        with patch.object(backend.app.vector_db, "_pooled_connection") as mock_pool:
            mock_pool.return_value.__enter__ = MagicMock(return_value=mock_conn)
            mock_pool.return_value.__exit__ = MagicMock(return_value=False)

            backend.app.vector_db.delete_pending_sync("sync-123")

            sql = mock_cur.execute.call_args[0][0]
            assert "DELETE FROM pending_embedding_syncs" in sql
            params = mock_cur.execute.call_args[0][1]
            assert params == ("sync-123",)
            mock_conn.commit.assert_called_once()

    def test_update_pending_sync_retry(self):
        """update_pending_sync_retry sets retry_count, next_retry_at, and error."""
        mock_conn, mock_cur = self._make_conn_mocks()

        with patch.object(backend.app.vector_db, "_pooled_connection") as mock_pool:
            mock_pool.return_value.__enter__ = MagicMock(return_value=mock_conn)
            mock_pool.return_value.__exit__ = MagicMock(return_value=False)

            backend.app.vector_db.update_pending_sync_retry(
                "sync-456", 3, 120, "connection refused"
            )

            sql = mock_cur.execute.call_args[0][0]
            assert "UPDATE pending_embedding_syncs" in sql
            assert "retry_count" in sql
            assert "next_retry_at" in sql
            assert "last_error" in sql
            params = mock_cur.execute.call_args[0][1]
            assert params[0] == 3  # retry_count
            assert params[2] == "connection refused"  # error
            assert params[3] == "sync-456"  # id
            mock_conn.commit.assert_called_once()

    def test_get_pending_sync_stats(self):
        """get_pending_sync_stats returns total/pending/failed counts."""
        mock_conn, mock_cur = self._make_conn_mocks()
        mock_cur.fetchone.return_value = {"total": 5, "pending": 3, "failed": 2}

        with patch.object(backend.app.vector_db, "_pooled_connection") as mock_pool:
            mock_pool.return_value.__enter__ = MagicMock(return_value=mock_conn)
            mock_pool.return_value.__exit__ = MagicMock(return_value=False)

            stats = backend.app.vector_db.get_pending_sync_stats()

            assert stats == {"total": 5, "pending": 3, "failed": 2}


# ---------------------------------------------------------------------------
# 5. create_person_node — Neo4j write happens before embedding sync
# ---------------------------------------------------------------------------


class TestCreatePersonNode:
    """Tests for graph_db.create_person_node embedding sync behavior."""

    @pytest.mark.asyncio
    async def test_neo4j_write_happens_before_embedding_sync(self):
        """The Neo4j CREATE is executed before _sync_embedding is called."""
        mock_node = MagicMock()
        mock_node.__iter__ = MagicMock(return_value=iter([
            ("id", "p-1"), ("user_id", "u-1"), ("name", "Alice"),
            ("aliases", []), ("contacts", "{}"),
            ("short_bio", ""), ("trust_score", "0.0"),
            ("first_seen", "2025-01-01"), ("last_seen", "2025-01-01"),
        ]))
        mock_node.__contains__ = lambda self, key: key in dict(self)
        mock_node.__getitem__ = lambda self, key: dict(iter(self))[key]

        mock_record = MagicMock()
        mock_record.__getitem__ = lambda self, key: mock_node

        mock_result = AsyncMock()
        mock_result.single.return_value = mock_record

        mock_session = AsyncMock()
        mock_session.run.return_value = mock_result
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_driver = MagicMock()
        mock_driver.session.return_value = mock_session

        with (
            patch.object(backend.app.graph_db, "_get_driver", return_value=mock_driver),
            patch("asyncio.to_thread", new_callable=AsyncMock,
                  side_effect=RuntimeError("boom")),
        ):
            # The embedding sync fails, but Neo4j write should have happened
            try:
                await backend.app.graph_db.create_person_node("u-1", "Alice")
            except RuntimeError:
                pass

            mock_session.run.assert_called_once()  # Neo4j CREATE was executed
