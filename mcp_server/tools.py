"""
MCP tools for Engram knowledge graph operations.
Each tool takes an explicit user_id — no hardcoded default.

Person/face/relationship tools use the Neo4j graph_db backend.
Generic entity tools (idea, content, project) use the md_storage backend.
"""

import sys
import logging
import shutil
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from backend.app import graph_db, face_service
from backend.app import embedding_service, vector_db
from backend.app import md_storage

logger = logging.getLogger(__name__)


def _resolve_image_path(image_url: str) -> Path:
    """Resolve an image URL like /uploads/chat/abc.jpg to an absolute file path."""
    upload_dir = Path(__file__).parent.parent / "backend" / "uploads"
    relative_path = image_url.lstrip("/")
    if relative_path.startswith("uploads/"):
        relative_path = relative_path[len("uploads/"):]
    return upload_dir / relative_path


async def _handle_relationship(
    user_id: str,
    person: dict,
    relationship_with: str | None,
    relationship_type: str | None,
    relationship_direction: str | None,
    relationship_notes: str | None = None,
    relationship_strength: float | None = None,
    incoming_direction: str = "other_to_created",
) -> dict | None:
    """Shared helper: resolve the other person and create a relationship edge.

    Args:
        person: The person being created/updated (already exists in Neo4j).
        relationship_with: Name of the other person to link to.
        relationship_type: Edge type (FRIEND, MANAGES, etc.).
        relationship_direction: Direction value — tool-specific string.
        incoming_direction: The direction value that means other→person
                           ("other_to_created" for create, "other_to_updated" for update).
    Returns:
        Relationship result dict, or None if no relationship was requested.
    """
    if not relationship_with and not relationship_type:
        return None

    if bool(relationship_with) != bool(relationship_type):
        return {"warning": "Both relationship_with and relationship_type are required to create a relationship."}

    # Determine valid direction values for this tool context
    outgoing_direction = incoming_direction.replace("other_to_", "").replace("created", "created_to_other").replace("updated", "updated_to_other")
    # Simpler: derive from incoming_direction pattern
    if incoming_direction == "other_to_created":
        outgoing_direction = "created_to_other"
    elif incoming_direction == "other_to_updated":
        outgoing_direction = "updated_to_other"

    valid_directions = {incoming_direction, outgoing_direction}
    if relationship_direction and relationship_direction not in valid_directions:
        return {"warning": f"Invalid relationship_direction '{relationship_direction}'. Must be one of: {', '.join(valid_directions)}"}

    try:
        other_results = await graph_db.search_persons(user_id, relationship_with)
        if not other_results:
            return {"warning": f"Person '{relationship_with}' not found — relationship skipped. Create them first."}

        other_person = other_results[0]
        logger.info("[relationship] resolved '%s' to person '%s' (id=%s)",
                     relationship_with, other_person.get("name"), other_person.get("id"))

        props = {}
        if relationship_notes:
            props["notes"] = relationship_notes
        if relationship_strength is not None:
            props["strength"] = relationship_strength

        if relationship_direction == incoming_direction:
            from_id, to_id = other_person["id"], person["id"]
        else:  # default: person → other
            from_id, to_id = person["id"], other_person["id"]

        result = await graph_db.add_relationship(
            from_person_id=from_id,
            to_person_id=to_id,
            rel_type=relationship_type,
            properties=props,
        )
        if result:
            logger.info("[relationship] created %s -> %s (%s)", result.get("from"), result.get("to"), relationship_type)
            return {"success": True, "relationship": result}
        return {"warning": "Failed to create relationship edge"}
    except Exception as e:
        logger.error("[relationship] failed: %s", e)
        return {"warning": "Relationship creation failed. Person was saved successfully."}


