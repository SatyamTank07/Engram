# Shared Dockerfile for all A2A sub-agents (person, idea, content, project, orchestrator).
# Build context must be the project root so that agents/ and mcp_server/ are accessible.
#
# Usage (from project root):
#   docker build -f agents/Dockerfile --build-arg AGENT_MODULE=agents.person_agent.server -t engram-person-agent .

# ---- Stage 1: Builder ----
FROM python:3.11-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc g++ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY backend/requirements.txt .

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir -r requirements.txt

# ---- Stage 2: Runtime ----
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 libgomp1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd -r engram && useradd -r -g engram -m engram

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONPATH="/app"

# Copy agent code + shared dependencies
COPY agents/ /app/agents/
COPY mcp_server/ /app/mcp_server/

# Sub-agents import backend.app.{graph_db, vector_db, embedding_service, face_service}
# via mcp_server.tools — copy only the needed modules, not the full backend.
RUN mkdir -p /app/backend/app
RUN touch /app/backend/__init__.py /app/backend/app/__init__.py
COPY backend/app/graph_db.py /app/backend/app/graph_db.py
COPY backend/app/vector_db.py /app/backend/app/vector_db.py
COPY backend/app/embedding_service.py /app/backend/app/embedding_service.py
COPY backend/app/face_service.py /app/backend/app/face_service.py

RUN chown -R engram:engram /app

USER engram

# The agent module to run — overridden per service in docker-compose
ARG AGENT_MODULE=agents.orchestrator.server
ENV AGENT_MODULE=${AGENT_MODULE}

HEALTHCHECK --interval=15s --timeout=10s --start-period=60s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${AGENT_PORT:-5000}/.well-known/agent-card.json')" || exit 1

CMD ["sh", "-c", "python -m ${AGENT_MODULE}"]
