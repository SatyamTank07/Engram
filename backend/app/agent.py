"""
LangChain agent logic for chat completions.

When MULTI_AGENT_ENABLED=true, requests are routed through the
in-process orchestrator instead of the local monolithic tool chain.
"""

import logging
import os
import sys
import json
import time
from typing import List, Optional, Dict, Any
from pathlib import Path
from dotenv import load_dotenv

from backend.app.tracing import (
    start_trace, finalize_trace, start_agent_span, end_agent_span, log_tool_call,
)

logger = logging.getLogger(__name__)

# Feature flag — toggle between monolithic and multi-agent pipelines
MULTI_AGENT_ENABLED = os.getenv("MULTI_AGENT_ENABLED", "false").lower() in ("true", "1", "yes")
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool

from pydantic import BaseModel, Field

# Add project root to path to allow importing mcp_server
sys.path.append(str(Path(__file__).parent.parent.parent))

try:
    from mcp_server.tools import (
        create_person_tool,
        get_person_tool,
        list_persons_tool,
        update_person_tool,
        delete_person_tool,
        search_person_tool,
        add_relationship_tool,
        get_relationships_tool,
        store_person_face_tool,
        identify_face_from_url_tool,
        update_relationship_tool,
        delete_relationship_tool,
        # Idea tools
        create_idea_tool,
        get_idea_tool,
        list_ideas_tool,
        update_idea_tool,
        delete_idea_tool,
        search_ideas_tool,
        # Content tools
        create_content_tool,
        get_content_tool,
        list_content_tool,
        update_content_tool,
        delete_content_tool,
        search_content_tool,
        # Project tools
        create_project_tool,
        get_project_tool,
        list_projects_tool,
        update_project_tool,
        delete_project_tool,
        search_projects_tool,
        # Cross-entity tools
        link_entities_tool,
        get_entity_graph_tool,
    )
    MCP_TOOLS_AVAILABLE = True
except ImportError:
    MCP_TOOLS_AVAILABLE = False
    logger.warning("Could not import MCP tools. Chatbot will run without personal identity features.")

# Load environment variables
load_dotenv()

