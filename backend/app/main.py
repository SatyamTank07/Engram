"""
FastAPI main application with chat endpoints.
"""

import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from io import BytesIO
from pathlib import Path

import aiofiles
import aiofiles.os

from fastapi import FastAPI, Depends, HTTPException, Request, Response, status, UploadFile, File
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from . import crud, schemas, database, agent, auth, graph_db, vector_db, face_service, sync_worker

# File upload constraints
MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
CHUNK_SIZE = 1024 * 1024  # 1MB

# Ensure upload directories exist
UPLOAD_DIR = Path(__file__).parent.parent / "uploads"
(UPLOAD_DIR / "chat").mkdir(parents=True, exist_ok=True)
(UPLOAD_DIR / "faces").mkdir(parents=True, exist_ok=True)

# Initialize database
database.init_db()

# Initialize pgvector extension and embeddings table
try:
    vector_db.init_vector_db()
    print("pgvector initialized successfully.")
except Exception as e:
    print(f"Warning: Could not initialize pgvector: {e}. Semantic search may not work.")

# Neo4j is initialized asynchronously in the lifespan handler below.

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app):
    """Startup: eagerly load heavy models + init Neo4j. Shutdown: release connection pools."""
    await run_in_threadpool(face_service.init_face_model)
    try:
        await graph_db.init_graph_db()
        print("Neo4j knowledge graph initialized successfully.")
    except Exception as e:
        print(f"Warning: Could not initialize Neo4j: {e}. Person identity features may not work.")

    # Start background embedding sync worker
    sync_task = asyncio.create_task(sync_worker.run_sync_worker())

    yield

    # Shutdown: cancel sync worker, close connections
    sync_task.cancel()
    try:
        await sync_task
    except asyncio.CancelledError:
        pass
    await graph_db.Neo4jConnection.close()
    vector_db.close_pool()


# Create FastAPI app
app = FastAPI(
    title="Chat API",
    description="FastAPI backend for chat application with LangChain",
    version="1.0.0",
    lifespan=lifespan,
)

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Serve uploaded images
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

# CORS middleware for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://192.168.1.12:3000"],  # Next.js default port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    """Health check endpoint."""
    return {"status": "ok", "message": "Chat API is running"}


@app.get("/readyz")
def readiness_check():
    """Readiness probe — returns 503 until the face model is loaded."""
    if not face_service.is_model_ready():
        return Response(status_code=503, content="Face model loading...")
    return {"status": "ready"}


@app.get("/admin/pending-syncs")
async def pending_sync_stats(
    current_user: database.User = Depends(auth.get_current_user),
):
    """Return counts of pending/failed embedding sync operations."""
    stats = await run_in_threadpool(vector_db.get_pending_sync_stats)
    return stats


# Authentication endpoints

@app.post("/api/auth/register", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
def register(
    request: Request,
    user_data: schemas.RegisterRequest,
    db: Session = Depends(database.get_db)
):
    """Register a new user (admin use only - call via curl)."""
    # Check if user already exists
    existing_user = crud.get_user_by_phone(db, user_data.phone)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phone number already registered"
        )
    
    try:
        user = crud.create_user(db, user_data.phone, user_data.password)
        return user
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User creation failed"
        )


@app.post("/api/auth/login", response_model=schemas.LoginResponse)
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
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    access_token = auth.create_access_token(data={"sub": str(user.id)})
    refresh_token = auth.create_refresh_token(db, user.id)
    auth.set_auth_cookies(response, access_token, refresh_token)

    return schemas.LoginResponse(
        expires_in=auth.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=user,
    )


@app.get("/api/auth/me", response_model=schemas.UserResponse)
def get_current_user_info(
    current_user: database.User = Depends(auth.get_current_user)
):
    """Get current authenticated user."""
    return current_user


@app.post("/api/auth/refresh", response_model=schemas.RefreshResponse)
def refresh_token(
    request: Request,
    response: Response,
    db: Session = Depends(database.get_db),
):
    """Refresh the access token using the refresh-token cookie."""
    old_refresh = request.cookies.get(auth.REFRESH_COOKIE)
    old_access = request.cookies.get(auth.ACCESS_COOKIE)
    if not old_refresh or not old_access:
        raise HTTPException(status_code=401, detail="Missing auth cookies")

    # Decode expired access token to get user_id (signature still verified)
    payload = auth.decode_access_token_no_expiry(old_access)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    # Verify + rotate refresh token
    auth.verify_refresh_token(db, old_refresh, user_id)
    new_access = auth.create_access_token(data={"sub": user_id})
    new_refresh = auth.create_refresh_token(db, user_id)  # rotation
    auth.set_auth_cookies(response, new_access, new_refresh)

    return schemas.RefreshResponse(expires_in=auth.ACCESS_TOKEN_EXPIRE_MINUTES * 60)


