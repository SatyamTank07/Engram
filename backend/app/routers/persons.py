"""Person identity routes (Neo4j knowledge graph + pgvector)."""

import logging
from io import BytesIO
from pathlib import Path

import aiofiles
import aiofiles.os
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, status
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
    person = await graph_db.create_person_node(
        user_id=str(current_user.id),
        name=person_data.name,
        aliases=person_data.aliases,
        contacts=person_data.contacts,
        short_bio=person_data.short_bio,
        trust_score=person_data.trust_score,
    )
    logger.info("Person created: name=%s, user_id=%s", person_data.name, current_user.id)
    return person


@router.get("")
async def get_persons(
    current_user: database.User = Depends(auth.get_current_user),
):
    """Get all person identities for the authenticated user from the knowledge graph."""
    return await graph_db.list_person_nodes(str(current_user.id))


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
    """Update a person identity in the knowledge graph."""
    person = await graph_db.get_person_node(person_id)
    if not person:
        raise HTTPException(status_code=404, detail={"code": "PERSON_NOT_FOUND", "message": "Person not found"})

    if person.get("user_id") != str(current_user.id):
        raise HTTPException(status_code=403, detail={"code": "ACCESS_DENIED", "message": "You do not have permission to access this resource"})

    updated_person = await graph_db.update_person_node(
        person_id,
        name=person_data.name,
        aliases=person_data.aliases,
        contacts=person_data.contacts,
        short_bio=person_data.short_bio,
        trust_score=person_data.trust_score,
    )
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
    """Get all connections (relationships + connected persons) for a person, rendered as a graph."""
    person = await graph_db.get_person_node(person_id)
    if not person:
        raise HTTPException(status_code=404, detail={"code": "PERSON_NOT_FOUND", "message": "Person not found"})

    if person.get("user_id") != str(current_user.id):
        raise HTTPException(status_code=403, detail={"code": "ACCESS_DENIED", "message": "You do not have permission to access this resource"})

    result = await graph_db.get_person_connections(person_id)
    return result


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
    """
    Upload a photo (single or group) — detects ALL faces and matches each
    against the database independently.
    """
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
