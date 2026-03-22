"""Person identity routes (Neo4j knowledge graph + pgvector)."""

import logging
from io import BytesIO
from pathlib import Path

import aiofiles
import aiofiles.os
from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, File, status
from fastapi.concurrency import run_in_threadpool

from .. import schemas, database, auth, graph_db, vector_db, face_service
from .deps import limiter, MAX_UPLOAD_SIZE, ALLOWED_IMAGE_TYPES, CHUNK_SIZE, UPLOAD_DIR

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/persons", tags=["persons"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_person(
    person_data: schemas.PersonIdentityCreate,
    current_user: database.User = Depends(auth.get_current_user),
):
    """Create a new person identity in the knowledge graph."""
    # Extract all fields from schema, excluding unset optional fields
    create_kwargs = person_data.model_dump(exclude_unset=False)
    person = await graph_db.create_person_node(
        user_id=str(current_user.id),
        **create_kwargs,
    )
    logger.info("Person created: name=%s, user_id=%s", person_data.name, current_user.id)
    return person


@router.get("")
async def get_persons(
    current_user: database.User = Depends(auth.get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    tags: str | None = Query(default=None, description="Comma-separated tags to filter by"),
    location: str | None = Query(default=None),
    occupation: str | None = Query(default=None),
    company: str | None = Query(default=None),
    interaction_frequency: str | None = Query(default=None),
):
    """Get person identities for the authenticated user with optional filtering and pagination."""
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else None

    items, total = await graph_db.list_person_nodes(
        user_id=str(current_user.id),
        limit=limit,
        offset=offset,
        tags=tag_list,
        location=location,
        occupation=occupation,
        company=company,
        interaction_frequency=interaction_frequency,
    )
    return {"items": items, "total": total, "offset": offset, "limit": limit}


@router.get("/{person_id}")
async def get_person(
    person_id: str,
    current_user: database.User = Depends(auth.get_current_user),
):
    """Get a specific person identity from the knowledge graph."""
    person = await graph_db.get_person_node(person_id)
    if not person:
        raise HTTPException(status_code=404, detail={"code": "PERSON_NOT_FOUND", "message": "Person not found"})

    if person.get("user_id") != str(current_user.id):
        raise HTTPException(status_code=403, detail={"code": "ACCESS_DENIED", "message": "You do not have permission to access this resource"})

    return person


@router.put("/{person_id}")
async def update_person(
    person_id: str,
    person_data: schemas.PersonIdentityUpdate,
    current_user: database.User = Depends(auth.get_current_user),
):
    """Update a person identity in the knowledge graph (full update)."""
    person = await graph_db.get_person_node(person_id)
    if not person:
        raise HTTPException(status_code=404, detail={"code": "PERSON_NOT_FOUND", "message": "Person not found"})

    if person.get("user_id") != str(current_user.id):
        raise HTTPException(status_code=403, detail={"code": "ACCESS_DENIED", "message": "You do not have permission to access this resource"})

    # Only pass non-None fields
    updates = {k: v for k, v in person_data.model_dump(exclude_unset=True).items() if v is not None}
    updated_person = await graph_db.update_person_node(person_id, **updates)
    return updated_person


@router.patch("/{person_id}")
async def patch_person(
    person_id: str,
    person_data: schemas.PersonIdentityUpdate,
    current_user: database.User = Depends(auth.get_current_user),
):
    """Partially update a person identity (only provided fields are changed)."""
    person = await graph_db.get_person_node(person_id)
    if not person:
        raise HTTPException(status_code=404, detail={"code": "PERSON_NOT_FOUND", "message": "Person not found"})

    if person.get("user_id") != str(current_user.id):
        raise HTTPException(status_code=403, detail={"code": "ACCESS_DENIED", "message": "You do not have permission to access this resource"})

    updates = {k: v for k, v in person_data.model_dump(exclude_unset=True).items() if v is not None}
    if not updates:
        return person

    updated_person = await graph_db.update_person_node(person_id, **updates)
    return updated_person


@router.delete("/{person_id}")
async def delete_person(
    person_id: str,
    current_user: database.User = Depends(auth.get_current_user),
):
    """Delete a person identity from the knowledge graph."""
    person = await graph_db.get_person_node(person_id)
    if not person:
        raise HTTPException(status_code=404, detail={"code": "PERSON_NOT_FOUND", "message": "Person not found"})

    if person.get("user_id") != str(current_user.id):
        raise HTTPException(status_code=403, detail={"code": "ACCESS_DENIED", "message": "You do not have permission to access this resource"})

    await graph_db.delete_person_node(person_id)
    logger.info("Person deleted: person_id=%s, user_id=%s", person_id, current_user.id)
    return {"status": "deleted", "person_id": person_id}


@router.get("/{person_id}/connections")
async def get_person_connections(
    person_id: str,
    current_user: database.User = Depends(auth.get_current_user),
):
    """Get all connections (relationships + connected persons) for a person."""
    person = await graph_db.get_person_node(person_id)
    if not person:
        raise HTTPException(status_code=404, detail={"code": "PERSON_NOT_FOUND", "message": "Person not found"})

    if person.get("user_id") != str(current_user.id):
        raise HTTPException(status_code=403, detail={"code": "ACCESS_DENIED", "message": "You do not have permission to access this resource"})

    result = await graph_db.get_person_connections(person_id)
    return result


# ---------------------------------------------------------------------------
# Relationship CRUD
# ---------------------------------------------------------------------------

@router.put("/{from_id}/relationships/{to_id}")
async def update_relationship(
    from_id: str,
    to_id: str,
    rel_data: schemas.RelationshipUpdate,
    rel_type: str = Query(..., alias="type", description="Relationship type e.g. FRIEND"),
    current_user: database.User = Depends(auth.get_current_user),
):
    """Update properties on an existing relationship between two persons."""
    # Verify ownership of from_person
    person = await graph_db.get_person_node(from_id)
    if not person or person.get("user_id") != str(current_user.id):
        raise HTTPException(status_code=404, detail={"code": "PERSON_NOT_FOUND", "message": "Person not found"})

    props = {k: v for k, v in rel_data.model_dump(exclude_unset=True).items() if v is not None}
    result = await graph_db.update_relationship(from_id, to_id, rel_type, props)
    if not result:
        raise HTTPException(status_code=404, detail={"code": "RELATIONSHIP_NOT_FOUND", "message": "Relationship not found"})
    return result


@router.delete("/{from_id}/relationships/{to_id}")
async def delete_relationship(
    from_id: str,
    to_id: str,
    rel_type: str = Query(..., alias="type", description="Relationship type e.g. FRIEND"),
    current_user: database.User = Depends(auth.get_current_user),
):
    """Delete a relationship between two persons."""
    person = await graph_db.get_person_node(from_id)
    if not person or person.get("user_id") != str(current_user.id):
        raise HTTPException(status_code=404, detail={"code": "PERSON_NOT_FOUND", "message": "Person not found"})

    deleted = await graph_db.delete_relationship(from_id, to_id, rel_type)
    if not deleted:
        raise HTTPException(status_code=404, detail={"code": "RELATIONSHIP_NOT_FOUND", "message": "Relationship not found"})
    return {"status": "deleted", "from_id": from_id, "to_id": to_id, "type": rel_type}


# ---------------------------------------------------------------------------
# Search & Face Identification
# ---------------------------------------------------------------------------

@router.post("/search")
async def semantic_search_persons(
    search_req: schemas.SemanticSearchRequest,
    current_user: database.User = Depends(auth.get_current_user),
):
    """Search persons using semantic similarity."""
    from .. import embedding_service

    query_embedding = await run_in_threadpool(
        embedding_service.generate_text_embedding, search_req.query,
    )

    matches = await run_in_threadpool(
        vector_db.semantic_search,
        user_id=str(current_user.id),
        query_embedding=query_embedding,
        limit=search_req.limit,
    )

    person_ids = [match["person_id"] for match in matches]
    persons_map = await graph_db.get_person_nodes_batch(person_ids)

    results = []
    for match in matches:
        person = persons_map.get(match["person_id"])
        if person:
            results.append({**person, "similarity_score": match["similarity_score"]})

    return results


@router.post("/identify")
@limiter.limit("10/minute")
async def identify_person_from_face(
    request: Request,
    file: UploadFile = File(...),
    current_user: database.User = Depends(auth.get_current_user),
):
    """Upload a photo — detects ALL faces and matches each against the database."""
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "UNSUPPORTED_FILE_TYPE", "message": f"Unsupported file type: {file.content_type}. Allowed: {', '.join(ALLOWED_IMAGE_TYPES)}"},
        )

    buffer = BytesIO()
    size = 0
    while chunk := await file.read(CHUNK_SIZE):
        size += len(chunk)
        if size > MAX_UPLOAD_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail={"code": "FILE_TOO_LARGE", "message": f"File size exceeds maximum limit of {MAX_UPLOAD_SIZE / (1024*1024):.0f}MB"},
            )
        buffer.write(chunk)

    logger.info("Face identification requested: user_id=%s, content_type=%s", current_user.id, file.content_type)
    return await face_service.identify_faces_in_image(buffer.getvalue(), str(current_user.id))