@app.post("/api/auth/logout")
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(database.get_db),
):
    """Logout — revoke refresh token and clear cookies."""
    access_token = request.cookies.get(auth.ACCESS_COOKIE)
    if access_token:
        try:
            payload = auth.decode_access_token_no_expiry(access_token)
            user_id = payload.get("sub")
            if user_id:
                auth.revoke_refresh_token(db, user_id)
        except Exception:
            pass  # best-effort revocation
    auth.clear_auth_cookies(response)
    return {"status": "logged out"}


# Session endpoints



@app.post("/api/sessions", response_model=schemas.SessionResponse)
def create_session(
    session_data: schemas.SessionCreate,
    current_user: database.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db)
):
    """Create a new chat session for the authenticated user."""
    session = crud.create_session(db, user_id=current_user.id, title=session_data.title)
    return session



@app.get("/api/sessions", response_model=list[schemas.SessionResponse])
def get_sessions(
    current_user: database.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db)
):
    """Get all chat sessions for the authenticated user."""
    return crud.get_user_sessions(db, current_user.id)



@app.get("/api/sessions/{session_id}/messages", response_model=list[schemas.MessageResponse])
def get_session_messages(
    session_id: str,
    current_user: database.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db)
):
    """Get all messages for a specific session."""
    # Verify session exists and belongs to user
    session = crud.get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return crud.get_session_messages(db, session_id)



@app.delete("/api/sessions/{session_id}")
def delete_session(
    session_id: str,
    current_user: database.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db)
):
    """Delete a chat session."""
    # Verify session exists and belongs to user
    session = crud.get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    crud.delete_session(db, session_id)
    return {"status": "deleted", "session_id": session_id}



@app.post("/api/chat", response_model=schemas.ChatResponse)
@limiter.limit("20/minute")
async def chat(
    request: Request,
    chat_request: schemas.ChatRequest,
    current_user: database.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db)
):
    """
    Send a message and get AI response.
    """
    # Verify session exists and belongs to user
    session = crud.get_session(db, chat_request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Get chat history
    messages = crud.get_session_messages(db, chat_request.session_id)
    chat_history = [
        {"role": msg.role, "content": msg.content}
        for msg in messages
    ]

    # Save user message
    user_message = crud.save_message(
        db,
        chat_request.session_id,
        "user",
        chat_request.message,
        image_url=chat_request.image_url,
    )

    # Update session title if this is the first message
    if len(messages) == 0:
        title = chat_request.message[:50]
        if len(chat_request.message) > 50:
            title += "..."
        crud.update_session_title(db, chat_request.session_id, title)

    try:
        # Get AI response (async — tools natively await Neo4j on this event loop)
        ai_response = await agent.get_agent_response(
            chat_request.message, chat_history, chat_request.image_url,
            user_id=str(current_user.id),
        )

        # Save assistant message
        assistant_message = crud.save_message(
            db,
            chat_request.session_id,
            "assistant",
            ai_response
        )

        return schemas.ChatResponse(
            session_id=chat_request.session_id,
            user_message=user_message,
            assistant_message=assistant_message
        )

    except Exception as e:
        # If AI fails, still return user message but with error
        raise HTTPException(status_code=500, detail=str(e))

# Image upload endpoint

@app.post("/api/upload")
async def upload_image(
    file: UploadFile = File(...),
    current_user: database.User = Depends(auth.get_current_user),
):
    """Upload an image and return its URL."""
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {file.content_type}. Allowed types are: {', '.join(ALLOWED_IMAGE_TYPES)}"
        )
    
    ext = Path(file.filename or "image.jpg").suffix or ".jpg"
    filename = f"{uuid.uuid4()}{ext}"
    filepath = UPLOAD_DIR / "chat" / filename

    size = 0
    async with aiofiles.open(filepath, "wb") as f:
        while chunk := await file.read(CHUNK_SIZE):
            size += len(chunk)
            if size > MAX_UPLOAD_SIZE:
                await aiofiles.os.remove(filepath)
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"File size exceeds maximum limit of {MAX_UPLOAD_SIZE / (1024*1024)}MB"
                )
            await f.write(chunk)

    return {"url": f"/uploads/chat/{filename}"}


# PersonIdentity endpoints (powered by Neo4j Knowledge Graph)

@app.post("/api/persons", status_code=status.HTTP_201_CREATED)
async def create_person(
    person_data: schemas.PersonIdentityCreate,
    current_user: database.User = Depends(auth.get_current_user),
):
    """Create a new person identity in the knowledge graph."""
    person = await graph_db.create_person_node(
        user_id=str(current_user.id),
        name=person_data.name,
        aliases=person_data.aliases,
        contacts=person_data.contacts,
        short_bio=person_data.short_bio,
        trust_score=person_data.trust_score,
    )
    return person


@app.get("/api/persons")
async def get_persons(
    current_user: database.User = Depends(auth.get_current_user),
):
    """Get all person identities for the authenticated user from the knowledge graph."""
    return await graph_db.list_person_nodes(str(current_user.id))


@app.get("/api/persons/{person_id}")
async def get_person(
    person_id: str,
    current_user: database.User = Depends(auth.get_current_user),
):
    """Get a specific person identity from the knowledge graph."""
    person = await graph_db.get_person_node(person_id)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    if person.get("user_id") != str(current_user.id):
        raise HTTPException(status_code=403, detail="Access denied")

    return person