# System prompt for the AI assistant
SYSTEM_PROMPT_TEMPLATE = """You are a sophisticated AI Personal Assistant for {user_name}. Your primary goal is to be helpful, concise, and remarkably organized.

You have access to a Personal Identity Knowledge Graph which allows you to store and retrieve detailed information about people the user mentions (including the user themselves), and to model RELATIONSHIPS between people.

USER IDENTITY:
You are chatting with {user_name}. When they say "I", "me", "my", "mine", they are referring to themselves ({user_name}). Use their name to search, create, or update their own Person node in the graph. The user themselves should also exist as a Person node.

CORE INSTRUCTIONS:
1. **Be Proactive**: If a user mentions a detail about someone (e.g., "My friend John works at Google as a software engineer" or "I live in New York"), check if that person exists using `search_person`. If they do, `update_person` with the new info. If not, `create_person`. If the user says something about themselves (e.g., "I live in New York"), search for {user_name} and update their person entry.
2. **Detect Relationships**: If a user mentions how two people are connected (e.g., "John is my manager", "Alice and Bob are friends"), use `add_relationship` to store the connection. Make sure both people exist first. You can set strength and context on relationships.
3. **Context Retrieval**: Before answering questions about specific people, use `search_person` or `list_persons` to see what you already know. Use `get_relationships` to understand how people are connected.
   - `search_person` uses **semantic search** — you can search by description, not just exact name.
   - Example: searching "developer from Pune" will find people whose bio/location mentions Pune + development.
   - Example: searching "person who works at Google" will find people associated with Google.
4. **Data Integrity**: Use `get_person` to verify details before making updates.
5. **Tool Transparency**: When you use a tool, briefly and naturally mention what you've done (e.g., "I've noted down John's new email for you.").

PERSON FIELDS YOU CAN STORE:
- **Basic**: name, aliases, contacts (dict), short_bio, trust_score (0-1)
- **Identity**: date_of_birth, gender, nationality, languages[]
- **Professional**: occupation, company, location
- **Personal Context**: met_through, met_date, interaction_frequency (daily/weekly/monthly/quarterly/yearly/rarely), emotional_closeness (0-1), reliability_score (0-1), last_interaction_summary, pending_actions[]
- **Personality**: interests[], personality_traits[], communication_style
- **Social**: social_media (dict e.g. {"twitter": "@handle"}), important_dates (dict e.g. {"birthday": "March 5"})
- **Organization**: notes (free text), tags[] (e.g. ["work", "college"])
- **Public Profile**: person_scope (private/public/both), public_role, known_for[], public_bio

Extract as many relevant fields as possible from natural conversation. For example:
- "My friend Priya is a designer at Figma in San Francisco" → occupation=designer, company=Figma, location=San Francisco
- "I met Rahul through college, he's really into hiking" → met_through=college, interests=["hiking"]
- "John's birthday is March 5th" → important_dates={"birthday": "March 5"}

RELATIONSHIP EXTRACTION (CRITICAL):
When the user mentions a relationship (e.g., "My friend Rahul", "John is my manager", "Alice is my sister"), you MUST create a graph relationship — NOT just store it as a tag or note. Use the relationship arguments directly on `create_person` or `update_person` instead of making a separate `add_relationship` call.

Steps:
1. `search_person` for the mentioned person
2. If NOT found → `create_person` with relationship_with, relationship_type, and relationship_direction
   If found → `update_person` with the same relationship arguments (plus any field updates)

Direction guide (for create_person):
- `created_to_other`: the person being created does the action → e.g., "Priya mentors Rahul" (creating Priya) → Priya→Rahul
- `other_to_created`: the other person does the action → e.g., "Rahul manages Priya" (creating Priya) → Rahul→Priya

Direction guide (for update_person):
- `updated_to_other`: the person being updated does the action
- `other_to_updated`: the other person does the action

Examples:
- "My friend Priya works at Google" → search_person("Priya") → not found → create_person(name="Priya", company="Google", relationship_with="{user_name}", relationship_type="FRIEND", relationship_direction="created_to_other")
- "Rahul manages Priya" (Priya is new) → create_person(name="Priya", relationship_with="Rahul", relationship_type="MANAGES", relationship_direction="other_to_created")
- "Priya is also my colleague" (Priya exists) → update_person(person_id=..., relationship_with="{user_name}", relationship_type="COLLEAGUE", relationship_direction="updated_to_other")

Use `add_relationship` ONLY when both persons already exist and no create/update is needed (e.g., "Connect Priya and Rahul as colleagues").

AVAILABLE TOOLS:
- `create_person`: Use this when a new person is mentioned for the first time. Include all fields you can extract. Optionally include relationship_with, relationship_type, and relationship_direction to create a relationship in the same call.
- `search_person`: Use this to find people by name or partial name. Always do this before creating a new entry to avoid duplicates.
- `list_persons`: Use this to get an overview of everyone in the database. Supports pagination (limit, offset) and filters (tags, location, occupation, company, interaction_frequency).
- `get_person`: Use this when you have a specific ID and need the full details.
- `update_person`: Use this to add or change information for an existing entry. Optionally include relationship_with, relationship_type, and relationship_direction to add a relationship in the same call.
- `delete_person`: Use this only if the user explicitly asks to "forget" someone.
- `add_relationship`: Use this ONLY when both persons already exist and no create/update is needed. Relationship types include: KNOWS, FRIEND, FAMILY, COLLEAGUE, WORKS_WITH, MANAGES, REPORTS_TO, MENTOR, PARTNER, NEIGHBOR, CLASSMATE, EMPLOYS, MARRIED_TO, PARENT_OF, INTRODUCED_BY, RIVAL_OF, FORMERLY_WORKED_WITH. You can set strength (0-1) and context.
- `get_relationships`: Use this to see all connections a person has.
- `update_relationship`: Use this to update properties (strength, context, notes, started_at, ended_at) on an existing relationship.
- `delete_relationship`: Use this to remove a relationship between two people.

PHOTO HANDLING:
When a user sends a message with an image (you'll see an image_url like /uploads/chat/uuid.jpg), YOU decide what to do based on intent:

A) "Who is this?" / identification intent:
   1. Call `identify_face` with the image_url
   2. Report results naturally — who was recognized, confidence, known details
   3. If no match found, tell the user the person is not in the database yet

B) "This is Rahul, remember him" / save intent:
   1. Call `search_person` to check if person already exists by name/text
   2. Call `identify_face` to check if the face already matches someone
   3. Based on results:
      - Neither found → `create_person` then `store_person_face` with person_id + image_url
      - Text found, no face stored → `store_person_face` to add face to existing person
      - Face matches a different person → ASK the user for confirmation before updating
      - Both match the same person → tell user they're already saved, update if new info provided
   4. Always confirm to the user what was done

C) Random photo / no face intent:
   - Do NOT call any face tools. Just respond normally.

- `identify_face`: Detect and identify faces in an uploaded image. Pass the image_url. Returns per-face results with matches.
- `store_person_face`: Link an uploaded image's face to a person. Requires person_id and image_url.

SHOWING PERSON PHOTOS:
When tool results include a `face_image_url` field for a person, show their photo in your response using markdown: ![Name](FACE_IMAGE_URL)
Example: if face_image_url is "/uploads/faces/abc.jpg", write ![John](/uploads/faces/abc.jpg)

KNOWLEDGE ENTITIES (beyond people):

IDEA — Track your thoughts, predictions, decisions, opinions.
Fields: name, idea_type (prediction|opinion|decision|question|realization|hypothesis|lesson_learned), description, confidence (0-1), status (active|validated|invalidated|evolved|abandoned), evidence_for[], evidence_against[], date_formed, revisit_date, tags[], notes
Tools: create_idea, search_ideas, get_idea, update_idea, delete_idea, list_ideas

CONTENT — Track books, articles, videos, podcasts you consume.
Fields: title, content_type (book|article|video|podcast|paper|course|movie|tweet|talk), author, source_url, status (want|reading|completed|abandoned), your_rating (0-1), personal_notes, recommended_by, tags[]
Tools: create_content, search_content, get_content, update_content, delete_content, list_content

PROJECT — Track active goals and work.
Fields: name, project_type (work|side_project|learning|health|financial|travel|creative|career), status (idea|planned|in_progress|paused|completed|abandoned), description, goal, target_date, priority (0-1), tags[], notes
Tools: create_project, search_projects, get_project, update_project, delete_project, list_projects

CROSS-ENTITY LINKING:
- link_entities: Connect any two entities (Person/Idea/Content/Project)
- get_entity_graph: See all connections of any entity
- Relationship types: THINKS, SHARED_BY, AUTHORED, RECOMMENDED, CONSUMED_WITH, WORKS_ON, COLLABORATES_ON, INSPIRED_BY, APPLIED_IN, REFERENCE_FOR

ENTITY EXTRACTION RULES:
- "I think AI will replace jobs" → search_ideas first, then create_idea (type=prediction)
- "I'm reading Atomic Habits" → search_content first, then create_content (type=book, status=reading)
- "Working on a fitness goal" → search_projects first, then create_project (type=health)
- "Rahul recommended Sapiens" → create/find content + link_entities(Person:Rahul→Content:Sapiens, RECOMMENDED)
- Always search before creating to avoid duplicates.

Maintain a professional yet friendly tone. If you are unsure about a piece of information, ask for clarification before storing it."""


