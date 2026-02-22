"""
Knowledge Graph operations using Neo4j for PersonIdentity storage.
Replaces PostgreSQL-based PersonIdentity CRUD with graph-native operations.
"""

import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from neo4j import GraphDatabase


# Neo4j connection settings
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "engram_graph")


class Neo4jConnection:
    """Singleton Neo4j driver manager."""

    _driver = None

    @classmethod
    def get_driver(cls):
        if cls._driver is None:
            cls._driver = GraphDatabase.driver(
                NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)
            )
        return cls._driver

    @classmethod
    def close(cls):
        if cls._driver is not None:
            cls._driver.close()
            cls._driver = None


def _get_driver():
    return Neo4jConnection.get_driver()


def init_graph_db():
    """Create indexes and constraints for the Person nodes."""
    driver = _get_driver()
    with driver.session() as session:
        # Unique constraint on Person.id
        session.run(
            "CREATE CONSTRAINT person_id_unique IF NOT EXISTS "
            "FOR (p:Person) REQUIRE p.id IS UNIQUE"
        )
        # Index on Person.user_id for fast per-user lookups
        session.run(
            "CREATE INDEX person_user_id IF NOT EXISTS "
            "FOR (p:Person) ON (p.user_id)"
        )
        # Index on Person.name for search
        session.run(
            "CREATE INDEX person_name IF NOT EXISTS "
            "FOR (p:Person) ON (p.name)"
        )


# ---------------------
# CRUD Operations
# ---------------------


def create_person_node(
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

    with driver.session() as session:
        result = session.run(
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
        record = result.single()
        if record:
            return _node_to_dict(record["p"])
    return {}


def get_person_node(person_id: str) -> dict | None:
    """Get a Person node by its ID."""
    driver = _get_driver()
    with driver.session() as session:
        result = session.run(
            "MATCH (p:Person {id: $id}) RETURN p",
            id=person_id,
        )
        record = result.single()
        if record:
            return _node_to_dict(record["p"])
    return None


def list_person_nodes(user_id: str, limit: int = 50) -> list[dict]:
    """List all Person nodes for a given user, ordered by last_seen desc."""
    driver = _get_driver()
    with driver.session() as session:
        result = session.run(
            """
            MATCH (p:Person {user_id: $user_id})
            RETURN p
            ORDER BY p.last_seen DESC
            LIMIT $limit
            """,
            user_id=str(user_id),
            limit=limit,
        )
        return [_node_to_dict(record["p"]) for record in result]


def update_person_node(
    person_id: str,
    name: str | None = None,
    aliases: list[str] | None = None,
    contacts: dict | None = None,
    short_bio: str | None = None,
    trust_score: float | None = None,
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

    set_clause = ", ".join(set_parts)

    with driver.session() as session:
        result = session.run(
            f"MATCH (p:Person {{id: $id}}) SET {set_clause} RETURN p",
            **params,
        )
        record = result.single()
        if record:
            return _node_to_dict(record["p"])
    return None


def delete_person_node(person_id: str) -> bool:
    """Delete a Person node and all its relationships."""
    driver = _get_driver()
    with driver.session() as session:
        result = session.run(
            "MATCH (p:Person {id: $id}) DETACH DELETE p RETURN count(p) AS deleted",
            id=person_id,
        )
        record = result.single()
        return record and record["deleted"] > 0


def search_persons(user_id: str, search_term: str) -> list[dict]:
    """Search Person nodes by name (case-insensitive partial match)."""
    driver = _get_driver()
    with driver.session() as session:
        result = session.run(
            """
            MATCH (p:Person {user_id: $user_id})
            WHERE toLower(p.name) CONTAINS toLower($search_term)
            RETURN p
            """,
            user_id=str(user_id),
            search_term=search_term,
        )
        return [_node_to_dict(record["p"]) for record in result]


# ---------------------
# Relationship Operations (Future-ready)
# ---------------------


def add_relationship(
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

    with driver.session() as session:
        # Use APOC or dynamic relationship type
        result = session.run(
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
        record = result.single()
        if record:
            return {
                "from": record["from_name"],
                "to": record["to_name"],
                "relationship": record["rel_type"],
            }
    return None


def get_relationships(person_id: str) -> list[dict]:
    """Get all relationships for a Person node."""
    driver = _get_driver()
    with driver.session() as session:
        result = session.run(
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
        return [
            {
                "relationship": record["rel_type"],
                "properties": dict(record["rel_props"]) if record["rel_props"] else {},
                "person_id": record["other_id"],
                "person_name": record["other_name"],
                "direction": "outgoing" if record["is_outgoing"] else "incoming",
            }
            for record in result
        ]


# ---------------------
# Helpers
# ---------------------


def _node_to_dict(node) -> dict:
    """Convert a Neo4j node to a plain dictionary."""
    data = dict(node)
    # Deserialize contacts back from JSON string
    if "contacts" in data and isinstance(data["contacts"], str):
        import json
        try:
            data["contacts"] = json.loads(data["contacts"])
        except (json.JSONDecodeError, TypeError):
            data["contacts"] = {}
    return data


def _serialize_contacts(contacts: dict) -> str:
    """Serialize contacts dict to JSON string for Neo4j storage.
    
    Neo4j doesn't natively support nested maps, so we store contacts as a JSON string.
    """
    import json
    return json.dumps(contacts)


def _sanitize_rel_type(rel_type: str) -> str:
    """Sanitize relationship type to be a valid Neo4j relationship type."""
    # Only allow alphanumeric and underscores
    sanitized = "".join(c if c.isalnum() or c == "_" else "_" for c in rel_type.upper())
    return sanitized or "RELATED_TO"
