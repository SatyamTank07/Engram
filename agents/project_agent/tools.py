"""
LangChain tool factory for the Project sub-agent.

Creates 6 project tools with user_id baked in via closures,
exactly like backend/app/agent.py but scoped to project operations only.
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
        """Create a new project/goal in the knowledge graph."""
        return await create_project_tool(user_id, name=name, **kwargs)

    @tool(args_schema=SearchProjectsInput)
    async def search_projects(search_term: str) -> dict:
        """Search for projects by name or description using semantic search."""
        return await search_projects_tool(user_id, search_term)

    @tool(args_schema=GetProjectInput)
    async def get_project(project_id: str) -> dict:
        """Get details of a specific project by ID."""
        return await get_project_tool(user_id, project_id)

    @tool(args_schema=ListProjectsInput)
    async def list_projects(
        limit: Optional[int] = 50,
        offset: Optional[int] = 0,
        project_type: Optional[str] = None,
        status: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> dict:
        """List all saved projects. Supports filtering by project_type, status, tags."""
        return await list_projects_tool(user_id, limit, offset, project_type, status, tags)

    @tool(args_schema=UpdateProjectInput)
    async def update_project(project_id: str, **kwargs) -> dict:
        """Update an existing project's information."""
        return await update_project_tool(user_id, project_id=project_id, **kwargs)

    @tool(args_schema=DeleteProjectInput)
    async def delete_project(project_id: str) -> dict:
        """Delete a project from the knowledge graph."""
        return await delete_project_tool(user_id, project_id)

    return [
        create_project,
        search_projects,
        get_project,
        list_projects,
        update_project,
        delete_project,
    ]
