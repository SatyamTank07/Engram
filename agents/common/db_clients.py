"""
Database initialization helpers shared across all sub-agents.

Each sub-agent imports and calls init_databases() at startup to ensure
Neo4j schema and pgvector tables are ready.
"""

import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# Ensure project root is on sys.path so `backend.app.*` imports work.
_project_root = str(Path(__file__).parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


async def init_databases():
    """Initialize Neo4j schema + pgvector tables (idempotent)."""
    from backend.app import graph_db, vector_db

    logger.info("Initializing Neo4j schema …")
    await graph_db.init_graph_db()

    logger.info("Initializing pgvector tables …")
    vector_db.init_vector_db()

    logger.info("Databases ready.")