@router.post("/{person_id}/face")
@limiter.limit("10/minute")
async def upload_person_face(
    request: Request,
    person_id: str,
    file: UploadFile = File(...),
    current_user: database.User = Depends(auth.get_current_user),
):
    """Upload a face photo for a known person."""
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "UNSUPPORTED_FILE_TYPE", "message": f"Unsupported file type: {file.content_type}. Allowed: {', '.join(ALLOWED_IMAGE_TYPES)}"},
        )

    person = await graph_db.get_person_node(person_id)
    if not person or person.get("user_id") != str(current_user.id):
        raise HTTPException(status_code=404, detail={"code": "PERSON_NOT_FOUND", "message": "Person not found"})

    ext = Path(file.filename or "face.jpg").suffix or ".jpg"
    filename = f"{person_id}{ext}"
    filepath = UPLOAD_DIR / "faces" / filename

    buffer = BytesIO()
    size = 0
    async with aiofiles.open(filepath, "wb") as f:
        while chunk := await file.read(CHUNK_SIZE):
            size += len(chunk)
            if size > MAX_UPLOAD_SIZE:
                await aiofiles.os.remove(filepath)
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail={"code": "FILE_TOO_LARGE", "message": f"File size exceeds maximum limit of {MAX_UPLOAD_SIZE / (1024*1024):.0f}MB"},
                )
            buffer.write(chunk)
            await f.write(chunk)
    final_image_bytes = buffer.getvalue()

    face_image_url = f"/uploads/faces/{filename}"

    face_vector = await run_in_threadpool(face_service.generate_face_embedding, final_image_bytes)
    await run_in_threadpool(vector_db.upsert_face_embedding, person_id, str(current_user.id), face_vector)

    await graph_db.update_person_node(person_id, face_image_url=face_image_url)

    logger.info("Face stored for person_id=%s", person_id)
    return {"message": "Face embedding stored", "person_id": person_id, "face_image_url": face_image_url}
