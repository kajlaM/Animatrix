"""
generate_scene.py
Core AI Animation Pipeline:
1. Prompts Google Gemini (gemini-2.5-flash) to generate Manim Community Edition code.
2. Extracts clean Python code from the response.
3. Renders the animation to MP4 using Manim via subprocess.
4. Executes an LLM self-healing render loop (feeding stderr back to Gemini) up to 3 times on failure.
5. Updates task status, code, and video location in SQLite.

Resume Claims Backed:
- "Developed a full-stack text-to-animation pipeline using the Gemini API to generate Manim code from user prompts."
- "Engineered an LLM self-healing render loop with FastAPI and subprocess, feeding Manim render errors to the LLM for correction."
"""

import os
import re
import sys
import glob
import datetime
import subprocess
from dotenv import load_dotenv
from google import genai
from google.genai import types

from database import SessionLocal
from models import Task

# Load environment configuration
load_dotenv()

# Resolve repository root directory
REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
TEMP_SCENES_DIR = os.path.join(REPO_ROOT, "temp_scenes")
MEDIA_DIR = os.path.join(REPO_ROOT, "media")

# Ensure required working directories exist
os.makedirs(TEMP_SCENES_DIR, exist_ok=True)
os.makedirs(MEDIA_DIR, exist_ok=True)

# Manim rendering quality flag: 'l' (low 480p), 'm' (medium 720p), 'h' (high 1080p)
# Default is 'm' as specified in requirements
MANIM_QUALITY = os.getenv("MANIM_QUALITY", "m")

# Manim render timeout in seconds (prevents infinite render loops)
MANIM_TIMEOUT_SECONDS = int(os.getenv("MANIM_TIMEOUT", "180"))

# Initialize Gemini Client lazily or at module import
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")


