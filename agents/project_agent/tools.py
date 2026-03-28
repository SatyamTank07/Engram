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

from backend.app import md_storage

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
        data = {"name": name, **kwargs}
        try:
            result = await md_storage.create_entity(user_id, "project", data)
            return {"success": True, "message": f"Project '{name}' created.", "project": result}
        except Exception as e:
            return {"success": False, "message": f"Error creating project: {e}"}

    @tool(args_schema=SearchProjectsInput)
    async def search_projects(search_term: str) -> dict:
        """Semantic search for projects by name, description, or goal. Uses keyword scoring with fallback to exact match. Always call before create_project to check for existing projects. Returns: {success, count, search_type: 'keyword', projects: [{id, name, ...}]}"""
        try:
            results = await md_storage.search_entities(user_id, "project", search_term)
            return {"success": True, "count": len(results), "search_type": "keyword", "projects": results}
        except Exception as e:
            return {"success": False, "message": f"Error searching projects: {e}"}

    @tool(args_schema=GetProjectInput)
    async def get_project(project_id: str) -> dict:
        """Fetch full details of a project by UUID. Use to verify current state before updating. Returns: {success, project: {id, name, project_type, status, goal, priority, target_date, ...}}"""
        try:
            result = await md_storage.get_entity(user_id, "project", project_id)
            if result is None:
                return {"success": False, "message": f"Project not found: {project_id}"}
            return {"success": True, "project": result}
        except Exception as e:
            return {"success": False, "message": f"Error getting project: {e}"}

    @tool(args_schema=ListProjectsInput)
    async def list_projects(
        limit: Optional[int] = 50,
        offset: Optional[int] = 0,
        project_type: Optional[str] = None,
        status: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> dict:
        """List all projects with pagination and optional filters. Filter by project_type (work/side_project/learning/health/financial/travel/creative/career), status (idea/planned/in_progress/paused/completed/abandoned), or tags. Returns: {success, count, total, projects: [...]}"""
        try:
            filters = {}
            if project_type:
                filters["project_type"] = project_type
            if status:
                filters["status"] = status
            if tags:
                filters["tags"] = tags
            items, total = await md_storage.list_entities(user_id, "project", limit or 50, offset or 0, **filters)
            return {"success": True, "count": len(items), "total": total, "projects": items}
        except Exception as e:
            return {"success": False, "message": f"Error listing projects: {e}"}

    @tool(args_schema=UpdateProjectInput)
    async def update_project(project_id: str, **kwargs) -> dict:
        """Update an existing project's fields by UUID. Only provide fields that need changing. Commonly used to change status (planned->in_progress->completed), adjust priority, update target_date, or add notes. Returns: {success, message, project: {id, name, ...}}"""
        try:
            result = await md_storage.update_entity(user_id, "project", project_id, kwargs)
            if result is None:
                return {"success": False, "message": f"Project not found: {project_id}"}
            return {"success": True, "message": "Project updated.", "project": result}
        except Exception as e:
            return {"success": False, "message": f"Error updating project: {e}"}

    @tool(args_schema=DeleteProjectInput)
    async def delete_project(project_id: str) -> dict:
        """Permanently delete a project by UUID. Only call when the user explicitly asks to remove a project. Returns: {success, message, deleted_id}"""
        try:
            deleted = await md_storage.delete_entity(user_id, "project", project_id)
            if not deleted:
                return {"success": False, "message": f"Project not found: {project_id}"}
            return {"success": True, "message": "Project deleted.", "deleted_id": project_id}
        except Exception as e:
            return {"success": False, "message": f"Error deleting project: {e}"}

    return [
        create_project,
        search_projects,
        get_project,
        list_projects,
        update_project,
        delete_project,
    ]
