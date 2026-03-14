"""
Authentication utilities for JWT tokens, password hashing,
refresh-token encryption and httpOnly cookie management.
"""

import logging
import os
import secrets
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

from cryptography.fernet import Fernet, InvalidToken
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from . import database

# ---------------------------------------------------------------------------
# Security configuration
# ---------------------------------------------------------------------------
SECRET_KEY = os.environ.get("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY environment variable is not set. Cannot start.")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60            # 1 hour
REFRESH_TOKEN_EXPIRE_DAYS = 7               # 7 days

# Fernet key for encrypting refresh tokens at rest
TOKEN_ENCRYPTION_KEY = os.environ.get("TOKEN_ENCRYPTION_KEY")
if not TOKEN_ENCRYPTION_KEY:
    raise RuntimeError("TOKEN_ENCRYPTION_KEY environment variable is not set. Cannot start.")
_fernet = Fernet(TOKEN_ENCRYPTION_KEY.encode())

# Cookie settings
COOKIE_DOMAIN = os.environ.get("COOKIE_DOMAIN", None)   # None = current host
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "false").lower() == "true"
COOKIE_SAMESITE = "lax"
ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# HTTP Bearer (auto_error=False so cookie-based auth can also work)
security = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# Password helpers
# ---------------------------------------------------------------------------
def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


# ---------------------------------------------------------------------------
# Access token (short-lived stateless JWT)
# ---------------------------------------------------------------------------
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError as e:
        logger.warning("Invalid access token: %s", type(e).__name__)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_TOKEN", "message": "Could not validate credentials"},
        )


def decode_access_token_no_expiry(token: str) -> dict:
    """Decode JWT ignoring expiry — used during refresh to identify the user."""
    try:
        return jwt.decode(
            token, SECRET_KEY, algorithms=[ALGORITHM],
            options={"verify_exp": False},
        )
    except JWTError as e:
        logger.warning("Failed to decode access token (no-expiry mode): %s", type(e).__name__)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_TOKEN", "message": "Could not validate credentials"},
        )


# ---------------------------------------------------------------------------
# Refresh token (long-lived, encrypted at rest in User row)
# ---------------------------------------------------------------------------
def create_refresh_token(db: Session, user_id) -> str:
    """Generate a random refresh token, encrypt it, store on the User row."""
    raw_token = secrets.token_urlsafe(64)
    encrypted = _fernet.encrypt(raw_token.encode()).decode()
    expires_at = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    db.query(database.User).filter(database.User.id == user_id).update({
        "refresh_token_encrypted": encrypted,
        "refresh_token_expires_at": expires_at,
    })
    db.commit()
    logger.debug("Refresh token created for user_id=%s", user_id)
    return raw_token


def verify_refresh_token(db: Session, raw_token: str, user_id: str) -> database.User:
    """Decrypt the stored refresh token and compare with the provided one."""
    user = db.query(database.User).filter(database.User.id == user_id).first()
    if not user or not user.refresh_token_encrypted:
        logger.warning("Refresh token verification failed: user not found or no token stored, user_id=%s", user_id)
        raise HTTPException(
            status_code=401,
            detail={"code": "INVALID_REFRESH_TOKEN", "message": "Invalid refresh token"},
        )

    if user.refresh_token_expires_at and user.refresh_token_expires_at < datetime.utcnow():
        logger.warning("Refresh token expired for user_id=%s", user_id)
        raise HTTPException(
            status_code=401,
            detail={"code": "REFRESH_TOKEN_EXPIRED", "message": "Refresh token has expired"},
        )

    try:
        stored_token = _fernet.decrypt(user.refresh_token_encrypted.encode()).decode()
    except InvalidToken:
        logger.warning("Refresh token decryption failed for user_id=%s", user_id)
        raise HTTPException(
            status_code=401,
            detail={"code": "INVALID_REFRESH_TOKEN", "message": "Invalid refresh token"},
        )

    if not secrets.compare_digest(stored_token, raw_token):
        logger.warning("Refresh token mismatch for user_id=%s", user_id)
        raise HTTPException(
            status_code=401,
            detail={"code": "INVALID_REFRESH_TOKEN", "message": "Invalid refresh token"},
        )

    return user


def revoke_refresh_token(db: Session, user_id) -> None:
    """Clear the refresh token on the User row (logout / revoke)."""
    db.query(database.User).filter(database.User.id == user_id).update({
        "refresh_token_encrypted": None,
        "refresh_token_expires_at": None,
    })
    db.commit()
    logger.info("Refresh token revoked for user_id=%s", user_id)


# ---------------------------------------------------------------------------
# Cookie helpers
# ---------------------------------------------------------------------------
def set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    response.set_cookie(
        key=ACCESS_COOKIE,
        value=access_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
        domain=COOKIE_DOMAIN,
    )
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=refresh_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/api/v1/auth",          # only sent to auth endpoints
        domain=COOKIE_DOMAIN,
    )


def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(key=ACCESS_COOKIE, path="/", domain=COOKIE_DOMAIN)
    response.delete_cookie(key=REFRESH_COOKIE, path="/api/v1/auth", domain=COOKIE_DOMAIN)


# ---------------------------------------------------------------------------
# FastAPI dependency — get current user from cookie OR Bearer header
# ---------------------------------------------------------------------------
def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(database.get_db),
) -> database.User:
    # 1. Try httpOnly cookie
    token = request.cookies.get(ACCESS_COOKIE)
    # 2. Fallback to Bearer header (for MCP / programmatic clients)
    if not token and credentials:
        token = credentials.credentials
    if not token:
        logger.warning("Authentication failed: no token provided")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "NOT_AUTHENTICATED", "message": "Authentication required"},
        )

    payload = decode_access_token(token)
    user_id: str = payload.get("sub")
    if user_id is None:
        logger.warning("Authentication failed: token has no 'sub' claim")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_TOKEN", "message": "Access token is invalid"},
        )

    user = db.query(database.User).filter(database.User.id == user_id).first()
    if user is None:
        logger.warning("Authentication failed: user not found for id=%s", user_id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "USER_NOT_FOUND", "message": "User associated with this token no longer exists"},
        )

    return user
