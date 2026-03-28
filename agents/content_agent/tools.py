"""
LangChain tool factory for the Content sub-agent.

Creates 6 content tools with user_id baked in via closures.
Each tool has improved descriptions and output schema annotations.
"""

import sys
from pathlib import Path
from typing import List, Optional

from langchain_core.tools import tool

_project_root = str(Path(__file__).parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from backend.app import md_storage

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
        """Create a new content record (book, article, video, podcast, paper, course, movie, tweet, talk). Extract all available context: content_type, author, source_url, status (want/reading/completed/abandoned), your_rating (0-1), personal_notes, recommended_by, tags. Always search_content first to avoid duplicates. Returns: {success, message, content: {id, title, content_type, author, status, ...}}"""
        data = {"title": title, **kwargs}
        try:
            result = await md_storage.create_entity(user_id, "content", data)
            return {"success": True, "message": f"Content '{title}' created.", "content": result}
        except Exception as e:
            return {"success": False, "message": f"Error creating content: {e}"}

    @tool(args_schema=SearchContentInput)
    async def search_content(search_term: str) -> dict:
        """Semantic search for content by title, author, description, or topic. Uses keyword scoring with fallback to exact match. Always call before create_content to check for existing items. Returns: {success, count, search_type: 'keyword', content: [{id, title, ...}]}"""
        try:
            results = await md_storage.search_entities(user_id, "content", search_term)
            return {"success": True, "count": len(results), "search_type": "keyword", "content": results}
        except Exception as e:
            return {"success": False, "message": f"Error searching content: {e}"}

    @tool(args_schema=GetContentInput)
    async def get_content(content_id: str) -> dict:
        """Fetch full details of a content item by UUID. Use to verify current state before updating. Returns: {success, content: {id, title, content_type, author, status, your_rating, personal_notes, ...}}"""
        try:
            result = await md_storage.get_entity(user_id, "content", content_id)
            if result is None:
                return {"success": False, "message": f"Content not found: {content_id}"}
            return {"success": True, "content": result}
        except Exception as e:
            return {"success": False, "message": f"Error getting content: {e}"}

    @tool(args_schema=ListContentInput)
    async def list_content(
        limit: Optional[int] = 50,
        offset: Optional[int] = 0,
        content_type: Optional[str] = None,
        status: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> dict:
        """List all content with pagination and optional filters. Filter by content_type (book/article/video/podcast/paper/course/movie/tweet/talk), status (want/reading/completed/abandoned), or tags. Returns: {success, count, total, content: [...]}"""
        try:
            filters = {}
            if content_type:
                filters["content_type"] = content_type
            if status:
                filters["status"] = status
            if tags:
                filters["tags"] = tags
            items, total = await md_storage.list_entities(user_id, "content", limit or 50, offset or 0, **filters)
            return {"success": True, "count": len(items), "total": total, "content": items}
        except Exception as e:
            return {"success": False, "message": f"Error listing content: {e}"}

    @tool(args_schema=UpdateContentInput)
    async def update_content(content_id: str, **kwargs) -> dict:
        """Update an existing content item's fields by UUID. Only provide fields that need changing. Commonly used to change status (want->reading->completed), add rating, or update notes. Returns: {success, message, content: {id, title, ...}}"""
        try:
            result = await md_storage.update_entity(user_id, "content", content_id, kwargs)
            if result is None:
                return {"success": False, "message": f"Content not found: {content_id}"}
            return {"success": True, "message": "Content updated.", "content": result}
        except Exception as e:
            return {"success": False, "message": f"Error updating content: {e}"}

    @tool(args_schema=DeleteContentInput)
    async def delete_content(content_id: str) -> dict:
        """Permanently delete a content item by UUID. Only call when the user explicitly asks to remove content. Returns: {success, message, deleted_id}"""
        try:
            deleted = await md_storage.delete_entity(user_id, "content", content_id)
            if not deleted:
                return {"success": False, "message": f"Content not found: {content_id}"}
            return {"success": True, "message": "Content deleted.", "deleted_id": content_id}
        except Exception as e:
            return {"success": False, "message": f"Error deleting content: {e}"}

    return [
        create_content,
        search_content,
        get_content,
        list_content,
        update_content,
        delete_content,
    ]
