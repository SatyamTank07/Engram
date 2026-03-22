"""
LangChain tool factory for the Idea sub-agent.

Creates 6 idea tools with user_id baked in via closures.
Each tool has improved descriptions and output schema annotations.
"""

import sys
from pathlib import Path
from typing import List, Optional

from langchain_core.tools import tool

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
        """Create a new idea, thought, prediction, opinion, decision, question, hypothesis, or lesson learned. Extract all available context: idea_type, confidence (0-1), status, evidence_for/against, date_formed, revisit_date, tags. Always search_ideas first to avoid duplicates. Returns: {success, message, idea: {id, name, idea_type, confidence, status, ...}}"""
        return await create_idea_tool(user_id, name=name, **kwargs)

    @tool(args_schema=SearchIdeasInput)
    async def search_ideas(search_term: str) -> dict:
        """Semantic search for ideas by name, description, or topic. Uses vector embeddings with fallback to exact match. Always call before create_idea to check for existing similar ideas. Returns: {success, count, search_type: 'semantic'|'exact', ideas: [{id, name, similarity_score, ...}]}"""
        return await search_ideas_tool(user_id, search_term)

    @tool(args_schema=GetIdeaInput)
    async def get_idea(idea_id: str) -> dict:
        """Fetch full details of an idea by UUID. Use to verify current state before updating. Returns: {success, idea: {id, name, idea_type, confidence, status, evidence_for, evidence_against, ...}}"""
        return await get_idea_tool(user_id, idea_id)

    @tool(args_schema=ListIdeasInput)
    async def list_ideas(
        limit: Optional[int] = 50,
        offset: Optional[int] = 0,
        idea_type: Optional[str] = None,
        status: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> dict:
        """List all ideas with pagination and optional filters. Filter by idea_type (prediction/opinion/decision/question/realization/hypothesis/lesson_learned), status (active/validated/invalidated/evolved/abandoned), or tags. Returns: {success, count, total, ideas: [...]}"""
        return await list_ideas_tool(user_id, limit, offset, idea_type, status, tags)

    @tool(args_schema=UpdateIdeaInput)
    async def update_idea(idea_id: str, **kwargs) -> dict:
        """Update an existing idea's fields by UUID. Only provide fields that need changing. Commonly used to update status (e.g., active->validated), add new evidence, or adjust confidence. Returns: {success, message, idea: {id, name, ...}}"""
        return await update_idea_tool(user_id, idea_id=idea_id, **kwargs)

    @tool(args_schema=DeleteIdeaInput)
    async def delete_idea(idea_id: str) -> dict:
        """Permanently delete an idea by UUID. Only call when the user explicitly asks to remove an idea. Returns: {success, message, deleted_id}"""
        return await delete_idea_tool(user_id, idea_id)

    return [
        create_idea,
        search_ideas,
        get_idea,
        list_ideas,
        update_idea,
        delete_idea,
    ]
