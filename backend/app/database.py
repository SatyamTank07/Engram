"""
Database models and connection for FastAPI backend.
"""

import logging
import os
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)
from sqlalchemy import create_engine, Column, String, Text, DateTime, ForeignKey, Boolean, Index, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

# Database connection
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/engram")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class User(Base):
    """Model for users."""
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    phone = Column(String(15), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    refresh_token_encrypted = Column(Text, nullable=True)
    refresh_token_expires_at = Column(DateTime, nullable=True)

    sessions = relationship("ChatSession", back_populates="user", cascade="all, delete-orphan")


class ChatSession(Base):
    """Model for chat sessions."""
    __tablename__ = "chat_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(255), default="New Chat")
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="sessions")
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")


class ChatMessage(Base):
    """Model for chat messages."""
    __tablename__ = "chat_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    session_id = Column(UUID(as_uuid=True), ForeignKey("chat_sessions.id"), nullable=False)
    role = Column(String(20), nullable=False)  # 'user' or 'assistant'
    content = Column(Text, nullable=False)
    image_url = Column(String(512), nullable=True)
    trace_json = Column(JSON, nullable=True)  # Agent/tool call trace for assistant messages
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('ix_chat_messages_session_timestamp', 'session_id', 'timestamp'),
    )

    session = relationship("ChatSession", back_populates="messages")


def init_db():
    """Initialize database tables."""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables initialized successfully")

        # Migrate: add trace_json column if it doesn't exist (safe for existing DBs)
        with engine.connect() as conn:
            from sqlalchemy import text, inspect
            inspector = inspect(engine)
            columns = [c["name"] for c in inspector.get_columns("chat_messages")]
            if "trace_json" not in columns:
                conn.execute(text("ALTER TABLE chat_messages ADD COLUMN trace_json JSON"))
                conn.commit()
                logger.info("Added trace_json column to chat_messages")
    except Exception as e:
        logger.critical("Failed to initialize database tables: %s", e)
        raise


def get_db():
    """Get database session dependency for FastAPI."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
