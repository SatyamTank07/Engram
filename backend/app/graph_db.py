"""
Knowledge Graph operations using Neo4j for PersonIdentity storage.
Replaces PostgreSQL-based PersonIdentity CRUD with graph-native operations.
"""

import asyncio
import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

from neo4j import AsyncGraphDatabase

logger = logging.getLogger(__name__)


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
            logger.info("Connecting to Neo4j at %s", NEO4J_URI)
            cls._driver = AsyncGraphDatabase.driver(
                NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)
            )
        return cls._driver

    @classmethod
    async def close(cls):
        if cls._driver is not None:
            await cls._driver.close()
            cls._driver = None
            logger.info("Neo4j connection closed")


def _get_driver():
    return Neo4jConnection.get_driver()


async def init_graph_db():
    """Create indexes and constraints for the Person nodes."""
    logger.info("Initializing Neo4j schema (constraints + indexes)...")
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
        # Drop old narrow fulltext index if it exists
        try:
            await session.run("DROP INDEX person_name_fulltext IF EXISTS")
        except Exception:
            pass
        # Broader full-text index on multiple fields
        await session.run(
            "CREATE FULLTEXT INDEX person_search_fulltext IF NOT EXISTS "
            "FOR (p:Person) ON EACH [p.name, p.occupation, p.company, p.location, p.notes]"
        )
        # Index on tags for filtering
        await session.run(
            "CREATE INDEX person_tags IF NOT EXISTS "
            "FOR (p:Person) ON (p.tags)"
        )
        # --- Idea constraints and indexes ---
        await session.run(
            "CREATE CONSTRAINT idea_id_unique IF NOT EXISTS "
            "FOR (i:Idea) REQUIRE i.id IS UNIQUE"
        )
        await session.run(
            "CREATE INDEX idea_user_id IF NOT EXISTS "
            "FOR (i:Idea) ON (i.user_id)"
        )
        await session.run(
            "CREATE FULLTEXT INDEX idea_search_fulltext IF NOT EXISTS "
            "FOR (i:Idea) ON EACH [i.name, i.description, i.notes]"
        )

        # --- Content constraints and indexes ---
        await session.run(
            "CREATE CONSTRAINT content_id_unique IF NOT EXISTS "
            "FOR (c:Content) REQUIRE c.id IS UNIQUE"
        )
        await session.run(
            "CREATE INDEX content_user_id IF NOT EXISTS "
            "FOR (c:Content) ON (c.user_id)"
        )
        await session.run(
            "CREATE FULLTEXT INDEX content_search_fulltext IF NOT EXISTS "
            "FOR (c:Content) ON EACH [c.title, c.author, c.personal_notes]"
        )

        # --- Project constraints and indexes ---
        await session.run(
            "CREATE CONSTRAINT project_id_unique IF NOT EXISTS "
            "FOR (p:Project) REQUIRE p.id IS UNIQUE"
        )
        await session.run(
            "CREATE INDEX project_user_id IF NOT EXISTS "
            "FOR (p:Project) ON (p.user_id)"
        )
        await session.run(
            "CREATE FULLTEXT INDEX project_search_fulltext IF NOT EXISTS "
            "FOR (p:Project) ON EACH [p.name, p.description, p.goal, p.notes]"
        )

    logger.info("Neo4j schema ready")


# ---------------------
# Serialization Helpers
# ---------------------

# Fields that are stored as JSON strings in Neo4j (nested dicts/objects)
_DICT_FIELDS = ("contacts", "social_media", "important_dates")

# All person fields (besides id, user_id, first_seen, last_seen, face_image_url)
_PERSON_FIELDS = (
    "name", "aliases", "contacts", "short_bio", "trust_score",
    "date_of_birth", "gender", "nationality", "languages",
    "occupation", "company", "location",
    "met_through", "met_date", "interaction_frequency",
    "emotional_closeness", "reliability_score", "last_interaction_summary",
    "pending_actions", "interests", "personality_traits", "communication_style",
    "social_media", "important_dates", "notes", "tags",
    "person_scope", "public_role", "known_for", "public_bio",
)

# Idea fields (besides id, user_id, first_seen, last_seen)
_IDEA_FIELDS = (
    "name", "idea_type", "description", "confidence", "status",
    "evidence_for", "evidence_against", "date_formed", "revisit_date",
    "tags", "notes",
)

# Content fields (besides id, user_id, first_seen, last_seen)
_CONTENT_FIELDS = (
    "title", "content_type", "author", "source_url", "status",
    "your_rating", "personal_notes", "recommended_by", "tags",
)

# Project fields (besides id, user_id, first_seen, last_seen)
_PROJECT_FIELDS = (
    "name", "project_type", "status", "description", "goal",
    "target_date", "priority", "tags", "notes",
)


def _serialize_dict(value: dict) -> str:
    """Serialize a dict to JSON string for Neo4j storage."""
    return json.dumps(value)


