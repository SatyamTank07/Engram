"""
LangChain tool factory for the Person sub-agent.

Creates 8 person tools with user_id baked in via closures.
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
    ManageRelationshipInput,
    HandleFaceInput,
)


def make_person_tools(user_id: str):
    """Return 8 LangChain tools bound to the given user_id via closures."""

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
        """Fetch the complete profile of a person by their UUID, including all their relationships. Use this to verify data before updating or to retrieve full details after a search. Returns: {success, person: {id, name, occupation, company, tags, ...}, relationships: [...], relationship_count: N}"""
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

    @tool(args_schema=ManageRelationshipInput)
    async def manage_relationship(
        action: str,
        from_person_name: str,
        to_person_name: str,
        relationship_type: str,
        notes: Optional[str] = None,
        strength: Optional[float] = None,
        context: Optional[str] = None,
        started_at: Optional[str] = None,
        ended_at: Optional[str] = None,
    ) -> dict:
        """Manage relationships between two existing people. Actions: 'add' (create new relationship), 'update' (modify properties like strength, context, dates, notes), 'delete' (remove relationship). Prefer create_person/update_person with relationship args when one person is being created/updated. Types: KNOWS, FRIEND, FAMILY, COLLEAGUE, WORKS_WITH, MANAGES, REPORTS_TO, MENTOR, PARTNER, NEIGHBOR, CLASSMATE, EMPLOYS, MARRIED_TO, PARENT_OF, INTRODUCED_BY, RIVAL_OF, FORMERLY_WORKED_WITH. Returns: {success, message, relationship?: {...}}"""
        if action == "add":
            return await add_relationship_tool(
                user_id, from_person_name=from_person_name,
                to_person_name=to_person_name, relationship_type=relationship_type,
                notes=notes, strength=strength, context=context,
            )
        elif action == "update":
            return await update_relationship_tool(
                user_id, from_person_name=from_person_name,
                to_person_name=to_person_name, relationship_type=relationship_type,
                strength=strength, context=context,
                started_at=started_at, ended_at=ended_at, notes=notes,
            )
        elif action == "delete":
            return await delete_relationship_tool(
                user_id, from_person_name=from_person_name,
                to_person_name=to_person_name, relationship_type=relationship_type,
            )
        else:
            return {"success": False, "message": f"Invalid action '{action}'. Must be 'add', 'update', or 'delete'."}

    @tool(args_schema=HandleFaceInput)
    async def handle_face(
        action: str,
        image_url: str,
        person_id: Optional[str] = None,
    ) -> dict:
        """Handle face operations on uploaded images. Actions: 'identify' (detect and identify all faces — use when user asks 'Who is this?' or sends a photo), 'store' (link a face photo to a known person by person_id — use when user says 'This is [Name]' with a photo). Returns: For identify: {success, faces_detected, faces: [{face_index, bbox, det_score, match_status, matches}]}. For store: {success, message, face_image_url}"""
        if action == "identify":
            return await identify_face_from_url_tool(user_id, image_url)
        elif action == "store":
            if not person_id:
                return {"success": False, "message": "person_id is required for 'store' action. Search for the person first."}
            return await store_person_face_tool(user_id, person_id, image_url)
        else:
            return {"success": False, "message": f"Invalid action '{action}'. Must be 'identify' or 'store'."}

    return [
        create_person,
        get_person,
        list_persons,
        update_person,
        delete_person,
        search_person,
        manage_relationship,
        handle_face,
    ]
