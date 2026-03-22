"""
Pydantic schemas for request/response validation.
"""

from datetime import datetime
from enum import Enum
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict, field_serializer


class UserResponse(BaseModel):
    """Schema for user response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: str | UUID
    phone: str
    name: str | None = None
    created_at: datetime

    @field_serializer('id', when_used='json')
    def serialize_id(self, value):
        return str(value)


class RegisterRequest(BaseModel):
    """Schema for user registration."""
    phone: str = Field(..., min_length=10, max_length=15)
    password: str = Field(..., min_length=6)
    name: str | None = Field(default=None, max_length=100)


class LoginRequest(BaseModel):
    """Schema for login."""
    phone: str
    password: str


class LoginResponse(BaseModel):
    """Schema for login response (tokens are set via httpOnly cookies)."""
    token_type: str = "bearer"
    expires_in: int = 3600  # seconds until access token expires
    user: UserResponse


class RefreshResponse(BaseModel):
    """Schema for token refresh response."""
    token_type: str = "bearer"
    expires_in: int = 3600


class MessageResponse(BaseModel):
    """Schema for chat message response."""
    model_config = ConfigDict(from_attributes=True)

    id: str | UUID
    session_id: str | UUID
    role: str
    content: str
    image_url: str | None = None
    trace_json: dict | None = None
    timestamp: datetime

    @field_serializer('id', 'session_id', when_used='json')
    def serialize_ids(self, value):
        return str(value)


class SessionResponse(BaseModel):
    """Schema for chat session response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: str | UUID
    title: str
    created_at: datetime

    @field_serializer('id', when_used='json')
    def serialize_id(self, value):
        return str(value)


class SessionCreate(BaseModel):
    """Schema for creating a new session."""
    title: str = "New Chat"


class ChatRequest(BaseModel):
    """Schema for chat request."""
    session_id: str | UUID
    message: str
    image_url: str | None = None


# ---------------------------------------------------------------------------
# Agent tracing schemas
# ---------------------------------------------------------------------------
class ToolCallTrace(BaseModel):
    """Single tool invocation within an agent span."""
    tool_name: str
    args: dict = {}
    result: dict | list | str | None = None
    error: str | None = None
    duration_ms: float = 0.0


class AgentSpanTrace(BaseModel):
    """One agent's execution span, with its tool calls and child agent spans."""
    agent_name: str
    tool_calls: list[ToolCallTrace] = []
    child_spans: list["AgentSpanTrace"] = []
    duration_ms: float = 0.0


class RequestTraceResponse(BaseModel):
    """Full request trace returned alongside the chat response."""
    trace_id: str
    duration_ms: float = 0.0
    agent_spans: list[AgentSpanTrace] = []


class ChatResponse(BaseModel):
    """Schema for chat response."""
    session_id: str | UUID
    user_message: MessageResponse
    assistant_message: MessageResponse
    trace: RequestTraceResponse | None = None

    @field_serializer('session_id', when_used='json')
    def serialize_session_id(self, value):
        return str(value)

class RelationshipTypeEnum(str, Enum):
    """Allowed relationship types between persons."""
    KNOWS = "KNOWS"
    FRIEND = "FRIEND"
    FAMILY = "FAMILY"
    COLLEAGUE = "COLLEAGUE"
    WORKS_WITH = "WORKS_WITH"
    MANAGES = "MANAGES"
    REPORTS_TO = "REPORTS_TO"
    MENTOR = "MENTOR"
    PARTNER = "PARTNER"
    NEIGHBOR = "NEIGHBOR"
    CLASSMATE = "CLASSMATE"
    EMPLOYS = "EMPLOYS"
    MARRIED_TO = "MARRIED_TO"
    PARENT_OF = "PARENT_OF"
    INTRODUCED_BY = "INTRODUCED_BY"
    RIVAL_OF = "RIVAL_OF"
    FORMERLY_WORKED_WITH = "FORMERLY_WORKED_WITH"


