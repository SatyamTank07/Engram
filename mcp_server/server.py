"""
FastMCP server for PersonIdentity CRUD operations.
Allows LLMs to interact with the PersonIdentity database table.

NOTE: When used standalone (outside the chat API), the MCP client must
provide user_id as a required parameter on every tool call.
"""

import os
import sys
from pathlib import Path

# Add parent directory to path to import backend modules
sys.path.append(str(Path(__file__).parent.parent))

from fastmcp import FastMCP
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

import json

# Import tool functions (each now requires user_id as first arg)
from mcp_server import tools
from mcp_server.tools import (
    create_person_tool,
    get_person_tool,
    list_persons_tool,
    update_person_tool,
    delete_person_tool,
    search_person_tool,
    add_relationship_tool,
    get_relationships_tool,
    update_relationship_tool,
    delete_relationship_tool,
)

# Initialize FastMCP server
mcp = FastMCP("Engram Knowledge Graph Server")


# Wrap each tool so user_id is a required MCP parameter.
@mcp.tool()
def create_person(
    user_id: str,
    name: str,
    aliases: list[str] | None = None,
    contacts: dict | None = None,
    short_bio: str | None = None,
    trust_score: float | None = 0.0,
    occupation: str | None = None,
    company: str | None = None,
    location: str | None = None,
    tags: list[str] | None = None,
    interests: list[str] | None = None,
    notes: str | None = None,
    nationality: str | None = None,
    languages: list[str] | None = None,
    person_scope: str | None = None,
    public_role: str | None = None,
    known_for: list[str] | None = None,
    public_bio: str | None = None,
    relationship_with: str | None = None,
    relationship_type: str | None = None,
    relationship_direction: str | None = None,
    relationship_notes: str | None = None,
    relationship_strength: float | None = None,
) -> dict:
    """Create a new person identity in the knowledge graph. Optionally include relationship_with, relationship_type, and relationship_direction to create a relationship in the same call."""
    kwargs = {}
    for field in ("occupation", "company", "location", "tags", "interests", "notes",
                  "nationality", "languages", "person_scope", "public_role", "known_for", "public_bio",
                  "relationship_with", "relationship_type", "relationship_direction",
                  "relationship_notes", "relationship_strength"):
        val = locals()[field]
        if val is not None:
            kwargs[field] = val
    return create_person_tool(user_id, name, aliases, contacts, short_bio, trust_score, **kwargs)


@mcp.tool()
def get_person(user_id: str, person_id: str) -> dict:
    """Get details of a specific person by their ID."""
    return get_person_tool(user_id, person_id)


@mcp.tool()
def list_persons(
    user_id: str,
    limit: int | None = 50,
    offset: int | None = 0,
    tags: list[str] | None = None,
    location: str | None = None,
    occupation: str | None = None,
    company: str | None = None,
    interaction_frequency: str | None = None,
) -> dict:
    """List saved persons for a user with optional filtering and pagination."""
    return list_persons_tool(user_id, limit, offset, tags, location, occupation, company, interaction_frequency)


@mcp.tool()
def update_person(
    user_id: str,
    person_id: str,
    name: str | None = None,
    aliases: list[str] | None = None,
    contacts: dict | None = None,
    short_bio: str | None = None,
    trust_score: float | None = None,
    occupation: str | None = None,
    company: str | None = None,
    location: str | None = None,
    tags: list[str] | None = None,
    interests: list[str] | None = None,
    notes: str | None = None,
    nationality: str | None = None,
    languages: list[str] | None = None,
    person_scope: str | None = None,
    public_role: str | None = None,
    known_for: list[str] | None = None,
    public_bio: str | None = None,
    relationship_with: str | None = None,
    relationship_type: str | None = None,
    relationship_direction: str | None = None,
    relationship_notes: str | None = None,
    relationship_strength: float | None = None,
) -> dict:
    """Update an existing person's information. Optionally include relationship_with, relationship_type, and relationship_direction to add a relationship in the same call."""
    kwargs = {}
    for field in ("name", "aliases", "contacts", "short_bio", "trust_score",
                  "occupation", "company", "location", "tags", "interests", "notes",
                  "nationality", "languages", "person_scope", "public_role", "known_for", "public_bio",
                  "relationship_with", "relationship_type", "relationship_direction",
                  "relationship_notes", "relationship_strength"):
        val = locals()[field]
        if val is not None:
            kwargs[field] = val
    return update_person_tool(user_id, person_id, **kwargs)


@mcp.tool()
def delete_person(user_id: str, person_id: str) -> dict:
    """Delete a person from the knowledge graph."""
    return delete_person_tool(user_id, person_id)


