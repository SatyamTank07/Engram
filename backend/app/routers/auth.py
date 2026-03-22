"""Authentication routes: register, login, me, refresh, logout."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from .. import crud, schemas, database, auth
from .deps import limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/register", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
def register(
    request: Request,
    user_data: schemas.RegisterRequest,
    db: Session = Depends(database.get_db),
):
    """Register a new user (admin use only - call via curl)."""
    existing_user = crud.get_user_by_phone(db, user_data.phone)
    if existing_user:
        logger.warning("Registration failed: phone already registered")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "PHONE_ALREADY_REGISTERED", "message": "Phone number already registered"},
        )

    try:
        user = crud.create_user(db, user_data.phone, user_data.password, name=user_data.name)
        logger.info("New user registered: user_id=%s", user.id)
        return user
    except IntegrityError:
        logger.warning("Registration failed: IntegrityError during user creation")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "USER_CREATION_FAILED", "message": "User creation failed"},
        )


@router.post("/login", response_model=schemas.LoginResponse)
@limiter.limit("5/minute")
def login(
    request: Request,
    login_data: schemas.LoginRequest,
    response: Response,
    db: Session = Depends(database.get_db),
):
    """Login with phone and password. Tokens set via httpOnly cookies."""
    user = crud.get_user_by_phone(db, login_data.phone)
    if not user or not auth.verify_password(login_data.password, user.password_hash):
        logger.warning("Failed login attempt: phone=%s", login_data.phone[-4:].rjust(len(login_data.phone), '*'))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_CREDENTIALS", "message": "Invalid phone number or password"},
        )

    access_token = auth.create_access_token(data={"sub": str(user.id)})
    refresh_token = auth.create_refresh_token(db, user.id)
    auth.set_auth_cookies(response, access_token, refresh_token)
    logger.info("User logged in: user_id=%s", user.id)

    return schemas.LoginResponse(
        expires_in=auth.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=user,
    )


@router.get("/me", response_model=schemas.UserResponse)
def get_current_user_info(
    current_user: database.User = Depends(auth.get_current_user),
):
    """Get current authenticated user."""
    return current_user


@router.post("/refresh", response_model=schemas.RefreshResponse)
def refresh_token(
    request: Request,
    response: Response,
    db: Session = Depends(database.get_db),
):
    """Refresh the access token using the refresh-token cookie."""
    old_refresh = request.cookies.get(auth.REFRESH_COOKIE)
    old_access = request.cookies.get(auth.ACCESS_COOKIE)
    if not old_refresh or not old_access:
        raise HTTPException(
            status_code=401,
            detail={"code": "MISSING_AUTH_COOKIES", "message": "Missing authentication cookies"},
        )

    payload = auth.decode_access_token_no_expiry(old_access)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=401,
            detail={"code": "INVALID_TOKEN", "message": "Access token is invalid"},
        )

    auth.verify_refresh_token(db, old_refresh, user_id)
    new_access = auth.create_access_token(data={"sub": user_id})
    new_refresh = auth.create_refresh_token(db, user_id)  # rotation
    auth.set_auth_cookies(response, new_access, new_refresh)

    return schemas.RefreshResponse(expires_in=auth.ACCESS_TOKEN_EXPIRE_MINUTES * 60)


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(database.get_db),
):
    """Logout — revoke refresh token and clear cookies."""
    access_token = request.cookies.get(auth.ACCESS_COOKIE)
    user_id = None
    if access_token:
        try:
            payload = auth.decode_access_token_no_expiry(access_token)
            user_id = payload.get("sub")
            if user_id:
                auth.revoke_refresh_token(db, user_id)
        except Exception as e:
            logger.warning("Best-effort token revocation failed: %s", e)
    auth.clear_auth_cookies(response)
    logger.info("User logged out: user_id=%s", user_id or "unknown")
    return {"status": "logged out"}