class PersonIdentityBase(BaseModel):
    """Base schema for person identity."""
    name: str = Field(..., max_length=200)
    aliases: list[str] = []
    contacts: dict = {}
    short_bio: str | None = None
    trust_score: float = Field(default=0.0, ge=0.0, le=1.0)

    # Identity
    date_of_birth: str | None = Field(default=None, max_length=20)
    gender: str | None = Field(default=None, max_length=50)
    nationality: str | None = Field(default=None, max_length=100)
    languages: list[str] = []

    # Professional
    occupation: str | None = Field(default=None, max_length=200)
    company: str | None = Field(default=None, max_length=200)
    location: str | None = Field(default=None, max_length=200)

    # Personal context
    met_through: str | None = Field(default=None, max_length=200)
    met_date: str | None = Field(default=None, max_length=20)
    interaction_frequency: Literal["daily", "weekly", "monthly", "quarterly", "yearly", "rarely", None] = None
    emotional_closeness: float | None = Field(default=None, ge=0.0, le=1.0)
    reliability_score: float | None = Field(default=None, ge=0.0, le=1.0)
    last_interaction_summary: str | None = Field(default=None, max_length=500)
    pending_actions: list[str] = []

    # Personality
    interests: list[str] = []
    personality_traits: list[str] = []
    communication_style: str | None = Field(default=None, max_length=200)

    # Social
    social_media: dict = {}
    important_dates: dict = {}

    # Organization
    notes: str | None = None
    tags: list[str] = []

    # Public profile
    person_scope: Literal["private", "public", "both", None] = None
    public_role: str | None = Field(default=None, max_length=200)
    known_for: list[str] = []
    public_bio: str | None = None


class PersonIdentityCreate(PersonIdentityBase):
    """Schema for creating a person identity."""
    pass


class PersonIdentityUpdate(BaseModel):
    """Schema for updating a person identity."""
    name: str | None = Field(default=None, max_length=200)
    aliases: list[str] | None = None
    contacts: dict | None = None
    short_bio: str | None = None
    trust_score: float | None = Field(default=None, ge=0.0, le=1.0)

    # Identity
    date_of_birth: str | None = Field(default=None, max_length=20)
    gender: str | None = Field(default=None, max_length=50)
    nationality: str | None = Field(default=None, max_length=100)
    languages: list[str] | None = None

    # Professional
    occupation: str | None = Field(default=None, max_length=200)
    company: str | None = Field(default=None, max_length=200)
    location: str | None = Field(default=None, max_length=200)

    # Personal context
    met_through: str | None = Field(default=None, max_length=200)
    met_date: str | None = Field(default=None, max_length=20)
    interaction_frequency: Literal["daily", "weekly", "monthly", "quarterly", "yearly", "rarely", None] = None
    emotional_closeness: float | None = Field(default=None, ge=0.0, le=1.0)
    reliability_score: float | None = Field(default=None, ge=0.0, le=1.0)
    last_interaction_summary: str | None = Field(default=None, max_length=500)
    pending_actions: list[str] | None = None

    # Personality
    interests: list[str] | None = None
    personality_traits: list[str] | None = None
    communication_style: str | None = Field(default=None, max_length=200)

    # Social
    social_media: dict | None = None
    important_dates: dict | None = None

    # Organization
    notes: str | None = None
    tags: list[str] | None = None

    # Public profile
    person_scope: Literal["private", "public", "both", None] = None
    public_role: str | None = Field(default=None, max_length=200)
    known_for: list[str] | None = None
    public_bio: str | None = None


class PersonIdentityResponse(PersonIdentityBase):
    """Schema for person identity response."""
    model_config = ConfigDict(from_attributes=True)

    id: str | UUID
    user_id: str | UUID
    first_seen: datetime
    last_seen: datetime
    face_image_url: str | None = None

    @field_serializer('id', 'user_id', when_used='json')
    def serialize_ids(self, value):
        return str(value)


class PaginatedPersonsResponse(BaseModel):
    """Paginated list of persons."""
    items: list[dict] = []
    total: int = 0
    offset: int = 0
    limit: int = 50