def _node_to_dict(node) -> dict:
    """Convert a Neo4j node to a plain dictionary with proper deserialization."""
    data = dict(node)

    # Deserialize dict fields from JSON strings
    for field in _DICT_FIELDS:
        if field in data and isinstance(data[field], str):
            try:
                data[field] = json.loads(data[field])
            except (json.JSONDecodeError, TypeError):
                data[field] = {}

    # Fix trust_score: parse string → float (backward compat for old data)
    if "trust_score" in data:
        try:
            data["trust_score"] = float(data["trust_score"])
        except (ValueError, TypeError):
            data["trust_score"] = 0.0

    # Fix emotional_closeness and reliability_score similarly
    for score_field in ("emotional_closeness", "reliability_score"):
        if score_field in data and data[score_field] is not None:
            try:
                data[score_field] = float(data[score_field])
            except (ValueError, TypeError):
                data[score_field] = None

    # Ensure list fields default to empty lists
    for list_field in ("aliases", "languages", "pending_actions", "interests",
                       "personality_traits", "tags", "known_for"):
        if list_field not in data or data[list_field] is None:
            data[list_field] = []

    # Ensure dict fields default to empty dicts
    for dict_field in _DICT_FIELDS:
        if dict_field not in data or data[dict_field] is None:
            data[dict_field] = {}

    return data


def _build_props(data: dict) -> dict:
    """Prepare a properties dict for Neo4j, serializing dict fields to JSON."""
    props = {}
    for key, value in data.items():
        if value is None:
            continue
        if key in _DICT_FIELDS and isinstance(value, dict):
            props[key] = _serialize_dict(value)
        else:
            props[key] = value
    return props


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
    **kwargs,
) -> dict:
    """Create a new Person node in the knowledge graph."""
    driver = _get_driver()
    now = datetime.now(timezone.utc).isoformat()
    person_id = str(uuid.uuid4())

    # Build properties dict
    raw_props = {
        "id": person_id,
        "user_id": str(user_id),
        "name": name,
        "aliases": aliases or [],
        "contacts": contacts or {},
        "short_bio": short_bio or "",
        "trust_score": float(trust_score),
        "first_seen": now,
        "last_seen": now,
    }

    # Add any new fields from kwargs
    for field in _PERSON_FIELDS:
        if field in kwargs and kwargs[field] is not None and field not in raw_props:
            raw_props[field] = kwargs[field]

    props = _build_props(raw_props)

    try:
        async with driver.session() as session:
            result = await session.run(
                "CREATE (p:Person $props) RETURN p",
                props=props,
            )
            record = await result.single()
            if record:
                person = _node_to_dict(record["p"])
                await asyncio.to_thread(_sync_embedding, person)
                return person
        return {}
    except Exception as e:
        logger.error("Failed to create person node '%s': %s", name, e)
        raise


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


async def list_person_nodes(
    user_id: str,
    limit: int = 50,
    offset: int = 0,
    tags: list[str] | None = None,
    location: str | None = None,
    occupation: str | None = None,
    company: str | None = None,
    interaction_frequency: str | None = None,
) -> tuple[list[dict], int]:
    """List Person nodes for a user with optional filtering and pagination.

    Returns (results, total_count).
    """
    driver = _get_driver()

    # Build WHERE clauses
    where_parts = ["p.user_id = $user_id"]
    params: dict = {"user_id": str(user_id), "limit": limit, "offset": offset}

    if tags:
        # Match persons that have ANY of the specified tags
        where_parts.append("ANY(t IN $filter_tags WHERE t IN p.tags)")
        params["filter_tags"] = tags
    if location:
        where_parts.append("toLower(p.location) CONTAINS toLower($filter_location)")
        params["filter_location"] = location
    if occupation:
        where_parts.append("toLower(p.occupation) CONTAINS toLower($filter_occupation)")
        params["filter_occupation"] = occupation
    if company:
        where_parts.append("toLower(p.company) CONTAINS toLower($filter_company)")
        params["filter_company"] = company
    if interaction_frequency:
        where_parts.append("p.interaction_frequency = $filter_freq")
        params["filter_freq"] = interaction_frequency

    where_clause = " AND ".join(where_parts)

    async with driver.session() as session:
        # Get total count
        count_result = await session.run(
            f"MATCH (p:Person) WHERE {where_clause} RETURN count(p) AS total",
            **params,
        )
        count_record = await count_result.single()
        total = count_record["total"] if count_record else 0

        # Get paginated results
        result = await session.run(
            f"""
            MATCH (p:Person)
            WHERE {where_clause}
            RETURN p
            ORDER BY p.last_seen DESC
            SKIP $offset
            LIMIT $limit
            """,
            **params,
        )
        records = [record async for record in result]
        items = [_node_to_dict(record["p"]) for record in records]

    return items, total