def get_gemini_client() -> genai.Client:
    """
    Initializes and returns the Google GenAI client.
    Fails with an informative message if GEMINI_API_KEY is not configured.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Please add GEMINI_API_KEY to your .env file."
        )
    return genai.Client(api_key=api_key)


# ============================================================================
# LLM Code Generation & Prompt Engineering
# ============================================================================

def ask_ai_for_manim_code(prompt: str, error_feedback: str = None, previous_code: str = None) -> str:
    """
    Sends the user prompt (and optional render error feedback for self-healing) to Gemini.
    Returns the raw response text from the model.

    Prompt Engineering:
    We use strict system instructions requiring valid Python code, explicit imports,
    MathTex for formulas, Text for labels, and proper 3D camera setup if needed.
    """
    system_prompt = (
        "You are an expert Python developer and an expert in the Manim Community Edition animation library.\n"
        "Your output must consist ONLY of valid, executable Python code.\n"
        "Do NOT include any explanations, greetings, or markdown outside of standard code blocks.\n\n"
        "Strict Manim Generation Rules:\n"
        "1. Always begin your code with:\n"
        "from manim import *\n\n"
        "2. Always use MathTex() for equations and mathematical expressions.\n"
        "3. Always use Text() for normal text and labels.\n"
        "4. Never use Tex().\n"
        "5. Always animate elements using self.play(). Never rely on self.add() to just display them without animation.\n"
        "6. Use self.wait() between logical animation steps to give the viewer time to follow.\n"
        "7. If the user requests a 3D animation:\n"
        "   - The scene class must inherit from ThreeDScene.\n"
        "   - You must call self.set_camera_orientation(...) in the construct method.\n"
        "8. Space objects properly using shift(), next_to(), or move_to() to avoid overlapping.\n"
        "9. Rate functions must always use 'rate_functions.smooth' instead of just 'smooth'.\n"
        "10. Return ONLY Python code. No text before or after the code block."
    )

    if error_feedback and previous_code:
        user_content = (
            f"The previous Manim Python code generated for the prompt \"{prompt}\" failed to compile or render.\n"
            f"Here is the generated code that failed:\n"
            f"```python\n"
            f"{previous_code}\n"
            f"```\n\n"
            f"Here is the error message / stack trace from the rendering process:\n"
            f"{error_feedback}\n\n"
            f"Please fix the error(s). Do NOT rewrite the entire animation logic from scratch;\n"
            f"preserve the original concept but ensure the syntax and Manim function calls are correct\n"
            f"and compile successfully. Return ONLY the corrected Python code inside a python code block."
        )
    else:
        user_content = f"Generate a Manim scene for the following prompt: {prompt}"

    client = get_gemini_client()

    try:
        # Generate content with system instruction configuration
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=user_content,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt
            )
        )
        return response.text
    except Exception as e:
        # Fallback to direct prompt concatenation if config option fails
        try:
            full_prompt = f"{system_prompt}\n\nUser request:\n{user_content}"
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=full_prompt
            )
            return response.text
        except Exception as inner_e:
            raise RuntimeError(f"Failed to communicate with Gemini API: {inner_e}")


# ============================================================================
# Code Extraction & Scene Parsing
# ============================================================================

def extract_python_code(raw_text: str) -> str:
    """
    Extracts executable Python code from the raw model response.
    Strips markdown code fences (```python ... ```) or returns trimmed text.
    """
    if not raw_text:
        return ""

    pattern = r"```(?:python)?\s*(.*?)\s*```"
    match = re.search(pattern, raw_text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()

    return raw_text.strip()


def get_scene_class_name(code: str) -> str:
    """
    Extracts the name of the Scene class defined in the generated python code.
    Matches classes inheriting from standard Manim Scene types.
    """
    pattern = r"class\s+(\w+)\s*\((?:Scene|ThreeDScene|VectorScene|LinearTransformationScene|MovingCameraScene|MovingCamera|GraphScene)\)"
    match = re.search(pattern, code)
    if match:
        return match.group(1)

    # Fallback pattern for any subclassed class
    pattern_fallback = r"class\s+(\w+)\s*\("
    match_fallback = re.search(pattern_fallback, code)
    if match_fallback:
        return match_fallback.group(1)

    return None


def extract_short_error(stderr_text: str) -> str:
    """
    Extracts a short, human-readable error summary from stderr.
    Takes the trailing lines of the traceback rather than the entire dump.
    """
    if not stderr_text:
        return "Rendering failed with unknown error."

    lines = [line.strip() for line in stderr_text.strip().splitlines() if line.strip()]
    if not lines:
        return "Rendering failed with unknown error."

    # Take the last 3-4 lines which typically contain the exact Python exception
    short_summary = " | ".join(lines[-4:])
    if len(short_summary) > 300:
        short_summary = short_summary[-300:]
    return short_summary


# ============================================================================
# Main Background Generation & LLM Self-Healing Render Loop
# ============================================================================

def generate_animation_video(prompt: str, task_id: str) -> None:
    """
    Main background pipeline function executed by FastAPI BackgroundTasks.

    Resume Claims Backed:
    - "Developed a full-stack text-to-animation pipeline using the Gemini API to generate Manim code from user prompts."
    - "Engineered an LLM self-healing render loop with FastAPI and subprocess, feeding Manim render errors to the LLM for correction."

    Execution Steps:
    1. Opens its OWN dedicated database session with SessionLocal() and closes it in finally.
    2. Marks task status as 'processing'.
    3. Calls Gemini for Manim code.
    4. Writes code to a timestamped file in temp_scenes/.
    5. Runs Manim via subprocess with timeout protection.
    6. Self-Healing Loop: On non-zero exit code or timeout, sends code + stderr back to Gemini
       for up to 3 fix attempts (attempts 1, 2, and 3 after initial failure).
    7. On success: Updates task status to 'completed', records code, video_path, and video_url.
    8. On exhaustion or error: Updates task status to 'failed' with short error message.
       Never lets an unhandled exception escape, ensuring the server process never crashes.
    """
    db = SessionLocal()
    try:
        # Retrieve the task from the database
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            print(f"[Pipeline] Error: Task '{task_id}' was not found in the database.")
            return

        task.status = "processing"
        db.commit()

        max_fix_retries = 3
        current_retry = 0
        error_feedback = None
        previous_code = None
        final_code = None
        rendered_video_path = None
        last_error_summary = None

        print(f"[Pipeline] Starting generation for task {task_id}: '{prompt}'")

        # Loop: attempt 0 is initial try; attempts 1 to 3 are self-healing retries
        while current_retry <= max_fix_retries:
            if current_retry > 0:
                print(f"[Self-Healing] attempt {current_retry} of {max_fix_retries}")

            # Step 1: Prompt Gemini for Manim code
            try:
                raw_output = ask_ai_for_manim_code(prompt, error_feedback, previous_code)
                code = extract_python_code(raw_output)
            except Exception as e:
                error_feedback = f"Gemini API request failed: {str(e)}"
                last_error_summary = extract_short_error(str(e))
                print(f"[Self-Healing] LLM call error: {error_feedback}")
                current_retry += 1
                continue

            previous_code = code
            final_code = code

            # Step 2: Write code to timestamped file in temp_scenes
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            script_basename = f"animation_{task_id[:8]}_{timestamp}_try{current_retry}"
            script_filename = f"{script_basename}.py"
            script_path = os.path.join(TEMP_SCENES_DIR, script_filename)

            with open(script_path, "w", encoding="utf-8") as f:
                f.write(code)

            # Step 3: Extract scene class name
            scene_name = get_scene_class_name(code)
            if not scene_name:
                error_feedback = (
                    "Syntax Error: No class inheriting from Scene or ThreeDScene found in the code. "
                    "Make sure to define: class YourSceneName(Scene):"
                )
                last_error_summary = "No Manim Scene class found in generated code."
                current_retry += 1
                continue

            # Step 4: Run Manim via subprocess
            # Command format: [python, -m, manim, -q<quality>, <script_path>, <scene_name>]
            manim_cmd = [
                sys.executable,
                "-m",
                "manim",
                f"-q{MANIM_QUALITY}",
                script_path,
                scene_name
            ]

            print(f"[Pipeline] Executing: {' '.join(manim_cmd)}")

            try:
                result = subprocess.run(
                    manim_cmd,
                    capture_output=True,
                    text=True,
                    cwd=REPO_ROOT,
                    timeout=MANIM_TIMEOUT_SECONDS
                )

                if result.returncode == 0:
                    # Rendering succeeded! Search for the generated MP4
                    # Pattern: media/videos/<script_basename>/**/*.mp4
                    search_pattern = os.path.join(
                        MEDIA_DIR, "videos", script_basename, "**", "*.mp4"
                    )
                    matches = glob.glob(search_pattern, recursive=True)

                    if matches:
                        rendered_video_path = os.path.abspath(matches[0])
                        print(f"[Pipeline] Task {task_id} rendered successfully: {rendered_video_path}")
                        break
                    else:
                        error_feedback = (
                            f"Manim completed with exit code 0, but the output MP4 could not be found "
                            f"under media/videos/{script_basename}."
                        )
                        last_error_summary = "Video file not found after render."
                        current_retry += 1
                else:
                    # Non-zero exit code: Manim compilation or runtime error
                    print(f"[Self-Healing] Render failed with exit code {result.returncode}")
                    last_error_summary = extract_short_error(result.stderr)
                    error_feedback = (
                        f"Manim render failed with return code {result.returncode}.\n"
                        f"STDERR:\n{result.stderr}\n"
                        f"STDOUT:\n{result.stdout}"
                    )
                    current_retry += 1

            except subprocess.TimeoutExpired:
                print(f"[Self-Healing] Subprocess timed out after {MANIM_TIMEOUT_SECONDS}s")
                last_error_summary = f"Render timed out after {MANIM_TIMEOUT_SECONDS} seconds."
                error_feedback = (
                    f"Execution timed out after {MANIM_TIMEOUT_SECONDS} seconds. "
                    "The animation might have too many complex objects or infinite loops. "
                    "Please optimize and simplify the scene."
                )
                current_retry += 1

            except Exception as sub_err:
                print(f"[Self-Healing] Subprocess execution exception: {sub_err}")
                last_error_summary = extract_short_error(str(sub_err))
                error_feedback = f"Subprocess exception: {str(sub_err)}"
                current_retry += 1

        # Post-loop status persistence
        if rendered_video_path and os.path.exists(rendered_video_path):
            task.status = "completed"
            task.code = final_code
            task.video_path = rendered_video_path
            task.video_url = f"/api/videos/{task_id}"
            task.error = None
            db.commit()
            print(f"[Pipeline] Task {task_id} marked as completed.")
        else:
            task.status = "failed"
            task.code = final_code
            task.video_path = None
            task.video_url = None
            task.error = last_error_summary or "Rendering failed after maximum retry attempts."
            db.commit()
            print(f"[Pipeline] Task {task_id} marked as failed: {task.error}")

    except Exception as e:
        print(f"[Pipeline] Unexpected exception in background generation: {e}")
        try:
            task = db.query(Task).filter(Task.id == task_id).first()
            if task:
                task.status = "failed"
                task.error = f"Internal pipeline failure: {str(e)}"[:300]
                db.commit()
        except Exception as db_err:
            print(f"[Pipeline] Failed to update task status on exception: {db_err}")
            db.rollback()
    finally:
        # Guarantee that database session is closed
        db.close()

