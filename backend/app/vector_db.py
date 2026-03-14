"""
pgvector operations for person embeddings.

Manages the person_embeddings table in PostgreSQL with the pgvector extension.
Provides upsert, delete, and semantic similarity search.
"""

import logging
import os
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool
from pgvector.psycopg2 import register_vector

# Use the same DATABASE_URL as SQLAlchemy
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/engram"
)

# Pool configuration (tunable via environment)
DB_POOL_MIN = int(os.getenv("DB_POOL_MIN", "2"))
DB_POOL_MAX = int(os.getenv("DB_POOL_MAX", "10"))

# Embedding dimensions
TEXT_EMBEDDING_DIM = 1536  # OpenAI text-embedding-3-small
FACE_EMBEDDING_DIM = 512   # Phase 2: CLIP

# HNSW index tuning (configurable via environment)
HNSW_M = int(os.getenv("HNSW_M", "16"))
HNSW_EF_CONSTRUCTION = int(os.getenv("HNSW_EF_CONSTRUCTION", "200"))
HNSW_EF_SEARCH = int(os.getenv("HNSW_EF_SEARCH", "100"))
RECREATE_INDEXES = os.getenv("RECREATE_INDEXES", "false").lower() == "true"

# Module-level connection pool (initialized lazily)
_pool: ThreadedConnectionPool | None = None


def _get_pool() -> ThreadedConnectionPool:
    """Return the connection pool, creating it on first use."""
    global _pool
    if _pool is None:
        logger.info("Creating pgvector connection pool (min=%d, max=%d)", DB_POOL_MIN, DB_POOL_MAX)
        _pool = ThreadedConnectionPool(DB_POOL_MIN, DB_POOL_MAX, DATABASE_URL)
    return _pool


@contextmanager
def _pooled_connection(register_vec: bool = True):
    """Checkout a connection from the pool and return it when done.

    Args:
        register_vec: If True, register the pgvector type on the connection.
                      Set to False for DDL operations before the extension exists.
    """
    pool = _get_pool()
    conn = pool.getconn()
    try:
        if register_vec:
            register_vector(conn)
        yield conn
    finally:
        pool.putconn(conn)


def close_pool():
    """Close all connections in the pool. Call on application shutdown."""
    global _pool
    if _pool is not None:
        _pool.closeall()
        _pool = None
        logger.info("pgvector connection pool closed")


def init_vector_db():
    """
    Create the pgvector extension, person_embeddings table, and indexes.
    Called once on application startup.
    Uses register_vec=False since the vector extension may not exist yet.
    """
    logger.info("Initializing pgvector schema...")
    with _pooled_connection(register_vec=False) as conn:
        with conn.cursor() as cur:
            # Enable the vector extension — must happen BEFORE any vector type usage
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            conn.commit()

            # Now create the embeddings table (vector type is now available)
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS person_embeddings (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    person_id VARCHAR(255) UNIQUE NOT NULL,
                    user_id VARCHAR(255) NOT NULL,
                    text_content TEXT,
                    text_embedding vector({TEXT_EMBEDDING_DIM}),
                    face_embedding vector({FACE_EMBEDDING_DIM}),
                    updated_at TIMESTAMP DEFAULT NOW()
                );
            """)

            # HNSW indexes with tuned parameters for better recall
            if RECREATE_INDEXES:
                cur.execute("DROP INDEX IF EXISTS idx_text_embedding;")
                cur.execute("DROP INDEX IF EXISTS idx_face_embedding;")

            cur.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_text_embedding
                ON person_embeddings
                USING hnsw (text_embedding vector_cosine_ops)
                WITH (m = {HNSW_M}, ef_construction = {HNSW_EF_CONSTRUCTION});
            """)

            cur.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_face_embedding
                ON person_embeddings
                USING hnsw (face_embedding vector_cosine_ops)
                WITH (m = {HNSW_M}, ef_construction = {HNSW_EF_CONSTRUCTION});
            """)

            # Index for fast user_id filtering
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_emb_user_id
                ON person_embeddings (user_id);
            """)

            # Pending embedding syncs table for retry logic
            cur.execute("""
                CREATE TABLE IF NOT EXISTS pending_embedding_syncs (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    person_id VARCHAR(255) NOT NULL,
                    user_id VARCHAR(255) NOT NULL,
                    operation VARCHAR(20) NOT NULL,
                    retry_count INT DEFAULT 0,
                    max_retries INT DEFAULT 5,
                    next_retry_at TIMESTAMP DEFAULT NOW(),
                    created_at TIMESTAMP DEFAULT NOW(),
                    last_error TEXT
                );
            """)

            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_pending_sync_next_retry
                ON pending_embedding_syncs (next_retry_at)
                WHERE retry_count < max_retries;
            """)

        conn.commit()
    logger.info("pgvector schema ready")


def upsert_text_embedding(
    person_id: str,
    user_id: str,
    text_content: str,
    embedding: list[float],
):
    """
    Insert or update the text embedding for a person.
    Uses ON CONFLICT for idempotent upserts.
    """
    try:
        with _pooled_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO person_embeddings
                        (id, person_id, user_id, text_content, text_embedding, updated_at)
                    VALUES
                        (%s, %s, %s, %s, %s::vector, %s)
                    ON CONFLICT (person_id) DO UPDATE SET
                        text_content = EXCLUDED.text_content,
                        text_embedding = EXCLUDED.text_embedding,
                        updated_at = EXCLUDED.updated_at
                    """,
                    (
                        str(uuid.uuid4()),
                        person_id,
                        user_id,
                        text_content,
                        str(embedding),
                        datetime.now(timezone.utc),
                    ),
                )
            conn.commit()
    except Exception as e:
        logger.error("Failed to upsert text embedding for person_id=%s: %s", person_id, e)
        raise