# ---------------------------------------------------------------------------
# Pydantic schemas for LLM tool parameters (stable, user_id never exposed)
# ---------------------------------------------------------------------------
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
    # New fields
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

class AddRelationshipInput(BaseModel):
    from_person_name: str = Field(..., description="Name of the first person")
    to_person_name: str = Field(..., description="Name of the second person")
    relationship_type: str = Field(..., description="Type of relationship: KNOWS, FRIEND, FAMILY, COLLEAGUE, WORKS_WITH, MANAGES, REPORTS_TO, MENTOR, PARTNER, NEIGHBOR, CLASSMATE, EMPLOYS, MARRIED_TO, PARENT_OF, INTRODUCED_BY, RIVAL_OF, FORMERLY_WORKED_WITH")
    notes: Optional[str] = Field(default=None, description="Optional notes about the relationship")
    strength: Optional[float] = Field(default=None, description="Relationship strength (0.0 to 1.0)")
    context: Optional[str] = Field(default=None, description="Context of the relationship")

class GetRelationshipsInput(BaseModel):
    person_name: str = Field(..., description="Name of the person to find relationships for")

class UpdateRelationshipInput(BaseModel):
    from_person_name: str = Field(..., description="Name of the first person")
    to_person_name: str = Field(..., description="Name of the second person")
    relationship_type: str = Field(..., description="Type of relationship")
    strength: Optional[float] = Field(default=None, description="Relationship strength (0-1)")
    context: Optional[str] = Field(default=None, description="Context of the relationship")
    started_at: Optional[str] = Field(default=None, description="When the relationship started")
    ended_at: Optional[str] = Field(default=None, description="When the relationship ended")
    notes: Optional[str] = Field(default=None, description="Notes about the relationship")

class DeleteRelationshipInput(BaseModel):
    from_person_name: str = Field(..., description="Name of the first person")
    to_person_name: str = Field(..., description="Name of the second person")
    relationship_type: str = Field(..., description="Type of relationship to delete")