async def create_person_tool(
    user_id: str,
    name: str,
    aliases: list[str] | None = None,
    contacts: dict | None = None,
    short_bio: str | None = None,
    trust_score: float | None = 0.0,
    **kwargs,
) -> dict:
    """Create a new person identity in the knowledge graph."""
    try:
        logger.info("[create_person] user_id=%s, name=%s", user_id, name)

        # Extract relationship args before passing kwargs to graph_db
        relationship_with = kwargs.pop("relationship_with", None)
        relationship_type = kwargs.pop("relationship_type", None)
        relationship_direction = kwargs.pop("relationship_direction", None)
        relationship_notes = kwargs.pop("relationship_notes", None)
        relationship_strength = kwargs.pop("relationship_strength", None)

        person = await graph_db.create_person_node(
            user_id=user_id,
            name=name,
            aliases=aliases or [],
            contacts=contacts or {},
            short_bio=short_bio,
            trust_score=trust_score,
            **kwargs,
        )
        logger.info("[create_person] created person: %s", person.get("id") if person else None)

        # Handle optional relationship
        relationship_result = await _handle_relationship(
            user_id=user_id,
            person=person,
            relationship_with=relationship_with,
            relationship_type=relationship_type,
            relationship_direction=relationship_direction,
            relationship_notes=relationship_notes,
            relationship_strength=relationship_strength,
            incoming_direction="other_to_created",
        )

        response = {
            "success": True,
            "message": f"Successfully created person: {name}",
            "person": person,
        }
        if relationship_result:
            response["relationship"] = relationship_result
        return response
    except Exception as e:
        logger.exception("[create_person] failed")
        return {"success": False, "message": f"Error creating person: {str(e)}"}


async def identify_face_from_url_tool(user_id: str, image_url: str) -> dict:
    """Detect and identify faces in an already-uploaded image."""
    try:
        logger.info("[identify_face] user_id=%s, image_url=%s", user_id, image_url)
        source_path = _resolve_image_path(image_url)
        logger.info("[identify_face] resolved path: %s, exists=%s", source_path, source_path.exists())
        if not source_path.exists():
            return {"success": False, "message": f"Image file not found: {image_url}"}

        image_bytes = source_path.read_bytes()
        logger.info("[identify_face] image size: %d bytes", len(image_bytes))
        detected_faces = face_service.detect_and_embed_all_faces(image_bytes)
        logger.info("[identify_face] detected %d faces", len(detected_faces))

        if not detected_faces:
            return {"success": True, "faces_detected": 0, "faces": [], "message": "No faces detected in the image"}

        faces_result = []
        for idx, face_data in enumerate(detected_faces):
            matches = vector_db.face_search(user_id, face_data["embedding"], limit=3)
            logger.info("[identify_face] face %d: %d vector matches", idx, len(matches))

            face_matches = []
            for match in matches:
                logger.info("[identify_face] looking up person_id=%s (score=%.3f)", match["person_id"], match["similarity_score"])
                person = await graph_db.get_person_node(match["person_id"])
                logger.info("[identify_face] person lookup result: %s", type(person).__name__ if person else None)
                if person:
                    face_matches.append({
                        **person,
                        "confidence_score": round(match["similarity_score"], 3),
                    })

            faces_result.append({
                "face_index": idx,
                "bbox": face_data["bbox"],
                "det_score": face_data["det_score"],
                "match_status": "matched" if face_matches else "unknown",
                "matches": face_matches,
            })

        logger.info("[identify_face] returning %d faces", len(faces_result))
        return {"success": True, "faces_detected": len(detected_faces), "faces": faces_result}
    except Exception as e:
        logger.exception("[identify_face] failed")
        return {"success": False, "message": f"Error identifying faces: {str(e)}"}


