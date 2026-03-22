"""Project entity routes (Neo4j knowledge graph + pgvector)."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.concurrency import run_in_threadpool

from .. import schemas, database, auth, graph_db, vector_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_project(
    project_data: schemas.ProjectCreate,
    current_user: database.User = Depends(auth.get_current_user),
):
    """Create a new project in the knowledge graph."""
    create_kwargs = project_data.model_dump(exclude_unset=False)
    project = await graph_db.create_project_node(user_id=str(current_user.id), **create_kwargs)
    return project


@router.get("")
async def get_projects(
    current_user: database.User = Depends(auth.get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    project_type: str | None = Query(default=None),
    project_status: str | None = Query(default=None, alias="status"),
    tags: str | None = Query(default=None, description="Comma-separated tags"),
):
    """List projects for the authenticated user."""
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else None
    items, total = await graph_db.list_project_nodes(
        user_id=str(current_user.id), limit=limit, offset=offset,
        project_type=project_type, status=project_status, tags=tag_list,
    )
    return {"items": items, "total": total, "offset": offset, "limit": limit}


@router.get("/{project_id}")
async def get_project(
    project_id: str,
    current_user: database.User = Depends(auth.get_current_user),
):
    """Get a specific project."""
    project = await graph_db.get_project_node(project_id)
    if not project:
        raise HTTPException(status_code=404, detail={"code": "PROJECT_NOT_FOUND", "message": "Project not found"})
    if project.get("user_id") != str(current_user.id):
        raise HTTPException(status_code=403, detail={"code": "ACCESS_DENIED", "message": "Access denied"})
    return project


@router.put("/{project_id}")
async def update_project(
    project_id: str,
    project_data: schemas.ProjectUpdate,
    current_user: database.User = Depends(auth.get_current_user),
):
    """Full update of a project."""
    project = await graph_db.get_project_node(project_id)
    if not project:
        raise HTTPException(status_code=404, detail={"code": "PROJECT_NOT_FOUND", "message": "Project not found"})
    if project.get("user_id") != str(current_user.id):
        raise HTTPException(status_code=403, detail={"code": "ACCESS_DENIED", "message": "Access denied"})
    updates = {k: v for k, v in project_data.model_dump(exclude_unset=True).items() if v is not None}
    return await graph_db.update_project_node(project_id, **updates)


@router.patch("/{project_id}")
async def patch_project(
    project_id: str,
    project_data: schemas.ProjectUpdate,
    current_user: database.User = Depends(auth.get_current_user),
):
    """Partial update of a project."""
    project = await graph_db.get_project_node(project_id)
    if not project:
        raise HTTPException(status_code=404, detail={"code": "PROJECT_NOT_FOUND", "message": "Project not found"})
    if project.get("user_id") != str(current_user.id):
        raise HTTPException(status_code=403, detail={"code": "ACCESS_DENIED", "message": "Access denied"})
    updates = {k: v for k, v in project_data.model_dump(exclude_unset=True).items() if v is not None}
    if not updates:
        return project
    return await graph_db.update_project_node(project_id, **updates)


@router.delete("/{project_id}")
async def delete_project(
    project_id: str,
    current_user: database.User = Depends(auth.get_current_user),
):
    """Delete a project."""
    project = await graph_db.get_project_node(project_id)
    if not project:
        raise HTTPException(status_code=404, detail={"code": "PROJECT_NOT_FOUND", "message": "Project not found"})
    if project.get("user_id") != str(current_user.id):
        raise HTTPException(status_code=403, detail={"code": "ACCESS_DENIED", "message": "Access denied"})
    await graph_db.delete_project_node(project_id)
    return {"status": "deleted", "project_id": project_id}


@router.post("/search")
async def semantic_search_projects(
    search_req: schemas.SemanticSearchRequest,
    current_user: database.User = Depends(auth.get_current_user),
):
    """Search projects using semantic similarity."""
    from .. import embedding_service
    query_embedding = await run_in_threadpool(embedding_service.generate_text_embedding, search_req.query)
    matches = await run_in_threadpool(
        vector_db.project_semantic_search,
        user_id=str(current_user.id), query_embedding=query_embedding, limit=search_req.limit,
    )
    results = []
    for match in matches:
        project = await graph_db.get_project_node(match["project_id"])
        if project:
            results.append({**project, "similarity_score": match["similarity_score"]})
    return results
