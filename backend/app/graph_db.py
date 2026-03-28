"""
Knowledge Graph operations using Neo4j for PersonIdentity storage.
Idea/Content/Project CRUD has been moved to md_storage.
"""

import asyncio
import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone

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