@app.put("/api/persons/{person_id}")
async def update_person(
    person_id: str,
    person_data: schemas.PersonIdentityUpdate,
    current_user: database.User = Depends(auth.get_current_user),
):
    """Update a person identity in the knowledge graph."""
    person = await graph_db.get_person_node(person_id)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    if person.get("user_id") != str(current_user.id):
        raise HTTPException(status_code=403, detail="Access denied")

    updated_person = await graph_db.update_person_node(
        person_id,
        name=person_data.name,
        aliases=person_data.aliases,
        contacts=person_data.contacts,
        short_bio=person_data.short_bio,
        trust_score=person_data.trust_score,
    )
    return updated_person


@app.delete("/api/persons/{person_id}")
async def delete_person(
    person_id: str,
    current_user: database.User = Depends(auth.get_current_user),
):
    """Delete a person identity from the knowledge graph."""
    person = await graph_db.get_person_node(person_id)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    if person.get("user_id") != str(current_user.id):
        raise HTTPException(status_code=403, detail="Access denied")

    await graph_db.delete_person_node(person_id)
    return {"status": "deleted", "person_id": person_id}


@app.post("/api/persons/search")
async def semantic_search_persons(
    search_req: schemas.SemanticSearchRequest,
    current_user: database.User = Depends(auth.get_current_user),
):
    """Search persons using semantic similarity."""
    from . import embedding_service

    # Generate embedding for the search query
    query_embedding = await run_in_threadpool(
        embedding_service.generate_text_embedding, search_req.query
    )

    # Search pgvector for similar persons
    matches = await run_in_threadpool(
        vector_db.semantic_search,
        user_id=str(current_user.id),
        query_embedding=query_embedding,
        limit=search_req.limit,
    )

    # Batch enrich with full Neo4j data — 1 query instead of N
    person_ids = [match["person_id"] for match in matches]
    persons_map = await graph_db.get_person_nodes_batch(person_ids)

    results = []
    for match in matches:
        person = persons_map.get(match["person_id"])
        if person:
            results.append({
                **person,
                "similarity_score": match["similarity_score"],
            })

    return results


@app.post("/api/persons/identify")
@limiter.limit("10/minute")
async def identify_person_from_face(
    request: Request,
    file: UploadFile = File(...),
    current_user: database.User = Depends(auth.get_current_user),
):
    """
    Upload a photo (single or group) — detects ALL faces and matches each
    against the database independently. Returns per-face results with
    bounding boxes and match info.
    """
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {file.content_type}. Allowed types are: {', '.join(ALLOWED_IMAGE_TYPES)}"
        )
        
    buffer = BytesIO()
    size = 0
    while chunk := await file.read(CHUNK_SIZE):
        size += len(chunk)
        if size > MAX_UPLOAD_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File size exceeds maximum limit of {MAX_UPLOAD_SIZE / (1024*1024)}MB"
            )
        buffer.write(chunk)

    return await face_service.identify_faces_in_image(buffer.getvalue(), str(current_user.id))


@app.post("/api/persons/{person_id}/face")
@limiter.limit("10/minute")
async def upload_person_face(
    request: Request,
    person_id: str,
    file: UploadFile = File(...),
    current_user: database.User = Depends(auth.get_current_user),
):
    """Upload a face photo for a known person. Detects face via InsightFace and stores ArcFace embedding in pgvector."""
    
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {file.content_type}. Allowed types are: {', '.join(ALLOWED_IMAGE_TYPES)}"
        )

    person = await graph_db.get_person_node(person_id)
    if not person or person.get("user_id") != str(current_user.id):
        raise HTTPException(status_code=404, detail="Person not found")

    ext = Path(file.filename or "face.jpg").suffix or ".jpg"
    filename = f"{person_id}{ext}"
    filepath = UPLOAD_DIR / "faces" / filename

    # Read and write securely
    buffer = BytesIO()
    size = 0
    async with aiofiles.open(filepath, "wb") as f:
        while chunk := await file.read(CHUNK_SIZE):
            size += len(chunk)
            if size > MAX_UPLOAD_SIZE:
                await aiofiles.os.remove(filepath)
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"File size exceeds maximum limit of {MAX_UPLOAD_SIZE / (1024*1024)}MB"
                )
            buffer.write(chunk)
            await f.write(chunk)
    final_image_bytes = buffer.getvalue()

    face_image_url = f"/uploads/faces/{filename}"

    # Store embedding using the generated image bytes
    face_vector = await run_in_threadpool(face_service.generate_face_embedding, final_image_bytes)
    await run_in_threadpool(vector_db.upsert_face_embedding, person_id, str(current_user.id), face_vector)

    # Save image URL on the person node
    await graph_db.update_person_node(person_id, face_image_url=face_image_url)

    return {"message": "Face embedding stored", "person_id": person_id, "face_image_url": face_image_url}
