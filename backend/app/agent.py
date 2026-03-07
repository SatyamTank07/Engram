"""
LangChain agent logic for chat completions.
"""

import os
import sys
import json
from typing import List, Optional, Dict, Any
from pathlib import Path
from dotenv import load_dotenv
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
    )
    MCP_TOOLS_AVAILABLE = True
except ImportError:
    MCP_TOOLS_AVAILABLE = False
    print("Warning: Could not import MCP tools. Chatbot will run without personal identity features.")

# Load environment variables
load_dotenv()

# System prompt for the AI assistant
SYSTEM_PROMPT = """You are a sophisticated AI Personal Assistant. Your primary goal is to be helpful, concise, and remarkably organized.

You have access to a Personal Identity Knowledge Graph which allows you to store and retrieve detailed information about people the user mentions (including the user themselves), and to model RELATIONSHIPS between people.

CORE INSTRUCTIONS:
1. **Be Proactive**: If a user mentions a detail about someone (e.g., "My friend John's email is john@example.com" or "I live in New York"), check if that person exists using `search_person`. If they do, `update_person` with the new info. If not, `create_person`.
2. **Detect Relationships**: If a user mentions how two people are connected (e.g., "John is my manager", "Alice and Bob are friends"), use `add_relationship` to store the connection. Make sure both people exist first.
3. **Context Retrieval**: Before answering questions about specific people, use `search_person` or `list_persons` to see what you already know. Use `get_relationships` to understand how people are connected.
   - `search_person` uses **semantic search** — you can search by description, not just exact name.
   - Example: searching "developer from Pune" will find people whose bio mentions Pune + development.
   - Example: searching "person who works at Google" will find people associated with Google.
4. **Data Integrity**: Use `get_person` to verify details before making updates.
5. **Tool Transparency**: When you use a tool, briefly and naturally mention what you've done (e.g., "I've noted down John's new email for you.").

AVAILABLE TOOLS:
- `create_person`: Use this when a new person is mentioned for the first time.
- `search_person`: Use this to find people by name or partial name. Always do this before creating a new entry to avoid duplicates.
- `list_persons`: Use this to get an overview of everyone in the database.
- `get_person`: Use this when you have a specific ID and need the full details.
- `update_person`: Use this to add or change information for an existing entry.
- `delete_person`: Use this only if the user explicitly asks to "forget" someone.
- `add_relationship`: Use this to record how two people are connected. Relationship types include: KNOWS, FRIEND, FAMILY, COLLEAGUE, WORKS_WITH, MANAGES, REPORTS_TO, MENTOR, PARTNER, NEIGHBOR, CLASSMATE.
- `get_relationships`: Use this to see all connections a person has.
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

class UpdatePersonInput(BaseModel):
    person_id: str = Field(..., description="UUID of the person to update")
    name: Optional[str] = Field(default=None, description="New canonical name")
    aliases: Optional[List[str]] = Field(default=None, description="New list of aliases")
    contacts: Optional[Dict[str, Any]] = Field(default=None, description="New contact information")
    short_bio: Optional[str] = Field(default=None, description="New biography or notes")
    trust_score: Optional[float] = Field(default=None, description="New confidence score")

class GetPersonInput(BaseModel):
    person_id: str = Field(..., description="UUID of the person to retrieve")

class ListPersonsInput(BaseModel):
    limit: Optional[int] = Field(default=50, description="Maximum number of persons to return")

class DeletePersonInput(BaseModel):
    person_id: str = Field(..., description="UUID of the person to delete")

class SearchPersonInput(BaseModel):
    search_term: str = Field(..., description="Name or partial name to search for")

class AddRelationshipInput(BaseModel):
    from_person_name: str = Field(..., description="Name of the first person")
    to_person_name: str = Field(..., description="Name of the second person")
    relationship_type: str = Field(..., description="Type of relationship: KNOWS, FRIEND, FAMILY, COLLEAGUE, WORKS_WITH, MANAGES, REPORTS_TO, MENTOR, PARTNER, NEIGHBOR, CLASSMATE")
    notes: Optional[str] = Field(default=None, description="Optional notes about the relationship")

class GetRelationshipsInput(BaseModel):
    person_name: str = Field(..., description="Name of the person to find relationships for")

class IdentifyFaceInput(BaseModel):
    image_url: str = Field(..., description="URL path of the uploaded image (e.g. /uploads/chat/uuid.jpg)")

class StorePersonFaceInput(BaseModel):
    person_id: str = Field(..., description="UUID of the person to link the face to")
    image_url: str = Field(..., description="URL path of the uploaded chat image (e.g. /uploads/chat/uuid.jpg)")


# ---------------------------------------------------------------------------
# Tool factory — creates LangChain tools with user_id baked into closures.
# The LLM never sees or controls user_id.
# ---------------------------------------------------------------------------
def _make_tools(user_id: str):
    """Return a list of LangChain tools bound to the authenticated user_id."""

    @tool(args_schema=CreatePersonInput)
    def create_person(
        name: str,
        aliases: List[str] = [],
        contacts: Dict[str, Any] = {},
        short_bio: str = "",
        trust_score: float = 0.0,
    ) -> dict:
        """Create a new person identity in the database."""
        return create_person_tool(user_id, name=name, aliases=aliases, contacts=contacts, short_bio=short_bio, trust_score=trust_score)

    @tool(args_schema=UpdatePersonInput)
    def update_person(
        person_id: str,
        name: Optional[str] = None,
        aliases: Optional[List[str]] = None,
        contacts: Optional[Dict[str, Any]] = None,
        short_bio: Optional[str] = None,
        trust_score: Optional[float] = None,
    ) -> dict:
        """Update an existing person's information."""
        return update_person_tool(user_id, person_id=person_id, name=name, aliases=aliases, contacts=contacts, short_bio=short_bio, trust_score=trust_score)

    @tool(args_schema=GetPersonInput)
    def get_person(person_id: str) -> dict:
        """Get details of a specific person by their ID."""
        return get_person_tool(user_id, person_id)

    @tool(args_schema=ListPersonsInput)
    def list_persons(limit: Optional[int] = 50) -> dict:
        """List all saved persons for the current user."""
        return list_persons_tool(user_id, limit)

    @tool(args_schema=DeletePersonInput)
    def delete_person(person_id: str) -> dict:
        """Delete a person from the database."""
        return delete_person_tool(user_id, person_id)

    @tool(args_schema=SearchPersonInput)
    def search_person(search_term: str) -> dict:
        """Search for persons by name."""
        return search_person_tool(user_id, search_term)

    @tool(args_schema=AddRelationshipInput)
    def add_relationship(
        from_person_name: str,
        to_person_name: str,
        relationship_type: str,
        notes: Optional[str] = None,
    ) -> dict:
        """Create a relationship between two people in the knowledge graph. Both persons must already exist."""
        return add_relationship_tool(user_id, from_person_name=from_person_name, to_person_name=to_person_name, relationship_type=relationship_type, notes=notes)

    @tool(args_schema=GetRelationshipsInput)
    def get_relationships(person_name: str) -> dict:
        """Get all relationships for a person — shows how they are connected to others."""
        return get_relationships_tool(user_id, person_name)

    @tool(args_schema=IdentifyFaceInput)
    def identify_face(image_url: str) -> dict:
        """Detect and identify all faces in an uploaded image. Returns per-face results with bounding boxes, detection scores, and matched persons with confidence scores."""
        return identify_face_from_url_tool(user_id, image_url)

    @tool(args_schema=StorePersonFaceInput)
    def store_person_face(person_id: str, image_url: str) -> dict:
        """Store a face embedding for a person from an uploaded chat image. Call this after creating or finding a person when the user wants to link their face from an uploaded photo."""
        return store_person_face_tool(user_id, person_id, image_url)

    return [
        create_person,
        get_person,
        list_persons,
        update_person,
        delete_person,
        search_person,
        add_relationship,
        get_relationships,
        identify_face,
        store_person_face,
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
def format_chat_history(messages: list[dict]) -> list:
    """Convert chat history to LangChain message format."""
    formatted = [SystemMessage(content=SYSTEM_PROMPT)]
    for msg in messages:
        if msg["role"] == "user":
            formatted.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            formatted.append(AIMessage(content=msg["content"]))
    return formatted


# ---------------------------------------------------------------------------
# Main agent entry point
# ---------------------------------------------------------------------------
MAX_TOOL_ITERATIONS = 10


def get_agent_response(
    user_message: str,
    chat_history: list[dict] = None,
    image_url: str | None = None,
    user_id: str | None = None,
) -> str:
    """
    Get a response from the AI agent.

    Args:
        user_message: The user's input message
        chat_history: List of previous messages [{"role": "user"|"assistant", "content": "..."}]
        image_url: Optional URL of an uploaded image attached to this message
        user_id: Authenticated user's ID — used to scope all tool operations
    """
    if chat_history is None:
        chat_history = []

    if image_url:
        user_message = f"[ATTACHED_IMAGE]\nImage URL: {image_url}\n[/ATTACHED_IMAGE]\n\n{user_message}"

    try:
        llm = get_llm()

        # Build tools scoped to this user
        tools = []
        if MCP_TOOLS_AVAILABLE and user_id:
            tools = _make_tools(user_id)

        if tools:
            llm_with_tools = llm.bind_tools(tools)
        else:
            llm_with_tools = llm

        # Format the conversation history
        messages = format_chat_history(chat_history)
        messages.append(HumanMessage(content=user_message))

        # Get response from the model
        response = llm_with_tools.invoke(messages)

        # Handle tool calls with iteration limit
        iterations = 0
        while response.tool_calls and iterations < MAX_TOOL_ITERATIONS:
            iterations += 1
            messages.append(response)

            for tool_call in response.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]

                selected_tool = next((t for t in tools if t.name == tool_name), None)

                if selected_tool:
                    try:
                        tool_result = selected_tool.invoke(tool_args)
                        content = json.dumps(tool_result)
                    except Exception as e:
                        content = f"Error executing tool {tool_name}: {str(e)}"
                else:
                    content = f"Error: Tool {tool_name} not found"

                messages.append(ToolMessage(content=content, tool_call_id=tool_call["id"]))

            response = llm_with_tools.invoke(messages)

        return response.content

    except Exception as e:
        error_msg = str(e)
        if "API key" in error_msg.lower():
            raise ValueError("Invalid or missing API key")
        raise Exception(f"Error getting response: {error_msg}")
