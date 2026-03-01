"""
MCP tools for PersonIdentity operations via Neo4j Knowledge Graph.
Each tool corresponds to a graph database operation.
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from backend.app import graph_db
from backend.app import embedding_service, vector_db

# For MVP: Hard-coded user ID (you'll need to replace this with actual user ID from your database)
# To get a user ID, run: SELECT id FROM users LIMIT 1;
# Or create a test user and use their ID
DEFAULT_USER_ID = os.getenv("MCP_DEFAULT_USER_ID", "replace-with-actual-user-uuid")


def create_person_tool(
    name: str,
    aliases: list[str] | None = None,
    contacts: dict | None = None,
    short_bio: str | None = None,
    trust_score: float | None = 0.0,
) -> dict:
    """
    Create a new person identity in the knowledge graph.
    
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
    try:
        person = graph_db.create_person_node(
            user_id=DEFAULT_USER_ID,
            name=name,
            aliases=aliases or [],
            contacts=contacts or {},
            short_bio=short_bio,
            trust_score=trust_score,
        )
        
        return {
            "success": True,
            "message": f"Successfully created person: {name}",
            "person": person,
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Error creating person: {str(e)}",
        }


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
    try:
        person = graph_db.get_person_node(person_id)
        
        if not person:
            return {
                "success": False,
                "message": f"Person with ID {person_id} not found",
            }
        
        if person.get("user_id") != DEFAULT_USER_ID:
            return {
                "success": False,
                "message": "Access denied: This person belongs to a different user",
            }
        
        return {
            "success": True,
            "person": person,
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Error retrieving person: {str(e)}",
        }


def list_persons_tool(limit: int | None = 50) -> dict:
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
    try:
        persons = graph_db.list_person_nodes(DEFAULT_USER_ID, limit or 50)
        
        return {
            "success": True,
            "count": len(persons),
            "persons": persons,
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Error listing persons: {str(e)}",
        }


