"""
Database CRUD operations.
"""

from sqlalchemy.orm import Session
from . import database, schemas, auth


# User operations

def create_user(db: Session, phone: str, password: str) -> database.User:
    """Create a new user."""
    hashed_password = auth.hash_password(password)
    user = database.User(phone=phone, password_hash=hashed_password)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_user_by_phone(db: Session, phone: str) -> database.User | None:
    """Get a user by phone number."""
    return db.query(database.User).filter(database.User.phone == phone).first()


def get_user_by_id(db: Session, user_id: str) -> database.User | None:
    """Get a user by ID."""
    return db.query(database.User).filter(database.User.id == user_id).first()


# Session operations



def create_session(db: Session, user_id: str, title: str = "New Chat") -> database.ChatSession:
    """Create a new chat session for a user."""
    session = database.ChatSession(user_id=user_id, title=title)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session



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
    session = db.query(database.ChatSession).filter(database.ChatSession.id == session_id).first()
    if session:
        session.title = title[:255]
        db.commit()


def save_message(db: Session, session_id: str, role: str, content: str) -> database.ChatMessage:
    """Save a message to a chat session."""
    message = database.ChatMessage(session_id=session_id, role=role, content=content)
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


def get_session_messages(db: Session, session_id: str) -> list[database.ChatMessage]:
    """Get all messages for a chat session."""
    return db.query(database.ChatMessage).filter(
        database.ChatMessage.session_id == session_id
    ).order_by(database.ChatMessage.timestamp.asc()).all()


def delete_session(db: Session, session_id: str):
    """Delete a chat session and all its messages."""
    session = db.query(database.ChatSession).filter(database.ChatSession.id == session_id).first()
    if session:
        db.delete(session)
        db.commit()

        
# ==========================
# PersonIdentity operations
# ==========================

def create_person_identity(
    db: Session, 
    user_id: str, 
    name: str,
    aliases: list[str] = None,
    contacts: dict = None,
    short_bio: str = None,
    trust_score: float = 0.0
) -> database.PersonIdentity:
    """Create a new person identity."""
    person = database.PersonIdentity(
        user_id=user_id,
        name=name,
        aliases=aliases or [],
        contacts=contacts or {},
        short_bio=short_bio,
        trust_score=str(trust_score)
    )
    db.add(person)
    db.commit()
    db.refresh(person)
    return person


def get_person_identity(db: Session, person_id: str) -> database.PersonIdentity | None:
    """Get a person identity by ID."""
    return db.query(database.PersonIdentity).filter(database.PersonIdentity.id == person_id).first()


def get_user_person_identities(db: Session, user_id: str) -> list[database.PersonIdentity]:
    """Get all person identities for a specific user."""
    return db.query(database.PersonIdentity).filter(
        database.PersonIdentity.user_id == user_id
    ).order_by(database.PersonIdentity.last_seen.desc()).all()


def update_person_identity(
    db: Session,
    person_id: str,
    name: str = None,
    aliases: list[str] = None,
    contacts: dict = None,
    short_bio: str = None,
    trust_score: float = None
) -> database.PersonIdentity | None:
    """Update a person identity."""
    person = db.query(database.PersonIdentity).filter(database.PersonIdentity.id == person_id).first()
    if person:
        if name is not None:
            person.name = name
        if aliases is not None:
            person.aliases = aliases
        if contacts is not None:
            person.contacts = contacts
        if short_bio is not None:
            person.short_bio = short_bio
        if trust_score is not None:
            person.trust_score = str(trust_score)
        
        person.last_seen = datetime.utcnow()
        db.commit()
        db.refresh(person)
    return person


def delete_person_identity(db: Session, person_id: str):
    """Delete a person identity."""
    person = db.query(database.PersonIdentity).filter(database.PersonIdentity.id == person_id).first()
    if person:
        db.delete(person)
        db.commit()


def search_person_by_name(db: Session, user_id: str, search_term: str) -> list[database.PersonIdentity]:
    """Search person identities by name or aliases."""
    return db.query(database.PersonIdentity).filter(
        database.PersonIdentity.user_id == user_id,
        database.PersonIdentity.name.ilike(f"%{search_term}%")
    ).all()