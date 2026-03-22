"""
Text embedding service using OpenAI text-embedding-3-small.

Provides functions to generate text embeddings for person data,
enabling semantic search via pgvector.
"""

import logging
import os
from typing import Optional

from openai import OpenAI

logger = logging.getLogger(__name__)

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
        logger.info("Initializing OpenAI client for embeddings")
        _client = OpenAI(api_key=api_key)
    return _client


def build_person_text(
    name: str,
    aliases: list[str] | None = None,
    short_bio: str | None = None,
    contacts: dict | None = None,
    occupation: str | None = None,
    company: str | None = None,
    location: str | None = None,
    tags: list[str] | None = None,
    interests: list[str] | None = None,
    notes: str | None = None,
) -> str:
    """
    Combine person fields into a single searchable string for embedding.

    Example output:
        "Rahul Sharma | Aliases: Rahul, RS | Software Developer at TechCorp
         | Location: Pune | Bio: ... | Tags: dev, friend | Interests: coding"
    """
    parts = [name]

    if aliases:
        parts.append(f"Aliases: {', '.join(aliases)}")

    if occupation and company:
        parts.append(f"{occupation} at {company}")
    elif occupation:
        parts.append(f"Occupation: {occupation}")
    elif company:
        parts.append(f"Company: {company}")

    if location:
        parts.append(f"Location: {location}")

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

    if tags:
        parts.append(f"Tags: {', '.join(tags)}")

    if interests:
        parts.append(f"Interests: {', '.join(interests)}")

    if notes:
        # Truncate notes to avoid overly long embeddings
        truncated = notes[:500]
        parts.append(f"Notes: {truncated}")

    return " | ".join(parts)


def generate_text_embedding(text: str) -> list[float]:
    """
    Generate a 1536-dimension embedding vector for the given text.

    Calls the OpenAI text-embedding-3-small API.
    """
    try:
        client = get_openai_client()
        response = client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=text,
        )
        logger.debug("Generated embedding for text of length %d", len(text))
        return response.data[0].embedding
    except Exception as e:
        logger.error("OpenAI embedding API call failed: %s", e)
        raise


def generate_person_embedding(
    name: str,
    aliases: list[str] | None = None,
    short_bio: str | None = None,
    contacts: dict | None = None,
    occupation: str | None = None,
    company: str | None = None,
    location: str | None = None,
    tags: list[str] | None = None,
    interests: list[str] | None = None,
    notes: str | None = None,
) -> tuple[str, list[float]]:
    """
    Build a combined text from person fields and generate its embedding.

    Returns:
        (text_content, embedding_vector) — the raw text and its 1536-dim vector.
    """
    logger.debug("Generating embedding for person: %s", name)
    text_content = build_person_text(
        name, aliases, short_bio, contacts,
        occupation, company, location, tags, interests, notes,
    )
    embedding = generate_text_embedding(text_content)
    return text_content, embedding


# ---------------------------------------------------------------------------
# Idea embedding
# ---------------------------------------------------------------------------

def build_idea_text(
    name: str,
    idea_type: str | None = None,
    description: str | None = None,
    tags: list[str] | None = None,
    notes: str | None = None,
) -> str:
    """Combine idea fields into a single searchable string for embedding."""
    parts = [name]
    if idea_type:
        parts.append(f"Type: {idea_type}")
    if description:
        parts.append(f"Description: {description[:500]}")
    if tags:
        parts.append(f"Tags: {', '.join(tags)}")
    if notes:
        parts.append(f"Notes: {notes[:500]}")
    return " | ".join(parts)


def generate_idea_embedding(
    name: str,
    idea_type: str | None = None,
    description: str | None = None,
    tags: list[str] | None = None,
    notes: str | None = None,
) -> tuple[str, list[float]]:
    """Build combined text from idea fields and generate its embedding."""
    text_content = build_idea_text(name, idea_type, description, tags, notes)
    embedding = generate_text_embedding(text_content)
    return text_content, embedding


# ---------------------------------------------------------------------------
# Content embedding
# ---------------------------------------------------------------------------

def build_content_text(
    title: str,
    content_type: str | None = None,
    author: str | None = None,
    personal_notes: str | None = None,
    tags: list[str] | None = None,
) -> str:
    """Combine content fields into a single searchable string for embedding."""
    parts = [title]
    if content_type:
        parts.append(f"Type: {content_type}")
    if author:
        parts.append(f"Author: {author}")
    if personal_notes:
        parts.append(f"Notes: {personal_notes[:500]}")
    if tags:
        parts.append(f"Tags: {', '.join(tags)}")
    return " | ".join(parts)


def generate_content_embedding(
    title: str,
    content_type: str | None = None,
    author: str | None = None,
    personal_notes: str | None = None,
    tags: list[str] | None = None,
) -> tuple[str, list[float]]:
    """Build combined text from content fields and generate its embedding."""
    text_content = build_content_text(title, content_type, author, personal_notes, tags)
    embedding = generate_text_embedding(text_content)
    return text_content, embedding


# ---------------------------------------------------------------------------
# Project embedding
# ---------------------------------------------------------------------------

def build_project_text(
    name: str,
    project_type: str | None = None,
    description: str | None = None,
    goal: str | None = None,
    tags: list[str] | None = None,
    notes: str | None = None,
) -> str:
    """Combine project fields into a single searchable string for embedding."""
    parts = [name]
    if project_type:
        parts.append(f"Type: {project_type}")
    if description:
        parts.append(f"Description: {description[:500]}")
    if goal:
        parts.append(f"Goal: {goal[:300]}")
    if tags:
        parts.append(f"Tags: {', '.join(tags)}")
    if notes:
        parts.append(f"Notes: {notes[:500]}")
    return " | ".join(parts)


def generate_project_embedding(
    name: str,
    project_type: str | None = None,
    description: str | None = None,
    goal: str | None = None,
    tags: list[str] | None = None,
    notes: str | None = None,
) -> tuple[str, list[float]]:
    """Build combined text from project fields and generate its embedding."""
    text_content = build_project_text(name, project_type, description, goal, tags, notes)
    embedding = generate_text_embedding(text_content)
    return text_content, embedding