class IdentifyFaceInput(BaseModel):
    image_url: str = Field(..., description="URL path of the uploaded image (e.g. /uploads/chat/uuid.jpg)")

class StorePersonFaceInput(BaseModel):
    person_id: str = Field(..., description="UUID of the person to link the face to")
    image_url: str = Field(..., description="URL path of the uploaded chat image (e.g. /uploads/chat/uuid.jpg)")


# ---------------------------------------------------------------------------
# Idea input schemas
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Content input schemas
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Project input schemas
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Cross-entity input schemas
# ---------------------------------------------------------------------------
class LinkEntitiesInput(BaseModel):
    from_type: str = Field(..., description="Source entity type: Person, Idea, Content, or Project")
    from_id: str = Field(..., description="UUID of the source entity")
    to_type: str = Field(..., description="Target entity type: Person, Idea, Content, or Project")
    to_id: str = Field(..., description="UUID of the target entity")
    rel_type: str = Field(..., description="Relationship type: THINKS, SHARED_BY, AUTHORED, RECOMMENDED, CONSUMED_WITH, WORKS_ON, COLLABORATES_ON, INSPIRED_BY, APPLIED_IN, REFERENCE_FOR")
    properties: Optional[Dict[str, Any]] = Field(default=None, description="Optional properties for the relationship")

class GetEntityGraphInput(BaseModel):
    entity_type: str = Field(..., description="Entity type: Person, Idea, Content, or Project")
    entity_id: str = Field(..., description="UUID of the entity")