async def update_person_node(person_id: str, **updates) -> dict | None:
    """Update fields on an existing Person node.

    Accepts arbitrary keyword arguments for any person field.
    """
    driver = _get_driver()

    # Build SET clauses dynamically for provided fields
    set_parts = ["p.last_seen = $now"]
    params: dict = {
        "id": person_id,
        "now": datetime.now(timezone.utc).isoformat(),
    }

    for key, value in updates.items():
        if value is None:
            continue
        param_name = f"upd_{key}"
        if key in _DICT_FIELDS and isinstance(value, dict):
            set_parts.append(f"p.{key} = ${param_name}")
            params[param_name] = _serialize_dict(value)
        elif key == "trust_score":
            set_parts.append(f"p.trust_score = ${param_name}")
            params[param_name] = float(value)
        else:
            set_parts.append(f"p.{key} = ${param_name}")
            params[param_name] = value

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
    """Delete a Person node and all its relationships."""
    person = await get_person_node(person_id)
    user_id = person.get("user_id", "") if person else ""

    try:
        driver = _get_driver()
        async with driver.session() as session:
            result = await session.run(
                "MATCH (p:Person {id: $id}) DETACH DELETE p RETURN count(p) AS deleted",
                id=person_id,
            )
            record = await result.single()
            deleted = record and record["deleted"] > 0
    except Exception as e:
        logger.error("Failed to delete person node %s: %s", person_id, e)
        raise

    if deleted:
        try:
            from . import vector_db
            vector_db.delete_embedding(person_id)
        except Exception as e:
            logger.warning("Failed to delete embedding for person_id=%s: %s. Queued for retry.", person_id, e)
            try:
                from . import vector_db
                vector_db.insert_pending_sync(person_id, user_id, operation="delete")
            except Exception as queue_err:
                logger.error("Could not queue pending delete for person_id=%s: %s", person_id, queue_err)

    return deleted


async def get_person_nodes_batch(person_ids: list[str]) -> dict[str, dict]:
    """Fetch multiple Person nodes in a single Neo4j query."""
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
    """Search Person nodes using full-text index (case-insensitive)."""
    if not search_term or not search_term.strip():
        return []

    driver = _get_driver()
    escaped = _escape_lucene_query(search_term.strip())
    lucene_query = f"*{escaped}*"

    try:
        async with driver.session() as session:
            result = await session.run(
                """
                CALL db.index.fulltext.queryNodes('person_search_fulltext', $search_query)
                YIELD node AS p, score
                WHERE p.user_id = $user_id
                RETURN p
                ORDER BY score DESC
                """,
                search_query=lucene_query,
                user_id=str(user_id),
            )
            records = [record async for record in result]
            return [_node_to_dict(record["p"]) for record in records]
    except Exception as e:
        logger.error("Person search failed for term '%s': %s", search_term, e)
        raise


# ---------------------
# Relationship Operations
# ---------------------


async def add_relationship(
    from_person_id: str,
    to_person_id: str,
    rel_type: str,
    properties: dict | None = None,
) -> dict | None:
    """Create a relationship between two Person nodes."""
    driver = _get_driver()
    props = properties or {}
    props["created_at"] = datetime.now(timezone.utc).isoformat()

    try:
        async with driver.session() as session:
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
    except Exception as e:
        logger.error("Failed to add relationship %s->%s (%s): %s", from_person_id, to_person_id, rel_type, e)
        raise


async def update_relationship(
    from_person_id: str,
    to_person_id: str,
    rel_type: str,
    properties: dict,
) -> dict | None:
    """Update properties on an existing relationship."""
    driver = _get_driver()
    sanitized = _sanitize_rel_type(rel_type)

    # Build SET clauses for relationship properties
    set_parts = []
    params = {"from_id": from_person_id, "to_id": to_person_id}
    for key, value in properties.items():
        if value is not None:
            param_name = f"rel_{key}"
            set_parts.append(f"r.{key} = ${param_name}")
            params[param_name] = value

    if not set_parts:
        return None

    set_clause = ", ".join(set_parts)

    try:
        async with driver.session() as session:
            result = await session.run(
                f"""
                MATCH (a:Person {{id: $from_id}})-[r:{sanitized}]->(b:Person {{id: $to_id}})
                SET {set_clause}
                RETURN a.name AS from_name, b.name AS to_name, type(r) AS rel_type, properties(r) AS props
                """,
                **params,
            )
            record = await result.single()
            if record:
                return {
                    "from": record["from_name"],
                    "to": record["to_name"],
                    "relationship": record["rel_type"],
                    "properties": dict(record["props"]) if record["props"] else {},
                }
        return None
    except Exception as e:
        logger.error("Failed to update relationship %s->%s (%s): %s", from_person_id, to_person_id, rel_type, e)
        raise


async def delete_relationship(
    from_person_id: str,
    to_person_id: str,
    rel_type: str,
) -> bool:
    """Delete a relationship between two Person nodes."""
    driver = _get_driver()
    sanitized = _sanitize_rel_type(rel_type)

    try:
        async with driver.session() as session:
            result = await session.run(
                f"""
                MATCH (a:Person {{id: $from_id}})-[r:{sanitized}]->(b:Person {{id: $to_id}})
                DELETE r
                RETURN count(r) AS deleted
                """,
                from_id=from_person_id,
                to_id=to_person_id,
            )
            record = await result.single()
            return record and record["deleted"] > 0
    except Exception as e:
        logger.error("Failed to delete relationship %s->%s (%s): %s", from_person_id, to_person_id, rel_type, e)
        raise


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


