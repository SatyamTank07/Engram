"""
MCP tools for PersonIdentity CRUD operations.
Each tool corresponds to a database operation.
"""

import os
import sys
from pathlib import Path
from typing import Optional

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from backend.app import database, crud
from sqlalchemy.orm import Session

# For MVP: Hard-coded user ID (you'll need to replace this with actual user ID from your database)
# To get a user ID, run: SELECT id FROM users LIMIT 1;
# Or create a test user and use their ID
DEFAULT_USER_ID = os.getenv("MCP_DEFAULT_USER_ID", "replace-with-actual-user-uuid")


def get_db() -> Session:
    """Get database session."""
    db = database.SessionLocal()
    try:
        return db
    except Exception as e:
        db.close()
        raise e


def create_person_tool(
    name: str,
    aliases: Optional[list[str]] = None,
    contacts: Optional[dict] = None,
    short_bio: Optional[str] = None,
    trust_score: Optional[float] = 0.0
) -> dict:
    """
    Create a new person identity in the database.
    
    Use this when the user asks to remember, save, or store information about a person.
    
    Args:
        name: Full canonical name of the person (required)
        aliases: List of alternative names, nicknames, or previous names
        contacts: Dictionary containing contact information (phone, email, social_media, etc.)
        short_bio: Brief biography, description, or notes about the person
        trust_score: Confidence level in the information (0.0 to 1.0, default 0.0)
    
    Returns:
        Dictionary with person details and success status
    
    Examples:
        - "Remember John Doe works at Google" 
        - "Store info about Alice: she's a software engineer, email alice@example.com"
        - "Save that Bob Smith (also known as Bobby) is my colleague"
    """
    db = get_db()
    try:
        person = crud.create_person_identity(
            db=db,
            user_id=DEFAULT_USER_ID,
            name=name,
            aliases=aliases or [],
            contacts=contacts or {},
            short_bio=short_bio,
            trust_score=trust_score
        )
        
        return {
            "success": True,
            "message": f"Successfully created person: {name}",
            "person": {
                "id": str(person.id),
                "name": person.name,
                "aliases": person.aliases,
                "contacts": person.contacts,
                "short_bio": person.short_bio,
                "trust_score": person.trust_score,
                "first_seen": person.first_seen.isoformat(),
                "last_seen": person.last_seen.isoformat()
            }
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Error creating person: {str(e)}"
        }
    finally:
        db.close()


def get_person_tool(person_id: str) -> dict:
    """
    Get details of a specific person by their ID.
    
    Use this when you need to retrieve full information about a person using their ID.
    
    Args:
        person_id: UUID of the person to retrieve
    
    Returns:
        Dictionary with person details or error message
    
    Examples:
        - "Show me details for person ID abc-123"
        - "Get information about person xyz-789"
    """
    db = get_db()
    try:
        person = crud.get_person_identity(db, person_id)
        
        if not person:
            return {
                "success": False,
                "message": f"Person with ID {person_id} not found"
            }
        
        if str(person.user_id) != DEFAULT_USER_ID:
            return {
                "success": False,
                "message": "Access denied: This person belongs to a different user"
            }
        
        return {
            "success": True,
            "person": {
                "id": str(person.id),
                "name": person.name,
                "aliases": person.aliases,
                "contacts": person.contacts,
                "short_bio": person.short_bio,
                "trust_score": person.trust_score,
                "first_seen": person.first_seen.isoformat(),
                "last_seen": person.last_seen.isoformat()
            }
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Error retrieving person: {str(e)}"
        }
    finally:
        db.close()


def list_persons_tool(limit: Optional[int] = 50) -> dict:
    """
    List all saved persons for the current user.
    
    Use this when the user asks to see all people, list contacts, or show saved persons.
    
    Args:
        limit: Maximum number of persons to return (default 50)
    
    Returns:
        Dictionary with list of persons and count
    
    Examples:
        - "Show me all the people I've saved"
        - "List everyone in my contacts"
        - "Who do you know about?"
    """
    db = get_db()
    try:
        persons = crud.get_user_person_identities(db, DEFAULT_USER_ID)
        
        # Apply limit
        persons = persons[:limit]
        
        persons_list = [
            {
                "id": str(p.id),
                "name": p.name,
                "aliases": p.aliases,
                "contacts": p.contacts,
                "short_bio": p.short_bio,
                "trust_score": p.trust_score,
                "first_seen": p.first_seen.isoformat(),
                "last_seen": p.last_seen.isoformat()
            }
            for p in persons
        ]
        
        return {
            "success": True,
            "count": len(persons_list),
            "persons": persons_list
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Error listing persons: {str(e)}"
        }
    finally:
        db.close()