class RelationshipCreate(BaseModel):
    """Schema for creating a relationship."""
    from_person_id: str
    to_person_id: str
    rel_type: str
    strength: float | None = Field(default=None, ge=0.0, le=1.0)
    context: str | None = Field(default=None, max_length=500)
    started_at: str | None = None
    ended_at: str | None = None
    notes: str | None = None


class RelationshipUpdate(BaseModel):
    """Schema for updating relationship properties."""
    strength: float | None = Field(default=None, ge=0.0, le=1.0)
    context: str | None = Field(default=None, max_length=500)
    started_at: str | None = None
    ended_at: str | None = None
    notes: str | None = None


class RelationshipResponse(BaseModel):
    """Schema for relationship response."""
    relationship: str
    properties: dict = {}
    person_id: str
    person_name: str
    direction: str


class SemanticSearchRequest(BaseModel):
    """Schema for semantic search."""
    query: str = Field(..., min_length=1, description="Natural language search query")
    limit: int = Field(default=5, ge=1, le=20, description="Max results to return")


class FaceIdentifyResult(BaseModel):
    """Single result from face identification — person data + confidence score."""
    id: str
    name: str
    short_bio: str | None = None
    confidence_score: float  # 0.0 to 1.0, higher = better match


# ---------------------------------------------------------------------------
# Standardized error response
# ---------------------------------------------------------------------------
class ErrorDetail(BaseModel):
    """Inner error object."""
    code: str
    message: str


class ErrorResponse(BaseModel):
    """Standardized error envelope returned by all endpoints."""
    error: ErrorDetail


# ---------------------------------------------------------------------------
# Cross-entity relationship types
# ---------------------------------------------------------------------------
class CrossEntityRelTypeEnum(str, Enum):
    """Allowed relationship types between different entity types."""
    THINKS = "THINKS"
    SHARED_BY = "SHARED_BY"
    AUTHORED = "AUTHORED"
    RECOMMENDED = "RECOMMENDED"
    CONSUMED_WITH = "CONSUMED_WITH"
    WORKS_ON = "WORKS_ON"
    COLLABORATES_ON = "COLLABORATES_ON"
    INSPIRED_BY = "INSPIRED_BY"
    APPLIED_IN = "APPLIED_IN"
    REFERENCE_FOR = "REFERENCE_FOR"


# ---------------------------------------------------------------------------
# Idea schemas
# ---------------------------------------------------------------------------
class IdeaBase(BaseModel):
    """Base schema for idea entity."""
    name: str = Field(..., max_length=300)
    idea_type: Literal[
        "prediction", "opinion", "decision", "question",
        "realization", "hypothesis", "lesson_learned", None
    ] = None
    description: str | None = None
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    status: Literal["active", "validated", "invalidated", "evolved", "abandoned"] = "active"
    evidence_for: list[str] = []
    evidence_against: list[str] = []
    date_formed: str | None = None
    revisit_date: str | None = None
    tags: list[str] = []
    notes: str | None = None


class IdeaCreate(IdeaBase):
    """Schema for creating an idea."""
    pass


class IdeaUpdate(BaseModel):
    """Schema for updating an idea."""
    name: str | None = Field(default=None, max_length=300)
    idea_type: Literal[
        "prediction", "opinion", "decision", "question",
        "realization", "hypothesis", "lesson_learned", None
    ] = None
    description: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    status: Literal["active", "validated", "invalidated", "evolved", "abandoned", None] = None
    evidence_for: list[str] | None = None
    evidence_against: list[str] | None = None
    date_formed: str | None = None
    revisit_date: str | None = None
    tags: list[str] | None = None
    notes: str | None = None


class IdeaResponse(IdeaBase):
    """Schema for idea response."""
    model_config = ConfigDict(from_attributes=True)

    id: str | UUID
    user_id: str | UUID
    first_seen: datetime
    last_seen: datetime

    @field_serializer('id', 'user_id', when_used='json')
    def serialize_ids(self, value):
        return str(value)


class PaginatedIdeasResponse(BaseModel):
    """Paginated list of ideas."""
    items: list[dict] = []
    total: int = 0
    offset: int = 0
    limit: int = 50


