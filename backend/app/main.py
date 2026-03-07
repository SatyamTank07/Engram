"""
FastAPI main application with chat endpoints.
"""

import os
import uuid
from pathlib import Path

from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from . import crud, schemas, database, agent, auth, graph_db, vector_db, face_service

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

# Initialize Neo4j knowledge graph indexes
try:
    graph_db.init_graph_db()
    print("Neo4j knowledge graph initialized successfully.")
except Exception as e:
    print(f"Warning: Could not initialize Neo4j: {e}. Person identity features may not work.")

# Create FastAPI app
app = FastAPI(
    title="Chat API",
    description="FastAPI backend for chat application with LangChain",
    version="1.0.0"
)

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


# Authentication endpoints

@app.post("/api/auth/register", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED)
def register(
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
def login(
    login_data: schemas.LoginRequest,
    db: Session = Depends(database.get_db)
):
    """Login with phone and password."""
    # Get user
    user = crud.get_user_by_phone(db, login_data.phone)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    # Verify password
    if not auth.verify_password(login_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    # Create access token (sub must be a string)
    access_token = auth.create_access_token(data={"sub": str(user.id)})
    
    return schemas.LoginResponse(
        access_token=access_token,
        user=user
    )


@app.get("/api/auth/me", response_model=schemas.UserResponse)
def get_current_user_info(
    current_user: database.User = Depends(auth.get_current_user)
):
    """Get current authenticated user."""
    return current_user


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
def chat(
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
        # Get AI response
        ai_response = agent.get_agent_response(chat_request.message, chat_history, chat_request.image_url)
        
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
    ext = Path(file.filename or "image.jpg").suffix or ".jpg"
    filename = f"{uuid.uuid4()}{ext}"
    filepath = UPLOAD_DIR / "chat" / filename

    contents = await file.read()
    with open(filepath, "wb") as f:
        f.write(contents)

    return {"url": f"/uploads/chat/{filename}"}


# PersonIdentity endpoints (powered by Neo4j Knowledge Graph)

@app.post("/api/persons", status_code=status.HTTP_201_CREATED)
def create_person(
    person_data: schemas.PersonIdentityCreate,
    current_user: database.User = Depends(auth.get_current_user),
):
    """Create a new person identity in the knowledge graph."""
    person = graph_db.create_person_node(
        user_id=str(current_user.id),
        name=person_data.name,
        aliases=person_data.aliases,
        contacts=person_data.contacts,
        short_bio=person_data.short_bio,
        trust_score=person_data.trust_score,
    )
    return person


@app.get("/api/persons")
def get_persons(
    current_user: database.User = Depends(auth.get_current_user),
):
    """Get all person identities for the authenticated user from the knowledge graph."""
    return graph_db.list_person_nodes(str(current_user.id))


@app.get("/api/persons/{person_id}")
def get_person(
    person_id: str,
    current_user: database.User = Depends(auth.get_current_user),
):
    """Get a specific person identity from the knowledge graph."""
    person = graph_db.get_person_node(person_id)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    
    if person.get("user_id") != str(current_user.id):
        raise HTTPException(status_code=403, detail="Access denied")
    
    return person


@app.put("/api/persons/{person_id}")
def update_person(
    person_id: str,
    person_data: schemas.PersonIdentityUpdate,
    current_user: database.User = Depends(auth.get_current_user),
):
    """Update a person identity in the knowledge graph."""
    person = graph_db.get_person_node(person_id)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    
    if person.get("user_id") != str(current_user.id):
        raise HTTPException(status_code=403, detail="Access denied")
    
    updated_person = graph_db.update_person_node(
        person_id,
        name=person_data.name,
        aliases=person_data.aliases,
        contacts=person_data.contacts,
        short_bio=person_data.short_bio,
        trust_score=person_data.trust_score,
    )
    return updated_person


@app.delete("/api/persons/{person_id}")
def delete_person(
    person_id: str,
    current_user: database.User = Depends(auth.get_current_user),
):
    """Delete a person identity from the knowledge graph."""
    person = graph_db.get_person_node(person_id)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    
    if person.get("user_id") != str(current_user.id):
        raise HTTPException(status_code=403, detail="Access denied")
    
    graph_db.delete_person_node(person_id)
    return {"status": "deleted", "person_id": person_id}


@app.post("/api/persons/search")
def semantic_search_persons(
    search_req: schemas.SemanticSearchRequest,
    current_user: database.User = Depends(auth.get_current_user),
):
    """Search persons using semantic similarity."""
    from . import embedding_service

    # Generate embedding for the search query
    query_embedding = embedding_service.generate_text_embedding(search_req.query)

    # Search pgvector for similar persons
    matches = vector_db.semantic_search(
        user_id=str(current_user.id),
        query_embedding=query_embedding,
        limit=search_req.limit,
    )

    # Enrich with full Neo4j data
    results = []
    for match in matches:
        person = graph_db.get_person_node(match["person_id"])
        if person:
            results.append({
                **person,
                "similarity_score": match["similarity_score"],
            })

    return results


@app.post("/api/persons/identify")
async def identify_person_from_face(
    file: UploadFile = File(...),
    current_user: database.User = Depends(auth.get_current_user),
):
    """
    Upload a photo (single or group) — detects ALL faces and matches each
    against the database independently. Returns per-face results with
    bounding boxes and match info.
    """
    image_bytes = await file.read()
    return face_service.identify_faces_in_image(image_bytes, str(current_user.id))


@app.post("/api/persons/{person_id}/face")
async def upload_person_face(
    person_id: str,
    file: UploadFile = File(...),
    current_user: database.User = Depends(auth.get_current_user),
):
    """Upload a face photo for a known person. Detects face via InsightFace and stores ArcFace embedding in pgvector."""
    person = graph_db.get_person_node(person_id)
    if not person or person.get("user_id") != str(current_user.id):
        raise HTTPException(status_code=404, detail="Person not found")

    image_bytes = await file.read()

    # Save image file
    ext = Path(file.filename or "face.jpg").suffix or ".jpg"
    filename = f"{person_id}{ext}"
    filepath = UPLOAD_DIR / "faces" / filename
    with open(filepath, "wb") as f:
        f.write(image_bytes)

    face_image_url = f"/uploads/faces/{filename}"

    # Store embedding
    face_vector = face_service.generate_face_embedding(image_bytes)
    vector_db.upsert_face_embedding(person_id, str(current_user.id), face_vector)

    # Save image URL on the person node
    graph_db.update_person_node(person_id, face_image_url=face_image_url)

    return {"message": "Face embedding stored", "person_id": person_id, "face_image_url": face_image_url}