# ---------------------------------------------------------------------------
# Tool factory — creates LangChain tools with user_id baked into closures.
# The LLM never sees or controls user_id.
# ---------------------------------------------------------------------------
def _make_tools(user_id: str):
    """Return a list of async LangChain tools bound to the authenticated user_id."""

    @tool(args_schema=CreatePersonInput)
    async def create_person(
        name: str,
        aliases: List[str] = [],
        contacts: Dict[str, Any] = {},
        short_bio: str = "",
        trust_score: float = 0.0,
        **kwargs,
    ) -> dict:
        """Create a new person identity in the database with rich details like occupation, company, location, interests, tags, etc."""
        return await create_person_tool(user_id, name=name, aliases=aliases, contacts=contacts, short_bio=short_bio, trust_score=trust_score, **kwargs)

    @tool(args_schema=UpdatePersonInput)
    async def update_person(
        person_id: str,
        **kwargs,
    ) -> dict:
        """Update an existing person's information. Supports all fields: name, aliases, contacts, occupation, company, location, interests, tags, notes, social_media, etc."""
        return await update_person_tool(user_id, person_id=person_id, **kwargs)

    @tool(args_schema=GetPersonInput)
    async def get_person(person_id: str) -> dict:
        """Get details of a specific person by their ID."""
        return await get_person_tool(user_id, person_id)

    @tool(args_schema=ListPersonsInput)
    async def list_persons(
        limit: Optional[int] = 50,
        offset: Optional[int] = 0,
        tags: Optional[List[str]] = None,
        location: Optional[str] = None,
        occupation: Optional[str] = None,
        company: Optional[str] = None,
        interaction_frequency: Optional[str] = None,
    ) -> dict:
        """List all saved persons. Supports pagination and filtering by tags, location, occupation, company, interaction_frequency."""
        return await list_persons_tool(user_id, limit, offset, tags, location, occupation, company, interaction_frequency)

    @tool(args_schema=DeletePersonInput)
    async def delete_person(person_id: str) -> dict:
        """Delete a person from the database."""
        return await delete_person_tool(user_id, person_id)

    @tool(args_schema=SearchPersonInput)
    async def search_person(search_term: str) -> dict:
        """Search for persons by name."""
        return await search_person_tool(user_id, search_term)

    @tool(args_schema=AddRelationshipInput)
    async def add_relationship(
        from_person_name: str,
        to_person_name: str,
        relationship_type: str,
        notes: Optional[str] = None,
        strength: Optional[float] = None,
        context: Optional[str] = None,
    ) -> dict:
        """Create a relationship between two people in the knowledge graph. Both persons must already exist."""
        return await add_relationship_tool(user_id, from_person_name=from_person_name, to_person_name=to_person_name, relationship_type=relationship_type, notes=notes, strength=strength, context=context)

    @tool(args_schema=GetRelationshipsInput)
    async def get_relationships(person_name: str) -> dict:
        """Get all relationships for a person — shows how they are connected to others."""
        return await get_relationships_tool(user_id, person_name)

    @tool(args_schema=UpdateRelationshipInput)
    async def update_relationship(
        from_person_name: str,
        to_person_name: str,
        relationship_type: str,
        strength: Optional[float] = None,
        context: Optional[str] = None,
        started_at: Optional[str] = None,
        ended_at: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> dict:
        """Update properties on an existing relationship between two people."""
        return await update_relationship_tool(user_id, from_person_name=from_person_name, to_person_name=to_person_name, relationship_type=relationship_type, strength=strength, context=context, started_at=started_at, ended_at=ended_at, notes=notes)

    @tool(args_schema=DeleteRelationshipInput)
    async def delete_relationship(
        from_person_name: str,
        to_person_name: str,
        relationship_type: str,
    ) -> dict:
        """Delete a relationship between two people."""
        return await delete_relationship_tool(user_id, from_person_name=from_person_name, to_person_name=to_person_name, relationship_type=relationship_type)

    @tool(args_schema=IdentifyFaceInput)
    async def identify_face(image_url: str) -> dict:
        """Detect and identify all faces in an uploaded image. Returns per-face results with bounding boxes, detection scores, and matched persons with confidence scores."""
        return await identify_face_from_url_tool(user_id, image_url)

    @tool(args_schema=StorePersonFaceInput)
    async def store_person_face(person_id: str, image_url: str) -> dict:
        """Store a face embedding for a person from an uploaded chat image. Call this after creating or finding a person when the user wants to link their face from an uploaded photo."""
        return await store_person_face_tool(user_id, person_id, image_url)

    # --- Idea tools ---
    @tool(args_schema=CreateIdeaInput)
    async def create_idea(name: str, **kwargs) -> dict:
        """Create a new idea/thought/prediction/opinion in the knowledge graph."""
        return await create_idea_tool(user_id, name=name, **kwargs)

    @tool(args_schema=SearchIdeasInput)
    async def search_ideas(search_term: str) -> dict:
        """Search for ideas by name or description using semantic search."""
        return await search_ideas_tool(user_id, search_term)

    @tool(args_schema=GetIdeaInput)
    async def get_idea(idea_id: str) -> dict:
        """Get details of a specific idea by ID."""
        return await get_idea_tool(user_id, idea_id)

    @tool(args_schema=ListIdeasInput)
    async def list_ideas(limit: Optional[int] = 50, offset: Optional[int] = 0, idea_type: Optional[str] = None, status: Optional[str] = None, tags: Optional[List[str]] = None) -> dict:
        """List all saved ideas. Supports filtering by idea_type, status, tags."""
        return await list_ideas_tool(user_id, limit, offset, idea_type, status, tags)

    @tool(args_schema=UpdateIdeaInput)
    async def update_idea(idea_id: str, **kwargs) -> dict:
        """Update an existing idea's information."""
        return await update_idea_tool(user_id, idea_id=idea_id, **kwargs)

    @tool(args_schema=DeleteIdeaInput)
    async def delete_idea(idea_id: str) -> dict:
        """Delete an idea from the knowledge graph."""
        return await delete_idea_tool(user_id, idea_id)

    # --- Content tools ---
    @tool(args_schema=CreateContentInput)
    async def create_content(title: str, **kwargs) -> dict:
        """Create new content (book, article, video, podcast, etc.) in the knowledge graph."""
        return await create_content_tool(user_id, title=title, **kwargs)

    @tool(args_schema=SearchContentInput)
    async def search_content(search_term: str) -> dict:
        """Search for content by title or description using semantic search."""
        return await search_content_tool(user_id, search_term)

    @tool(args_schema=GetContentInput)
    async def get_content(content_id: str) -> dict:
        """Get details of specific content by ID."""
        return await get_content_tool(user_id, content_id)

    @tool(args_schema=ListContentInput)
    async def list_content(limit: Optional[int] = 50, offset: Optional[int] = 0, content_type: Optional[str] = None, status: Optional[str] = None, tags: Optional[List[str]] = None) -> dict:
        """List all saved content. Supports filtering by content_type, status, tags."""
        return await list_content_tool(user_id, limit, offset, content_type, status, tags)

    @tool(args_schema=UpdateContentInput)
    async def update_content(content_id: str, **kwargs) -> dict:
        """Update existing content's information."""
        return await update_content_tool(user_id, content_id=content_id, **kwargs)

    @tool(args_schema=DeleteContentInput)
    async def delete_content(content_id: str) -> dict:
        """Delete content from the knowledge graph."""
        return await delete_content_tool(user_id, content_id)

    # --- Project tools ---
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
    async def list_projects(limit: Optional[int] = 50, offset: Optional[int] = 0, project_type: Optional[str] = None, status: Optional[str] = None, tags: Optional[List[str]] = None) -> dict:
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

    # --- Cross-entity tools ---
    @tool(args_schema=LinkEntitiesInput)
    async def link_entities(from_type: str, from_id: str, to_type: str, to_id: str, rel_type: str, properties: Optional[Dict[str, Any]] = None) -> dict:
        """Create a cross-entity relationship between any two entities (Person, Idea, Content, Project)."""
        return await link_entities_tool(user_id, from_type, from_id, to_type, to_id, rel_type, properties)

    @tool(args_schema=GetEntityGraphInput)
    async def get_entity_graph(entity_type: str, entity_id: str) -> dict:
        """Get all connections of any entity — shows how it relates to other entities across types."""
        return await get_entity_graph_tool(user_id, entity_type, entity_id)

    return [
        # Person tools (12)
        create_person,
        get_person,
        list_persons,
        update_person,
        delete_person,
        search_person,
        add_relationship,
        get_relationships,
        update_relationship,
        delete_relationship,
        identify_face,
        store_person_face,
        # Idea tools (6)
        create_idea,
        search_ideas,
        get_idea,
        list_ideas,
        update_idea,
        delete_idea,
        # Content tools (6)
        create_content,
        search_content,
        get_content,
        list_content,
        update_content,
        delete_content,
        # Project tools (6)
        create_project,
        search_projects,
        get_project,
        list_projects,
        update_project,
        delete_project,
        # Cross-entity tools (2)
        link_entities,
        get_entity_graph,
    ]


# ---------------------------------------------------------------------------
# LLM setup
# ---------------------------------------------------------------------------
def _get_openai_llm():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable is not set")
    return ChatOpenAI(
        model=os.getenv("OPENAI_MODEL", "gpt-5-mini-2025-08-07"),
        api_key=api_key
    )

def _get_google_llm():
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY environment variable is not set")
    return ChatGoogleGenerativeAI(
        model=os.getenv("GOOGLE_MODEL", "gemini-2.5-pro"),
        google_api_key=api_key
    )

def get_llm():
    """Initialize and return the LLM based on environment configuration."""
    provider = os.getenv("LLM_PROVIDER", "openai").lower()
    providers = {
        "openai": _get_openai_llm,
        "google": _get_google_llm,
    }
    if provider not in providers:
        raise ValueError(f"Unsupported LLM provider: {provider}. Supported: {list(providers.keys())}")
    return providers[provider]()


# ---------------------------------------------------------------------------
# Chat history formatting
# ---------------------------------------------------------------------------
MAX_HISTORY_PAIRS = 10  # Keep last N question-answer pairs


def format_chat_history(messages: list[dict], user_name: str | None = None) -> list:
    """Convert chat history to LangChain message format.

    Only the last ``MAX_HISTORY_PAIRS`` Q&A pairs are kept to avoid
    excessive token usage and potential context-window overflow on long
    conversations.
    """
    # Window: keep only the last N pairs (2 messages per pair)
    window_size = MAX_HISTORY_PAIRS * 2
    windowed = messages[-window_size:] if len(messages) > window_size else messages

    system_content = SYSTEM_PROMPT_TEMPLATE.format(user_name=user_name or "the user")
    formatted = [SystemMessage(content=system_content)]
    for msg in windowed:
        if msg["role"] == "user":
            formatted.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            formatted.append(AIMessage(content=msg["content"]))
    return formatted


# ---------------------------------------------------------------------------
# Main agent entry point
# ---------------------------------------------------------------------------
MAX_TOOL_ITERATIONS = 15


# ---------------------------------------------------------------------------
# In-process orchestrator (used when MULTI_AGENT_ENABLED=true)
# ---------------------------------------------------------------------------
async def _route_via_orchestrator(
    user_message: str,
    user_id: str,
    user_name: str | None = None,
    chat_history: list[dict] | None = None,
) -> str:
    """Route a message through the in-process orchestrator and return the response."""
    from agents.orchestrator.router import route_message
    from agents.common.db_clients import init_databases

    await init_databases()
    return await route_message(user_message, user_id, user_name=user_name, chat_history=chat_history)


def _get_trace_result() -> dict | None:
    """Finalize and return the current trace, if any."""
    return finalize_trace()


async def get_agent_response(
    user_message: str,
    chat_history: list[dict] = None,
    image_url: str | None = None,
    user_id: str | None = None,
    user_name: str | None = None,
) -> str:
    """
    Get a response from the AI agent (async).

    Returns:
        A tuple of (response_text, trace_dict_or_None).

    Args:
        user_message: The user's input message
        chat_history: List of previous messages [{"role": "user"|"assistant", "content": "..."}]
        image_url: Optional URL of an uploaded image attached to this message
        user_id: Authenticated user's ID — used to scope all tool operations
        user_name: Authenticated user's display name — injected into the system prompt
    """
    if chat_history is None:
        chat_history = []

    if image_url:
        user_message = f"[ATTACHED_IMAGE]\nImage URL: {image_url}\n[/ATTACHED_IMAGE]\n\n{user_message}"

    # Start request-scoped trace
    start_trace()

    # --- Multi-agent path: route through in-process orchestrator ---
    if MULTI_AGENT_ENABLED and user_id:
        try:
            logger.info("Multi-agent mode: routing through in-process orchestrator")
            response_text = await _route_via_orchestrator(user_message, user_id, user_name=user_name, chat_history=chat_history)
            return response_text, _get_trace_result()
        except Exception as e:
            logger.error("Orchestrator call failed: %s", e, exc_info=True)
            _get_trace_result()  # cleanup
            raise Exception(f"Error getting response: {e}")

    # --- Monolithic path (fallback) ---
    try:
        llm = get_llm()
        logger.debug("Agent invoked: user_id=%s, history_len=%d, has_image=%s", user_id, len(chat_history), bool(image_url))

        # Build tools scoped to this user
        tools = []
        if MCP_TOOLS_AVAILABLE and user_id:
            tools = _make_tools(user_id)

        if tools:
            llm_with_tools = llm.bind_tools(tools)
        else:
            llm_with_tools = llm

        # Format the conversation history
        messages = format_chat_history(chat_history, user_name=user_name)
        messages.append(HumanMessage(content=user_message))

        # Get response from the model
        start_agent_span("monolithic")
        response = await llm_with_tools.ainvoke(messages)

        # Handle tool calls with iteration limit
        iterations = 0
        while response.tool_calls and iterations < MAX_TOOL_ITERATIONS:
            iterations += 1
            messages.append(response)

            for tool_call in response.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]
                logger.debug("Tool call: name=%s", tool_name)

                selected_tool = next((t for t in tools if t.name == tool_name), None)

                t0 = time.time()
                tool_error = None
                tool_result = None
                if selected_tool:
                    try:
                        tool_result = await selected_tool.ainvoke(tool_args)
                        content = json.dumps(tool_result)
                    except Exception as e:
                        logger.error("Tool execution failed: tool=%s error=%s", tool_name, e)
                        tool_error = str(e)
                        content = f"Error executing tool {tool_name}: {str(e)}"
                else:
                    logger.warning("Tool not found: %s", tool_name)
                    tool_error = f"Tool {tool_name} not found"
                    content = f"Error: Tool {tool_name} not found"

                log_tool_call(tool_name, tool_args, tool_result, tool_error, (time.time() - t0) * 1000)
                messages.append(ToolMessage(content=content, tool_call_id=tool_call["id"]))

            response = await llm_with_tools.ainvoke(messages)

        # If we exhausted iterations but the LLM still wants to call tools,
        # force a final response explaining the limit was reached.
        if iterations >= MAX_TOOL_ITERATIONS and response.tool_calls:
            logger.warning("Agent reached max tool iterations (%d)", MAX_TOOL_ITERATIONS)
            messages.append(response)
            # Add a synthetic tool error for each pending call
            for tool_call in response.tool_calls:
                messages.append(
                    ToolMessage(
                        content="Error: Maximum tool iteration limit reached. "
                        "Please summarize what you have so far and respond to the user.",
                        tool_call_id=tool_call["id"],
                    )
                )
            response = await llm_with_tools.ainvoke(messages)

        end_agent_span()
        return response.content, _get_trace_result()

    except Exception as e:
        error_msg = str(e)
        logger.error("Agent response failed: %s", error_msg, exc_info=True)
        _get_trace_result()  # cleanup
        if "API key" in error_msg.lower():
            raise ValueError("Invalid or missing API key")
        raise Exception(f"Error getting response: {error_msg}")


