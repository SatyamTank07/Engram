"""
System prompt for the Person sub-agent.
Rendered from Jinja2 template with dynamic context variables.
"""

from agents.common.prompt_loader import render_prompt

# Enum values injected into the template
RELATIONSHIP_TYPES = [
    "KNOWS", "FRIEND", "FAMILY", "COLLEAGUE", "WORKS_WITH", "MANAGES",
    "REPORTS_TO", "MENTOR", "PARTNER", "NEIGHBOR", "CLASSMATE", "EMPLOYS",
    "MARRIED_TO", "PARENT_OF", "INTRODUCED_BY", "RIVAL_OF", "FORMERLY_WORKED_WITH",
]

INTERACTION_FREQUENCIES = ["daily", "weekly", "monthly", "quarterly", "yearly", "rarely"]

# Default tool descriptions (used when tools list is not provided)
DEFAULT_TOOLS = [
    {"name": "create_person", "description": "Create a new person. Include all extractable fields. Optionally include relationship_with, relationship_type, and relationship_direction to create a relationship in the same call."},
    {"name": "search_person", "description": "Semantic search by name/description. Always search before creating."},
    {"name": "list_persons", "description": "List all persons. Supports pagination and filters (tags, location, occupation, company, interaction_frequency)."},
    {"name": "get_person", "description": "Fetch full details by ID."},
    {"name": "update_person", "description": "Modify person fields. Optionally include relationship_with, relationship_type, and relationship_direction to add a relationship in the same call."},
    {"name": "delete_person", "description": "Remove a person (only if user explicitly asks)."},
    {"name": "add_relationship", "description": "Create a relationship between two existing people. Use ONLY when both persons already exist and no create/update is needed."},
    {"name": "get_relationships", "description": "See all connections for a person."},
    {"name": "update_relationship", "description": "Update relationship properties (strength, context, dates, notes)."},
    {"name": "delete_relationship", "description": "Remove a relationship between two people."},
    {"name": "identify_face", "description": "Detect and identify faces in an uploaded image."},
    {"name": "store_person_face", "description": "Link a face photo to a person."},
]


def get_person_prompt(user_name: str | None = None, tools: list | None = None) -> str:
    """Render the person agent system prompt with context variables."""
    return render_prompt(
        "person_agent",
        user_name=user_name,
        tools=tools or DEFAULT_TOOLS,
        relationship_types=RELATIONSHIP_TYPES,
        interaction_frequencies=INTERACTION_FREQUENCIES,
    )


# Backwards-compatible constant (renders without user_name)
PERSON_AGENT_PROMPT = get_person_prompt()
