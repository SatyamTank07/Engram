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

# Import tool functions (each now requires user_id as first arg)
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
    # Idea tools
    create_idea_tool,
    get_idea_tool,
    list_ideas_tool,
    update_idea_tool,
    delete_idea_tool,
    search_ideas_tool,
    # Content tools
    create_content_tool,
    get_content_tool,
    list_content_tool,
    update_content_tool,
    delete_content_tool,
    search_content_tool,
    # Project tools
    create_project_tool,
    get_project_tool,
    list_projects_tool,
    update_project_tool,
    delete_project_tool,
    search_projects_tool,
    # Cross-entity tools
    link_entities_tool,
    get_entity_graph_tool,
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
# Idea MCP tools
# =====================================================================

@mcp.tool()
def create_idea(
    user_id: str, name: str,
    idea_type: str | None = None, description: str | None = None,
    confidence: float | None = None, status: str | None = None,
    evidence_for: list[str] | None = None, evidence_against: list[str] | None = None,
    date_formed: str | None = None, revisit_date: str | None = None,
    tags: list[str] | None = None, notes: str | None = None,
) -> dict:
    """Create a new idea in the knowledge graph."""
    kwargs = {}
    for field in ("idea_type", "description", "confidence", "status", "evidence_for",
                  "evidence_against", "date_formed", "revisit_date", "tags", "notes"):
        val = locals()[field]
        if val is not None:
            kwargs[field] = val
    return create_idea_tool(user_id, name, **kwargs)


@mcp.tool()
def get_idea(user_id: str, idea_id: str) -> dict:
    """Get details of a specific idea by ID."""
    return get_idea_tool(user_id, idea_id)


@mcp.tool()
def list_ideas(
    user_id: str, limit: int | None = 50, offset: int | None = 0,
    idea_type: str | None = None, status: str | None = None,
    tags: list[str] | None = None,
) -> dict:
    """List ideas for a user."""
    return list_ideas_tool(user_id, limit, offset, idea_type, status, tags)


@mcp.tool()
def update_idea(
    user_id: str, idea_id: str,
    name: str | None = None, idea_type: str | None = None,
    description: str | None = None, confidence: float | None = None,
    status: str | None = None, evidence_for: list[str] | None = None,
    evidence_against: list[str] | None = None, date_formed: str | None = None,
    revisit_date: str | None = None, tags: list[str] | None = None,
    notes: str | None = None,
) -> dict:
    """Update an existing idea."""
    kwargs = {}
    for field in ("name", "idea_type", "description", "confidence", "status",
                  "evidence_for", "evidence_against", "date_formed", "revisit_date", "tags", "notes"):
        val = locals()[field]
        if val is not None:
            kwargs[field] = val
    return update_idea_tool(user_id, idea_id, **kwargs)


@mcp.tool()
def delete_idea(user_id: str, idea_id: str) -> dict:
    """Delete an idea."""
    return delete_idea_tool(user_id, idea_id)


@mcp.tool()
def search_ideas(user_id: str, search_term: str) -> dict:
    """Search ideas by name or description."""
    return search_ideas_tool(user_id, search_term)


# =====================================================================
# Content MCP tools
# =====================================================================

@mcp.tool()
def create_content(
    user_id: str, title: str,
    content_type: str | None = None, author: str | None = None,
    source_url: str | None = None, status: str | None = None,
    your_rating: float | None = None, personal_notes: str | None = None,
    recommended_by: str | None = None, tags: list[str] | None = None,
) -> dict:
    """Create new content in the knowledge graph."""
    kwargs = {}
    for field in ("content_type", "author", "source_url", "status",
                  "your_rating", "personal_notes", "recommended_by", "tags"):
        val = locals()[field]
        if val is not None:
            kwargs[field] = val
    return create_content_tool(user_id, title, **kwargs)


@mcp.tool()
def get_content(user_id: str, content_id: str) -> dict:
    """Get details of specific content by ID."""
    return get_content_tool(user_id, content_id)


