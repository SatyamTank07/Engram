"""Content entity routes (markdown file storage)."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status

from .. import schemas, database, auth, md_storage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/content", tags=["content"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_content(
    content_data: schemas.ContentCreate,
    current_user: database.User = Depends(auth.get_current_user),
):
    """Create new content."""
    result = await md_storage.create_entity(str(current_user.id), "content", content_data.model_dump())
    return result


@router.get("")
async def get_content_list(
    current_user: database.User = Depends(auth.get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    content_type: str | None = Query(default=None),
    content_status: str | None = Query(default=None, alias="status"),
    tags: str | None = Query(default=None, description="Comma-separated tags"),
):
    """List content for the authenticated user."""
    filters: dict = {}
    if content_type:
        filters["content_type"] = content_type
    if content_status:
        filters["status"] = content_status
    if tags:
        filters["tags"] = [t.strip() for t in tags.split(",") if t.strip()]
    items, total = await md_storage.list_entities(
        str(current_user.id), "content", limit, offset, **filters,
    )
    return {"items": items, "total": total, "offset": offset, "limit": limit}


@router.get("/{content_id}")
async def get_content(
    content_id: str,
    current_user: database.User = Depends(auth.get_current_user),
):
    """Get specific content."""
    content = await md_storage.get_entity(str(current_user.id), "content", content_id)
    if not content:
        raise HTTPException(status_code=404, detail={"code": "CONTENT_NOT_FOUND", "message": "Content not found"})
    if content.get("user_id") != str(current_user.id):
        raise HTTPException(status_code=403, detail={"code": "ACCESS_DENIED", "message": "Access denied"})
    return content


@router.put("/{content_id}")
async def update_content(
    content_id: str,
    content_data: schemas.ContentUpdate,
    current_user: database.User = Depends(auth.get_current_user),
):
    """Full update of content."""
    content = await md_storage.get_entity(str(current_user.id), "content", content_id)
    if not content:
        raise HTTPException(status_code=404, detail={"code": "CONTENT_NOT_FOUND", "message": "Content not found"})
    if content.get("user_id") != str(current_user.id):
        raise HTTPException(status_code=403, detail={"code": "ACCESS_DENIED", "message": "Access denied"})
    updates = {k: v for k, v in content_data.model_dump(exclude_unset=True).items() if v is not None}
    result = await md_storage.update_entity(str(current_user.id), "content", content_id, updates)
    return result


@router.patch("/{content_id}")
async def patch_content(
    content_id: str,
    content_data: schemas.ContentUpdate,
    current_user: database.User = Depends(auth.get_current_user),
):
    """Partial update of content."""
    content = await md_storage.get_entity(str(current_user.id), "content", content_id)
    if not content:
        raise HTTPException(status_code=404, detail={"code": "CONTENT_NOT_FOUND", "message": "Content not found"})
    if content.get("user_id") != str(current_user.id):
        raise HTTPException(status_code=403, detail={"code": "ACCESS_DENIED", "message": "Access denied"})
    updates = {k: v for k, v in content_data.model_dump(exclude_unset=True).items() if v is not None}
    if not updates:
        return content
    result = await md_storage.update_entity(str(current_user.id), "content", content_id, updates)
    return result


@router.delete("/{content_id}")
async def delete_content(
    content_id: str,
    current_user: database.User = Depends(auth.get_current_user),
):
    """Delete content."""
    content = await md_storage.get_entity(str(current_user.id), "content", content_id)
    if not content:
        raise HTTPException(status_code=404, detail={"code": "CONTENT_NOT_FOUND", "message": "Content not found"})
    if content.get("user_id") != str(current_user.id):
        raise HTTPException(status_code=403, detail={"code": "ACCESS_DENIED", "message": "Access denied"})
    await md_storage.delete_entity(str(current_user.id), "content", content_id)
    return {"status": "deleted", "content_id": content_id}


@router.post("/search")
async def semantic_search_content(
    search_req: schemas.SemanticSearchRequest,
    current_user: database.User = Depends(auth.get_current_user),
):
    """Search content using keyword matching."""
    results = await md_storage.search_entities(
        str(current_user.id), "content", search_req.query, search_req.limit,
    )
    return results
