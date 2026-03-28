"""Idea entity routes (markdown file storage)."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status

from .. import schemas, database, auth, md_storage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/ideas", tags=["ideas"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_idea(
    idea_data: schemas.IdeaCreate,
    current_user: database.User = Depends(auth.get_current_user),
):
    """Create a new idea."""
    result = await md_storage.create_entity(str(current_user.id), "idea", idea_data.model_dump())
    return result


@router.get("")
async def get_ideas(
    current_user: database.User = Depends(auth.get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    idea_type: str | None = Query(default=None),
    idea_status: str | None = Query(default=None, alias="status"),
    tags: str | None = Query(default=None, description="Comma-separated tags"),
):
    """List ideas for the authenticated user."""
    filters: dict = {}
    if idea_type:
        filters["idea_type"] = idea_type
    if idea_status:
        filters["status"] = idea_status
    if tags:
        filters["tags"] = [t.strip() for t in tags.split(",") if t.strip()]
    items, total = await md_storage.list_entities(
        str(current_user.id), "idea", limit, offset, **filters,
    )
    return {"items": items, "total": total, "offset": offset, "limit": limit}


@router.get("/{idea_id}")
async def get_idea(
    idea_id: str,
    current_user: database.User = Depends(auth.get_current_user),
):
    """Get a specific idea."""
    idea = await md_storage.get_entity(str(current_user.id), "idea", idea_id)
    if not idea:
        raise HTTPException(status_code=404, detail={"code": "IDEA_NOT_FOUND", "message": "Idea not found"})
    if idea.get("user_id") != str(current_user.id):
        raise HTTPException(status_code=403, detail={"code": "ACCESS_DENIED", "message": "Access denied"})
    return idea


@router.put("/{idea_id}")
async def update_idea(
    idea_id: str,
    idea_data: schemas.IdeaUpdate,
    current_user: database.User = Depends(auth.get_current_user),
):
    """Full update of an idea."""
    idea = await md_storage.get_entity(str(current_user.id), "idea", idea_id)
    if not idea:
        raise HTTPException(status_code=404, detail={"code": "IDEA_NOT_FOUND", "message": "Idea not found"})
    if idea.get("user_id") != str(current_user.id):
        raise HTTPException(status_code=403, detail={"code": "ACCESS_DENIED", "message": "Access denied"})
    updates = {k: v for k, v in idea_data.model_dump(exclude_unset=True).items() if v is not None}
    result = await md_storage.update_entity(str(current_user.id), "idea", idea_id, updates)
    return result


@router.patch("/{idea_id}")
async def patch_idea(
    idea_id: str,
    idea_data: schemas.IdeaUpdate,
    current_user: database.User = Depends(auth.get_current_user),
):
    """Partial update of an idea."""
    idea = await md_storage.get_entity(str(current_user.id), "idea", idea_id)
    if not idea:
        raise HTTPException(status_code=404, detail={"code": "IDEA_NOT_FOUND", "message": "Idea not found"})
    if idea.get("user_id") != str(current_user.id):
        raise HTTPException(status_code=403, detail={"code": "ACCESS_DENIED", "message": "Access denied"})
    updates = {k: v for k, v in idea_data.model_dump(exclude_unset=True).items() if v is not None}
    if not updates:
        return idea
    result = await md_storage.update_entity(str(current_user.id), "idea", idea_id, updates)
    return result


@router.delete("/{idea_id}")
async def delete_idea(
    idea_id: str,
    current_user: database.User = Depends(auth.get_current_user),
):
    """Delete an idea."""
    idea = await md_storage.get_entity(str(current_user.id), "idea", idea_id)
    if not idea:
        raise HTTPException(status_code=404, detail={"code": "IDEA_NOT_FOUND", "message": "Idea not found"})
    if idea.get("user_id") != str(current_user.id):
        raise HTTPException(status_code=403, detail={"code": "ACCESS_DENIED", "message": "Access denied"})
    await md_storage.delete_entity(str(current_user.id), "idea", idea_id)
    return {"status": "deleted", "idea_id": idea_id}


@router.post("/search")
async def semantic_search_ideas(
    search_req: schemas.SemanticSearchRequest,
    current_user: database.User = Depends(auth.get_current_user),
):
    """Search ideas using keyword matching."""
    results = await md_storage.search_entities(
        str(current_user.id), "idea", search_req.query, search_req.limit,
    )
    return results
