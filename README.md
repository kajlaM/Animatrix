# Animatrix — AI Text-to-Animation Platform

**Animatrix** is a full-stack, AI-powered text-to-animation platform that converts natural language prompts into mathematical and scientific animations. It pairs Google's **Gemini API (`gemini-2.5-flash`)** for dynamic code synthesis with the **Manim Community Edition** rendering engine, featuring an automated **LLM self-healing render loop**, persistent task tracking in SQLite, strict JWT-based multi-user isolation, and a ChatGPT-style web UI.

---

## Architecture

```
[User via Web UI]
       │
       ▼
[POST /api/generate] (JWT Bearer Auth)
       │
       ├──► 1. Save Task (status="processing") to SQLite
       │
       └──► 2. Dispatch FastAPI BackgroundTask
                    │
                    ▼
          ┌──────────────────────────────────────────────┐
          │  LLM Self-Healing Render Pipeline            │
          │                                              │
          │  [User Prompt]                               │
          │         │                                    │
          │         ▼                                    │
          │  [Gemini 2.5 Flash API]                      │
          │         │                                    │
          │         ▼                                    │
          │  [Regex Python Code Extraction]              │
          │         │                                    │
          │         ▼                                    │
          │  [Save Script to temp_scenes/]               │
          │         │                                    │
          │         ▼                                    │
          │  [Subprocess: Manim Community Render]        │
          │         │                                    │
          │   ┌─────┴─────────────────────┐              │
          │   ▼                           ▼              │
          │ [Success]                [Render Error]      │
          │ Locate MP4                    │              │
          │                               ▼              │
          │                    Feed Stderr + Code Back   │
          │                    to Gemini (Max 3 Retries) │
          │                               │              │
          │                               └──────────────┘
          │
          ▼
[Update Task in SQLite: status="completed", video_path, video_url]
          │
          ▼
[Client Polls GET /api/tasks/{task_id} every 2s]
          │
          ▼
[Authenticated Stream GET /api/videos/{task_id} as Blob]
```

---

## Key Features

1. **AI Manim Code Generation**: Specialized system prompts engineer Gemini to produce clean, executable Python scripts adhering to strict Manim syntax rules.
2. **LLM Self-Healing Render Loop**: If Manim encounters syntax errors, missing objects, or execution timeouts, the subprocess `stderr` traceback is captured and fed back to Gemini to self-heal the script up to 3 times.
3. **Strict Multi-User Data Separation**: JWT authentication middleware ensures users can only access, view, and poll their own animation tasks and history.
4. **Secure Video Streaming**: Rendered MP4 files are not exposed over public static mounts. Videos are streamed via `/api/videos/{task_id}` only after verifying user ownership, completion status, and path-traversal safety.
5. **Modern Vanilla Chat Interface**: ChatGPT-style dark-mode UI with generation history, live spinners, collapsible code viewers, inline video players, and sample prompt chips.

---

## Tech Stack

- **Backend**: FastAPI, SQLAlchemy ORM, SQLite, Pydantic, Uvicorn
- **AI Model**: Google GenAI SDK (`google-genai`), `gemini-2.5-flash`
- **Animation Engine**: Manim Community Edition (executed via Python `subprocess`)
- **Authentication**: PyJWT (HS256) and Passlib (`pbkdf2_sha256`)
- **Configuration**: `python-dotenv`
- **Frontend**: Vanilla HTML5, CSS3 (Modern Dark Theme), JavaScript ES6+ (No build step required)

---

## Project Structure

```
Animatrix/
├── main.py                     # FastAPI app, REST endpoints, static mounting, entry point
├── generate_scene.py           # Core AI pipeline: Gemini prompt + Manim render + self-healing loop
├── auth.py                     # PBKDF2 hashing, JWT signing/verification, get_current_user middleware
├── database.py                 # SQLite engine, SessionLocal, init_db(), get_db() dependency
├── models.py                   # SQLAlchemy User and Task database models
├── animatrix.db                # SQLite database (auto-generated, git-ignored)
├── requirements.txt            # Pinned Python package dependencies
├── .env.example                # Environment variables template
├── .gitignore                  # Git exclusions (credentials, db, media, cache)
├── README.md                   # System documentation and setup guide
├── frontend/                   # Web user interface
│   ├── index.html              # Chat UI structure and auth modal
│   ├── index.css               # Responsive dark-theme styling
│   └── script.js               # Polling, JWT management, chat stream, video streaming
├── tests/
│   ├── smoke_test.py           # End-to-end integration and security test suite
│   └── test_self_healing.py    # Self-healing render loop verification test
├── temp_scenes/                # Working directory for generated Manim scripts (git-ignored)
└── media/                      # Working directory for rendered Manim MP4s (git-ignored)
```

---

## Setup & Installation

### 1. Prerequisites
- Python 3.10 – 3.13
- FFmpeg (required by Manim for video rendering):
  ```bash
  # macOS
  brew install ffmpeg cairo pango
  # Ubuntu / Debian
  sudo apt update && sudo apt install -y ffmpeg libcairo2-dev libpango1.0-dev
  ```

