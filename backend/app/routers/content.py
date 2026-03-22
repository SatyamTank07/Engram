"""Content entity routes (Neo4j knowledge graph + pgvector)."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.concurrency import run_in_threadpool

from .. import schemas, database, auth, graph_db, vector_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/content", tags=["content"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_content(
    content_data: schemas.ContentCreate,
    current_user: database.User = Depends(auth.get_current_user),
):
    """Create new content in the knowledge graph."""
    create_kwargs = content_data.model_dump(exclude_unset=False)
    content = await graph_db.create_content_node(user_id=str(current_user.id), **create_kwargs)
    return content


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
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else None
    items, total = await graph_db.list_content_nodes(
        user_id=str(current_user.id), limit=limit, offset=offset,
        content_type=content_type, status=content_status, tags=tag_list,
    )
    return {"items": items, "total": total, "offset": offset, "limit": limit}


@router.get("/{content_id}")
async def get_content(
    content_id: str,
    current_user: database.User = Depends(auth.get_current_user),
):
    """Get specific content."""
    content = await graph_db.get_content_node(content_id)
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
    content = await graph_db.get_content_node(content_id)
    if not content:
        raise HTTPException(status_code=404, detail={"code": "CONTENT_NOT_FOUND", "message": "Content not found"})
    if content.get("user_id") != str(current_user.id):
        raise HTTPException(status_code=403, detail={"code": "ACCESS_DENIED", "message": "Access denied"})
    updates = {k: v for k, v in content_data.model_dump(exclude_unset=True).items() if v is not None}
    return await graph_db.update_content_node(content_id, **updates)


@router.patch("/{content_id}")
async def patch_content(
    content_id: str,
    content_data: schemas.ContentUpdate,
    current_user: database.User = Depends(auth.get_current_user),
):
    """Partial update of content."""
    content = await graph_db.get_content_node(content_id)
    if not content:
        raise HTTPException(status_code=404, detail={"code": "CONTENT_NOT_FOUND", "message": "Content not found"})
    if content.get("user_id") != str(current_user.id):
        raise HTTPException(status_code=403, detail={"code": "ACCESS_DENIED", "message": "Access denied"})
    updates = {k: v for k, v in content_data.model_dump(exclude_unset=True).items() if v is not None}
    if not updates:
        return content
    return await graph_db.update_content_node(content_id, **updates)


@router.delete("/{content_id}")
async def delete_content(
    content_id: str,
    current_user: database.User = Depends(auth.get_current_user),
):
    """Delete content."""
    content = await graph_db.get_content_node(content_id)
    if not content:
        raise HTTPException(status_code=404, detail={"code": "CONTENT_NOT_FOUND", "message": "Content not found"})
    if content.get("user_id") != str(current_user.id):
        raise HTTPException(status_code=403, detail={"code": "ACCESS_DENIED", "message": "Access denied"})
    await graph_db.delete_content_node(content_id)
    return {"status": "deleted", "content_id": content_id}


@router.post("/search")
async def semantic_search_content(
    search_req: schemas.SemanticSearchRequest,
    current_user: database.User = Depends(auth.get_current_user),
):
    """Search content using semantic similarity."""
    from .. import embedding_service
    query_embedding = await run_in_threadpool(embedding_service.generate_text_embedding, search_req.query)
    matches = await run_in_threadpool(
        vector_db.content_semantic_search,
        user_id=str(current_user.id), query_embedding=query_embedding, limit=search_req.limit,
    )
    results = []
    for match in matches:
        content = await graph_db.get_content_node(match["content_id"])
        if content:
            results.append({**content, "similarity_score": match["similarity_score"]})
    return results
