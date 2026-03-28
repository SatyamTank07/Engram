"""Cross-entity relationship routes."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from .. import schemas, database, auth, md_storage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/entities", tags=["entities"])


@router.post("/link")
async def link_entities(
    link_data: schemas.CrossEntityLinkCreate,
    current_user: database.User = Depends(auth.get_current_user),
):
    """Create a cross-entity relationship."""
    from_type = link_data.from_type.lower()
    to_type = link_data.to_type.lower()
    result = await md_storage.add_relationship(
        user_id=str(current_user.id),
        entity_type=from_type,
        from_id=link_data.from_id,
        to_id=link_data.to_id,
        rel_type=link_data.rel_type,
        properties=link_data.properties,
        to_entity_type=to_type,
    )
    if not result:
        raise HTTPException(status_code=404, detail={
            "code": "ENTITY_NOT_FOUND",
            "message": "One or both entities not found",
        })
    return {"status": "linked", **result}


@router.delete("/link")
async def unlink_entities(
    link_data: schemas.CrossEntityLinkCreate,
    current_user: database.User = Depends(auth.get_current_user),
):
    """Remove a cross-entity relationship."""
    from_type = link_data.from_type.lower()
    to_type = link_data.to_type.lower()
    deleted = await md_storage.delete_relationship(
        user_id=str(current_user.id),
        entity_type=from_type,
        from_id=link_data.from_id,
        to_id=link_data.to_id,
        rel_type=link_data.rel_type,
        to_entity_type=to_type,
    )
    if not deleted:
        raise HTTPException(status_code=404, detail={
            "code": "RELATIONSHIP_NOT_FOUND",
            "message": "Relationship not found",
        })
    return {"status": "unlinked"}


@router.get("/{entity_type}/{entity_id}/graph")
async def get_entity_graph(
    entity_type: str,
    entity_id: str,
    current_user: database.User = Depends(auth.get_current_user),
):
    """Get all connections of any entity."""
    valid_types = {"person", "idea", "content", "project"}
    normalized = entity_type.lower()
    if normalized not in valid_types:
        raise HTTPException(status_code=400, detail={
            "code": "INVALID_ENTITY_TYPE",
            "message": f"Invalid entity type: {entity_type}. Valid: person, idea, content, project",
        })
    result = await md_storage.get_entity_connections(str(current_user.id), normalized, entity_id)
    if not result or not result.get("entity"):
        raise HTTPException(status_code=404, detail={
            "code": "ENTITY_NOT_FOUND",
            "message": "Entity not found",
        })
    return result
