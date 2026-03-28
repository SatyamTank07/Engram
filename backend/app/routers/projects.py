"""Project entity routes (markdown file storage)."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status

from .. import schemas, database, auth, md_storage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_project(
    project_data: schemas.ProjectCreate,
    current_user: database.User = Depends(auth.get_current_user),
):
    """Create a new project."""
    result = await md_storage.create_entity(str(current_user.id), "project", project_data.model_dump())
    return result


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
    filters: dict = {}
    if project_type:
        filters["project_type"] = project_type
    if project_status:
        filters["status"] = project_status
    if tags:
        filters["tags"] = [t.strip() for t in tags.split(",") if t.strip()]
    items, total = await md_storage.list_entities(
        str(current_user.id), "project", limit, offset, **filters,
    )
    return {"items": items, "total": total, "offset": offset, "limit": limit}


@router.get("/{project_id}")
async def get_project(
    project_id: str,
    current_user: database.User = Depends(auth.get_current_user),
):
    """Get a specific project."""
    project = await md_storage.get_entity(str(current_user.id), "project", project_id)
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
    project = await md_storage.get_entity(str(current_user.id), "project", project_id)
    if not project:
        raise HTTPException(status_code=404, detail={"code": "PROJECT_NOT_FOUND", "message": "Project not found"})
    if project.get("user_id") != str(current_user.id):
        raise HTTPException(status_code=403, detail={"code": "ACCESS_DENIED", "message": "Access denied"})
    updates = {k: v for k, v in project_data.model_dump(exclude_unset=True).items() if v is not None}
    result = await md_storage.update_entity(str(current_user.id), "project", project_id, updates)
    return result


@router.patch("/{project_id}")
async def patch_project(
    project_id: str,
    project_data: schemas.ProjectUpdate,
    current_user: database.User = Depends(auth.get_current_user),
):
    """Partial update of a project."""
    project = await md_storage.get_entity(str(current_user.id), "project", project_id)
    if not project:
        raise HTTPException(status_code=404, detail={"code": "PROJECT_NOT_FOUND", "message": "Project not found"})
    if project.get("user_id") != str(current_user.id):
        raise HTTPException(status_code=403, detail={"code": "ACCESS_DENIED", "message": "Access denied"})
    updates = {k: v for k, v in project_data.model_dump(exclude_unset=True).items() if v is not None}
    if not updates:
        return project
    result = await md_storage.update_entity(str(current_user.id), "project", project_id, updates)
    return result


@router.delete("/{project_id}")
async def delete_project(
    project_id: str,
    current_user: database.User = Depends(auth.get_current_user),
):
    """Delete a project."""
    project = await md_storage.get_entity(str(current_user.id), "project", project_id)
    if not project:
        raise HTTPException(status_code=404, detail={"code": "PROJECT_NOT_FOUND", "message": "Project not found"})
    if project.get("user_id") != str(current_user.id):
        raise HTTPException(status_code=403, detail={"code": "ACCESS_DENIED", "message": "Access denied"})
    await md_storage.delete_entity(str(current_user.id), "project", project_id)
    return {"status": "deleted", "project_id": project_id}


@router.post("/search")
async def semantic_search_projects(
    search_req: schemas.SemanticSearchRequest,
    current_user: database.User = Depends(auth.get_current_user),
):
    """Search projects using keyword matching."""
    results = await md_storage.search_entities(
        str(current_user.id), "project", search_req.query, search_req.limit,
    )
    return results
