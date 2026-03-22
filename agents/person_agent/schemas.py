"""
Pydantic input schemas for person-related LangChain tools.
Extracted from backend/app/agent.py — only person schemas.
"""

from typing import List, Literal, Optional, Dict, Any
from pydantic import BaseModel, Field


class CreatePersonInput(BaseModel):
    name: str = Field(..., description="Full canonical name of the person")
    aliases: List[str] = Field(default=[], description="List of alternative names, nicknames, or previous names")
    contacts: Dict[str, Any] = Field(default={}, description="Dictionary containing contact information (phone, email, etc.)")
    short_bio: str = Field(default="", description="Brief biography, description, or notes")
    trust_score: float = Field(default=0.0, description="Confidence level (0.0 to 1.0)")
    date_of_birth: Optional[str] = Field(default=None, description="Date of birth")
    gender: Optional[str] = Field(default=None, description="Gender")
    nationality: Optional[str] = Field(default=None, description="Nationality or country of origin")
    languages: List[str] = Field(default=[], description="Languages spoken")
    occupation: Optional[str] = Field(default=None, description="Job title or occupation")
    company: Optional[str] = Field(default=None, description="Company or organization")
    location: Optional[str] = Field(default=None, description="City, state, or country")
    met_through: Optional[str] = Field(default=None, description="How/where you met this person")
    met_date: Optional[str] = Field(default=None, description="When you first met")
    interaction_frequency: Optional[str] = Field(default=None, description="How often you interact: daily, weekly, monthly, quarterly, yearly, rarely")
    emotional_closeness: Optional[float] = Field(default=None, description="Emotional closeness (0.0 to 1.0)")
    reliability_score: Optional[float] = Field(default=None, description="How reliable this person is (0.0 to 1.0)")
    interests: List[str] = Field(default=[], description="Hobbies and interests")
    personality_traits: List[str] = Field(default=[], description="Key personality traits")
    communication_style: Optional[str] = Field(default=None, description="Preferred communication style")
    social_media: Dict[str, Any] = Field(default={}, description="Social media handles e.g. {'twitter': '@handle'}")
    important_dates: Dict[str, Any] = Field(default={}, description="Important dates e.g. {'birthday': 'March 5'}")
    notes: Optional[str] = Field(default=None, description="Free-form notes")
    tags: List[str] = Field(default=[], description="Tags for categorization e.g. ['work', 'college']")
    person_scope: Optional[str] = Field(default=None, description="Visibility scope: private, public, or both")
    public_role: Optional[str] = Field(default=None, description="Public role or title")
    known_for: List[str] = Field(default=[], description="What this person is known for")
    public_bio: Optional[str] = Field(default=None, description="Public-facing biography")
    # Optional relationship — include when user mentions a connection
    relationship_with: Optional[str] = Field(default=None, description="Name of the other person in the relationship (e.g. the user's name, or another person's name)")
    relationship_type: Optional[str] = Field(default=None, description="Type of relationship: FRIEND, FAMILY, COLLEAGUE, MANAGES, REPORTS_TO, MENTOR, KNOWS, etc.")
    relationship_direction: Optional[str] = Field(default=None, description="Direction of the relationship: 'created_to_other' (the person being created does the action) or 'other_to_created' (the other person does the action). Example: 'Rahul manages Priya' when creating Priya → direction='other_to_created'")
    relationship_notes: Optional[str] = Field(default=None, description="Optional context about the relationship")
    relationship_strength: Optional[float] = Field(default=None, description="Relationship strength (0.0 to 1.0)")


