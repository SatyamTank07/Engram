"""
Shared output schemas (Pydantic models) for structured tool responses.

Every tool in the system returns a dict matching one of these models.
These schemas serve two purposes:
  1. Document the exact shape of tool responses for LLM context
  2. Enable structured output validation when needed
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# =====================================================================
# Base response
# =====================================================================

class ToolResponse(BaseModel):
    """Base response returned by every tool."""
    success: bool = Field(..., description="Whether the operation succeeded")
    message: Optional[str] = Field(default=None, description="Human-readable status or error message")


# =====================================================================
# Entity data models (what gets stored in Neo4j)
# =====================================================================

class PersonData(BaseModel):
    """Full person entity as stored in the knowledge graph."""
    id: str = Field(..., description="UUID of the person")
    user_id: str = Field(..., description="Owner user ID")
    name: str = Field(..., description="Full canonical name")
    aliases: List[str] = Field(default=[], description="Alternative names or nicknames")
    contacts: Dict[str, Any] = Field(default={}, description="Contact info (phone, email, etc.)")
    short_bio: Optional[str] = Field(default=None, description="Brief biography")
    trust_score: Optional[float] = Field(default=None, description="Confidence level 0.0-1.0")
    date_of_birth: Optional[str] = Field(default=None, description="Date of birth")
    gender: Optional[str] = Field(default=None, description="Gender")
    nationality: Optional[str] = Field(default=None, description="Nationality")
    languages: List[str] = Field(default=[], description="Languages spoken")
    occupation: Optional[str] = Field(default=None, description="Job title")
    company: Optional[str] = Field(default=None, description="Company or organization")
    location: Optional[str] = Field(default=None, description="City, state, or country")
    met_through: Optional[str] = Field(default=None, description="How/where you met")
    met_date: Optional[str] = Field(default=None, description="When you first met")
    interaction_frequency: Optional[str] = Field(default=None, description="How often you interact")
    emotional_closeness: Optional[float] = Field(default=None, description="Emotional closeness 0.0-1.0")
    reliability_score: Optional[float] = Field(default=None, description="Reliability 0.0-1.0")
    last_interaction_summary: Optional[str] = Field(default=None, description="Summary of last interaction")
    pending_actions: List[str] = Field(default=[], description="Pending action items")
    interests: List[str] = Field(default=[], description="Hobbies and interests")
    personality_traits: List[str] = Field(default=[], description="Key personality traits")
    communication_style: Optional[str] = Field(default=None, description="Communication style")
    social_media: Dict[str, Any] = Field(default={}, description="Social media handles")
    important_dates: Dict[str, Any] = Field(default={}, description="Important dates")
    notes: Optional[str] = Field(default=None, description="Free-form notes")
    tags: List[str] = Field(default=[], description="Tags for categorization")
    person_scope: Optional[str] = Field(default=None, description="Visibility scope")
    public_role: Optional[str] = Field(default=None, description="Public role or title")
    known_for: List[str] = Field(default=[], description="What this person is known for")
    public_bio: Optional[str] = Field(default=None, description="Public biography")
    face_image_url: Optional[str] = Field(default=None, description="URL to stored face image")
    similarity_score: Optional[float] = Field(default=None, description="Semantic search similarity score (only in search results)")
    created_at: Optional[str] = Field(default=None, description="Creation timestamp")
    updated_at: Optional[str] = Field(default=None, description="Last update timestamp")


class RelationshipData(BaseModel):
    """Relationship edge between two entities."""
    from_id: Optional[str] = Field(default=None, description="Source entity UUID", alias="from")
    to_id: Optional[str] = Field(default=None, description="Target entity UUID", alias="to")
    from_name: Optional[str] = Field(default=None, description="Source entity name")
    to_name: Optional[str] = Field(default=None, description="Target entity name")
    type: Optional[str] = Field(default=None, description="Relationship type (FRIEND, MANAGES, etc.)")
    strength: Optional[float] = Field(default=None, description="Relationship strength 0.0-1.0")
    context: Optional[str] = Field(default=None, description="Context of the relationship")
    notes: Optional[str] = Field(default=None, description="Notes about the relationship")
    started_at: Optional[str] = Field(default=None, description="When the relationship started")
    ended_at: Optional[str] = Field(default=None, description="When the relationship ended")

    class Config:
        populate_by_name = True


class IdeaData(BaseModel):
    """Full idea entity as stored in the knowledge graph."""
    id: str = Field(..., description="UUID of the idea")
    user_id: str = Field(..., description="Owner user ID")
    name: str = Field(..., description="Name/title of the idea")
    idea_type: Optional[str] = Field(default=None, description="Type: prediction, opinion, decision, question, realization, hypothesis, lesson_learned")
    description: Optional[str] = Field(default=None, description="Detailed description")
    confidence: Optional[float] = Field(default=None, description="Confidence level 0.0-1.0")
    status: Optional[str] = Field(default=None, description="Status: active, validated, invalidated, evolved, abandoned")
    evidence_for: List[str] = Field(default=[], description="Supporting evidence")
    evidence_against: List[str] = Field(default=[], description="Opposing evidence")
    date_formed: Optional[str] = Field(default=None, description="When formed")
    revisit_date: Optional[str] = Field(default=None, description="When to revisit")
    tags: List[str] = Field(default=[], description="Tags")
    notes: Optional[str] = Field(default=None, description="Additional notes")
    similarity_score: Optional[float] = Field(default=None, description="Semantic search similarity (only in search results)")
    created_at: Optional[str] = Field(default=None, description="Creation timestamp")
    updated_at: Optional[str] = Field(default=None, description="Last update timestamp")


class ContentData(BaseModel):
    """Full content entity as stored in the knowledge graph."""
    id: str = Field(..., description="UUID of the content")
    user_id: str = Field(..., description="Owner user ID")
    title: str = Field(..., description="Title of the content")
    content_type: Optional[str] = Field(default=None, description="Type: book, article, video, podcast, paper, course, movie, tweet, talk")
    author: Optional[str] = Field(default=None, description="Author/creator")
    source_url: Optional[str] = Field(default=None, description="URL source")
    status: Optional[str] = Field(default=None, description="Status: want, reading, completed, abandoned")
    your_rating: Optional[float] = Field(default=None, description="Rating 0.0-1.0")
    personal_notes: Optional[str] = Field(default=None, description="Personal notes")
    recommended_by: Optional[str] = Field(default=None, description="Who recommended it")
    tags: List[str] = Field(default=[], description="Tags")
    similarity_score: Optional[float] = Field(default=None, description="Semantic search similarity (only in search results)")
    created_at: Optional[str] = Field(default=None, description="Creation timestamp")
    updated_at: Optional[str] = Field(default=None, description="Last update timestamp")


class ProjectData(BaseModel):
    """Full project entity as stored in the knowledge graph."""
    id: str = Field(..., description="UUID of the project")
    user_id: str = Field(..., description="Owner user ID")
    name: str = Field(..., description="Project name")
    project_type: Optional[str] = Field(default=None, description="Type: work, side_project, learning, health, financial, travel, creative, career")
    status: Optional[str] = Field(default=None, description="Status: idea, planned, in_progress, paused, completed, abandoned")
    description: Optional[str] = Field(default=None, description="Description")
    goal: Optional[str] = Field(default=None, description="Goal")
    target_date: Optional[str] = Field(default=None, description="Target completion date")
    priority: Optional[float] = Field(default=None, description="Priority 0.0-1.0")
    tags: List[str] = Field(default=[], description="Tags")
    notes: Optional[str] = Field(default=None, description="Notes")
    similarity_score: Optional[float] = Field(default=None, description="Semantic search similarity (only in search results)")
    created_at: Optional[str] = Field(default=None, description="Creation timestamp")
    updated_at: Optional[str] = Field(default=None, description="Last update timestamp")


# =====================================================================
# Person Agent — Output Schemas
# =====================================================================

class CreatePersonOutput(ToolResponse):
    """Response from create_person tool."""
    person: Optional[PersonData] = Field(default=None, description="The newly created person entity")
    relationship: Optional[Dict[str, Any]] = Field(default=None, description="Relationship result if a relationship was created alongside the person")


class GetPersonOutput(ToolResponse):
    """Response from get_person tool."""
    person: Optional[PersonData] = Field(default=None, description="The requested person entity")
    relationships: Optional[List[RelationshipData]] = Field(default=None, description="All relationships of this person")
    relationship_count: Optional[int] = Field(default=None, description="Number of relationships")


class ListPersonsOutput(ToolResponse):
    """Response from list_persons tool."""
    count: Optional[int] = Field(default=None, description="Number of persons in this page")
    total: Optional[int] = Field(default=None, description="Total number of matching persons")
    persons: Optional[List[PersonData]] = Field(default=None, description="List of person entities")


class UpdatePersonOutput(ToolResponse):
    """Response from update_person tool."""
    person: Optional[PersonData] = Field(default=None, description="The updated person entity")
    relationship: Optional[Dict[str, Any]] = Field(default=None, description="Relationship result if a relationship was created/updated")


class DeletePersonOutput(ToolResponse):
    """Response from delete_person tool."""
    deleted_id: Optional[str] = Field(default=None, description="UUID of the deleted person")


class SearchPersonOutput(ToolResponse):
    """Response from search_person tool."""
    count: Optional[int] = Field(default=None, description="Number of matching persons")
    search_term: Optional[str] = Field(default=None, description="The search term used")
    search_type: Optional[str] = Field(default=None, description="Search method used: 'semantic' or 'exact'")
    persons: Optional[List[PersonData]] = Field(default=None, description="Matching person entities with similarity_score")


class AddRelationshipOutput(ToolResponse):
    """Response from add_relationship tool."""
    relationship: Optional[RelationshipData] = Field(default=None, description="The created relationship")


class GetRelationshipsOutput(ToolResponse):
    """Response from get_relationships tool."""
    person: Optional[str] = Field(default=None, description="Name of the person queried")
    count: Optional[int] = Field(default=None, description="Number of relationships found")
    relationships: Optional[List[RelationshipData]] = Field(default=None, description="List of relationships")


class UpdateRelationshipOutput(ToolResponse):
    """Response from update_relationship tool."""
    relationship: Optional[RelationshipData] = Field(default=None, description="The updated relationship")


class DeleteRelationshipOutput(ToolResponse):
    """Response from delete_relationship tool."""
    pass  # Only success + message


class FaceMatchData(BaseModel):
    """A single face detection result with optional person matches."""
    face_index: int = Field(..., description="Index of the face in the image (0-based)")
    bbox: List[float] = Field(..., description="Bounding box [x1, y1, x2, y2]")
    det_score: float = Field(..., description="Face detection confidence score")
    match_status: str = Field(..., description="'matched' if known person found, 'unknown' otherwise")
    matches: List[Dict[str, Any]] = Field(default=[], description="Matched persons with confidence_score")


class IdentifyFaceOutput(ToolResponse):
    """Response from identify_face tool."""
    faces_detected: Optional[int] = Field(default=None, description="Number of faces detected in the image")
    faces: Optional[List[FaceMatchData]] = Field(default=None, description="Per-face results with bounding boxes and matches")


class StorePersonFaceOutput(ToolResponse):
    """Response from store_person_face tool."""
    face_image_url: Optional[str] = Field(default=None, description="URL path to the stored face image")


class ManageRelationshipOutput(ToolResponse):
    """Response from manage_relationship tool (add/update/delete)."""
    relationship: Optional[RelationshipData] = Field(default=None, description="The relationship (for add/update actions)")


class HandleFaceOutput(ToolResponse):
    """Response from handle_face tool (identify/store)."""
    faces_detected: Optional[int] = Field(default=None, description="Number of faces detected (identify action)")
    faces: Optional[List[FaceMatchData]] = Field(default=None, description="Per-face results (identify action)")
    face_image_url: Optional[str] = Field(default=None, description="Stored face URL (store action)")


# =====================================================================
# Idea Agent — Output Schemas
# =====================================================================

class CreateIdeaOutput(ToolResponse):
    """Response from create_idea tool."""
    idea: Optional[IdeaData] = Field(default=None, description="The newly created idea entity")


class GetIdeaOutput(ToolResponse):
    """Response from get_idea tool."""
    idea: Optional[IdeaData] = Field(default=None, description="The requested idea entity")


class ListIdeasOutput(ToolResponse):
    """Response from list_ideas tool."""
    count: Optional[int] = Field(default=None, description="Number of ideas in this page")
    total: Optional[int] = Field(default=None, description="Total number of matching ideas")
    ideas: Optional[List[IdeaData]] = Field(default=None, description="List of idea entities")


class UpdateIdeaOutput(ToolResponse):
    """Response from update_idea tool."""
    idea: Optional[IdeaData] = Field(default=None, description="The updated idea entity")


class DeleteIdeaOutput(ToolResponse):
    """Response from delete_idea tool."""
    deleted_id: Optional[str] = Field(default=None, description="UUID of the deleted idea")


class SearchIdeasOutput(ToolResponse):
    """Response from search_ideas tool."""
    count: Optional[int] = Field(default=None, description="Number of matching ideas")
    search_type: Optional[str] = Field(default=None, description="Search method: 'semantic' or 'exact'")
    ideas: Optional[List[IdeaData]] = Field(default=None, description="Matching ideas with similarity_score")


# =====================================================================
# Content Agent — Output Schemas
# =====================================================================

class CreateContentOutput(ToolResponse):
    """Response from create_content tool."""
    content: Optional[ContentData] = Field(default=None, description="The newly created content entity")


class GetContentOutput(ToolResponse):
    """Response from get_content tool."""
    content: Optional[ContentData] = Field(default=None, description="The requested content entity")


class ListContentOutput(ToolResponse):
    """Response from list_content tool."""
    count: Optional[int] = Field(default=None, description="Number of content items in this page")
    total: Optional[int] = Field(default=None, description="Total number of matching content items")
    content: Optional[List[ContentData]] = Field(default=None, description="List of content entities")


class UpdateContentOutput(ToolResponse):
    """Response from update_content tool."""
    content: Optional[ContentData] = Field(default=None, description="The updated content entity")


class DeleteContentOutput(ToolResponse):
    """Response from delete_content tool."""
    deleted_id: Optional[str] = Field(default=None, description="UUID of the deleted content")


class SearchContentOutput(ToolResponse):
    """Response from search_content tool."""
    count: Optional[int] = Field(default=None, description="Number of matching content items")
    search_type: Optional[str] = Field(default=None, description="Search method: 'semantic' or 'exact'")
    content: Optional[List[ContentData]] = Field(default=None, description="Matching content with similarity_score")


# =====================================================================
# Project Agent — Output Schemas
# =====================================================================

class CreateProjectOutput(ToolResponse):
    """Response from create_project tool."""
    project: Optional[ProjectData] = Field(default=None, description="The newly created project entity")


class GetProjectOutput(ToolResponse):
    """Response from get_project tool."""
    project: Optional[ProjectData] = Field(default=None, description="The requested project entity")


class ListProjectsOutput(ToolResponse):
    """Response from list_projects tool."""
    count: Optional[int] = Field(default=None, description="Number of projects in this page")
    total: Optional[int] = Field(default=None, description="Total number of matching projects")
    projects: Optional[List[ProjectData]] = Field(default=None, description="List of project entities")


class UpdateProjectOutput(ToolResponse):
    """Response from update_project tool."""
    project: Optional[ProjectData] = Field(default=None, description="The updated project entity")


class DeleteProjectOutput(ToolResponse):
    """Response from delete_project tool."""
    deleted_id: Optional[str] = Field(default=None, description="UUID of the deleted project")


class SearchProjectsOutput(ToolResponse):
    """Response from search_projects tool."""
    count: Optional[int] = Field(default=None, description="Number of matching projects")
    search_type: Optional[str] = Field(default=None, description="Search method: 'semantic' or 'exact'")
    projects: Optional[List[ProjectData]] = Field(default=None, description="Matching projects with similarity_score")


# =====================================================================
# Orchestrator — Output Schemas
# =====================================================================

class LinkEntitiesOutput(ToolResponse):
    """Response from link_entities tool."""
    link: Optional[Dict[str, Any]] = Field(default=None, description="The created cross-entity link with from/to names and type")


class GetEntityGraphOutput(ToolResponse):
    """Response from get_entity_graph tool."""
    entity: Optional[Dict[str, Any]] = Field(default=None, description="The queried entity details")
    connections: Optional[List[Dict[str, Any]]] = Field(default=None, description="All connected entities with relationship types")


# =====================================================================
# Agent-level structured response (final output from each sub-agent)
# =====================================================================

class EntityAffected(BaseModel):
    """An entity that was created, updated, deleted, or found during the operation."""
    id: str = Field(..., description="UUID of the entity")
    name: str = Field(..., description="Display name of the entity")
    action: str = Field(..., description="What happened: created, updated, deleted, or found")


class AgentResponse(BaseModel):
    """Structured response from any sub-agent."""
    message: str = Field(..., description="Natural language response to the user")
    entities_affected: List[EntityAffected] = Field(default=[], description="Entities that were affected by this operation")
    tool_calls_made: List[str] = Field(default=[], description="Names of tools that were called")


class OrchestratorResponse(BaseModel):
    """Structured response from the orchestrator."""
    message: str = Field(..., description="Natural language response to the user")
    agents_invoked: List[str] = Field(default=[], description="Sub-agents that were called (e.g., person_agent, content_agent)")
    entities_linked: List[Dict[str, Any]] = Field(default=[], description="Cross-entity links created")