@mcp.tool()
def search_person(user_id: str, search_term: str) -> dict:
    """Search for persons by name or description."""
    return search_person_tool(user_id, search_term)


@mcp.tool()
def add_relationship(
    user_id: str,
    from_person_name: str,
    to_person_name: str,
    relationship_type: str,
    notes: str | None = None,
    strength: float | None = None,
    context: str | None = None,
) -> dict:
    """Create a relationship between two people."""
    return add_relationship_tool(user_id, from_person_name, to_person_name, relationship_type, notes, strength, context)


@mcp.tool()
def get_relationships(user_id: str, person_name: str) -> dict:
    """Get all relationships for a person."""
    return get_relationships_tool(user_id, person_name)


@mcp.tool()
def update_relationship(
    user_id: str,
    from_person_name: str,
    to_person_name: str,
    relationship_type: str,
    strength: float | None = None,
    context: str | None = None,
    started_at: str | None = None,
    ended_at: str | None = None,
    notes: str | None = None,
) -> dict:
    """Update properties on an existing relationship."""
    return update_relationship_tool(
        user_id, from_person_name, to_person_name, relationship_type,
        strength, context, started_at, ended_at, notes,
    )


@mcp.tool()
def delete_relationship(
    user_id: str,
    from_person_name: str,
    to_person_name: str,
    relationship_type: str,
) -> dict:
    """Delete a relationship between two people."""
    return delete_relationship_tool(user_id, from_person_name, to_person_name, relationship_type)


# =====================================================================
# Generic Entity MCP tools (idea, content, project) — backed by md_storage
# =====================================================================

@mcp.tool()
async def create_entity(user_id: str, entity_type: str, data: dict) -> str:
    """Create a new entity.

    Args:
        user_id: The user's ID
        entity_type: Type of entity - "idea", "content", or "project"
        data: Entity data dict with type-specific fields.
              For ideas: name, idea_type, description, confidence, status, evidence_for, evidence_against, tags, notes
              For content: title, content_type, author, source_url, status, your_rating, personal_notes, tags
              For projects: name, project_type, status, description, goal, target_date, priority, tags, notes
    """
    result = await tools.create_entity(user_id, entity_type, data)
    return json.dumps(result, default=str)


@mcp.tool()
async def get_entity(user_id: str, entity_type: str, entity_id: str) -> str:
    """Get an entity by its ID.

    Args:
        user_id: The user's ID
        entity_type: Type of entity - "idea", "content", or "project"
        entity_id: The unique identifier of the entity
    """
    result = await tools.get_entity(user_id, entity_type, entity_id)
    return json.dumps(result, default=str)


@mcp.tool()
async def list_entities(
    user_id: str, entity_type: str,
    limit: int = 50, offset: int = 0,
    filters: dict | None = None,
) -> str:
    """List entities with optional filtering and pagination.

    Args:
        user_id: The user's ID
        entity_type: Type of entity - "idea", "content", or "project"
        limit: Maximum number of results to return (default 50)
        offset: Number of results to skip for pagination (default 0)
        filters: Optional dict of filter criteria (e.g. {"status": "active", "tags": ["ai"]})
    """
    result = await tools.list_entities(user_id, entity_type, limit, offset, filters)
    return json.dumps(result, default=str)


@mcp.tool()
async def update_entity(user_id: str, entity_type: str, entity_id: str, updates: dict) -> str:
    """Update an existing entity.

    Args:
        user_id: The user's ID
        entity_type: Type of entity - "idea", "content", or "project"
        entity_id: The unique identifier of the entity to update
        updates: Dict of fields to update (only provided fields are changed)
    """
    result = await tools.update_entity(user_id, entity_type, entity_id, updates)
    return json.dumps(result, default=str)


@mcp.tool()
async def delete_entity(user_id: str, entity_type: str, entity_id: str) -> str:
    """Delete an entity.

    Args:
        user_id: The user's ID
        entity_type: Type of entity - "idea", "content", or "project"
        entity_id: The unique identifier of the entity to delete
    """
    result = await tools.delete_entity(user_id, entity_type, entity_id)
    return json.dumps(result, default=str)


@mcp.tool()
async def search_entities(user_id: str, entity_type: str, query: str, limit: int = 20) -> str:
    """Search entities by keyword across their content.

    Args:
        user_id: The user's ID
        entity_type: Type of entity - "idea", "content", or "project"
        query: Search term to match against entity titles, descriptions, and body content
        limit: Maximum number of results to return (default 20)
    """
    result = await tools.search_entities(user_id, entity_type, query, limit)
    return json.dumps(result, default=str)


if __name__ == "__main__":
    mcp.run()