### 2. Clone Repository & Create Virtual Environment
```bash
git clone https://github.com/kajlaM/Animatrix.git
cd Animatrix

python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Generate a secure 256-bit secret key for JWT signing:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```
Edit `.env` and configure:
```env
# Required: Gemini API Key from https://aistudio.google.com/
GEMINI_API_KEY=your_actual_gemini_api_key_here

# Required: Generated JWT Secret Key
JWT_SECRET_KEY=your_generated_token_hex_here

# Server Configuration
PORT=8000
ALLOWED_ORIGINS=http://localhost:8000,http://127.0.0.1:8000
MANIM_QUALITY=m

# Optional: Google OAuth2 Client ID for Google SSO
# GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
```

---

## Running the Platform

### Start the Application
```bash
source .venv/bin/activate
python main.py
```
Or with Uvicorn directly:
```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```
Open your browser to: **`http://localhost:8000`**

---

## REST API Reference

| Method | Endpoint | Auth Required | Description |
|---|---|:---:|---|
| `POST` | `/api/register` | No | Creates a new user; returns JWT access token. |
| `POST` | `/api/login` | No | Authenticates user credentials; returns JWT token. |
| `POST` | `/api/google-login` | No | Authenticates Google ID token; auto-registers if new. |
| `POST` | `/api/generate` | **Yes (Bearer)** | Queues asynchronous animation task in background. |
| `GET` | `/api/tasks/{task_id}` | **Yes (Bearer)** | Returns status (`processing`, `completed`, `failed`). |
| `GET` | `/api/history` | **Yes (Bearer)** | Lists authenticated user's tasks (newest first). |
| `GET` | `/api/videos/{task_id}` | **Yes (Bearer)** | Securely streams completed MP4 video (FileResponse). |
| `GET` | `/api/health` | No | Service health check and feature capability check. |
| `GET` | `/` | No | Serves static frontend single-page application. |

---

## Database Schema (SQLite)

### Table: `users`
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | INTEGER | PRIMARY KEY, AUTOINCREMENT | Unique user identifier |
| `username` | VARCHAR(50) | UNIQUE, NOT NULL, INDEXED | User account login handle |
| `hashed_password` | VARCHAR(255) | NOT NULL | PBKDF2-SHA256 salted hash |

### Table: `tasks`
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | VARCHAR(36) | PRIMARY KEY, INDEXED | UUID string generation ID |
| `user_id` | INTEGER | FOREIGN KEY (`users.id`), NOT NULL | Owner user reference |
| `prompt` | VARCHAR(1000) | NOT NULL | Natural language prompt |
| `status` | VARCHAR(20) | NOT NULL, DEFAULT 'pending' | `pending`, `processing`, `completed`, `failed` |
| `video_url` | VARCHAR(255) | NULLABLE | Client API streaming URL (`/api/videos/{task_id}`) |
| `video_path` | VARCHAR(500) | NULLABLE | Absolute disk path to rendered MP4 |
| `code` | TEXT | NULLABLE | LLM-generated Manim Python script |
| `error` | TEXT | NULLABLE | Short human-readable render error message |
| `created_at` | DATETIME | NOT NULL, UTC | Task creation timestamp |

---

## Verification & Testing

Run the automated test suites using the virtual environment:

### 1. End-to-End Smoke Test
Tests user registration, login, 401 unauthenticated protection, generation dispatch, polling, multi-user history separation, cross-user 404 security checks, and authenticated video streaming:
```bash
python tests/smoke_test.py
```

### 2. Self-Healing Render Loop Test
Simulates an intentionally broken Manim script with an invalid function name, verifies error feedback is forwarded to Gemini, and confirms successful healing:
```bash
python tests/test_self_healing.py
```

---

## Known Limitations and Future Work

For an interview defense, here is an honest assessment of current design trade-offs and future production improvements:

1. **Background Tasks vs. Distributed Task Queue**:
   - *Current*: Uses FastAPI's in-memory `BackgroundTasks`. Tasks are lost if the server process restarts during generation (mitigated by startup recovery that marks interrupted tasks as `failed`).
   - *Production*: Implement **Celery with Redis / RabbitMQ** or **Temporal** for durable task queues, worker pools, and persistent retry management.

2. **Database Concurrency**:
   - *Current*: SQLite with `check_same_thread=False`. Excellent for prototypes and single-instance deployments, but SQLite limits concurrent write operations.
   - *Production*: Migrate to **PostgreSQL** with connection pooling (e.g., `asyncpg` or PgBouncer).

3. **Untrusted Code Execution Sandboxing**:
   - *Current*: Manim executes generated Python scripts locally via `subprocess.run`.
   - *Production*: Running arbitrary LLM-generated code presents security risks. In production, renders should execute inside **ephemeral isolated Docker containers**, **gVisor**, or AWS Lambda / Google Cloud Run microVMs with restricted network and filesystem permissions.

4. **Polling vs. Real-Time Streaming**:
   - *Current*: Client polls `/api/tasks/{task_id}` every 2 seconds.
   - *Production*: Transition to **WebSockets** or **Server-Sent Events (SSE)** for real-time progress updates and frame-by-frame rendering feedback.

5. **Token Lifecycle & Rate Limiting**:
   - *Current*: 60-minute JWT access tokens without refresh tokens; no request rate limiting.
   - *Production*: Add short-lived access tokens (15m) with rotating refresh tokens (HTTP-only cookies), paired with a **Redis Token Bucket** rate limiter per user/IP.