async def get_person_connections(person_id: str) -> dict:
    """Get a person's full connection graph."""
    driver = _get_driver()
    async with driver.session() as session:
        result = await session.run(
            """
            MATCH (p:Person {id: $id})
            OPTIONAL MATCH (p)-[r]-(other:Person)
            RETURN p,
                   type(r) AS rel_type,
                   properties(r) AS rel_props,
                   other,
                   startNode(r) = p AS is_outgoing
            """,
            id=person_id,
        )
        records = [record async for record in result]

    if not records:
        return {"person": None, "connections": []}

    center_person = _node_to_dict(records[0]["p"])

    connections = []
    seen_edges = set()
    for record in records:
        if record["other"] is None:
            continue
        other = _node_to_dict(record["other"])
        edge_key = (other["id"], record["rel_type"], record["is_outgoing"])
        if edge_key in seen_edges:
            continue
        seen_edges.add(edge_key)

        connections.append({
            "person": {
                "id": other.get("id"),
                "name": other.get("name"),
                "short_bio": other.get("short_bio"),
                "face_image_url": other.get("face_image_url"),
                "trust_score": other.get("trust_score"),
                "aliases": other.get("aliases", []),
                "occupation": other.get("occupation"),
                "company": other.get("company"),
                "tags": other.get("tags", []),
            },
            "relationship": record["rel_type"],
            "direction": "outgoing" if record["is_outgoing"] else "incoming",
            "properties": dict(record["rel_props"]) if record["rel_props"] else {},
        })

    return {"person": center_person, "connections": connections}


# ---------------------
# Helpers
# ---------------------


_LUCENE_SPECIAL_CHARS = re.compile(r'([+\-&|!(){}[\]^"~*?:\\])')


def _escape_lucene_query(query: str) -> str:
    """Escape Lucene special characters in a search term."""
    return _LUCENE_SPECIAL_CHARS.sub(r"\\\1", query)


def _sanitize_rel_type(rel_type: str) -> str:
    """Sanitize relationship type to be a valid Neo4j relationship type."""
    sanitized = "".join(c if c.isalnum() or c == "_" else "_" for c in rel_type.upper())
    return sanitized or "RELATED_TO"


def _sync_embedding(person: dict):
    """Sync person data to pgvector as a text embedding."""
    try:
        from . import embedding_service, vector_db

        text_content, embedding = embedding_service.generate_person_embedding(
            name=person.get("name", ""),
            aliases=person.get("aliases", []),
            short_bio=person.get("short_bio", ""),
            contacts=person.get("contacts", {}),
            occupation=person.get("occupation"),
            company=person.get("company"),
            location=person.get("location"),
            tags=person.get("tags", []),
            interests=person.get("interests", []),
            notes=person.get("notes"),
        )
        vector_db.upsert_text_embedding(
            person_id=person["id"],
            user_id=person["user_id"],
            text_content=text_content,
            embedding=embedding,
        )
        logger.info("Synced embedding for '%s': \"%s...\"", person.get('name'), text_content[:80])
    except Exception as e:
        logger.warning("Failed to sync embedding for person_id=%s: %s. Queued for retry.", person.get('id'), e)
        try:
            from . import vector_db
            vector_db.insert_pending_sync(
                person_id=person["id"],
                user_id=person["user_id"],
                operation="upsert",
            )
        except Exception as queue_err:
            logger.error("Could not queue pending sync for person_id=%s: %s", person.get('id'), queue_err)


# =====================================================================
# Idea Entity CRUD
# =====================================================================

def _idea_node_to_dict(node) -> dict:
    """Convert a Neo4j Idea node to a plain dictionary."""
    data = dict(node)
    # Float fields
    for f in ("confidence",):
        if f in data and data[f] is not None:
            try:
                data[f] = float(data[f])
            except (ValueError, TypeError):
                data[f] = 0.5
    # List fields default to []
    for f in ("evidence_for", "evidence_against", "tags"):
        if f not in data or data[f] is None:
            data[f] = []
    return data


def _sync_idea_embedding(idea: dict):
    """Sync idea data to pgvector as a text embedding."""
    try:
        from . import embedding_service, vector_db
        text_content, embedding = embedding_service.generate_idea_embedding(
            name=idea.get("name", ""),
            idea_type=idea.get("idea_type"),
            description=idea.get("description"),
            tags=idea.get("tags", []),
            notes=idea.get("notes"),
        )
        vector_db.upsert_idea_text_embedding(
            idea_id=idea["id"], user_id=idea["user_id"],
            text_content=text_content, embedding=embedding,
        )
    except Exception as e:
        logger.warning("Failed to sync idea embedding for id=%s: %s", idea.get("id"), e)
        try:
            from . import vector_db
            vector_db.insert_pending_sync(idea["id"], idea["user_id"], "upsert", "idea")
        except Exception:
            pass


async def create_idea_node(user_id: str, name: str, **kwargs) -> dict:
    """Create a new Idea node in the knowledge graph."""
    driver = _get_driver()
    now = datetime.now(timezone.utc).isoformat()
    idea_id = str(uuid.uuid4())
    raw_props = {
        "id": idea_id, "user_id": str(user_id), "name": name,
        "first_seen": now, "last_seen": now,
    }
    for field in _IDEA_FIELDS:
        if field in kwargs and kwargs[field] is not None and field not in raw_props:
            raw_props[field] = kwargs[field]
    # defaults
    raw_props.setdefault("confidence", 0.5)
    raw_props.setdefault("status", "active")
    raw_props.setdefault("evidence_for", [])
    raw_props.setdefault("evidence_against", [])
    raw_props.setdefault("tags", [])

    props = _build_props(raw_props)
    async with driver.session() as session:
        result = await session.run("CREATE (i:Idea $props) RETURN i", props=props)
        record = await result.single()
        if record:
            idea = _idea_node_to_dict(record["i"])
            await asyncio.to_thread(_sync_idea_embedding, idea)
            return idea
    return {}


