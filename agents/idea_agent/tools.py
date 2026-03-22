"""
LangChain tool factory for the Idea sub-agent.

Creates 6 idea tools with user_id baked in via closures,
exactly like backend/app/agent.py but scoped to idea operations only.
"""

import sys
from pathlib import Path
from typing import List, Optional

from langchain_core.tools import tool

# Ensure project root is on sys.path
_project_root = str(Path(__file__).parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from mcp_server.tools import (
    create_idea_tool,
    get_idea_tool,
    list_ideas_tool,
    update_idea_tool,
    delete_idea_tool,
    search_ideas_tool,
)

from agents.idea_agent.schemas import (
    CreateIdeaInput,
    UpdateIdeaInput,
    GetIdeaInput,
    ListIdeasInput,
    DeleteIdeaInput,
    SearchIdeasInput,
)


def make_idea_tools(user_id: str):
    """Return 6 LangChain tools bound to the given user_id via closures."""

    @tool(args_schema=CreateIdeaInput)
    async def create_idea(name: str, **kwargs) -> dict:
        """Create a new idea/thought/prediction/opinion in the knowledge graph."""
        return await create_idea_tool(user_id, name=name, **kwargs)

    @tool(args_schema=SearchIdeasInput)
    async def search_ideas(search_term: str) -> dict:
        """Search for ideas by name or description using semantic search."""
        return await search_ideas_tool(user_id, search_term)

    @tool(args_schema=GetIdeaInput)
    async def get_idea(idea_id: str) -> dict:
        """Get details of a specific idea by ID."""
        return await get_idea_tool(user_id, idea_id)

    @tool(args_schema=ListIdeasInput)
    async def list_ideas(
        limit: Optional[int] = 50,
        offset: Optional[int] = 0,
        idea_type: Optional[str] = None,
        status: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> dict:
        """List all saved ideas. Supports filtering by idea_type, status, tags."""
        return await list_ideas_tool(user_id, limit, offset, idea_type, status, tags)

    @tool(args_schema=UpdateIdeaInput)
    async def update_idea(idea_id: str, **kwargs) -> dict:
        """Update an existing idea's information."""
        return await update_idea_tool(user_id, idea_id=idea_id, **kwargs)

    @tool(args_schema=DeleteIdeaInput)
    async def delete_idea(idea_id: str) -> dict:
        """Delete an idea from the knowledge graph."""
        return await delete_idea_tool(user_id, idea_id)

    return [
        create_idea,
        search_ideas,
        get_idea,
        list_ideas,
        update_idea,
        delete_idea,
    ]