async def store_person_face_tool(user_id: str, person_id: str, image_url: str) -> dict:
    """Store a face embedding for a person from an already-uploaded chat image."""
    try:
        logger.info("[store_face] user_id=%s, person_id=%s, image_url=%s", user_id, person_id, image_url)
        source_path = _resolve_image_path(image_url)
        if not source_path.exists():
            return {"success": False, "message": f"Image file not found: {image_url}"}

        image_bytes = source_path.read_bytes()

        # Extract face embedding
        face_vector = face_service.generate_face_embedding(image_bytes)
        logger.info("[store_face] embedding generated, dim=%d", len(face_vector))

        # Store embedding in pgvector
        vector_db.upsert_face_embedding(person_id, user_id, face_vector)
        logger.info("[store_face] embedding stored in pgvector")

        # Copy image to faces directory
        upload_dir = Path(__file__).parent.parent / "backend" / "uploads"
        ext = source_path.suffix or ".jpg"
        face_filename = f"{person_id}{ext}"
        faces_dir = upload_dir / "faces"
        faces_dir.mkdir(parents=True, exist_ok=True)
        dest_path = faces_dir / face_filename
        shutil.copy2(str(source_path), str(dest_path))

        face_image_url = f"/uploads/faces/{face_filename}"

        # Update Neo4j node with face image URL
        await graph_db.update_person_node(person_id, face_image_url=face_image_url)
        logger.info("[store_face] Neo4j node updated with face_image_url")

        return {
            "success": True,
            "message": f"Face embedding stored and image linked to person {person_id}",
            "face_image_url": face_image_url,
        }
    except ValueError as e:
        logger.exception("[store_face] face detection failed")
        return {"success": False, "message": f"Face detection failed: {str(e)}"}
    except Exception as e:
        logger.exception("[store_face] failed")
        return {"success": False, "message": f"Error storing face: {str(e)}"}


async def get_person_tool(user_id: str, person_id: str) -> dict:
    """Get details of a specific person by their ID."""
    try:
        logger.info("[get_person] user_id=%s, person_id=%s", user_id, person_id)
        person = await graph_db.get_person_node(person_id)
        if not person:
            return {"success": False, "message": f"Person with ID {person_id} not found"}
        if person.get("user_id") != user_id:
            return {"success": False, "message": "Access denied: This person belongs to a different user"}
        # Also fetch relationships so callers get a complete picture
        relationships = await graph_db.get_relationships(person_id)
        return {
            "success": True,
            "person": person,
            "relationships": relationships,
            "relationship_count": len(relationships),
        }
    except Exception as e:
        logger.exception("[get_person] failed")
        return {"success": False, "message": f"Error retrieving person: {str(e)}"}


async def list_persons_tool(
    user_id: str,
    limit: int | None = 50,
    offset: int | None = 0,
    tags: list[str] | None = None,
    location: str | None = None,
    occupation: str | None = None,
    company: str | None = None,
    interaction_frequency: str | None = None,
) -> dict:
    """List saved persons for the current user with optional filtering and pagination."""
    try:
        logger.info("[list_persons] user_id=%s, limit=%s, offset=%s", user_id, limit, offset)
        items, total = await graph_db.list_person_nodes(
            user_id,
            limit=limit or 50,
            offset=offset or 0,
            tags=tags,
            location=location,
            occupation=occupation,
            company=company,
            interaction_frequency=interaction_frequency,
        )
        logger.info("[list_persons] found %d persons (total %d)", len(items), total)
        return {"success": True, "count": len(items), "total": total, "persons": items}
    except Exception as e:
        logger.exception("[list_persons] failed")
        return {"success": False, "message": f"Error listing persons: {str(e)}"}


async def update_person_tool(
    user_id: str,
    person_id: str,
    **kwargs,
) -> dict:
    """Update an existing person's information."""
    try:
        logger.info("[update_person] user_id=%s, person_id=%s", user_id, person_id)

        # Extract relationship args before passing kwargs to graph_db
        relationship_with = kwargs.pop("relationship_with", None)
        relationship_type = kwargs.pop("relationship_type", None)
        relationship_direction = kwargs.pop("relationship_direction", None)
        relationship_notes = kwargs.pop("relationship_notes", None)
        relationship_strength = kwargs.pop("relationship_strength", None)

        person = await graph_db.get_person_node(person_id)
        if not person:
            return {"success": False, "message": f"Person with ID {person_id} not found"}
        if person.get("user_id") != user_id:
            return {"success": False, "message": "Access denied: This person belongs to a different user"}

        # Filter out None values
        updates = {k: v for k, v in kwargs.items() if v is not None}
        updated_person = await graph_db.update_person_node(person_id, **updates)
        if not updated_person:
            return {"success": False, "message": "Failed to update person"}

        logger.info("[update_person] updated person: %s", updated_person.get("name"))

        # Handle optional relationship
        relationship_result = await _handle_relationship(
            user_id=user_id,
            person=updated_person,
            relationship_with=relationship_with,
            relationship_type=relationship_type,
            relationship_direction=relationship_direction,
            relationship_notes=relationship_notes,
            relationship_strength=relationship_strength,
            incoming_direction="other_to_updated",
        )

        response = {
            "success": True,
            "message": f"Successfully updated person: {updated_person.get('name', '')}",
            "person": updated_person,
        }
        if relationship_result:
            response["relationship"] = relationship_result
        return response
    except Exception as e:
        logger.exception("[update_person] failed")
        return {"success": False, "message": f"Error updating person: {str(e)}"}