async def get_idea_node(idea_id: str) -> dict | None:
    driver = _get_driver()
    async with driver.session() as session:
        result = await session.run("MATCH (i:Idea {id: $id}) RETURN i", id=idea_id)
        record = await result.single()
        if record:
            return _idea_node_to_dict(record["i"])
    return None


async def list_idea_nodes(
    user_id: str, limit: int = 50, offset: int = 0,
    idea_type: str | None = None, status: str | None = None,
    tags: list[str] | None = None,
) -> tuple[list[dict], int]:
    driver = _get_driver()
    where_parts = ["i.user_id = $user_id"]
    params: dict = {"user_id": str(user_id), "limit": limit, "offset": offset}
    if idea_type:
        where_parts.append("i.idea_type = $filter_type")
        params["filter_type"] = idea_type
    if status:
        where_parts.append("i.status = $filter_status")
        params["filter_status"] = status
    if tags:
        where_parts.append("ANY(t IN $filter_tags WHERE t IN i.tags)")
        params["filter_tags"] = tags
    where_clause = " AND ".join(where_parts)
    async with driver.session() as session:
        count_result = await session.run(f"MATCH (i:Idea) WHERE {where_clause} RETURN count(i) AS total", **params)
        count_record = await count_result.single()
        total = count_record["total"] if count_record else 0
        result = await session.run(
            f"MATCH (i:Idea) WHERE {where_clause} RETURN i ORDER BY i.last_seen DESC SKIP $offset LIMIT $limit",
            **params,
        )
        records = [record async for record in result]
        items = [_idea_node_to_dict(record["i"]) for record in records]
    return items, total


async def update_idea_node(idea_id: str, **updates) -> dict | None:
    driver = _get_driver()
    set_parts = ["i.last_seen = $now"]
    params: dict = {"id": idea_id, "now": datetime.now(timezone.utc).isoformat()}
    for key, value in updates.items():
        if value is None:
            continue
        param_name = f"upd_{key}"
        if key == "confidence":
            set_parts.append(f"i.confidence = ${param_name}")
            params[param_name] = float(value)
        else:
            set_parts.append(f"i.{key} = ${param_name}")
            params[param_name] = value
    set_clause = ", ".join(set_parts)
    async with driver.session() as session:
        result = await session.run(f"MATCH (i:Idea {{id: $id}}) SET {set_clause} RETURN i", **params)
        record = await result.single()
        if record:
            idea = _idea_node_to_dict(record["i"])
            await asyncio.to_thread(_sync_idea_embedding, idea)
            return idea
    return None


async def delete_idea_node(idea_id: str) -> bool:
    idea = await get_idea_node(idea_id)
    user_id = idea.get("user_id", "") if idea else ""
    driver = _get_driver()
    async with driver.session() as session:
        result = await session.run(
            "MATCH (i:Idea {id: $id}) DETACH DELETE i RETURN count(i) AS deleted", id=idea_id,
        )
        record = await result.single()
        deleted = record and record["deleted"] > 0
    if deleted:
        try:
            from . import vector_db
            vector_db.delete_idea_embedding(idea_id)
        except Exception:
            try:
                from . import vector_db
                vector_db.insert_pending_sync(idea_id, user_id, "delete", "idea")
            except Exception:
                pass
    return deleted


async def search_ideas(user_id: str, search_term: str) -> list[dict]:
    if not search_term or not search_term.strip():
        return []
    driver = _get_driver()
    escaped = _escape_lucene_query(search_term.strip())
    lucene_query = f"*{escaped}*"
    try:
        async with driver.session() as session:
            result = await session.run(
                """
                CALL db.index.fulltext.queryNodes('idea_search_fulltext', $search_query)
                YIELD node AS i, score
                WHERE i.user_id = $user_id
                RETURN i ORDER BY score DESC
                """,
                search_query=lucene_query, user_id=str(user_id),
            )
            records = [record async for record in result]
            return [_idea_node_to_dict(record["i"]) for record in records]
    except Exception as e:
        logger.error("Idea search failed for term '%s': %s", search_term, e)
        raise


# =====================================================================
# Content Entity CRUD
# =====================================================================

def _content_node_to_dict(node) -> dict:
    """Convert a Neo4j Content node to a plain dictionary."""
    data = dict(node)
    for f in ("your_rating",):
        if f in data and data[f] is not None:
            try:
                data[f] = float(data[f])
            except (ValueError, TypeError):
                data[f] = None
    for f in ("tags",):
        if f not in data or data[f] is None:
            data[f] = []
    return data


def _sync_content_embedding(content: dict):
    """Sync content data to pgvector as a text embedding."""
    try:
        from . import embedding_service, vector_db
        text_content, embedding = embedding_service.generate_content_embedding(
            title=content.get("title", ""),
            content_type=content.get("content_type"),
            author=content.get("author"),
            personal_notes=content.get("personal_notes"),
            tags=content.get("tags", []),
        )
        vector_db.upsert_content_text_embedding(
            content_id=content["id"], user_id=content["user_id"],
            text_content=text_content, embedding=embedding,
        )
    except Exception as e:
        logger.warning("Failed to sync content embedding for id=%s: %s", content.get("id"), e)
        try:
            from . import vector_db
            vector_db.insert_pending_sync(content["id"], content["user_id"], "upsert", "content")
        except Exception:
            pass


