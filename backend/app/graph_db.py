"""
Knowledge Graph operations using Neo4j for PersonIdentity storage.
Replaces PostgreSQL-based PersonIdentity CRUD with graph-native operations.
"""

import asyncio
import json
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

from neo4j import AsyncGraphDatabase


# Neo4j connection settings
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "engram_graph")


class Neo4jConnection:
    """Singleton Neo4j async driver manager."""

    _driver = None

    @classmethod
    def get_driver(cls):
        if cls._driver is None:
            cls._driver = AsyncGraphDatabase.driver(
                NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)
            )
        return cls._driver

    @classmethod
    async def close(cls):
        if cls._driver is not None:
            await cls._driver.close()
            cls._driver = None


def _get_driver():
    return Neo4jConnection.get_driver()


async def init_graph_db():
    """Create indexes and constraints for the Person nodes."""
    driver = _get_driver()
    async with driver.session() as session:
        # Unique constraint on Person.id
        await session.run(
            "CREATE CONSTRAINT person_id_unique IF NOT EXISTS "
            "FOR (p:Person) REQUIRE p.id IS UNIQUE"
        )
        # Index on Person.user_id for fast per-user lookups
        await session.run(
            "CREATE INDEX person_user_id IF NOT EXISTS "
            "FOR (p:Person) ON (p.user_id)"
        )
        # Full-text index on Person.name for case-insensitive search
        await session.run(
            "CREATE FULLTEXT INDEX person_name_fulltext IF NOT EXISTS "
            "FOR (p:Person) ON EACH [p.name]"
        )


# ---------------------
# CRUD Operations
# ---------------------


async def create_person_node(
    user_id: str,
    name: str,
    aliases: list[str] | None = None,
    contacts: dict | None = None,
    short_bio: str | None = None,
    trust_score: float = 0.0,
) -> dict:
    """Create a new Person node in the knowledge graph."""
    driver = _get_driver()
    now = datetime.now(timezone.utc).isoformat()
    person_id = str(uuid.uuid4())

    async with driver.session() as session:
        result = await session.run(
            """
            CREATE (p:Person {
                id: $id,
                user_id: $user_id,
                name: $name,
                aliases: $aliases,
                contacts: $contacts,
                short_bio: $short_bio,
                trust_score: $trust_score,
                first_seen: $now,
                last_seen: $now
            })
            RETURN p
            """,
            id=person_id,
            user_id=str(user_id),
            name=name,
            aliases=aliases or [],
            contacts=_serialize_contacts(contacts or {}),
            short_bio=short_bio or "",
            trust_score=str(trust_score),
            now=now,
        )
        record = await result.single()
        if record:
            person = _node_to_dict(record["p"])
            await asyncio.to_thread(_sync_embedding, person)
            return person
    return {}


async def get_person_node(person_id: str) -> dict | None:
    """Get a Person node by its ID."""
    driver = _get_driver()
    async with driver.session() as session:
        result = await session.run(
            "MATCH (p:Person {id: $id}) RETURN p",
            id=person_id,
        )
        record = await result.single()
        if record:
            return _node_to_dict(record["p"])
    return None


async def list_person_nodes(user_id: str, limit: int = 50) -> list[dict]:
    """List all Person nodes for a given user, ordered by last_seen desc."""
    driver = _get_driver()
    async with driver.session() as session:
        result = await session.run(
            """
            MATCH (p:Person {user_id: $user_id})
            RETURN p
            ORDER BY p.last_seen DESC
            LIMIT $limit
            """,
            user_id=str(user_id),
            limit=limit,
        )
        records = [record async for record in result]
        return [_node_to_dict(record["p"]) for record in records]