async def delete_person_tool(user_id: str, person_id: str) -> dict:
    """Delete a person from the knowledge graph."""
    try:
        logger.info("[delete_person] user_id=%s, person_id=%s", user_id, person_id)
        person = await graph_db.get_person_node(person_id)
        if not person:
            return {"success": False, "message": f"Person with ID {person_id} not found"}
        if person.get("user_id") != user_id:
            return {"success": False, "message": "Access denied: This person belongs to a different user"}

        person_name = person.get("name", "Unknown")
        await graph_db.delete_person_node(person_id)
        logger.info("[delete_person] deleted person: %s", person_name)
        return {"success": True, "message": f"Successfully deleted person: {person_name}", "deleted_id": person_id}
    except Exception as e:
        logger.exception("[delete_person] failed")
        return {"success": False, "message": f"Error deleting person: {str(e)}"}


async def search_person_tool(user_id: str, search_term: str) -> dict:
    """Search for persons using semantic similarity (with fallback to exact match)."""
    try:
        logger.info("[search_person] user_id=%s, search_term=%s", user_id, search_term)
        # Try semantic search first
        try:
            query_embedding = embedding_service.generate_text_embedding(search_term)
            matches = vector_db.semantic_search(user_id, query_embedding, limit=5)
            logger.info("[search_person] semantic matches: %d", len(matches) if matches else 0)

            if matches:
                persons = []
                for match in matches:
                    person = await graph_db.get_person_node(match["person_id"])
                    if person:
                        person["similarity_score"] = match["similarity_score"]
                        persons.append(person)
                return {
                    "success": True,
                    "count": len(persons),
                    "search_term": search_term,
                    "search_type": "semantic",
                    "persons": persons,
                }
        except Exception:
            logger.info("[search_person] semantic search failed, falling back to exact match")

        # Fallback: exact match
        persons = await graph_db.search_persons(user_id, search_term)
        logger.info("[search_person] exact match results: %d", len(persons))
        return {
            "success": True,
            "count": len(persons),
            "search_term": search_term,
            "search_type": "exact",
            "persons": persons,
        }
    except Exception as e:
        logger.exception("[search_person] failed")
        return {"success": False, "message": f"Error searching persons: {str(e)}"}


async def add_relationship_tool(
    user_id: str,
    from_person_name: str,
    to_person_name: str,
    relationship_type: str,
    notes: str | None = None,
    strength: float | None = None,
    context: str | None = None,
) -> dict:
    """Create a relationship between two people in the knowledge graph."""
    try:
        logger.info("[add_relationship] %s -> %s (%s)", from_person_name, to_person_name, relationship_type)
        from_results = await graph_db.search_persons(user_id, from_person_name)
        if not from_results:
            return {"success": False, "message": f"Person '{from_person_name}' not found. Create them first."}

        to_results = await graph_db.search_persons(user_id, to_person_name)
        if not to_results:
            return {"success": False, "message": f"Person '{to_person_name}' not found. Create them first."}

        from_person = from_results[0]
        to_person = to_results[0]

        properties = {}
        if notes:
            properties["notes"] = notes
        if strength is not None:
            properties["strength"] = strength
        if context:
            properties["context"] = context

        result = await graph_db.add_relationship(
            from_person_id=from_person["id"],
            to_person_id=to_person["id"],
            rel_type=relationship_type,
            properties=properties,
        )

        if result:
            logger.info("[add_relationship] created successfully")
            return {
                "success": True,
                "message": f"Created relationship: {from_person['name']} -{relationship_type}-> {to_person['name']}",
                "relationship": result,
            }
        return {"success": False, "message": "Failed to create relationship"}
    except Exception as e:
        logger.exception("[add_relationship] failed")
        return {"success": False, "message": f"Error creating relationship: {str(e)}"}


