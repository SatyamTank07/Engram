"""
LangChain tool factory for the Project sub-agent.

Creates 6 project tools with user_id baked in via closures.
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
    create_project_tool,
    get_project_tool,
    list_projects_tool,
    update_project_tool,
    delete_project_tool,
    search_projects_tool,
)

from agents.project_agent.schemas import (
    CreateProjectInput,
    UpdateProjectInput,
    GetProjectInput,
    ListProjectsInput,
    DeleteProjectInput,
    SearchProjectsInput,
)


def make_project_tools(user_id: str):
    """Return 6 LangChain tools bound to the given user_id via closures."""

    @tool(args_schema=CreateProjectInput)
    async def create_project(name: str, **kwargs) -> dict:
        """Create a new project or goal (work, side_project, learning, health, financial, travel, creative, career). Extract all available context: project_type, status (idea/planned/in_progress/paused/completed/abandoned), description, goal, target_date, priority (0-1), tags, notes. Always search_projects first to avoid duplicates. Returns: {success, message, project: {id, name, project_type, status, ...}}"""
        return await create_project_tool(user_id, name=name, **kwargs)

    @tool(args_schema=SearchProjectsInput)
    async def search_projects(search_term: str) -> dict:
        """Semantic search for projects by name, description, or goal. Uses vector embeddings with fallback to exact match. Always call before create_project to check for existing projects. Returns: {success, count, search_type: 'semantic'|'exact', projects: [{id, name, similarity_score, ...}]}"""
        return await search_projects_tool(user_id, search_term)

    @tool(args_schema=GetProjectInput)
    async def get_project(project_id: str) -> dict:
        """Fetch full details of a project by UUID. Use to verify current state before updating. Returns: {success, project: {id, name, project_type, status, goal, priority, target_date, ...}}"""
        return await get_project_tool(user_id, project_id)

    @tool(args_schema=ListProjectsInput)
    async def list_projects(
        limit: Optional[int] = 50,
        offset: Optional[int] = 0,
        project_type: Optional[str] = None,
        status: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> dict:
        """List all projects with pagination and optional filters. Filter by project_type (work/side_project/learning/health/financial/travel/creative/career), status (idea/planned/in_progress/paused/completed/abandoned), or tags. Returns: {success, count, total, projects: [...]}"""
        return await list_projects_tool(user_id, limit, offset, project_type, status, tags)

    @tool(args_schema=UpdateProjectInput)
    async def update_project(project_id: str, **kwargs) -> dict:
        """Update an existing project's fields by UUID. Only provide fields that need changing. Commonly used to change status (planned->in_progress->completed), adjust priority, update target_date, or add notes. Returns: {success, message, project: {id, name, ...}}"""
        return await update_project_tool(user_id, project_id=project_id, **kwargs)

    @tool(args_schema=DeleteProjectInput)
    async def delete_project(project_id: str) -> dict:
        """Permanently delete a project by UUID. Only call when the user explicitly asks to remove a project. Returns: {success, message, deleted_id}"""
        return await delete_project_tool(user_id, project_id)

    return [
        create_project,
        search_projects,
        get_project,
        list_projects,
        update_project,
        delete_project,
    ]