async def create_content_node(user_id: str, title: str, **kwargs) -> dict:
    driver = _get_driver()
    now = datetime.now(timezone.utc).isoformat()
    content_id = str(uuid.uuid4())
    raw_props = {
        "id": content_id, "user_id": str(user_id), "title": title,
        "first_seen": now, "last_seen": now,
    }
    for field in _CONTENT_FIELDS:
        if field in kwargs and kwargs[field] is not None and field not in raw_props:
            raw_props[field] = kwargs[field]
    raw_props.setdefault("tags", [])
    props = _build_props(raw_props)
    async with driver.session() as session:
        result = await session.run("CREATE (c:Content $props) RETURN c", props=props)
        record = await result.single()
        if record:
            content = _content_node_to_dict(record["c"])
            await asyncio.to_thread(_sync_content_embedding, content)
            return content
    return {}


async def get_content_node(content_id: str) -> dict | None:
    driver = _get_driver()
    async with driver.session() as session:
        result = await session.run("MATCH (c:Content {id: $id}) RETURN c", id=content_id)
        record = await result.single()
        if record:
            return _content_node_to_dict(record["c"])
    return None


async def list_content_nodes(
    user_id: str, limit: int = 50, offset: int = 0,
    content_type: str | None = None, status: str | None = None,
    tags: list[str] | None = None,
) -> tuple[list[dict], int]:
    driver = _get_driver()
    where_parts = ["c.user_id = $user_id"]
    params: dict = {"user_id": str(user_id), "limit": limit, "offset": offset}
    if content_type:
        where_parts.append("c.content_type = $filter_type")
        params["filter_type"] = content_type
    if status:
        where_parts.append("c.status = $filter_status")
        params["filter_status"] = status
    if tags:
        where_parts.append("ANY(t IN $filter_tags WHERE t IN c.tags)")
        params["filter_tags"] = tags
    where_clause = " AND ".join(where_parts)
    async with driver.session() as session:
        count_result = await session.run(f"MATCH (c:Content) WHERE {where_clause} RETURN count(c) AS total", **params)
        count_record = await count_result.single()
        total = count_record["total"] if count_record else 0
        result = await session.run(
            f"MATCH (c:Content) WHERE {where_clause} RETURN c ORDER BY c.last_seen DESC SKIP $offset LIMIT $limit",
            **params,
        )
        records = [record async for record in result]
        items = [_content_node_to_dict(record["c"]) for record in records]
    return items, total


async def update_content_node(content_id: str, **updates) -> dict | None:
    driver = _get_driver()
    set_parts = ["c.last_seen = $now"]
    params: dict = {"id": content_id, "now": datetime.now(timezone.utc).isoformat()}
    for key, value in updates.items():
        if value is None:
            continue
        param_name = f"upd_{key}"
        if key == "your_rating":
            set_parts.append(f"c.your_rating = ${param_name}")
            params[param_name] = float(value)
        else:
            set_parts.append(f"c.{key} = ${param_name}")
            params[param_name] = value
    set_clause = ", ".join(set_parts)
    async with driver.session() as session:
        result = await session.run(f"MATCH (c:Content {{id: $id}}) SET {set_clause} RETURN c", **params)
        record = await result.single()
        if record:
            content = _content_node_to_dict(record["c"])
            await asyncio.to_thread(_sync_content_embedding, content)
            return content
    return None


async def delete_content_node(content_id: str) -> bool:
    content = await get_content_node(content_id)
    user_id = content.get("user_id", "") if content else ""
    driver = _get_driver()
    async with driver.session() as session:
        result = await session.run(
            "MATCH (c:Content {id: $id}) DETACH DELETE c RETURN count(c) AS deleted", id=content_id,
        )
        record = await result.single()
        deleted = record and record["deleted"] > 0
    if deleted:
        try:
            from . import vector_db
            vector_db.delete_content_embedding(content_id)
        except Exception:
            try:
                from . import vector_db
                vector_db.insert_pending_sync(content_id, user_id, "delete", "content")
            except Exception:
                pass
    return deleted


async def search_content(user_id: str, search_term: str) -> list[dict]:
    if not search_term or not search_term.strip():
        return []
    driver = _get_driver()
    escaped = _escape_lucene_query(search_term.strip())
    lucene_query = f"*{escaped}*"
    try:
        async with driver.session() as session:
            result = await session.run(
                """
                CALL db.index.fulltext.queryNodes('content_search_fulltext', $search_query)
                YIELD node AS c, score
                WHERE c.user_id = $user_id
                RETURN c ORDER BY score DESC
                """,
                search_query=lucene_query, user_id=str(user_id),
            )
            records = [record async for record in result]
            return [_content_node_to_dict(record["c"]) for record in records]
    except Exception as e:
        logger.error("Content search failed for term '%s': %s", search_term, e)
        raise


# =====================================================================
# Project Entity CRUD
# =====================================================================

