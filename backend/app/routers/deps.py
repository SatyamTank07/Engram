"""Shared constants and utilities used across routers."""

from pathlib import Path

from slowapi import Limiter
from slowapi.util import get_remote_address

# Rate limiter (shared instance — attached to app.state in main.py)
limiter = Limiter(key_func=get_remote_address)

# File upload constraints
MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
CHUNK_SIZE = 1024 * 1024  # 1 MB

# Upload directories
UPLOAD_DIR = Path(__file__).parent.parent.parent / "uploads"
(UPLOAD_DIR / "chat").mkdir(parents=True, exist_ok=True)
(UPLOAD_DIR / "faces").mkdir(parents=True, exist_ok=True)