# ---------------------------------------------------------------------------
# Content schemas
# ---------------------------------------------------------------------------
class ContentBase(BaseModel):
    """Base schema for content entity."""
    title: str = Field(..., max_length=500)
    content_type: Literal[
        "book", "article", "video", "podcast", "paper",
        "course", "movie", "tweet", "talk", None
    ] = None
    author: str | None = None
    source_url: str | None = None
    status: Literal["want", "reading", "completed", "abandoned", None] = None
    your_rating: float | None = Field(default=None, ge=0.0, le=1.0)
    personal_notes: str | None = None
    recommended_by: str | None = None
    tags: list[str] = []


class ContentCreate(ContentBase):
    """Schema for creating content."""
    pass


class ContentUpdate(BaseModel):
    """Schema for updating content."""
    title: str | None = Field(default=None, max_length=500)
    content_type: Literal[
        "book", "article", "video", "podcast", "paper",
        "course", "movie", "tweet", "talk", None
    ] = None
    author: str | None = None
    source_url: str | None = None
    status: Literal["want", "reading", "completed", "abandoned", None] = None
    your_rating: float | None = Field(default=None, ge=0.0, le=1.0)
    personal_notes: str | None = None
    recommended_by: str | None = None
    tags: list[str] | None = None


class ContentResponse(ContentBase):
    """Schema for content response."""
    model_config = ConfigDict(from_attributes=True)

    id: str | UUID
    user_id: str | UUID
    first_seen: datetime
    last_seen: datetime

    @field_serializer('id', 'user_id', when_used='json')
    def serialize_ids(self, value):
        return str(value)


class PaginatedContentResponse(BaseModel):
    """Paginated list of content."""
    items: list[dict] = []
    total: int = 0
    offset: int = 0
    limit: int = 50


# ---------------------------------------------------------------------------
# Project schemas
# ---------------------------------------------------------------------------
class ProjectBase(BaseModel):
    """Base schema for project entity."""
    name: str = Field(..., max_length=300)
    project_type: Literal[
        "work", "side_project", "learning", "health",
        "financial", "travel", "creative", "career", None
    ] = None
    status: Literal[
        "idea", "planned", "in_progress", "paused",
        "completed", "abandoned", None
    ] = None
    description: str | None = None
    goal: str | None = None
    target_date: str | None = None
    priority: float = Field(default=0.5, ge=0.0, le=1.0)
    tags: list[str] = []
    notes: str | None = None


class ProjectCreate(ProjectBase):
    """Schema for creating a project."""
    pass


class ProjectUpdate(BaseModel):
    """Schema for updating a project."""
    name: str | None = Field(default=None, max_length=300)
    project_type: Literal[
        "work", "side_project", "learning", "health",
        "financial", "travel", "creative", "career", None
    ] = None
    status: Literal[
        "idea", "planned", "in_progress", "paused",
        "completed", "abandoned", None
    ] = None
    description: str | None = None
    goal: str | None = None
    target_date: str | None = None
    priority: float | None = Field(default=None, ge=0.0, le=1.0)
    tags: list[str] | None = None
    notes: str | None = None


class ProjectResponse(ProjectBase):
    """Schema for project response."""
    model_config = ConfigDict(from_attributes=True)

    id: str | UUID
    user_id: str | UUID
    first_seen: datetime
    last_seen: datetime

    @field_serializer('id', 'user_id', when_used='json')
    def serialize_ids(self, value):
        return str(value)


class PaginatedProjectsResponse(BaseModel):
    """Paginated list of projects."""
    items: list[dict] = []
    total: int = 0
    offset: int = 0
    limit: int = 50


# ---------------------------------------------------------------------------
# Cross-entity link
# ---------------------------------------------------------------------------
class CrossEntityLinkCreate(BaseModel):
    """Schema for creating a cross-entity relationship."""
    from_type: Literal["Person", "Idea", "Content", "Project"]
    from_id: str
    to_type: Literal["Person", "Idea", "Content", "Project"]
    to_id: str
    rel_type: str
    properties: dict = {}