def upsert_face_embedding(person_id: str, user_id: str, face_vector: list[float]):
    """
    Store or update the face embedding for a person.
    Only updates the face_embedding column — text_embedding is untouched.
    Creates a row if none exists yet (person may not have a text embedding yet).
    """
    try:
        with _pooled_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO person_embeddings
                        (id, person_id, user_id, face_embedding, updated_at)
                    VALUES
                        (%s, %s, %s, %s::vector, NOW())
                    ON CONFLICT (person_id) DO UPDATE SET
                        face_embedding = EXCLUDED.face_embedding,
                        updated_at = NOW()
                    """,
                    (str(uuid.uuid4()), person_id, user_id, str(face_vector)),
                )
            conn.commit()
    except Exception as e:
        logger.error("Failed to upsert face embedding for person_id=%s: %s", person_id, e)
        raise


def face_search(
    user_id: str,
    query_face_vector: list[float],
    limit: int = 3,
    min_score: float = 0.3,
) -> list[dict]:
    """
    Find persons whose face_embedding is closest to a query image.
    Only searches persons that have a face embedding stored (not NULL).
    Filters out results below min_score to prevent false identifications.

    Returns a list of dicts with person_id and similarity_score
    (0.0 to 1.0, higher = better match), sorted by similarity descending.
    """
    try:
        with _pooled_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(f"SET LOCAL hnsw.ef_search = {HNSW_EF_SEARCH}")
                cur.execute(
                    """
                    SELECT
                        person_id,
                        1 - (face_embedding <=> %s::vector) AS similarity_score
                    FROM person_embeddings
                    WHERE user_id = %s
                      AND face_embedding IS NOT NULL
                    ORDER BY face_embedding <=> %s::vector
                    LIMIT %s
                    """,
                    (str(query_face_vector), user_id, str(query_face_vector), limit),
                )
                rows = cur.fetchall()
                return [
                    {
                        "person_id": row["person_id"],
                        "similarity_score": round(float(row["similarity_score"]), 4),
                    }
                    for row in rows
                    if float(row["similarity_score"]) >= min_score
                ]
    except Exception as e:
        logger.error("Face search failed for user_id=%s: %s", user_id, e)
        raise


def face_search_batch(
    user_id: str,
    query_face_vectors: list[list[float]],
    limit: int = 3,
    min_score: float = 0.3,
) -> list[list[dict]]:
    """
    Batch face search: find closest persons for multiple face embeddings in ONE query.

    Uses CROSS JOIN LATERAL so each face independently uses the HNSW index.
    Returns a list of match-lists, one per input embedding (same order as input).
    """
    if not query_face_vectors:
        return []

    # Build VALUES clause: (0, vec0), (1, vec1), ...
    values_parts = []
    params: list = []
    for idx, vec in enumerate(query_face_vectors):
        values_parts.append(f"(%s, %s::vector)")
        params.extend([idx, str(vec)])

    values_sql = ", ".join(values_parts)

    # user_id and limit params
    params.append(user_id)
    params.append(limit)

    query = f"""
        SELECT
            q.face_idx,
            m.person_id,
            1 - (m.face_embedding <=> q.vec) AS similarity_score
        FROM (VALUES {values_sql}) AS q(face_idx, vec)
        CROSS JOIN LATERAL (
            SELECT person_id, face_embedding
            FROM person_embeddings
            WHERE user_id = %s
              AND face_embedding IS NOT NULL
            ORDER BY face_embedding <=> q.vec
            LIMIT %s
        ) m
        ORDER BY q.face_idx, similarity_score DESC
    """

    try:
        with _pooled_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(f"SET LOCAL hnsw.ef_search = {HNSW_EF_SEARCH}")
                cur.execute(query, params)
                rows = cur.fetchall()

        # Group results by face index
        results: list[list[dict]] = [[] for _ in query_face_vectors]
        for row in rows:
            score = round(float(row["similarity_score"]), 4)
            if score >= min_score:
                results[int(row["face_idx"])].append({
                    "person_id": row["person_id"],
                    "similarity_score": score,
                })

        return results
    except Exception as e:
        logger.error("Batch face search failed: %s", e)
        raise


def delete_embedding(person_id: str):
    """Delete the embedding record for a person."""
    try:
        with _pooled_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM person_embeddings WHERE person_id = %s",
                    (person_id,),
                )
            conn.commit()
    except Exception as e:
        logger.error("Failed to delete embedding for person_id=%s: %s", person_id, e)
        raise


def semantic_search(
    user_id: str,
    query_embedding: list[float],
    limit: int = 5,
) -> list[dict]:
    """
    Find persons most similar to a query using cosine distance.

    Returns a list of dicts with person_id, text_content, and similarity_score
    (0.0 to 1.0, higher = more similar), sorted by similarity descending.
    """
    try:
        with _pooled_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(f"SET LOCAL hnsw.ef_search = {HNSW_EF_SEARCH}")
                cur.execute(
                    """
                    SELECT
                        person_id,
                        text_content,
                        1 - (text_embedding <=> %s::vector) AS similarity_score
                    FROM person_embeddings
                    WHERE user_id = %s
                      AND text_embedding IS NOT NULL
                    ORDER BY text_embedding <=> %s::vector
                    LIMIT %s
                    """,
                    (str(query_embedding), user_id, str(query_embedding), limit),
                )
                rows = cur.fetchall()
                return [
                    {
                        "person_id": row["person_id"],
                        "text_content": row["text_content"],
                        "similarity_score": round(float(row["similarity_score"]), 4),
                    }
                    for row in rows
                ]
    except Exception as e:
        logger.error("Semantic search failed for user_id=%s: %s", user_id, e)
        raise


# ---------------------
# Pending Embedding Sync Operations
# ---------------------


def insert_pending_sync(person_id: str, user_id: str, operation: str = "upsert"):
    """Queue a failed embedding sync for later retry."""
    with _pooled_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO pending_embedding_syncs
                    (id, person_id, user_id, operation)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT DO NOTHING
                """,
                (str(uuid.uuid4()), person_id, user_id, operation),
            )
        conn.commit()