async def get_relationships_tool(user_id: str, person_name: str) -> dict:
    """Get all relationships for a person in the knowledge graph."""
    try:
        logger.info("[get_relationships] user_id=%s, person_name=%s", user_id, person_name)
        results = await graph_db.search_persons(user_id, person_name)
        if not results:
            return {"success": False, "message": f"Person '{person_name}' not found."}

        person = results[0]
        relationships = await graph_db.get_relationships(person["id"])
        logger.info("[get_relationships] found %d relationships", len(relationships))
        return {
            "success": True,
            "person": person["name"],
            "count": len(relationships),
            "relationships": relationships,
        }
    except Exception as e:
        logger.exception("[get_relationships] failed")
        return {"success": False, "message": f"Error getting relationships: {str(e)}"}


async def update_relationship_tool(
    user_id: str,
    from_person_name: str,
    to_person_name: str,
    relationship_type: str,
    strength: float | None = None,
    context: str | None = None,
    started_at: str | None = None,
    ended_at: str | None = None,
    notes: str | None = None,
) -> dict:
    """Update properties on an existing relationship between two people."""
    try:
        logger.info("[update_relationship] %s -> %s (%s)", from_person_name, to_person_name, relationship_type)
        from_results = await graph_db.search_persons(user_id, from_person_name)
        if not from_results:
            return {"success": False, "message": f"Person '{from_person_name}' not found."}

        to_results = await graph_db.search_persons(user_id, to_person_name)
        if not to_results:
            return {"success": False, "message": f"Person '{to_person_name}' not found."}

        properties = {}
        if strength is not None:
            properties["strength"] = strength
        if context is not None:
            properties["context"] = context
        if started_at is not None:
            properties["started_at"] = started_at
        if ended_at is not None:
            properties["ended_at"] = ended_at
        if notes is not None:
            properties["notes"] = notes

        result = await graph_db.update_relationship(
            from_person_id=from_results[0]["id"],
            to_person_id=to_results[0]["id"],
            rel_type=relationship_type,
            properties=properties,
        )

        if result:
            return {"success": True, "message": "Relationship updated", "relationship": result}
        return {"success": False, "message": "Relationship not found"}
    except Exception as e:
        logger.exception("[update_relationship] failed")
        return {"success": False, "message": f"Error updating relationship: {str(e)}"}


async def delete_relationship_tool(
    user_id: str,
    from_person_name: str,
    to_person_name: str,
    relationship_type: str,
) -> dict:
    """Delete a relationship between two people."""
    try:
        logger.info("[delete_relationship] %s -> %s (%s)", from_person_name, to_person_name, relationship_type)
        from_results = await graph_db.search_persons(user_id, from_person_name)
        if not from_results:
            return {"success": False, "message": f"Person '{from_person_name}' not found."}

        to_results = await graph_db.search_persons(user_id, to_person_name)
        if not to_results:
            return {"success": False, "message": f"Person '{to_person_name}' not found."}

        deleted = await graph_db.delete_relationship(
            from_person_id=from_results[0]["id"],
            to_person_id=to_results[0]["id"],
            rel_type=relationship_type,
        )

        if deleted:
            return {"success": True, "message": f"Deleted {relationship_type} relationship between {from_person_name} and {to_person_name}"}
        return {"success": False, "message": "Relationship not found"}
    except Exception as e:
        logger.exception("[delete_relationship] failed")
        return {"success": False, "message": f"Error deleting relationship: {str(e)}"}


# =====================================================================
# Generic Entity Tools (idea, content, project) — backed by md_storage
# =====================================================================

_VALID_ENTITY_TYPES = ("idea", "content", "project")


