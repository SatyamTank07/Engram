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
)

# Initialize FastMCP server
mcp = FastMCP("PersonIdentity CRUD Server")


# Wrap each tool so user_id is a required MCP parameter.
@mcp.tool()
def create_person(
    user_id: str,
    name: str,
    aliases: list[str] | None = None,
    contacts: dict | None = None,
    short_bio: str | None = None,
    trust_score: float | None = 0.0,
) -> dict:
    """Create a new person identity in the knowledge graph."""
    return create_person_tool(user_id, name, aliases, contacts, short_bio, trust_score)


@mcp.tool()
def get_person(user_id: str, person_id: str) -> dict:
    """Get details of a specific person by their ID."""
    return get_person_tool(user_id, person_id)


@mcp.tool()
def list_persons(user_id: str, limit: int | None = 50) -> dict:
    """List all saved persons for a user."""
    return list_persons_tool(user_id, limit)


@mcp.tool()
def update_person(
    user_id: str,
    person_id: str,
    name: str | None = None,
    aliases: list[str] | None = None,
    contacts: dict | None = None,
    short_bio: str | None = None,
    trust_score: float | None = None,
) -> dict:
    """Update an existing person's information."""
    return update_person_tool(user_id, person_id, name, aliases, contacts, short_bio, trust_score)


@mcp.tool()
def delete_person(user_id: str, person_id: str) -> dict:
    """Delete a person from the knowledge graph."""
    return delete_person_tool(user_id, person_id)


@mcp.tool()
def search_person(user_id: str, search_term: str) -> dict:
    """Search for persons by name or description."""
    return search_person_tool(user_id, search_term)


if __name__ == "__main__":
    mcp.run()
