"""Cross-entity relationship routes."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from .. import schemas, database, auth, graph_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/entities", tags=["entities"])


@router.post("/link")
async def link_entities(
    link_data: schemas.CrossEntityLinkCreate,
    current_user: database.User = Depends(auth.get_current_user),
):
    """Create a cross-entity relationship."""
    result = await graph_db.link_entities(
        from_label=link_data.from_type,
        from_id=link_data.from_id,
        to_label=link_data.to_type,
        to_id=link_data.to_id,
        rel_type=link_data.rel_type,
        properties=link_data.properties,
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
    deleted = await graph_db.unlink_entities(
        from_label=link_data.from_type,
        from_id=link_data.from_id,
        to_label=link_data.to_type,
        to_id=link_data.to_id,
        rel_type=link_data.rel_type,
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
    label_map = {
        "person": "Person", "idea": "Idea",
        "content": "Content", "project": "Project",
    }
    label = label_map.get(entity_type.lower())
    if not label:
        raise HTTPException(status_code=400, detail={
            "code": "INVALID_ENTITY_TYPE",
            "message": f"Invalid entity type: {entity_type}. Valid: person, idea, content, project",
        })
    result = await graph_db.get_entity_graph(label, entity_id)
    if not result.get("entity"):
        raise HTTPException(status_code=404, detail={
            "code": "ENTITY_NOT_FOUND",
            "message": "Entity not found",
        })
    return result