async def create_entity(user_id: str, entity_type: str, data: dict) -> dict:
    """Create a new entity (idea, content, or project) via md_storage."""
    if entity_type not in _VALID_ENTITY_TYPES:
        return {"error": f"Invalid entity_type: {entity_type}. Must be one of: {', '.join(_VALID_ENTITY_TYPES)}"}
    try:
        logger.info("[create_entity] user_id=%s, type=%s", user_id, entity_type)
        result = await md_storage.create_entity(user_id, entity_type, data)
        return result
    except Exception as e:
        logger.exception("[create_entity] failed")
        return {"error": f"Error creating {entity_type}: {str(e)}"}


async def get_entity(user_id: str, entity_type: str, entity_id: str) -> dict:
    """Get an entity by ID."""
    if entity_type not in _VALID_ENTITY_TYPES:
        return {"error": f"Invalid entity_type: {entity_type}. Must be one of: {', '.join(_VALID_ENTITY_TYPES)}"}
    try:
        logger.info("[get_entity] user_id=%s, type=%s, id=%s", user_id, entity_type, entity_id)
        result = await md_storage.get_entity(user_id, entity_type, entity_id)
        if result is None:
            return {"error": f"{entity_type} not found: {entity_id}"}
        return result
    except Exception as e:
        logger.exception("[get_entity] failed")
        return {"error": f"Error retrieving {entity_type}: {str(e)}"}


async def list_entities(user_id: str, entity_type: str, limit: int = 50, offset: int = 0, filters: dict | None = None) -> dict:
    """List entities with optional filtering."""
    if entity_type not in _VALID_ENTITY_TYPES:
        return {"error": f"Invalid entity_type: {entity_type}. Must be one of: {', '.join(_VALID_ENTITY_TYPES)}"}
    try:
        logger.info("[list_entities] user_id=%s, type=%s, limit=%d, offset=%d", user_id, entity_type, limit, offset)
        items, total = await md_storage.list_entities(user_id, entity_type, limit, offset, **(filters or {}))
        return {"items": items, "total": total, "offset": offset, "limit": limit}
    except Exception as e:
        logger.exception("[list_entities] failed")
        return {"error": f"Error listing {entity_type}s: {str(e)}"}


async def update_entity(user_id: str, entity_type: str, entity_id: str, updates: dict) -> dict:
    """Update an entity."""
    if entity_type not in _VALID_ENTITY_TYPES:
        return {"error": f"Invalid entity_type: {entity_type}. Must be one of: {', '.join(_VALID_ENTITY_TYPES)}"}
    try:
        logger.info("[update_entity] user_id=%s, type=%s, id=%s", user_id, entity_type, entity_id)
        result = await md_storage.update_entity(user_id, entity_type, entity_id, updates)
        if result is None:
            return {"error": f"{entity_type} not found: {entity_id}"}
        return result
    except Exception as e:
        logger.exception("[update_entity] failed")
        return {"error": f"Error updating {entity_type}: {str(e)}"}


async def delete_entity(user_id: str, entity_type: str, entity_id: str) -> dict:
    """Delete an entity."""
    if entity_type not in _VALID_ENTITY_TYPES:
        return {"error": f"Invalid entity_type: {entity_type}. Must be one of: {', '.join(_VALID_ENTITY_TYPES)}"}
    try:
        logger.info("[delete_entity] user_id=%s, type=%s, id=%s", user_id, entity_type, entity_id)
        deleted = await md_storage.delete_entity(user_id, entity_type, entity_id)
        return {"deleted": deleted, "entity_id": entity_id}
    except Exception as e:
        logger.exception("[delete_entity] failed")
        return {"error": f"Error deleting {entity_type}: {str(e)}"}


async def search_entities(user_id: str, entity_type: str, query: str, limit: int = 20) -> dict:
    """Search entities by keyword."""
    if entity_type not in _VALID_ENTITY_TYPES:
        return {"error": f"Invalid entity_type: {entity_type}. Must be one of: {', '.join(_VALID_ENTITY_TYPES)}"}
    try:
        logger.info("[search_entities] user_id=%s, type=%s, query=%s", user_id, entity_type, query)
        results = await md_storage.search_entities(user_id, entity_type, query, limit)
        return {"results": results, "total": len(results)}
    except Exception as e:
        logger.exception("[search_entities] failed")
        return {"error": f"Error searching {entity_type}s: {str(e)}"}