@mcp.tool()
def list_content(
    user_id: str, limit: int | None = 50, offset: int | None = 0,
    content_type: str | None = None, status: str | None = None,
    tags: list[str] | None = None,
) -> dict:
    """List content for a user."""
    return list_content_tool(user_id, limit, offset, content_type, status, tags)


@mcp.tool()
def update_content(
    user_id: str, content_id: str,
    title: str | None = None, content_type: str | None = None,
    author: str | None = None, source_url: str | None = None,
    status: str | None = None, your_rating: float | None = None,
    personal_notes: str | None = None, recommended_by: str | None = None,
    tags: list[str] | None = None,
) -> dict:
    """Update existing content."""
    kwargs = {}
    for field in ("title", "content_type", "author", "source_url", "status",
                  "your_rating", "personal_notes", "recommended_by", "tags"):
        val = locals()[field]
        if val is not None:
            kwargs[field] = val
    return update_content_tool(user_id, content_id, **kwargs)


@mcp.tool()
def delete_content(user_id: str, content_id: str) -> dict:
    """Delete content."""
    return delete_content_tool(user_id, content_id)


@mcp.tool()
def search_content(user_id: str, search_term: str) -> dict:
    """Search content by title or description."""
    return search_content_tool(user_id, search_term)


# =====================================================================
# Project MCP tools
# =====================================================================

@mcp.tool()
def create_project(
    user_id: str, name: str,
    project_type: str | None = None, status: str | None = None,
    description: str | None = None, goal: str | None = None,
    target_date: str | None = None, priority: float | None = None,
    tags: list[str] | None = None, notes: str | None = None,
) -> dict:
    """Create a new project in the knowledge graph."""
    kwargs = {}
    for field in ("project_type", "status", "description", "goal",
                  "target_date", "priority", "tags", "notes"):
        val = locals()[field]
        if val is not None:
            kwargs[field] = val
    return create_project_tool(user_id, name, **kwargs)


@mcp.tool()
def get_project(user_id: str, project_id: str) -> dict:
    """Get details of a specific project by ID."""
    return get_project_tool(user_id, project_id)


@mcp.tool()
def list_projects(
    user_id: str, limit: int | None = 50, offset: int | None = 0,
    project_type: str | None = None, status: str | None = None,
    tags: list[str] | None = None,
) -> dict:
    """List projects for a user."""
    return list_projects_tool(user_id, limit, offset, project_type, status, tags)


@mcp.tool()
def update_project(
    user_id: str, project_id: str,
    name: str | None = None, project_type: str | None = None,
    status: str | None = None, description: str | None = None,
    goal: str | None = None, target_date: str | None = None,
    priority: float | None = None, tags: list[str] | None = None,
    notes: str | None = None,
) -> dict:
    """Update an existing project."""
    kwargs = {}
    for field in ("name", "project_type", "status", "description", "goal",
                  "target_date", "priority", "tags", "notes"):
        val = locals()[field]
        if val is not None:
            kwargs[field] = val
    return update_project_tool(user_id, project_id, **kwargs)


@mcp.tool()
def delete_project(user_id: str, project_id: str) -> dict:
    """Delete a project."""
    return delete_project_tool(user_id, project_id)


@mcp.tool()
def search_projects(user_id: str, search_term: str) -> dict:
    """Search projects by name or description."""
    return search_projects_tool(user_id, search_term)


# =====================================================================
# Cross-entity MCP tools
# =====================================================================

@mcp.tool()
def link_entities(
    user_id: str,
    from_type: str, from_id: str,
    to_type: str, to_id: str,
    rel_type: str, properties: dict | None = None,
) -> dict:
    """Create a cross-entity relationship between any two entities."""
    return link_entities_tool(user_id, from_type, from_id, to_type, to_id, rel_type, properties)


@mcp.tool()
def get_entity_graph(user_id: str, entity_type: str, entity_id: str) -> dict:
    """Get all connections of any entity."""
    return get_entity_graph_tool(user_id, entity_type, entity_id)


if __name__ == "__main__":
    mcp.run()