async def update_person_node(
    person_id: str,
    name: str | None = None,
    aliases: list[str] | None = None,
    contacts: dict | None = None,
    short_bio: str | None = None,
    trust_score: float | None = None,
    face_image_url: str | None = None,
) -> dict | None:
    """Update fields on an existing Person node."""
    driver = _get_driver()

    # Build SET clauses dynamically for provided fields
    set_parts = ["p.last_seen = $now"]
    params: dict = {
        "id": person_id,
        "now": datetime.now(timezone.utc).isoformat(),
    }

    if name is not None:
        set_parts.append("p.name = $name")
        params["name"] = name
    if aliases is not None:
        set_parts.append("p.aliases = $aliases")
        params["aliases"] = aliases
    if contacts is not None:
        set_parts.append("p.contacts = $contacts")
        params["contacts"] = _serialize_contacts(contacts)
    if short_bio is not None:
        set_parts.append("p.short_bio = $short_bio")
        params["short_bio"] = short_bio
    if trust_score is not None:
        set_parts.append("p.trust_score = $trust_score")
        params["trust_score"] = str(trust_score)
    if face_image_url is not None:
        set_parts.append("p.face_image_url = $face_image_url")
        params["face_image_url"] = face_image_url

    set_clause = ", ".join(set_parts)

    async with driver.session() as session:
        result = await session.run(
            f"MATCH (p:Person {{id: $id}}) SET {set_clause} RETURN p",
            **params,
        )
        record = await result.single()
        if record:
            person = _node_to_dict(record["p"])
            await asyncio.to_thread(_sync_embedding, person)
            return person
    return None


async def delete_person_node(person_id: str) -> bool:
    """Delete a Person node and all its relationships.

    Deletes the Neo4j node first (authoritative), then cleans up
    the pgvector embedding. If embedding cleanup fails, it is queued
    for background retry.
    """
    # Get user_id before deleting (needed for pending sync queue)
    person = await get_person_node(person_id)
    user_id = person.get("user_id", "") if person else ""

    driver = _get_driver()
    async with driver.session() as session:
        result = await session.run(
            "MATCH (p:Person {id: $id}) DETACH DELETE p RETURN count(p) AS deleted",
            id=person_id,
        )
        record = await result.single()
        deleted = record and record["deleted"] > 0

    if deleted:
        try:
            from . import vector_db
            vector_db.delete_embedding(person_id)
        except Exception as e:
            print(f"Warning: Failed to delete embedding for {person_id}: {e}. Queued for retry.")
            try:
                from . import vector_db
                vector_db.insert_pending_sync(person_id, user_id, operation="delete")
            except Exception as queue_err:
                print(f"Error: Could not queue pending delete for {person_id}: {queue_err}")

    return deleted


async def get_person_nodes_batch(person_ids: list[str]) -> dict[str, dict]:
    """Fetch multiple Person nodes in a single Neo4j query.

    Returns a dict mapping person_id -> person dict for all found nodes.
    """
    if not person_ids:
        return {}

    driver = _get_driver()
    async with driver.session() as session:
        result = await session.run(
            "MATCH (p:Person) WHERE p.id IN $ids RETURN p",
            ids=person_ids,
        )
        records = [record async for record in result]
        return {record["p"]["id"]: _node_to_dict(record["p"]) for record in records}


async def search_persons(user_id: str, search_term: str) -> list[dict]:
    """Search Person nodes by name using full-text index (case-insensitive)."""
    if not search_term or not search_term.strip():
        return []

    driver = _get_driver()
    escaped = _escape_lucene_query(search_term.strip())
    # Wildcard prefix/suffix for substring-like matching
    lucene_query = f"*{escaped}*"

    async with driver.session() as session:
        result = await session.run(
            """
            CALL db.index.fulltext.queryNodes('person_name_fulltext', $query)
            YIELD node AS p, score
            WHERE p.user_id = $user_id
            RETURN p
            ORDER BY score DESC
            """,
            query=lucene_query,
            user_id=str(user_id),
        )
        records = [record async for record in result]
        return [_node_to_dict(record["p"]) for record in records]


# ---------------------
# Relationship Operations (Future-ready)
# ---------------------


