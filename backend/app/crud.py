"""
Database CRUD operations.
"""

import logging
from datetime import datetime
from sqlalchemy.orm import Session
from . import database, schemas, auth

logger = logging.getLogger(__name__)


# User operations

def create_user(db: Session, phone: str, password: str) -> database.User:
    """Create a new user."""
    try:
        hashed_password = auth.hash_password(password)
        user = database.User(phone=phone, password_hash=hashed_password)
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    except Exception as e:
        logger.error("Failed to create user: %s", e)
        db.rollback()
        raise


def get_user_by_phone(db: Session, phone: str) -> database.User | None:
    """Get a user by phone number."""
    return db.query(database.User).filter(database.User.phone == phone).first()


def get_user_by_id(db: Session, user_id: str) -> database.User | None:
    """Get a user by ID."""
    return db.query(database.User).filter(database.User.id == user_id).first()


# Session operations



def create_session(db: Session, user_id: str, title: str = "New Chat") -> database.ChatSession:
    """Create a new chat session for a user."""
    try:
        session = database.ChatSession(user_id=user_id, title=title)
        db.add(session)
        db.commit()
        db.refresh(session)
        return session
    except Exception as e:
        logger.error("Failed to create session for user_id=%s: %s", user_id, e)
        db.rollback()
        raise



def get_user_sessions(db: Session, user_id: str) -> list[database.ChatSession]:
    """Get all chat sessions for a specific user."""
    return db.query(database.ChatSession).filter(
        database.ChatSession.user_id == user_id
    ).order_by(database.ChatSession.created_at.desc()).all()


def get_session(db: Session, session_id: str) -> database.ChatSession | None:
    """Get a specific chat session."""
    return db.query(database.ChatSession).filter(database.ChatSession.id == session_id).first()


def update_session_title(db: Session, session_id: str, title: str):
    """Update the title of a chat session."""
    try:
        session = db.query(database.ChatSession).filter(database.ChatSession.id == session_id).first()
        if session:
            session.title = title[:255]
            db.commit()
    except Exception as e:
        logger.error("Failed to update session title for session_id=%s: %s", session_id, e)
        db.rollback()
        raise


def save_message(db: Session, session_id: str, role: str, content: str, image_url: str | None = None) -> database.ChatMessage:
    """Save a message to a chat session."""
    try:
        message = database.ChatMessage(session_id=session_id, role=role, content=content, image_url=image_url)
        db.add(message)
        db.commit()
        db.refresh(message)
        return message
    except Exception as e:
        logger.error("Failed to save message to session_id=%s: %s", session_id, e)
        db.rollback()
        raise


def get_session_messages(db: Session, session_id: str) -> list[database.ChatMessage]:
    """Get all messages for a chat session."""
    return db.query(database.ChatMessage).filter(
        database.ChatMessage.session_id == session_id
    ).order_by(database.ChatMessage.timestamp.asc()).all()


def delete_session(db: Session, session_id: str):
    """Delete a chat session and all its messages."""
    try:
        session = db.query(database.ChatSession).filter(database.ChatSession.id == session_id).first()
        if session:
            db.delete(session)
            db.commit()
    except Exception as e:
        logger.error("Failed to delete session_id=%s: %s", session_id, e)
        db.rollback()
        raise
