# ---- Stage 1: Builder ----
FROM python:3.11-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc g++ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY backend/requirements.txt .

# Install into a virtualenv so we can cleanly copy just the deps
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir -r requirements.txt

# ---- Stage 2: Runtime ----
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 libgomp1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r engram && useradd -r -g engram -m engram

WORKDIR /app

# Copy only the virtualenv from builder (no gcc/g++, no build artifacts)
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONPATH="/app"

# Preserve repo directory structure so imports like
# "from backend.app import ..." and "from mcp_server.tools import ..." work
COPY backend/ /app/backend/
COPY mcp_server/ /app/mcp_server/

# Create directories and set ownership (including insightface model cache)
RUN mkdir -p /app/backend/uploads/chat /app/backend/uploads/faces /home/engram/.insightface \
    && chown -R engram:engram /app /home/engram/.insightface

USER engram

# InsightFace buffalo_l model (~300MB) is downloaded on first startup.
# Mount a volume at /home/engram/.insightface to persist it across restarts.

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/readyz')" || exit 1

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