async def add_relationship(
    from_person_id: str,
    to_person_id: str,
    rel_type: str,
    properties: dict | None = None,
) -> dict | None:
    """
    Create a relationship between two Person nodes.

    Example rel_types: KNOWS, WORKS_WITH, FAMILY, FRIEND, COLLEAGUE, MANAGES
    """
    driver = _get_driver()
    props = properties or {}
    props["created_at"] = datetime.now(timezone.utc).isoformat()

    async with driver.session() as session:
        # Use APOC or dynamic relationship type
        result = await session.run(
            f"""
            MATCH (a:Person {{id: $from_id}})
            MATCH (b:Person {{id: $to_id}})
            CREATE (a)-[r:{_sanitize_rel_type(rel_type)} $props]->(b)
            RETURN a.name AS from_name, b.name AS to_name, type(r) AS rel_type
            """,
            from_id=from_person_id,
            to_id=to_person_id,
            props=props,
        )
        record = await result.single()
        if record:
            return {
                "from": record["from_name"],
                "to": record["to_name"],
                "relationship": record["rel_type"],
            }
    return None


async def get_relationships(person_id: str) -> list[dict]:
    """Get all relationships for a Person node."""
    driver = _get_driver()
    async with driver.session() as session:
        result = await session.run(
            """
            MATCH (p:Person {id: $id})-[r]-(other:Person)
            RETURN type(r) AS rel_type,
                   properties(r) AS rel_props,
                   other.id AS other_id,
                   other.name AS other_name,
                   startNode(r) = p AS is_outgoing
            """,
            id=person_id,
        )
        records = [record async for record in result]
        return [
            {
                "relationship": record["rel_type"],
                "properties": dict(record["rel_props"]) if record["rel_props"] else {},
                "person_id": record["other_id"],
                "person_name": record["other_name"],
                "direction": "outgoing" if record["is_outgoing"] else "incoming",
            }
            for record in records
        ]


# ---------------------
# Helpers
# ---------------------


_LUCENE_SPECIAL_CHARS = re.compile(r'([+\-&|!(){}[\]^"~*?:\\])')


def _escape_lucene_query(query: str) -> str:
    """Escape Lucene special characters in a search term."""
    return _LUCENE_SPECIAL_CHARS.sub(r"\\\1", query)


def _node_to_dict(node) -> dict:
    """Convert a Neo4j node to a plain dictionary."""
    data = dict(node)
    # Deserialize contacts back from JSON string
    if "contacts" in data and isinstance(data["contacts"], str):
        try:
            data["contacts"] = json.loads(data["contacts"])
        except (json.JSONDecodeError, TypeError):
            data["contacts"] = {}
    return data


def _serialize_contacts(contacts: dict) -> str:
    """Serialize contacts dict to JSON string for Neo4j storage.

    Neo4j doesn't natively support nested maps, so we store contacts as a JSON string.
    """
    return json.dumps(contacts)


def _sanitize_rel_type(rel_type: str) -> str:
    """Sanitize relationship type to be a valid Neo4j relationship type."""
    # Only allow alphanumeric and underscores
    sanitized = "".join(c if c.isalnum() or c == "_" else "_" for c in rel_type.upper())
    return sanitized or "RELATED_TO"


def _sync_embedding(person: dict):
    """Sync person data to pgvector as a text embedding.

    On failure, queues the sync for background retry so that Neo4j
    and pgvector stay eventually consistent.
    """
    try:
        from . import embedding_service, vector_db

        text_content, embedding = embedding_service.generate_person_embedding(
            name=person.get("name", ""),
            aliases=person.get("aliases", []),
            short_bio=person.get("short_bio", ""),
            contacts=person.get("contacts", {}),
        )
        vector_db.upsert_text_embedding(
            person_id=person["id"],
            user_id=person["user_id"],
            text_content=text_content,
            embedding=embedding,
        )
        print(f"[EMBEDDING] Synced embedding for '{person.get('name')}': \"{text_content[:80]}...\"")
    except Exception as e:
        print(f"Warning: Failed to sync embedding for person {person.get('id')}: {e}. Queued for retry.")
        try:
            from . import vector_db
            vector_db.insert_pending_sync(
                person_id=person["id"],
                user_id=person["user_id"],
                operation="upsert",
            )
        except Exception as queue_err:
            print(f"Error: Could not queue pending sync for {person.get('id')}: {queue_err}")