def get_pending_syncs(limit: int = 20) -> list[dict]:
    """Fetch pending syncs that are due for retry and haven't exceeded max_retries."""
    with _pooled_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, person_id, user_id, operation, retry_count
                FROM pending_embedding_syncs
                WHERE next_retry_at <= NOW()
                  AND retry_count < max_retries
                ORDER BY next_retry_at
                LIMIT %s
                """,
                (limit,),
            )
            return [dict(row) for row in cur.fetchall()]


def delete_pending_sync(sync_id: str):
    """Remove a completed pending sync record."""
    with _pooled_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM pending_embedding_syncs WHERE id = %s",
                (sync_id,),
            )
        conn.commit()


def update_pending_sync_retry(
    sync_id: str, retry_count: int, backoff_seconds: int, error_msg: str
):
    """Update a pending sync after a failed retry attempt."""
    next_retry = datetime.now(timezone.utc) + timedelta(seconds=backoff_seconds)
    with _pooled_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE pending_embedding_syncs
                SET retry_count = %s,
                    next_retry_at = %s,
                    last_error = %s
                WHERE id = %s
                """,
                (retry_count, next_retry, error_msg, sync_id),
            )
        conn.commit()


def get_pending_sync_stats() -> dict:
    """Return counts of pending, failed, and total sync records."""
    with _pooled_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                    COUNT(*) AS total,
                    COUNT(*) FILTER (WHERE retry_count >= max_retries) AS failed,
                    COUNT(*) FILTER (WHERE retry_count < max_retries) AS pending
                FROM pending_embedding_syncs
                """
            )
            return dict(cur.fetchone())
