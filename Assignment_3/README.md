# Animatrix ACA — Assignment 3 Backend API

Welcome to Assignment 3 of the Animatrix (Advanced Coding Academy) project. This assignment integrates the prompt engineering, code parsing, and Manim rendering pipeline developed in previous assignments into a production-grade FastAPI backend API.

The goal is to build an AI-powered animation service that converts a plain English prompt into a rendered Manim video and exposes it via a dynamic REST API.

---

## Features

1. **AI-to-Animation Engine** (`generate_scene.py`):
   - Secure credential loading with `python-dotenv`.
   - Rich prompt engineering targeting the `gemini-2.5-flash` model for high-fidelity Manim code generation.
   - Robust Python regex extraction from markdown and explanations.
   - Uniquely named timestamped python script files.
   - Programmatic rendering of Manim videos via `subprocess`.
2. **Self-Healing Loop**:
   - Captures stderr, stdout, stack traces, and generated code when rendering fails.
   - Automatically feeds compilation errors back to the Gemini model to rewrite/correct code.
   - Self-heals up to 3 times before raising a user-friendly exception.
3. **FastAPI Web Server** (`main.py`):
   - Modern schema validation using Pydantic models.
   - CORS middleware enabled to allow cross-origin requests from frontends.
   - Static mounting of the rendered media folder to make output files immediately accessible via HTTP URL.
   - Production-level exception handling.

---

## Folder Structure

All Assignment 3 specific code is placed in its own folder to ensure modularity and ease of evaluation:

```text
Assignment_3/
├── .env.example          # Template for environment configuration
├── README.md             # This documentation file
├── generate_scene.py     # Main AI generation & Manim rendering engine
├── main.py               # FastAPI backend entry point
└── temp_scenes/          # Temporary directory where generated scripts are stored
```

---

## Installation & Setup

### 1. Create a Virtual Environment

It is highly recommended to isolate dependencies inside a virtual environment.

```bash
# Navigate to the Assignment_3 directory
cd Assignment_3

# Create a virtual environment named .venv
python3 -m venv .venv

# Activate the virtual environment
# On macOS/Linux:
source .venv/bin/activate
# On Windows (cmd):
# .venv\Scripts\activate.bat
```

### 2. Install Dependencies

Install the required Python packages:

```bash
pip install fastapi uvicorn pydantic python-dotenv google-genai
```

*(Ensure you also have `manim` installed globally on your machine, or installed inside your system path environment so that the backend can execute it.)*

### 3. Configure Environment Variables

1. Copy the `.env.example` file to `.env`:
   ```bash
   cp .env.example .env
   ```
2. Open `.env` and fill in your Gemini API key:
   ```env
   GEMINI_API_KEY=your_actual_gemini_api_key_here
   PORT=8000
   ```

> [!WARNING]
> **Security Warning**: Do not commit or push your `.env` file containing secret keys to GitHub. The `.gitignore` at the root of the project should ignore `.env` files.

---

## Running the FastAPI Server

Start the FastAPI application by running `main.py` directly (which configures and runs Uvicorn under the hood):

```bash
python main.py
```

The server will start on `http://localhost:8000` (or the port defined in `.env`).

### Why `reload=True`?

By default, the server runs with Uvicorn's `reload=True` parameter enabled:
- **What it does**: Automatically detects file modifications and reloads the server instantly. This is extremely helpful during active development to see changes without manually stopping and restarting the process.
- **Why NOT to use it in production**: 
  - **Performance**: Watching files uses extra system resources.
  - **State issues**: In this project, we dynamically write python scene files to the `temp_scenes/` directory. If the server watches the entire directory recursively, writing a temporary scene script will trigger a server reload *in the middle* of processing the HTTP request, terminating the socket connection! We mitigate this by separating code logic, but in production, auto-reload should always be disabled.

---

## Example API Usage

Once the server is running, you can test it using a web client, postman, or `curl`:

### 1. Health Check (GET `/`)

Verify the server is running:

```bash
curl http://localhost:8000/
```

**Response**:
```json
{
  "status": "online",
  "message": "Animatrix FastAPI Backend is running.",
  "endpoints": {
    "root": "GET /",
    "generate": "POST /generate"
  }
}
```

### 2. Generate Animation (POST `/generate`)

Send a prompt to generate and render an animation:

```bash
curl -X POST http://localhost:8000/generate \
     -H "Content-Type: application/json" \
     -d '{"prompt": "A red circle fades in, scales up, and rotates"}'
```

**Response**:
```json
{
  "success": true,
  "message": "Animation generated and rendered successfully.",
  "prompt": "A red circle fades in, scales up, and rotates",
  "absolute_path": "/Users/.../Animatrix/media/videos/animation_20260701_233000_try0/480p15/MyScene.mp4",
  "relative_path": "media/videos/animation_20260701_233000_try0/480p15/MyScene.mp4",
  "video_url": "http://localhost:8000/media/videos/animation_20260701_233000_try0/480p15/MyScene.mp4"
}
```

You can copy and paste the `video_url` into your web browser to play the rendered MP4 file!
