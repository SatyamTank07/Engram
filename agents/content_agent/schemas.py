"""
Pydantic input schemas for content-related LangChain tools.
Extracted from backend/app/agent.py — only content schemas.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class CreateContentInput(BaseModel):
    title: str = Field(..., description="Title of the content")
    content_type: Optional[str] = Field(default=None, description="Type: book, article, video, podcast, paper, course, movie, tweet, talk")
    author: Optional[str] = Field(default=None, description="Author/creator")
    source_url: Optional[str] = Field(default=None, description="URL source")
    status: Optional[str] = Field(default=None, description="Status: want, reading, completed, abandoned")
    your_rating: Optional[float] = Field(default=None, description="Your rating (0-1)")
    personal_notes: Optional[str] = Field(default=None, description="Personal notes")
    recommended_by: Optional[str] = Field(default=None, description="Who recommended it")
    tags: Optional[List[str]] = Field(default=None, description="Tags")


class UpdateContentInput(BaseModel):
    content_id: str = Field(..., description="UUID of the content to update")
    title: Optional[str] = Field(default=None, description="New title")
    content_type: Optional[str] = Field(default=None, description="New type")
    author: Optional[str] = Field(default=None, description="New author")
    source_url: Optional[str] = Field(default=None, description="New URL")
    status: Optional[str] = Field(default=None, description="New status")
    your_rating: Optional[float] = Field(default=None, description="New rating (0-1)")
    personal_notes: Optional[str] = Field(default=None, description="New notes")
    recommended_by: Optional[str] = Field(default=None, description="New recommender")
    tags: Optional[List[str]] = Field(default=None, description="Tags")


class GetContentInput(BaseModel):
    content_id: str = Field(..., description="UUID of the content")


class ListContentInput(BaseModel):
    limit: Optional[int] = Field(default=50, description="Max results")
    offset: Optional[int] = Field(default=0, description="Skip count")
    content_type: Optional[str] = Field(default=None, description="Filter by type")
    status: Optional[str] = Field(default=None, description="Filter by status")
    tags: Optional[List[str]] = Field(default=None, description="Filter by tags")


class DeleteContentInput(BaseModel):
    content_id: str = Field(..., description="UUID of the content to delete")


class SearchContentInput(BaseModel):
    search_term: str = Field(..., description="Search term for content")