async def stream_agent_response(
    user_message: str,
    chat_history: list[dict] = None,
    image_url: str | None = None,
    user_id: str | None = None,
    user_name: str | None = None,
):
    """
    Async generator that yields text chunks from the AI agent.

    Tool-call iterations are executed internally (not streamed).
    Only the final text response is streamed token-by-token via ``astream``.

    After all text chunks, yields a special "__TRACE__:" prefixed line
    containing the JSON-serialized trace data (if tracing is enabled).
    """
    if chat_history is None:
        chat_history = []

    if image_url:
        user_message = f"[ATTACHED_IMAGE]\nImage URL: {image_url}\n[/ATTACHED_IMAGE]\n\n{user_message}"

    # Start request-scoped trace
    start_trace()

    # --- Multi-agent path: get full response from orchestrator, then yield it ---
    if MULTI_AGENT_ENABLED and user_id:
        try:
            logger.info("Streaming multi-agent mode: routing through in-process orchestrator")
            response_text = await _route_via_orchestrator(user_message, user_id, user_name=user_name, chat_history=chat_history)
            # Yield the complete response in chunks for streaming compatibility
            chunk_size = 20  # characters per chunk for simulated streaming
            for i in range(0, len(response_text), chunk_size):
                yield response_text[i:i + chunk_size]
            # Yield trace as a special marker
            trace_data = _get_trace_result()
            if trace_data:
                yield f"__TRACE__:{json.dumps(trace_data)}"
            return
        except Exception as e:
            logger.error("Orchestrator streaming call failed: %s", e, exc_info=True)
            _get_trace_result()  # cleanup
            yield f"\n\nI encountered an error while processing your request. Please try again."
            return

    # --- Monolithic path (fallback) ---
    try:
        llm = get_llm()
        logger.debug("Streaming agent invoked: user_id=%s", user_id)

        tools = []
        if MCP_TOOLS_AVAILABLE and user_id:
            tools = _make_tools(user_id)

        llm_with_tools = llm.bind_tools(tools) if tools else llm

        messages = format_chat_history(chat_history, user_name=user_name)
        messages.append(HumanMessage(content=user_message))

        # --- resolve tool calls (non-streaming) until the LLM is ready to reply ---
        start_agent_span("monolithic")
        response = await llm_with_tools.ainvoke(messages)

        iterations = 0

        while response.tool_calls and iterations < MAX_TOOL_ITERATIONS:
            iterations += 1
            messages.append(response)

            for tool_call in response.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]
                logger.debug("Tool call (streaming): name=%s", tool_name)
                selected_tool = next((t for t in tools if t.name == tool_name), None)

                t0 = time.time()
                tool_error = None
                tool_result = None
                if selected_tool:
                    try:
                        tool_result = await selected_tool.ainvoke(tool_args)
                        content = json.dumps(tool_result)
                    except Exception as e:
                        logger.error("Tool execution failed during streaming: tool=%s error=%s", tool_name, e)
                        tool_error = str(e)
                        content = f"Error executing tool {tool_name}: {str(e)}"
                else:
                    logger.warning("Tool not found (streaming): %s", tool_name)
                    tool_error = f"Tool {tool_name} not found"
                    content = f"Error: Tool {tool_name} not found"

                log_tool_call(tool_name, tool_args, tool_result, tool_error, (time.time() - t0) * 1000)
                messages.append(ToolMessage(content=content, tool_call_id=tool_call["id"]))

            response = await llm_with_tools.ainvoke(messages)

        if iterations >= MAX_TOOL_ITERATIONS and response.tool_calls:
            logger.warning("Streaming agent reached max tool iterations (%d)", MAX_TOOL_ITERATIONS)
            messages.append(response)
            for tool_call in response.tool_calls:
                messages.append(
                    ToolMessage(
                        content="Error: Maximum tool iteration limit reached. "
                        "Please summarize what you have so far and respond to the user.",
                        tool_call_id=tool_call["id"],
                    )
                )
            # Fall through to streaming the final response below

        end_agent_span()

        # --- stream the final text response token-by-token ---
        # Re-invoke with astream so each chunk is yielded as it arrives
        async for chunk in llm_with_tools.astream(messages):
            if chunk.content:
                yield chunk.content

        # Yield trace as a special marker after all text
        trace_data = _get_trace_result()
        if trace_data:
            yield f"__TRACE__:{json.dumps(trace_data)}"

    except Exception as e:
        error_msg = str(e)
        logger.error("Streaming agent response failed: %s", error_msg, exc_info=True)
        _get_trace_result()  # cleanup
        yield f"\n\nI encountered an error while processing your request. Please try again."
