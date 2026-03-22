"""Idea entity routes (Neo4j knowledge graph + pgvector)."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.concurrency import run_in_threadpool

from .. import schemas, database, auth, graph_db, vector_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/ideas", tags=["ideas"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_idea(
    idea_data: schemas.IdeaCreate,
    current_user: database.User = Depends(auth.get_current_user),
):
    """Create a new idea in the knowledge graph."""
    create_kwargs = idea_data.model_dump(exclude_unset=False)
    idea = await graph_db.create_idea_node(user_id=str(current_user.id), **create_kwargs)
    return idea


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
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else None
    items, total = await graph_db.list_idea_nodes(
        user_id=str(current_user.id), limit=limit, offset=offset,
        idea_type=idea_type, status=idea_status, tags=tag_list,
    )
    return {"items": items, "total": total, "offset": offset, "limit": limit}


@router.get("/{idea_id}")
async def get_idea(
    idea_id: str,
    current_user: database.User = Depends(auth.get_current_user),
):
    """Get a specific idea."""
    idea = await graph_db.get_idea_node(idea_id)
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
    idea = await graph_db.get_idea_node(idea_id)
    if not idea:
        raise HTTPException(status_code=404, detail={"code": "IDEA_NOT_FOUND", "message": "Idea not found"})
    if idea.get("user_id") != str(current_user.id):
        raise HTTPException(status_code=403, detail={"code": "ACCESS_DENIED", "message": "Access denied"})
    updates = {k: v for k, v in idea_data.model_dump(exclude_unset=True).items() if v is not None}
    return await graph_db.update_idea_node(idea_id, **updates)


@router.patch("/{idea_id}")
async def patch_idea(
    idea_id: str,
    idea_data: schemas.IdeaUpdate,
    current_user: database.User = Depends(auth.get_current_user),
):
    """Partial update of an idea."""
    idea = await graph_db.get_idea_node(idea_id)
    if not idea:
        raise HTTPException(status_code=404, detail={"code": "IDEA_NOT_FOUND", "message": "Idea not found"})
    if idea.get("user_id") != str(current_user.id):
        raise HTTPException(status_code=403, detail={"code": "ACCESS_DENIED", "message": "Access denied"})
    updates = {k: v for k, v in idea_data.model_dump(exclude_unset=True).items() if v is not None}
    if not updates:
        return idea
    return await graph_db.update_idea_node(idea_id, **updates)


@router.delete("/{idea_id}")
async def delete_idea(
    idea_id: str,
    current_user: database.User = Depends(auth.get_current_user),
):
    """Delete an idea."""
    idea = await graph_db.get_idea_node(idea_id)
    if not idea:
        raise HTTPException(status_code=404, detail={"code": "IDEA_NOT_FOUND", "message": "Idea not found"})
    if idea.get("user_id") != str(current_user.id):
        raise HTTPException(status_code=403, detail={"code": "ACCESS_DENIED", "message": "Access denied"})
    await graph_db.delete_idea_node(idea_id)
    return {"status": "deleted", "idea_id": idea_id}


@router.post("/search")
async def semantic_search_ideas(
    search_req: schemas.SemanticSearchRequest,
    current_user: database.User = Depends(auth.get_current_user),
):
    """Search ideas using semantic similarity."""
    from .. import embedding_service
    query_embedding = await run_in_threadpool(embedding_service.generate_text_embedding, search_req.query)
    matches = await run_in_threadpool(
        vector_db.idea_semantic_search,
        user_id=str(current_user.id), query_embedding=query_embedding, limit=search_req.limit,
    )
    idea_ids = [m["idea_id"] for m in matches]
    results = []
    for match in matches:
        idea = await graph_db.get_idea_node(match["idea_id"])
        if idea:
            results.append({**idea, "similarity_score": match["similarity_score"]})
    return results
