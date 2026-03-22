"""
LangChain tool factory for the Person sub-agent.

Creates 12 person tools with user_id baked in via closures,
exactly like backend/app/agent.py but scoped to person operations only.
"""

import sys
from pathlib import Path
from typing import List, Optional, Dict, Any

from langchain_core.tools import tool

# Ensure project root is on sys.path
_project_root = str(Path(__file__).parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from mcp_server.tools import (
    create_person_tool,
    get_person_tool,
    list_persons_tool,
    update_person_tool,
    delete_person_tool,
    search_person_tool,
    add_relationship_tool,
    get_relationships_tool,
    update_relationship_tool,
    delete_relationship_tool,
    identify_face_from_url_tool,
    store_person_face_tool,
)

from agents.person_agent.schemas import (
    CreatePersonInput,
    UpdatePersonInput,
    GetPersonInput,
    ListPersonsInput,
    DeletePersonInput,
    SearchPersonInput,
    AddRelationshipInput,
    GetRelationshipsInput,
    UpdateRelationshipInput,
    DeleteRelationshipInput,
    IdentifyFaceInput,
    StorePersonFaceInput,
)


def make_person_tools(user_id: str):
    """Return 12 LangChain tools bound to the given user_id via closures."""

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
    async def update_person(person_id: str, **kwargs) -> dict:
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
        """Search for persons by name using semantic search."""
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
        """Store a face embedding for a person from an uploaded chat image."""
        return await store_person_face_tool(user_id, person_id, image_url)

    return [
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
    ]
