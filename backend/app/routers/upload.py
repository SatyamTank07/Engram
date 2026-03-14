"""Image upload route."""

import logging
import uuid
from pathlib import Path

import aiofiles
import aiofiles.os
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status

from .. import database, auth
from .deps import MAX_UPLOAD_SIZE, ALLOWED_IMAGE_TYPES, CHUNK_SIZE, UPLOAD_DIR

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/upload", tags=["upload"])


@router.post("")
async def upload_image(
    file: UploadFile = File(...),
    current_user: database.User = Depends(auth.get_current_user),
):
    """Upload an image and return its URL."""
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "UNSUPPORTED_FILE_TYPE", "message": f"Unsupported file type: {file.content_type}. Allowed: {', '.join(ALLOWED_IMAGE_TYPES)}"},
        )

    ext = Path(file.filename or "image.jpg").suffix or ".jpg"
    filename = f"{uuid.uuid4()}{ext}"
    filepath = UPLOAD_DIR / "chat" / filename

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
            await f.write(chunk)

    logger.info("Image uploaded: filename=%s, size=%d bytes, user_id=%s", filename, size, current_user.id)
    return {"url": f"/uploads/chat/{filename}"}
