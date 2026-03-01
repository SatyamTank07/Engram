"""
Text embedding service using OpenAI text-embedding-3-small.

Provides functions to generate text embeddings for person data,
enabling semantic search via pgvector.
"""

import os
from typing import Optional

from openai import OpenAI

# Embedding model configuration
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536

# Singleton client
_client: Optional[OpenAI] = None


def get_openai_client() -> OpenAI:
    """Get or create OpenAI client using OPENAI_API_KEY from env."""
    global _client
    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set")
        _client = OpenAI(api_key=api_key)
    return _client


def build_person_text(
    name: str,
    aliases: list[str] | None = None,
    short_bio: str | None = None,
    contacts: dict | None = None,
) -> str:
    """
    Combine person fields into a single searchable string for embedding.

    Example output:
        "Rahul Sharma | Aliases: Rahul, RS | Bio: Software developer based
         in Pune, works at TechCorp | Contacts: email: rahul@techcorp.com"
    """
    parts = [name]

    if aliases:
        parts.append(f"Aliases: {', '.join(aliases)}")

    if short_bio:
        parts.append(f"Bio: {short_bio}")

    if contacts:
        contact_parts = []
        for key, value in contacts.items():
            if isinstance(value, dict):
                for sub_key, sub_value in value.items():
                    contact_parts.append(f"{sub_key}: {sub_value}")
            else:
                contact_parts.append(f"{key}: {value}")
        if contact_parts:
            parts.append(f"Contacts: {', '.join(contact_parts)}")

    return " | ".join(parts)


def generate_text_embedding(text: str) -> list[float]:
    """
    Generate a 1536-dimension embedding vector for the given text.

    Calls the OpenAI text-embedding-3-small API.
    """
    client = get_openai_client()
    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=text,
    )
    return response.data[0].embedding


def generate_person_embedding(
    name: str,
    aliases: list[str] | None = None,
    short_bio: str | None = None,
    contacts: dict | None = None,
) -> tuple[str, list[float]]:
    """
    Build a combined text from person fields and generate its embedding.

    Returns:
        (text_content, embedding_vector) — the raw text and its 1536-dim vector.
    """
    text_content = build_person_text(name, aliases, short_bio, contacts)
    embedding = generate_text_embedding(text_content)
    return text_content, embedding
