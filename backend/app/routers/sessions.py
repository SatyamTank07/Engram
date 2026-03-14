"""Session management routes."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import crud, schemas, database, auth

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])


@router.post("", response_model=schemas.SessionResponse)
def create_session(
    session_data: schemas.SessionCreate,
    current_user: database.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db),
):
    """Create a new chat session for the authenticated user."""
    session = crud.create_session(db, user_id=current_user.id, title=session_data.title)
    return session


@router.get("", response_model=list[schemas.SessionResponse])
def get_sessions(
    current_user: database.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db),
):
    """Get all chat sessions for the authenticated user."""
    return crud.get_user_sessions(db, current_user.id)


@router.get("/{session_id}/messages", response_model=list[schemas.MessageResponse])
def get_session_messages(
    session_id: str,
    current_user: database.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db),
):
    """Get all messages for a specific session."""
    session = crud.get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail={"code": "SESSION_NOT_FOUND", "message": "Session not found"})

    if session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail={"code": "ACCESS_DENIED", "message": "You do not have permission to access this resource"})

    return crud.get_session_messages(db, session_id)


@router.delete("/{session_id}")
def delete_session(
    session_id: str,
    current_user: database.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db),
):
    """Delete a chat session."""
    session = crud.get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail={"code": "SESSION_NOT_FOUND", "message": "Session not found"})

    if session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail={"code": "ACCESS_DENIED", "message": "You do not have permission to access this resource"})

    crud.delete_session(db, session_id)
    logger.info("Session deleted: session_id=%s, user_id=%s", session_id, current_user.id)
    return {"status": "deleted", "session_id": session_id}