def update_person_tool(
    person_id: str,
    name: str | None = None,
    aliases: list[str] | None = None,
    contacts: dict | None = None,
    short_bio: str | None = None,
    trust_score: float | None = None,
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
    try:
        # First check if person exists and belongs to user
        person = graph_db.get_person_node(person_id)
        if not person:
            return {
                "success": False,
                "message": f"Person with ID {person_id} not found",
            }
        
        if person.get("user_id") != DEFAULT_USER_ID:
            return {
                "success": False,
                "message": "Access denied: This person belongs to a different user",
            }
        
        # Update person
        updated_person = graph_db.update_person_node(
            person_id=person_id,
            name=name,
            aliases=aliases,
            contacts=contacts,
            short_bio=short_bio,
            trust_score=trust_score,
        )
        
        if not updated_person:
            return {
                "success": False,
                "message": "Failed to update person",
            }
        
        return {
            "success": True,
            "message": f"Successfully updated person: {updated_person.get('name', '')}",
            "person": updated_person,
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Error updating person: {str(e)}",
        }


def delete_person_tool(person_id: str) -> dict:
    """
    Delete a person from the knowledge graph.
    
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
    try:
        # Check if person exists and belongs to user
        person = graph_db.get_person_node(person_id)
        if not person:
            return {
                "success": False,
                "message": f"Person with ID {person_id} not found",
            }
        
        if person.get("user_id") != DEFAULT_USER_ID:
            return {
                "success": False,
                "message": "Access denied: This person belongs to a different user",
            }
        
        person_name = person.get("name", "Unknown")
        
        # Delete person (and all relationships)
        graph_db.delete_person_node(person_id)
        
        return {
            "success": True,
            "message": f"Successfully deleted person: {person_name}",
            "deleted_id": person_id,
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Error deleting person: {str(e)}",
        }


def search_person_tool(search_term: str) -> dict:
    """
    Search for persons using semantic similarity (with fallback to exact match).
    
    Use this when the user asks about a person by name, description, or any attribute.
    Now uses AI-powered semantic search for better matching.
    
    Args:
        search_term: Name, description, or any identifying text to search for
    
    Returns:
        Dictionary with matching persons and similarity scores
    
    Examples:
        - "Find John"
        - "Do you know anyone named Alice?"
        - "that engineer from Pune"
        - "the person who works at Google"
    """
    try:
        # Try semantic search first
        try:
            print(f"[SEARCH] Generating embedding for: '{search_term}'")
            query_embedding = embedding_service.generate_text_embedding(search_term)
            matches = vector_db.semantic_search(DEFAULT_USER_ID, query_embedding, limit=5)
            
            if matches:
                print(f"[SEARCH] ✅ Semantic search found {len(matches)} results:")
                persons = []
                for match in matches:
                    print(f"  → {match['text_content'][:60]}... (score: {match['similarity_score']})")
                    person = graph_db.get_person_node(match["person_id"])
                    if person:
                        person["similarity_score"] = match["similarity_score"]
                        persons.append(person)
                
                return {
                    "success": True,
                    "count": len(persons),
                    "search_term": search_term,
                    "search_type": "semantic",
                    "persons": persons,
                }
            else:
                print(f"[SEARCH] Semantic search returned 0 results, falling back to exact match")
        except Exception as e:
            print(f"[SEARCH] Semantic search failed ({e}), falling back to exact match")
        
        # Fallback: original exact match
        print(f"[SEARCH] Using exact match for: '{search_term}'")
        persons = graph_db.search_persons(DEFAULT_USER_ID, search_term)
        return {
            "success": True,
            "count": len(persons),
            "search_term": search_term,
            "search_type": "exact",
            "persons": persons,
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Error searching persons: {str(e)}",
        }


def add_relationship_tool(
    from_person_name: str,
    to_person_name: str,
    relationship_type: str,
    notes: str | None = None,
) -> dict:
    """
    Create a relationship between two people in the knowledge graph.
    
    Use this when the user describes how two people are connected.
    Both persons must already exist in the database — search for them first.
    
    Args:
        from_person_name: Name of the first person (will be searched by name to find ID)
        to_person_name: Name of the second person (will be searched by name to find ID)
        relationship_type: Type of relationship. Use one of: 
            KNOWS, FRIEND, FAMILY, COLLEAGUE, WORKS_WITH, MANAGES, REPORTS_TO, 
            MENTOR, PARTNER, NEIGHBOR, CLASSMATE
        notes: Optional notes about the relationship
    
    Returns:
        Dictionary with relationship details
    
    Examples:
        - "John is Alice's manager" → from=John, to=Alice, type=MANAGES
        - "Bob and Eve are friends" → from=Bob, to=Eve, type=FRIEND
        - "Sarah reports to Mike" → from=Sarah, to=Mike, type=REPORTS_TO
    """
    try:
        # Search for both persons
        from_results = graph_db.search_persons(DEFAULT_USER_ID, from_person_name)
        if not from_results:
            return {
                "success": False,
                "message": f"Person '{from_person_name}' not found. Create them first.",
            }
        
        to_results = graph_db.search_persons(DEFAULT_USER_ID, to_person_name)
        if not to_results:
            return {
                "success": False,
                "message": f"Person '{to_person_name}' not found. Create them first.",
            }
        
        from_person = from_results[0]
        to_person = to_results[0]
        
        properties = {}
        if notes:
            properties["notes"] = notes
        
        result = graph_db.add_relationship(
            from_person_id=from_person["id"],
            to_person_id=to_person["id"],
            rel_type=relationship_type,
            properties=properties,
        )
        
        if result:
            return {
                "success": True,
                "message": f"Created relationship: {from_person['name']} -{relationship_type}-> {to_person['name']}",
                "relationship": result,
            }
        else:
            return {
                "success": False,
                "message": "Failed to create relationship",
            }
    except Exception as e:
        return {
            "success": False,
            "message": f"Error creating relationship: {str(e)}",
        }


def get_relationships_tool(person_name: str) -> dict:
    """
    Get all relationships for a person in the knowledge graph.
    
    Use this when the user asks how someone is connected to others,
    or wants to see a person's network.
    
    Args:
        person_name: Name of the person to find relationships for
    
    Returns:
        Dictionary with list of relationships
    
    Examples:
        - "How is John connected to others?"
        - "Who does Alice know?"
        - "Show me Bob's relationships"
        - "What connections does Sarah have?"
    """
    try:
        results = graph_db.search_persons(DEFAULT_USER_ID, person_name)
        if not results:
            return {
                "success": False,
                "message": f"Person '{person_name}' not found.",
            }
        
        person = results[0]
        relationships = graph_db.get_relationships(person["id"])
        
        return {
            "success": True,
            "person": person["name"],
            "count": len(relationships),
            "relationships": relationships,
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Error getting relationships: {str(e)}",
        }