def _project_node_to_dict(node) -> dict:
    """Convert a Neo4j Project node to a plain dictionary."""
    data = dict(node)
    for f in ("priority",):
        if f in data and data[f] is not None:
            try:
                data[f] = float(data[f])
            except (ValueError, TypeError):
                data[f] = 0.5
    for f in ("tags",):
        if f not in data or data[f] is None:
            data[f] = []
    return data


def _sync_project_embedding(project: dict):
    """Sync project data to pgvector as a text embedding."""
    try:
        from . import embedding_service, vector_db
        text_content, embedding = embedding_service.generate_project_embedding(
            name=project.get("name", ""),
            project_type=project.get("project_type"),
            description=project.get("description"),
            goal=project.get("goal"),
            tags=project.get("tags", []),
            notes=project.get("notes"),
        )
        vector_db.upsert_project_text_embedding(
            project_id=project["id"], user_id=project["user_id"],
            text_content=text_content, embedding=embedding,
        )
    except Exception as e:
        logger.warning("Failed to sync project embedding for id=%s: %s", project.get("id"), e)
        try:
            from . import vector_db
            vector_db.insert_pending_sync(project["id"], project["user_id"], "upsert", "project")
        except Exception:
            pass


async def create_project_node(user_id: str, name: str, **kwargs) -> dict:
    driver = _get_driver()
    now = datetime.now(timezone.utc).isoformat()
    project_id = str(uuid.uuid4())
    raw_props = {
        "id": project_id, "user_id": str(user_id), "name": name,
        "first_seen": now, "last_seen": now,
    }
    for field in _PROJECT_FIELDS:
        if field in kwargs and kwargs[field] is not None and field not in raw_props:
            raw_props[field] = kwargs[field]
    raw_props.setdefault("priority", 0.5)
    raw_props.setdefault("tags", [])
    props = _build_props(raw_props)
    async with driver.session() as session:
        result = await session.run("CREATE (p:Project $props) RETURN p", props=props)
        record = await result.single()
        if record:
            project = _project_node_to_dict(record["p"])
            await asyncio.to_thread(_sync_project_embedding, project)
            return project
    return {}


async def get_project_node(project_id: str) -> dict | None:
    driver = _get_driver()
    async with driver.session() as session:
        result = await session.run("MATCH (p:Project {id: $id}) RETURN p", id=project_id)
        record = await result.single()
        if record:
            return _project_node_to_dict(record["p"])
    return None


async def list_project_nodes(
    user_id: str, limit: int = 50, offset: int = 0,
    project_type: str | None = None, status: str | None = None,
    tags: list[str] | None = None,
) -> tuple[list[dict], int]:
    driver = _get_driver()
    where_parts = ["p.user_id = $user_id"]
    params: dict = {"user_id": str(user_id), "limit": limit, "offset": offset}
    if project_type:
        where_parts.append("p.project_type = $filter_type")
        params["filter_type"] = project_type
    if status:
        where_parts.append("p.status = $filter_status")
        params["filter_status"] = status
    if tags:
        where_parts.append("ANY(t IN $filter_tags WHERE t IN p.tags)")
        params["filter_tags"] = tags
    where_clause = " AND ".join(where_parts)
    async with driver.session() as session:
        count_result = await session.run(f"MATCH (p:Project) WHERE {where_clause} RETURN count(p) AS total", **params)
        count_record = await count_result.single()
        total = count_record["total"] if count_record else 0
        result = await session.run(
            f"MATCH (p:Project) WHERE {where_clause} RETURN p ORDER BY p.last_seen DESC SKIP $offset LIMIT $limit",
            **params,
        )
        records = [record async for record in result]
        items = [_project_node_to_dict(record["p"]) for record in records]
    return items, total


async def update_project_node(project_id: str, **updates) -> dict | None:
    driver = _get_driver()
    set_parts = ["p.last_seen = $now"]
    params: dict = {"id": project_id, "now": datetime.now(timezone.utc).isoformat()}
    for key, value in updates.items():
        if value is None:
            continue
        param_name = f"upd_{key}"
        if key == "priority":
            set_parts.append(f"p.priority = ${param_name}")
            params[param_name] = float(value)
        else:
            set_parts.append(f"p.{key} = ${param_name}")
            params[param_name] = value
    set_clause = ", ".join(set_parts)
    async with driver.session() as session:
        result = await session.run(f"MATCH (p:Project {{id: $id}}) SET {set_clause} RETURN p", **params)
        record = await result.single()
        if record:
            project = _project_node_to_dict(record["p"])
            await asyncio.to_thread(_sync_project_embedding, project)
            return project
    return None


async def delete_project_node(project_id: str) -> bool:
    project = await get_project_node(project_id)
    user_id = project.get("user_id", "") if project else ""
    driver = _get_driver()
    async with driver.session() as session:
        result = await session.run(
            "MATCH (p:Project {id: $id}) DETACH DELETE p RETURN count(p) AS deleted", id=project_id,
        )
        record = await result.single()
        deleted = record and record["deleted"] > 0
    if deleted:
        try:
            from . import vector_db
            vector_db.delete_project_embedding(project_id)
        except Exception:
            try:
                from . import vector_db
                vector_db.insert_pending_sync(project_id, user_id, "delete", "project")
            except Exception:
                pass
    return deleted


