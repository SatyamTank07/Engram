"""
Pydantic input schemas for idea-related LangChain tools.
Extracted from backend/app/agent.py — only idea schemas.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class CreateIdeaInput(BaseModel):
    name: str = Field(..., description="Name/title of the idea")
    idea_type: Optional[str] = Field(default=None, description="Type: prediction, opinion, decision, question, realization, hypothesis, lesson_learned")
    description: Optional[str] = Field(default=None, description="Detailed description of the idea")
    confidence: Optional[float] = Field(default=None, description="Confidence level (0.0 to 1.0)")
    status: Optional[str] = Field(default=None, description="Status: active, validated, invalidated, evolved, abandoned")
    evidence_for: Optional[List[str]] = Field(default=None, description="Evidence supporting this idea")
    evidence_against: Optional[List[str]] = Field(default=None, description="Evidence against this idea")
    date_formed: Optional[str] = Field(default=None, description="When the idea was formed")
    revisit_date: Optional[str] = Field(default=None, description="When to revisit this idea")
    tags: Optional[List[str]] = Field(default=None, description="Tags for categorization")
    notes: Optional[str] = Field(default=None, description="Additional notes")


class UpdateIdeaInput(BaseModel):
    idea_id: str = Field(..., description="UUID of the idea to update")
    name: Optional[str] = Field(default=None, description="New name")
    idea_type: Optional[str] = Field(default=None, description="New type")
    description: Optional[str] = Field(default=None, description="New description")
    confidence: Optional[float] = Field(default=None, description="New confidence (0-1)")
    status: Optional[str] = Field(default=None, description="New status")
    evidence_for: Optional[List[str]] = Field(default=None, description="Updated evidence for")
    evidence_against: Optional[List[str]] = Field(default=None, description="Updated evidence against")
    date_formed: Optional[str] = Field(default=None, description="When formed")
    revisit_date: Optional[str] = Field(default=None, description="When to revisit")
    tags: Optional[List[str]] = Field(default=None, description="Tags")
    notes: Optional[str] = Field(default=None, description="Notes")


class GetIdeaInput(BaseModel):
    idea_id: str = Field(..., description="UUID of the idea")


class ListIdeasInput(BaseModel):
    limit: Optional[int] = Field(default=50, description="Max results")
    offset: Optional[int] = Field(default=0, description="Skip count")
    idea_type: Optional[str] = Field(default=None, description="Filter by type")
    status: Optional[str] = Field(default=None, description="Filter by status")
    tags: Optional[List[str]] = Field(default=None, description="Filter by tags")


class DeleteIdeaInput(BaseModel):
    idea_id: str = Field(..., description="UUID of the idea to delete")


class SearchIdeasInput(BaseModel):
    search_term: str = Field(..., description="Search term for ideas")
