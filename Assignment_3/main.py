import os
import sys
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Add current directory to path to allow importing generate_scene
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from generate_scene import generate_animation_video

# Checkpoint 1 — App setup
app = FastAPI(
    title="Animatrix AI Video Generation API",
    description="FastAPI backend to render Manim animations from natural language prompts using Gemini API.",
    version="1.0.0"
)

# Checkpoint 4 — Enable CORS
# Configure allowable origins. We allow all origins for easy development and integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Resolve directories and mount StaticFiles
workspace_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
media_dir = os.path.join(workspace_root, "media")

# Ensure the media directory exists
os.makedirs(media_dir, exist_ok=True)

# Mount the media directory to expose rendered videos via HTTP
app.mount("/media", StaticFiles(directory=media_dir), name="media")


# Checkpoint 2 — Define the request shape
class GenerateRequest(BaseModel):
    prompt: str


# Checkpoint 1 — Simple root route to verify the server is running
@app.get("/")
def read_root():
    return {
        "status": "online",
        "message": "Animatrix FastAPI Backend is running.",
        "endpoints": {
            "root": "GET /",
            "generate": "POST /generate"
        }
    }


# Checkpoint 3 & 5 — POST endpoint and Proper Error Handling
@app.post("/generate")
async def generate_video(payload: GenerateRequest, request: Request):
    """
    POST endpoint to generate a Manim video from a prompt.
    Validates request body, calls the generation pipeline,
    and returns absolute path, relative path, and accessible web URL.
    """
    if not payload.prompt.strip():
        raise HTTPException(
            status_code=400,
            detail="Prompt cannot be empty."
        )
        
    try:
        print(f"Received generation request for prompt: '{payload.prompt}'")
        # Call the pipeline from generate_scene.py
        absolute_video_path = generate_animation_video(payload.prompt)
        
        # Calculate paths relative to the media directory to expose via static route
        relative_video_path = os.path.relpath(absolute_video_path, media_dir)
        
        # Build dynamic URL for the video based on request context
        video_url = f"{request.base_url}media/{relative_video_path}"
        
        return {
            "success": True,
            "message": "Animation generated and rendered successfully.",
            "prompt": payload.prompt,
            "absolute_path": absolute_video_path,
            "relative_path": f"media/{relative_video_path}",
            "video_url": video_url
        }
        
    except Exception as e:
        print(f"Error during video generation: {e}")
        # Return a clean 500 error detailing the failure rather than crashing the server
        raise HTTPException(
            status_code=500,
            detail=f"Video generation or rendering failed. Details: {str(e)}"
        )


# Checkpoint 6 — Run the server
if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", 8000))
    
    # Explain reload=True for development:
    # reload=True automatically monitors source files for updates and restarts the server.
    # While convenient for development, it should be disabled in production due to performance 
    # overhead, potential race conditions when temporary python scenes are created in the folder,
    # and security.
    # Note: To enable reload, we pass the import string "main:app" instead of the app object.
    print(f"Starting Animatrix server on port {port}...")
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=True
    )
