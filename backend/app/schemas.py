"""
Pydantic schemas for request/response validation.
"""

from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict, field_serializer


class UserResponse(BaseModel):
    """Schema for user response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: str | UUID
    phone: str
    created_at: datetime

    @field_serializer('id', when_used='json')
    def serialize_id(self, value):
        return str(value)


class RegisterRequest(BaseModel):
    """Schema for user registration."""
    phone: str = Field(..., min_length=10, max_length=15)
    password: str = Field(..., min_length=6)


class LoginRequest(BaseModel):
    """Schema for login."""
    phone: str
    password: str


class LoginResponse(BaseModel):
    """Schema for login response."""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class MessageResponse(BaseModel):
    """Schema for chat message response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: str | UUID
    session_id: str | UUID
    role: str
    content: str
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


class ChatResponse(BaseModel):
    """Schema for chat response."""
    session_id: str | UUID
    user_message: MessageResponse
    assistant_message: MessageResponse

    @field_serializer('session_id', when_used='json')
    def serialize_session_id(self, value):
        return str(value)

class PersonIdentityBase(BaseModel):
    """Base schema for person identity."""
    name: str
    aliases: list[str] = []
    contacts: dict = {}
    short_bio: str | None = None
    trust_score: float = 0.0


class PersonIdentityCreate(PersonIdentityBase):
    """Schema for creating a person identity."""
    pass


class PersonIdentityUpdate(BaseModel):
    """Schema for updating a person identity."""
    name: str | None = None
    aliases: list[str] | None = None
    contacts: dict | None = None
    short_bio: str | None = None
    trust_score: float | None = None


class PersonIdentityResponse(PersonIdentityBase):
    """Schema for person identity response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: str | UUID
    user_id: str | UUID
    first_seen: datetime
    last_seen: datetime

    @field_serializer('id', 'user_id', when_used='json')
    def serialize_ids(self, value):
        return str(value)


class SemanticSearchRequest(BaseModel):
    """Schema for semantic search."""
    query: str = Field(..., min_length=1, description="Natural language search query")
    limit: int = Field(default=5, ge=1, le=20, description="Max results to return")