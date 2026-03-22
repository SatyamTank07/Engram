"""
LangChain tool factory for the Person sub-agent.

Creates 12 person tools with user_id baked in via closures.
Each tool has improved descriptions and output schema annotations.
"""

import sys
from pathlib import Path
from typing import List, Optional, Dict, Any

from langchain_core.tools import tool

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
        """Create a new person in the knowledge graph. Extract ALL available fields from the conversation: name, occupation, company, location, interests, tags, etc. Optionally include relationship_with + relationship_type + relationship_direction to create a relationship in the same call. Always search_person first to avoid duplicates. Returns: {success, message, person: {id, name, ...}, relationship?: {...}}"""
        return await create_person_tool(user_id, name=name, aliases=aliases, contacts=contacts, short_bio=short_bio, trust_score=trust_score, **kwargs)

    @tool(args_schema=UpdatePersonInput)
    async def update_person(person_id: str, **kwargs) -> dict:
        """Update an existing person's fields by their UUID. Only provide fields that need changing — unset fields are left unchanged. Supports all person fields plus relationship arguments. Use get_person first to verify current state. Returns: {success, message, person: {id, name, ...}, relationship?: {...}}"""
        return await update_person_tool(user_id, person_id=person_id, **kwargs)

    @tool(args_schema=GetPersonInput)
    async def get_person(person_id: str) -> dict:
        """Fetch the complete profile of a person by their UUID. Use this to verify data before updating or to retrieve full details after a search. Returns: {success, person: {id, name, occupation, company, tags, ...}}"""
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
        """List all persons with pagination and optional filters. Use filters to narrow results: tags=['work'], location='Pune', occupation='designer', company='Google', interaction_frequency='weekly'. Returns: {success, count, total, persons: [...]}"""
        return await list_persons_tool(user_id, limit, offset, tags, location, occupation, company, interaction_frequency)

    @tool(args_schema=DeletePersonInput)
    async def delete_person(person_id: str) -> dict:
        """Permanently delete a person by UUID. Only call when the user explicitly asks to remove someone. Returns: {success, message, deleted_id}"""
        return await delete_person_tool(user_id, person_id)

    @tool(args_schema=SearchPersonInput)
    async def search_person(search_term: str) -> dict:
        """Semantic search for people by name, description, or any attribute. Uses vector embeddings with fallback to exact name match. Always call this before create_person to check for duplicates. Returns: {success, count, search_type: 'semantic'|'exact', persons: [{id, name, similarity_score, ...}]}"""
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
        """Create a directed relationship between two EXISTING people. Both must already exist in the graph. Types: KNOWS, FRIEND, FAMILY, COLLEAGUE, WORKS_WITH, MANAGES, REPORTS_TO, MENTOR, PARTNER, NEIGHBOR, CLASSMATE, EMPLOYS, MARRIED_TO, PARENT_OF, INTRODUCED_BY, RIVAL_OF, FORMERLY_WORKED_WITH. Prefer using create_person/update_person with relationship args when one person is being created/updated. Returns: {success, message, relationship: {from, to, type}}"""
        return await add_relationship_tool(user_id, from_person_name=from_person_name, to_person_name=to_person_name, relationship_type=relationship_type, notes=notes, strength=strength, context=context)

    @tool(args_schema=GetRelationshipsInput)
    async def get_relationships(person_name: str) -> dict:
        """Get all relationships for a person by name. Shows who they are connected to and how (friend, colleague, manages, etc.). Returns: {success, person, count, relationships: [{from, to, type, strength, notes}]}"""
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
        """Update properties on an existing relationship edge. The relationship must already exist between the two named people. Returns: {success, message, relationship: {...}}"""
        return await update_relationship_tool(user_id, from_person_name=from_person_name, to_person_name=to_person_name, relationship_type=relationship_type, strength=strength, context=context, started_at=started_at, ended_at=ended_at, notes=notes)

    @tool(args_schema=DeleteRelationshipInput)
    async def delete_relationship(
        from_person_name: str,
        to_person_name: str,
        relationship_type: str,
    ) -> dict:
        """Remove a specific relationship between two people. Requires exact names and relationship type. Returns: {success, message}"""
        return await delete_relationship_tool(user_id, from_person_name=from_person_name, to_person_name=to_person_name, relationship_type=relationship_type)

    @tool(args_schema=IdentifyFaceInput)
    async def identify_face(image_url: str) -> dict:
        """Detect and identify all faces in an uploaded image. For each face found, returns bounding box, detection confidence, and matched persons with similarity scores. Use when user asks 'Who is this?' or sends a photo. Returns: {success, faces_detected, faces: [{face_index, bbox, det_score, match_status, matches: [{name, id, confidence_score}]}]}"""
        return await identify_face_from_url_tool(user_id, image_url)

    @tool(args_schema=StorePersonFaceInput)
    async def store_person_face(person_id: str, image_url: str) -> dict:
        """Link a face photo to a known person by extracting and storing their face embedding. Use when user says 'This is [Name]' with a photo. The person must already exist. Returns: {success, message, face_image_url}"""
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