async def search_projects(user_id: str, search_term: str) -> list[dict]:
    if not search_term or not search_term.strip():
        return []
    driver = _get_driver()
    escaped = _escape_lucene_query(search_term.strip())
    lucene_query = f"*{escaped}*"
    try:
        async with driver.session() as session:
            result = await session.run(
                """
                CALL db.index.fulltext.queryNodes('project_search_fulltext', $search_query)
                YIELD node AS p, score
                WHERE p.user_id = $user_id
                RETURN p ORDER BY score DESC
                """,
                search_query=lucene_query, user_id=str(user_id),
            )
            records = [record async for record in result]
            return [_project_node_to_dict(record["p"]) for record in records]
    except Exception as e:
        logger.error("Project search failed for term '%s': %s", search_term, e)
        raise


# =====================================================================
# Cross-Entity Operations
# =====================================================================

_VALID_ENTITY_LABELS = {"Person", "Idea", "Content", "Project"}

_NODE_DESERIALIZERS = {
    "Person": _node_to_dict,
    "Idea": _idea_node_to_dict,
    "Content": _content_node_to_dict,
    "Project": _project_node_to_dict,
}


async def link_entities(
    from_label: str, from_id: str,
    to_label: str, to_id: str,
    rel_type: str, properties: dict | None = None,
) -> dict | None:
    """Create a relationship between any two entity nodes."""
    if from_label not in _VALID_ENTITY_LABELS or to_label not in _VALID_ENTITY_LABELS:
        raise ValueError(f"Invalid entity labels: {from_label}, {to_label}")
    driver = _get_driver()
    props = properties or {}
    props["created_at"] = datetime.now(timezone.utc).isoformat()
    sanitized = _sanitize_rel_type(rel_type)
    try:
        async with driver.session() as session:
            result = await session.run(
                f"""
                MATCH (a:{from_label} {{id: $from_id}})
                MATCH (b:{to_label} {{id: $to_id}})
                CREATE (a)-[r:{sanitized} $props]->(b)
                RETURN a.name AS from_name, COALESCE(a.name, a.title) AS from_display,
                       b.name AS to_name, COALESCE(b.name, b.title) AS to_display,
                       type(r) AS rel_type
                """,
                from_id=from_id, to_id=to_id, props=props,
            )
            record = await result.single()
            if record:
                return {
                    "from": record["from_display"],
                    "to": record["to_display"],
                    "relationship": record["rel_type"],
                    "from_type": from_label,
                    "to_type": to_label,
                }
        return None
    except Exception as e:
        logger.error("Failed to link entities %s:%s -> %s:%s (%s): %s",
                      from_label, from_id, to_label, to_id, rel_type, e)
        raise


async def unlink_entities(
    from_label: str, from_id: str,
    to_label: str, to_id: str,
    rel_type: str,
) -> bool:
    """Remove a relationship between any two entity nodes."""
    if from_label not in _VALID_ENTITY_LABELS or to_label not in _VALID_ENTITY_LABELS:
        raise ValueError(f"Invalid entity labels: {from_label}, {to_label}")
    driver = _get_driver()
    sanitized = _sanitize_rel_type(rel_type)
    try:
        async with driver.session() as session:
            result = await session.run(
                f"""
                MATCH (a:{from_label} {{id: $from_id}})-[r:{sanitized}]->(b:{to_label} {{id: $to_id}})
                DELETE r RETURN count(r) AS deleted
                """,
                from_id=from_id, to_id=to_id,
            )
            record = await result.single()
            return record and record["deleted"] > 0
    except Exception as e:
        logger.error("Failed to unlink entities: %s", e)
        raise


async def get_entity_graph(entity_label: str, entity_id: str) -> dict:
    """Get all connections of any entity across all entity types."""
    if entity_label not in _VALID_ENTITY_LABELS:
        raise ValueError(f"Invalid entity label: {entity_label}")
    driver = _get_driver()
    async with driver.session() as session:
        result = await session.run(
            f"""
            MATCH (e:{entity_label} {{id: $id}})-[r]-(other)
            RETURN e, type(r) AS rel_type, properties(r) AS rel_props,
                   other, labels(other) AS other_labels,
                   startNode(r) = e AS is_outgoing
            """,
            id=entity_id,
        )
        records = [record async for record in result]

    if not records:
        return {"entity": None, "connections": []}

    deserializer = _NODE_DESERIALIZERS.get(entity_label, dict)
    center = deserializer(records[0]["e"])

    connections = []
    seen = set()
    for record in records:
        if record["other"] is None:
            continue
        other_labels = record["other_labels"]
        other_label = next((l for l in other_labels if l in _VALID_ENTITY_LABELS), "Unknown")
        other_deser = _NODE_DESERIALIZERS.get(other_label, dict)
        other = other_deser(record["other"])
        edge_key = (other.get("id"), record["rel_type"], record["is_outgoing"])
        if edge_key in seen:
            continue
        seen.add(edge_key)
        connections.append({
            "entity": {
                "id": other.get("id"),
                "name": other.get("name") or other.get("title"),
                "type": other_label,
            },
            "relationship": record["rel_type"],
            "direction": "outgoing" if record["is_outgoing"] else "incoming",
            "properties": dict(record["rel_props"]) if record["rel_props"] else {},
        })

    return {"entity": center, "connections": connections}
