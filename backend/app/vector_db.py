"""
pgvector operations for person embeddings.

Manages the person_embeddings table in PostgreSQL with the pgvector extension.
Provides upsert, delete, and semantic similarity search.
"""

import os
import uuid
from datetime import datetime, timezone

import psycopg2
from psycopg2.extras import RealDictCursor
from pgvector.psycopg2 import register_vector

# Use the same DATABASE_URL as SQLAlchemy
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/engram"
)

# Embedding dimensions
TEXT_EMBEDDING_DIM = 1536  # OpenAI text-embedding-3-small
FACE_EMBEDDING_DIM = 512   # Phase 2: CLIP


def _get_raw_connection():
    """Get a raw psycopg2 connection (without vector type registration)."""
    return psycopg2.connect(DATABASE_URL)


def _get_connection():
    """Get a psycopg2 connection with pgvector type registered.
    Only use this AFTER init_vector_db() has been called."""
    conn = psycopg2.connect(DATABASE_URL)
    register_vector(conn)
    return conn


def init_vector_db():
    """
    Create the pgvector extension, person_embeddings table, and indexes.
    Called once on application startup.
    Uses a raw connection since the vector extension may not exist yet.
    """
    conn = _get_raw_connection()
    try:
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
    finally:
        conn.close()


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
    conn = _get_connection()
    try:
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
    finally:
        conn.close()


def upsert_face_embedding(person_id: str, user_id: str, face_vector: list[float]):
    """
    Store or update the face embedding for a person.
    Only updates the face_embedding column — text_embedding is untouched.
    Creates a row if none exists yet (person may not have a text embedding yet).
    """
    conn = _get_connection()
    try:
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
    finally:
        conn.close()


def face_search(
    user_id: str,
    query_face_vector: list[float],
    limit: int = 3,
) -> list[dict]:
    """
    Find persons whose face_embedding is closest to a query image.
    Only searches persons that have a face embedding stored (not NULL).

    Returns a list of dicts with person_id and similarity_score
    (0.0 to 1.0, higher = better match), sorted by similarity descending.
    """
    conn = _get_connection()
    try:
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
            ]
    finally:
        conn.close()


def delete_embedding(person_id: str):
    """Delete the embedding record for a person."""
    conn = _get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM person_embeddings WHERE person_id = %s",
                (person_id,),
            )
        conn.commit()
    finally:
        conn.close()


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
    conn = _get_connection()
    try:
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
    finally:
        conn.close()
