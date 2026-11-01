"""
main.py
FastAPI application entry point for the Animatrix platform.
Implements authentication, video generation task management, history persistence,
secure asset streaming, and frontend static file serving.

Resume Claims Backed:
- "Developed a full-stack text-to-animation pipeline using the Gemini API to generate Manim code from user prompts."
- "Engineered an LLM self-healing render loop with FastAPI and subprocess, feeding Manim render errors to the LLM for correction."
- "Architected robust REST endpoints and a SQLite database for tracking task status and persisting user generation histories."
- "Implemented JWT authentication middleware to enforce strict data separation and secure user access to generated assets."
"""

import os
import uuid
import secrets
from contextlib import asynccontextmanager
from typing import List, Optional
import datetime

from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, status, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

# Local application imports
from database import get_db, init_db, DB_PATH
from models import User, Task
from auth import (
    get_password_hash,
    verify_password,
    create_access_token,
    get_current_user
)
from generate_scene import generate_animation_video, MEDIA_DIR

# Load environment configuration
load_dotenv()

# Optional Google OAuth Client ID
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")


# ============================================================================
# Application Lifecycle & Database Initialization
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan context manager.
    Runs database schema migrations and startup recovery logic before accepting traffic.
    """
    print("[Startup] Initializing SQLite database and checking tables...")
    init_db()
    print("[Startup] Ready to receive requests.")
    yield
    print("[Shutdown] Animatrix application shutting down.")


app = FastAPI(
    title="Animatrix API",
    description="Full-stack AI text-to-animation platform using Gemini and Manim.",
    version="2.0.0",
    lifespan=lifespan
)


# ============================================================================
# CORS Middleware Configuration
# ============================================================================

# Read allowed origins from environment variable (comma-separated list)
# Defaults to local development hosts instead of wildcard '*' for better security
allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000")
allowed_origins = [origin.strip() for origin in allowed_origins_env.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Pydantic Request & Response Schemas
# ============================================================================

class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=1, description="Unique username")
    password: str = Field(..., min_length=6, description="Password with minimum 6 characters")


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class GoogleLoginRequest(BaseModel):
    credential: str = Field(..., description="Google ID Token credential from Google Identity Services")


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str


class GenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=1, description="Natural language prompt describing the animation")


class TaskStatusResponse(BaseModel):
    id: str
    prompt: str
    status: str
    video_url: Optional[str] = None
    code: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime.datetime


# ============================================================================
# Authentication Endpoints
# ============================================================================

@app.post("/api/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    """
    Register a new user account.
    - Validates username and minimum password length (6 characters).
    - Checks for duplicate username (rejects with 400 Bad Request).
    - Hashes password using PBKDF2-SHA256.
    - Creates user record and returns a signed JWT access token.
    """
    username = payload.username.strip()
    if not username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username cannot be empty or blank."
        )

    # Check for duplicate username
    existing_user = db.query(User).filter(User.username == username).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken. Please choose another."
        )

    # Hash the password and save to SQLite
    hashed = get_password_hash(payload.password)
    user = User(username=username, hashed_password=hashed)
    db.add(user)
    db.commit()
    db.refresh(user)

    # Generate JWT token
    token = create_access_token({"sub": user.username})
    return TokenResponse(access_token=token, username=user.username)


@app.post("/api/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """
    Authenticate an existing user.
    - Verifies user exists and password hash matches.
    - Returns a signed JWT access token on success.
    - Returns 401 Unauthorized on invalid credentials.
    """
    username = payload.username.strip()
    user = db.query(User).filter(User.username == username).first()

    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token({"sub": user.username})
    return TokenResponse(access_token=token, username=user.username)


@app.post("/api/google-login", response_model=TokenResponse)
def google_login(payload: GoogleLoginRequest, db: Session = Depends(get_db)):
    """
    Optional Google Single Sign-On (SSO).
    - Verifies Google ID token using google-auth library.
    - Auto-provisions user record if logging in for the first time.
    - Returns application JWT token.
    - If GOOGLE_CLIENT_ID is not configured in .env, returns 501 Not Implemented.
    """
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Google Login is not configured on this server. GOOGLE_CLIENT_ID is missing."
        )

    try:
        from google.oauth2 import id_token
        from google.auth.transport import requests as google_requests

        # Verify Google OAuth2 ID Token
        id_info = id_token.verify_oauth2_token(
            payload.credential,
            google_requests.Request(),
            GOOGLE_CLIENT_ID
        )

        email = id_info.get("email")
        if not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Google token did not contain an email address."
            )

        # Look up or create user based on email
        user = db.query(User).filter(User.username == email).first()
        if not user:
            # Auto-provision new user with an unguessable random password hash
            random_pwd = secrets.token_urlsafe(32)
            user = User(username=email, hashed_password=get_password_hash(random_pwd))
            db.add(user)
            db.commit()
            db.refresh(user)

        token = create_access_token({"sub": user.username})
        return TokenResponse(access_token=token, username=user.username)

    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid Google credential: {str(ve)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error validating Google token: {str(e)}"
        )


# ============================================================================
# Animation Generation & Management Endpoints
# ============================================================================

@app.post("/api/generate", status_code=status.HTTP_202_ACCEPTED)
def generate_animation(
    payload: GenerateRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Initiates an asynchronous animation generation task.

    Resume Claims Backed:
    - "Developed a full-stack text-to-animation pipeline using the Gemini API to generate Manim code from user prompts."
    - "Engineered an LLM self-healing render loop with FastAPI and subprocess, feeding Manim render errors to the LLM for correction."
    - "Architected robust REST endpoints and a SQLite database for tracking task status and persisting user generation histories."

    Flow:
    1. Validates that prompt is not blank.
    2. Generates a new task UUID.
    3. Persists initial task row with status="processing" associated with current_user.id.
    4. Queues generate_animation_video in FastAPI BackgroundTasks.
    5. Returns immediately with task_id without blocking the HTTP worker thread.
    """
    clean_prompt = payload.prompt.strip()
    if not clean_prompt:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Prompt cannot be empty."
        )

    task_id = str(uuid.uuid4())

    # Create Task in database
    new_task = Task(
        id=task_id,
        user_id=current_user.id,
        prompt=clean_prompt,
        status="processing"
    )
    db.add(new_task)
    db.commit()

    # Schedule the self-healing generation pipeline to run in the background
    background_tasks.add_task(generate_animation_video, clean_prompt, task_id)

    return {
        "status": "success",
        "task_id": task_id,
        "message": "Animation task queued for generation."
    }