def update_person_tool(
    person_id: str,
    name: Optional[str] = None,
    aliases: Optional[list[str]] = None,
    contacts: Optional[dict] = None,
    short_bio: Optional[str] = None,
    trust_score: Optional[float] = None
) -> dict:
    """
    Update an existing person's information.
    
    Use this when the user wants to modify, update, or change information about a person.
    Only provided fields will be updated; others remain unchanged.
    
    Args:
        person_id: UUID of the person to update (required)
        name: New canonical name
        aliases: New list of aliases (replaces existing)
        contacts: New contact information (replaces existing)
        short_bio: New biography or notes
        trust_score: New confidence score (0.0 to 1.0)
    
    Returns:
        Dictionary with updated person details
    
    Examples:
        - "Update John's email to john@newcompany.com"
        - "Change Alice's bio to say she now works at Meta"
        - "Add 'Bobby' as an alias for Bob Smith"
    """
    db = get_db()
    try:
        # First check if person exists and belongs to user
        person = crud.get_person_identity(db, person_id)
        if not person:
            return {
                "success": False,
                "message": f"Person with ID {person_id} not found"
            }
        
        if str(person.user_id) != DEFAULT_USER_ID:
            return {
                "success": False,
                "message": "Access denied: This person belongs to a different user"
            }
        
        # Update person
        updated_person = crud.update_person_identity(
            db=db,
            person_id=person_id,
            name=name,
            aliases=aliases,
            contacts=contacts,
            short_bio=short_bio,
            trust_score=trust_score
        )
        
        if not updated_person:
            return {
                "success": False,
                "message": "Failed to update person"
            }
        
        return {
            "success": True,
            "message": f"Successfully updated person: {updated_person.name}",
            "person": {
                "id": str(updated_person.id),
                "name": updated_person.name,
                "aliases": updated_person.aliases,
                "contacts": updated_person.contacts,
                "short_bio": updated_person.short_bio,
                "trust_score": updated_person.trust_score,
                "first_seen": updated_person.first_seen.isoformat(),
                "last_seen": updated_person.last_seen.isoformat()
            }
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Error updating person: {str(e)}"
        }
    finally:
        db.close()


def delete_person_tool(person_id: str) -> dict:
    """
    Delete a person from the database.
    
    Use this when the user wants to remove, delete, or forget about a person.
    This action cannot be undone.
    
    Args:
        person_id: UUID of the person to delete (required)
    
    Returns:
        Dictionary with deletion status
    
    Examples:
        - "Delete John Doe"
        - "Remove the person with ID abc-123"
        - "Forget about Alice"
    """
    db = get_db()
    try:
        # Check if person exists and belongs to user
        person = crud.get_person_identity(db, person_id)
        if not person:
            return {
                "success": False,
                "message": f"Person with ID {person_id} not found"
            }
        
        if str(person.user_id) != DEFAULT_USER_ID:
            return {
                "success": False,
                "message": "Access denied: This person belongs to a different user"
            }
        
        person_name = person.name
        
        # Delete person
        crud.delete_person_identity(db, person_id)
        
        return {
            "success": True,
            "message": f"Successfully deleted person: {person_name}",
            "deleted_id": person_id
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Error deleting person: {str(e)}"
        }
    finally:
        db.close()


def search_person_tool(search_term: str) -> dict:
    """
    Search for persons by name.
    
    Use this when the user asks about a person by name but you don't have their ID.
    Searches in the name field (case-insensitive partial match).
    
    Args:
        search_term: Name or partial name to search for
    
    Returns:
        Dictionary with matching persons
    
    Examples:
        - "Find John"
        - "Do you know anyone named Alice?"
        - "Search for people with 'Smith' in their name"
    """
    db = get_db()
    try:
        persons = crud.search_person_by_name(db, DEFAULT_USER_ID, search_term)
        
        persons_list = [
            {
                "id": str(p.id),
                "name": p.name,
                "aliases": p.aliases,
                "contacts": p.contacts,
                "short_bio": p.short_bio,
                "trust_score": p.trust_score,
                "first_seen": p.first_seen.isoformat(),
                "last_seen": p.last_seen.isoformat()
            }
            for p in persons
        ]
        
        return {
            "success": True,
            "count": len(persons_list),
            "search_term": search_term,
            "persons": persons_list
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Error searching persons: {str(e)}"
        }
    finally:
        db.close()