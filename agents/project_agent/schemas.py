"""
Pydantic input schemas for project-related LangChain tools.
Extracted from backend/app/agent.py — only project schemas.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class CreateProjectInput(BaseModel):
    name: str = Field(..., description="Project name")
    project_type: Optional[str] = Field(default=None, description="Type: work, side_project, learning, health, financial, travel, creative, career")
    status: Optional[str] = Field(default=None, description="Status: idea, planned, in_progress, paused, completed, abandoned")
    description: Optional[str] = Field(default=None, description="Description")
    goal: Optional[str] = Field(default=None, description="Goal")
    target_date: Optional[str] = Field(default=None, description="Target completion date")
    priority: Optional[float] = Field(default=None, description="Priority (0-1)")
    tags: Optional[List[str]] = Field(default=None, description="Tags")
    notes: Optional[str] = Field(default=None, description="Notes")


class UpdateProjectInput(BaseModel):
    project_id: str = Field(..., description="UUID of the project to update")
    name: Optional[str] = Field(default=None, description="New name")
    project_type: Optional[str] = Field(default=None, description="New type")
    status: Optional[str] = Field(default=None, description="New status")
    description: Optional[str] = Field(default=None, description="New description")
    goal: Optional[str] = Field(default=None, description="New goal")
    target_date: Optional[str] = Field(default=None, description="New target date")
    priority: Optional[float] = Field(default=None, description="New priority (0-1)")
    tags: Optional[List[str]] = Field(default=None, description="Tags")
    notes: Optional[str] = Field(default=None, description="Notes")


class GetProjectInput(BaseModel):
    project_id: str = Field(..., description="UUID of the project")


class ListProjectsInput(BaseModel):
    limit: Optional[int] = Field(default=50, description="Max results")
    offset: Optional[int] = Field(default=0, description="Skip count")
    project_type: Optional[str] = Field(default=None, description="Filter by type")
    status: Optional[str] = Field(default=None, description="Filter by status")
    tags: Optional[List[str]] = Field(default=None, description="Filter by tags")


class DeleteProjectInput(BaseModel):
    project_id: str = Field(..., description="UUID of the project to delete")


class SearchProjectsInput(BaseModel):
    search_term: str = Field(..., description="Search term for projects")
