"""
Shared configuration for all A2A sub-agents.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# --- Agent ports ---
ORCHESTRATOR_PORT = int(os.getenv("ORCHESTRATOR_PORT", "5000"))
PERSON_AGENT_PORT = int(os.getenv("PERSON_AGENT_PORT", "5001"))
IDEA_AGENT_PORT = int(os.getenv("IDEA_AGENT_PORT", "5002"))
CONTENT_AGENT_PORT = int(os.getenv("CONTENT_AGENT_PORT", "5003"))
PROJECT_AGENT_PORT = int(os.getenv("PROJECT_AGENT_PORT", "5004"))

# --- LLM ---
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai").lower()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5-mini-2025-08-07")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_MODEL = os.getenv("GOOGLE_MODEL", "gemini-2.5-pro")

# --- Databases ---
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/engram")
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "engram_graph")

# --- Agent tool iteration limit ---
MAX_TOOL_ITERATIONS = int(os.getenv("MAX_TOOL_ITERATIONS", "15"))
MAX_HISTORY_PAIRS = int(os.getenv("MAX_HISTORY_PAIRS", "10"))