class UpdatePersonInput(BaseModel):
    person_id: str = Field(..., description="UUID of the person to update")
    name: Optional[str] = Field(default=None, description="New canonical name")
    aliases: Optional[List[str]] = Field(default=None, description="New list of aliases")
    contacts: Optional[Dict[str, Any]] = Field(default=None, description="New contact information")
    short_bio: Optional[str] = Field(default=None, description="New biography or notes")
    trust_score: Optional[float] = Field(default=None, description="New confidence score")
    date_of_birth: Optional[str] = Field(default=None, description="Date of birth")
    gender: Optional[str] = Field(default=None, description="Gender")
    nationality: Optional[str] = Field(default=None, description="Nationality")
    languages: Optional[List[str]] = Field(default=None, description="Languages spoken")
    occupation: Optional[str] = Field(default=None, description="Job title or occupation")
    company: Optional[str] = Field(default=None, description="Company or organization")
    location: Optional[str] = Field(default=None, description="City, state, or country")
    met_through: Optional[str] = Field(default=None, description="How/where you met this person")
    met_date: Optional[str] = Field(default=None, description="When you first met")
    interaction_frequency: Optional[str] = Field(default=None, description="How often you interact")
    emotional_closeness: Optional[float] = Field(default=None, description="Emotional closeness (0-1)")
    reliability_score: Optional[float] = Field(default=None, description="Reliability (0-1)")
    last_interaction_summary: Optional[str] = Field(default=None, description="Summary of last interaction")
    pending_actions: Optional[List[str]] = Field(default=None, description="Pending action items")
    interests: Optional[List[str]] = Field(default=None, description="Hobbies and interests")
    personality_traits: Optional[List[str]] = Field(default=None, description="Key personality traits")
    communication_style: Optional[str] = Field(default=None, description="Communication style")
    social_media: Optional[Dict[str, Any]] = Field(default=None, description="Social media handles")
    important_dates: Optional[Dict[str, Any]] = Field(default=None, description="Important dates")
    notes: Optional[str] = Field(default=None, description="Free-form notes")
    tags: Optional[List[str]] = Field(default=None, description="Tags for categorization")
    person_scope: Optional[str] = Field(default=None, description="Visibility scope")
    public_role: Optional[str] = Field(default=None, description="Public role or title")
    known_for: Optional[List[str]] = Field(default=None, description="Known for")
    public_bio: Optional[str] = Field(default=None, description="Public biography")
    # Optional relationship — include when user mentions a connection
    relationship_with: Optional[str] = Field(default=None, description="Name of the other person in the relationship")
    relationship_type: Optional[str] = Field(default=None, description="Type of relationship: FRIEND, FAMILY, COLLEAGUE, MANAGES, REPORTS_TO, MENTOR, KNOWS, etc.")
    relationship_direction: Optional[str] = Field(default=None, description="Direction of the relationship: 'updated_to_other' (the person being updated does the action) or 'other_to_updated' (the other person does the action)")
    relationship_notes: Optional[str] = Field(default=None, description="Optional context about the relationship")
    relationship_strength: Optional[float] = Field(default=None, description="Relationship strength (0.0 to 1.0)")


class GetPersonInput(BaseModel):
    person_id: str = Field(..., description="UUID of the person to retrieve")


class ListPersonsInput(BaseModel):
    limit: Optional[int] = Field(default=50, description="Maximum number of persons to return")
    offset: Optional[int] = Field(default=0, description="Number of results to skip for pagination")
    tags: Optional[List[str]] = Field(default=None, description="Filter by tags")
    location: Optional[str] = Field(default=None, description="Filter by location")
    occupation: Optional[str] = Field(default=None, description="Filter by occupation")
    company: Optional[str] = Field(default=None, description="Filter by company")
    interaction_frequency: Optional[str] = Field(default=None, description="Filter by interaction frequency")


class DeletePersonInput(BaseModel):
    person_id: str = Field(..., description="UUID of the person to delete")


class SearchPersonInput(BaseModel):
    search_term: str = Field(..., description="Name or partial name to search for")


class ManageRelationshipInput(BaseModel):
    action: Literal["add", "update", "delete"] = Field(..., description="Action to perform: 'add', 'update', or 'delete'")
    from_person_name: str = Field(..., description="Name of the first person")
    to_person_name: str = Field(..., description="Name of the second person")
    relationship_type: str = Field(..., description="Type: KNOWS, FRIEND, FAMILY, COLLEAGUE, WORKS_WITH, MANAGES, REPORTS_TO, MENTOR, PARTNER, NEIGHBOR, CLASSMATE, EMPLOYS, MARRIED_TO, PARENT_OF, INTRODUCED_BY, RIVAL_OF, FORMERLY_WORKED_WITH")
    notes: Optional[str] = Field(default=None, description="Notes about the relationship")
    strength: Optional[float] = Field(default=None, description="Relationship strength (0.0 to 1.0)")
    context: Optional[str] = Field(default=None, description="Context of the relationship")
    started_at: Optional[str] = Field(default=None, description="When the relationship started (update only)")
    ended_at: Optional[str] = Field(default=None, description="When the relationship ended (update only)")


class HandleFaceInput(BaseModel):
    action: Literal["identify", "store"] = Field(..., description="Action: 'identify' (detect+match faces) or 'store' (link face to person)")
    image_url: str = Field(..., description="URL path of the uploaded image (e.g. /uploads/chat/uuid.jpg)")
    person_id: Optional[str] = Field(default=None, description="UUID of the person to link face to (required for 'store' action)")
