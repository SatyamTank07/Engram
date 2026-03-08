"""
pgvector operations for person embeddings.

Manages the person_embeddings table in PostgreSQL with the pgvector extension.
Provides upsert, delete, and semantic similarity search.
"""

import os
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

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

# Module-level connection pool (initialized lazily)
_pool: ThreadedConnectionPool | None = None


def _get_pool() -> ThreadedConnectionPool:
    """Return the connection pool, creating it on first use."""
    global _pool
    if _pool is None:
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


def init_vector_db():
    """
    Create the pgvector extension, person_embeddings table, and indexes.
    Called once on application startup.
    Uses register_vec=False since the vector extension may not exist yet.
    """
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

            # HNSW index for fast cosine similarity search on text embeddings
            cur.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_text_embedding
                ON person_embeddings
                USING hnsw (text_embedding vector_cosine_ops);
            """)

            # HNSW index for fast cosine similarity search on face embeddings
            cur.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_face_embedding
                ON person_embeddings
                USING hnsw (face_embedding vector_cosine_ops);
            """)

            # Index for fast user_id filtering
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_emb_user_id
                ON person_embeddings (user_id);
            """)

        conn.commit()


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


def upsert_face_embedding(person_id: str, user_id: str, face_vector: list[float]):
    """
    Store or update the face embedding for a person.
    Only updates the face_embedding column — text_embedding is untouched.
    Creates a row if none exists yet (person may not have a text embedding yet).
    """
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
    with _pooled_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
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

    with _pooled_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
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


def delete_embedding(person_id: str):
    """Delete the embedding record for a person."""
    with _pooled_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM person_embeddings WHERE person_id = %s",
                (person_id,),
            )
        conn.commit()


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
    with _pooled_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
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
