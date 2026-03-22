"""
LangChain tool factory for the Content sub-agent.

Creates 6 content tools with user_id baked in via closures,
exactly like backend/app/agent.py but scoped to content operations only.
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
    create_content_tool,
    get_content_tool,
    list_content_tool,
    update_content_tool,
    delete_content_tool,
    search_content_tool,
)

from agents.content_agent.schemas import (
    CreateContentInput,
    UpdateContentInput,
    GetContentInput,
    ListContentInput,
    DeleteContentInput,
    SearchContentInput,
)


def make_content_tools(user_id: str):
    """Return 6 LangChain tools bound to the given user_id via closures."""

    @tool(args_schema=CreateContentInput)
    async def create_content(title: str, **kwargs) -> dict:
        """Create new content (book, article, video, podcast, etc.) in the knowledge graph."""
        return await create_content_tool(user_id, title=title, **kwargs)

    @tool(args_schema=SearchContentInput)
    async def search_content(search_term: str) -> dict:
        """Search for content by title or description using semantic search."""
        return await search_content_tool(user_id, search_term)

    @tool(args_schema=GetContentInput)
    async def get_content(content_id: str) -> dict:
        """Get details of specific content by ID."""
        return await get_content_tool(user_id, content_id)

    @tool(args_schema=ListContentInput)
    async def list_content(
        limit: Optional[int] = 50,
        offset: Optional[int] = 0,
        content_type: Optional[str] = None,
        status: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> dict:
        """List all saved content. Supports filtering by content_type, status, tags."""
        return await list_content_tool(user_id, limit, offset, content_type, status, tags)

    @tool(args_schema=UpdateContentInput)
    async def update_content(content_id: str, **kwargs) -> dict:
        """Update existing content's information."""
        return await update_content_tool(user_id, content_id=content_id, **kwargs)

    @tool(args_schema=DeleteContentInput)
    async def delete_content(content_id: str) -> dict:
        """Delete content from the knowledge graph."""
        return await delete_content_tool(user_id, content_id)

    return [
        create_content,
        search_content,
        get_content,
        list_content,
        update_content,
        delete_content,
    ]