@app.get("/api/tasks/{task_id}", response_model=TaskStatusResponse)
def get_task_status(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Polls the current status of an animation generation task.

    Strict Data Separation:
    Query filters by BOTH task.id == task_id AND task.user_id == current_user.id.
    If the task does not exist or belongs to another user, returns 404 Not Found
    to prevent information leakage about other users' tasks.
    """
    task = db.query(Task).filter(
        Task.id == task_id,
        Task.user_id == current_user.id
    ).first()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found."
        )

    return TaskStatusResponse(
        id=task.id,
        prompt=task.prompt,
        status=task.status,
        video_url=task.video_url,
        code=task.code,
        error=task.error,
        created_at=task.created_at
    )


@app.get("/api/history", response_model=List[TaskStatusResponse])
def get_user_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieves generation history for the currently authenticated user.

    Resume Claim Backed:
    "Implemented JWT authentication middleware to enforce strict data separation
     and secure user access to generated assets."

    Strict Data Separation:
    Only returns tasks where Task.user_id == current_user.id, ordered by creation time descending.
    A user can NEVER see another user's prompt or generation history.
    """
    tasks = (
        db.query(Task)
        .filter(Task.user_id == current_user.id)
        .order_by(Task.created_at.desc())
        .all()
    )

    return [
        TaskStatusResponse(
            id=t.id,
            prompt=t.prompt,
            status=t.status,
            video_url=t.video_url,
            code=t.code,
            error=t.error,
            created_at=t.created_at
        )
        for t in tasks
    ]


@app.get("/api/videos/{task_id}")
def get_task_video(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Streams the rendered MP4 video asset securely.

    Resume Claim Backed:
    "Implemented JWT authentication middleware to enforce strict data separation
     and secure user access to generated assets."

    Security Architecture:
    1. Authentication: Requires valid Bearer JWT.
    2. Authorization: Task must belong to current_user (Task.user_id == current_user.id).
       If owned by another user, returns 404 (does not disclose existence).
    3. Status Check: Must be 'completed'.
    4. Path Traversal Protection: Verifies file path is absolute, exists on disk,
       and resides strictly within the designated MEDIA_DIR directory.
    5. No Public Static Mount: Media files are NOT exposed under a public static folder,
       guaranteeing that unauthenticated visitors cannot access rendered videos directly.
    """
    task = db.query(Task).filter(
        Task.id == task_id,
        Task.user_id == current_user.id
    ).first()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video asset not found."
        )

    if task.status != "completed" or not task.video_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video has not finished rendering or failed."
        )

    # Path traversal and existence check
    normalized_path = os.path.abspath(task.video_path)
    normalized_media = os.path.abspath(MEDIA_DIR)

    # Ensure path stays within MEDIA_DIR and exists
    if not normalized_path.startswith(normalized_media) or not os.path.isfile(normalized_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video file is not available on disk."
        )

    return FileResponse(
        path=normalized_path,
        media_type="video/mp4",
        filename=f"animatrix_{task_id[:8]}.mp4"
    )


@app.get("/api/health")
def health_check():
    """
    Health check and server capability discovery endpoint.
    Informs frontend whether Google SSO is enabled on this backend.
    """
    return {
        "status": "healthy",
        "google_auth_enabled": bool(GOOGLE_CLIENT_ID),
        "database": "sqlite",
        "version": "2.0.0"
    }


# ============================================================================
# Frontend Static Files Serving
# ============================================================================

# Mount frontend directory LAST so that /api/* endpoints take precedence
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend")
os.makedirs(FRONTEND_DIR, exist_ok=True)

app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")


# ============================================================================
# Development Server Runner
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    print(f"Starting Animatrix server on http://0.0.0.0:{port} ...")
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)

