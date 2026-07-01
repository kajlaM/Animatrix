import os
import re
import sys
import datetime
import subprocess
import glob
import shutil
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Stage 1 — Load API credentials securely
# Attempt to load .env from current directory, parent directory, or environment fallback
current_dir = os.path.dirname(os.path.abspath(__file__))
env_paths = [
    os.path.join(current_dir, ".env"),
    os.path.join(os.path.dirname(current_dir), ".env")
]

loaded = False
for env_path in env_paths:
    if os.path.exists(env_path):
        load_dotenv(env_path)
        loaded = True
        break

if not loaded:
    load_dotenv()

# Initialize Gemini Client
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    # If not found, print warning but don't fail immediately (it will fail on client initialization or call)
    print("Warning: GEMINI_API_KEY not found in environment variables.")

client = genai.Client(api_key=api_key)

# Stage 2 & 3 — Send prompt to Gemini & Prompt Engineering
def ask_ai_for_manim_code(prompt: str, error_feedback: str = None, previous_code: str = None) -> str:
    """
    Sends the user prompt (and optional error feedback for self-healing) to Gemini
    and returns the raw model response containing the python code.
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

    try:
        # Use system_instruction config (recommended by google-genai SDK)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=user_content,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt
            )
        )
        return response.text
    except Exception as e:
        # Fallback to simple concatenation if config throws error or for compatibility
        try:
            full_prompt = f"{system_prompt}\n\nUser request:\n{user_content}"
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=full_prompt
            )
            return response.text
        except Exception as inner_e:
            raise RuntimeError(f"Failed to communicate with Gemini API: {inner_e}")

# Stage 4 — Extract Python
def extract_python_code(raw_text: str) -> str:
    """
    Extracts the python code from the raw text response of the LLM.
    Strips markdown code blocks, explanations, etc.
    """
    if not raw_text:
        return ""
    
    # Pattern to match ```python ... ``` or ``` ... ```
    pattern = r"```(?:python)?\s*(.*?)\s*```"
    match = re.search(pattern, raw_text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    
    # Fallback: if no markdown code fences found, return raw text trimmed
    return raw_text.strip()

def get_scene_class_name(code: str) -> str:
    """
    Extracts the name of the Scene class defined in the generated python code.
    Matches classes inheriting from standard Manim Scene types.
    """
    # Regex matching class ClassName(SceneType)
    pattern = r"class\s+(\w+)\s*\((?:Scene|ThreeDScene|VectorScene|LinearTransformationScene|MovingCameraScene|MovingCamera|GraphScene)\)"
    match = re.search(pattern, code)
    if match:
        return match.group(1)
    
    # Fallback to any class declaration in the code
    pattern_fallback = r"class\s+(\w+)\s*\("
    match_fallback = re.search(pattern_fallback, code)
    if match_fallback:
        return match_fallback.group(1)
        
    return None

# Public Pipeline Function
def generate_animation_video(prompt: str) -> str:
    """
    Converts user prompt to a rendered Manim video file.
    Saves generated code, calls Manim subprocess, and self-heals up to 3 times on failure.
    Returns the absolute path of the rendered MP4 video.
    """
    workspace_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    temp_dir = os.path.join(current_dir, "temp_scenes")
    os.makedirs(temp_dir, exist_ok=True)
    
    max_retries = 3
    current_retry = 0
    error_feedback = None
    previous_code = None
    
    # Determine the Manim command binary (use shutil.which or fallback to sys.executable)
    manim_bin = shutil.which("manim")
    
    while current_retry <= max_retries:
        if current_retry > 0:
            print(f"[Self-Healing] Attempt {current_retry} of {max_retries}...")
        
        # Stage 2 & 3: Send prompt and get raw response
        raw_output = ask_ai_for_manim_code(prompt, error_feedback, previous_code)
        
        # Stage 4: Extract python code
        code = extract_python_code(raw_output)
        previous_code = code
        
        # Stage 5: Save generated code into uniquely named timestamped file
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        script_basename = f"animation_{timestamp}_try{current_retry}"
        filename = f"{script_basename}.py"
        file_path = os.path.join(temp_dir, filename)
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(code)
            
        # Get scene class name for rendering
        scene_name = get_scene_class_name(code)
        if not scene_name:
            # Fallback if no class found in generated code
            error_feedback = "No class definition inheriting from Scene or ThreeDScene found in code."
            current_retry += 1
            continue
            
        # Stage 6: Render video
        # Build command list
        if manim_bin:
            cmd = [manim_bin, "-ql", file_path]
        else:
            cmd = [sys.executable, "-m", "manim", "-ql", file_path]
            
        cmd.append(scene_name)
        
        print(f"Running Manim: {' '.join(cmd)}")
        
        try:
            # Execute Manim in subprocess. Cwd is set to workspace_root so media directory is shared
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=workspace_root
            )
            
            if result.returncode == 0:
                # Rendering succeeded! Find the rendered MP4 file
                # Search inside: media/videos/animation_xxx/480p15/MyScene.mp4
                search_pattern = os.path.join(workspace_root, "media", "videos", script_basename, "**", "*.mp4")
                mp4_files = glob.glob(search_pattern, recursive=True)
                
                if mp4_files:
                    video_path = os.path.abspath(mp4_files[0])
                    print(f"Rendering successful! Video path: {video_path}")
                    return video_path
                else:
                    # Rendered successfully but MP4 search failed. Let's try searching general media/videos
                    # for any recently modified file or raise error
                    error_feedback = (
                        f"Manim execution reported success, but could not locate the output video "
                        f"using search pattern: {search_pattern}"
                    )
                    current_retry += 1
            else:
                # Rendering failed. Combine stdout and stderr for maximum context
                error_feedback = f"Return Code: {result.returncode}\nStderr:\n{result.stderr}\nStdout:\n{result.stdout}"
                current_retry += 1
                print(f"Manim error on try {current_retry - 1}:\n{result.stderr}")
                
        except Exception as e:
            error_feedback = f"Subprocess exception: {str(e)}"
            current_retry += 1
            print(f"Exception on try {current_retry - 1}: {e}")
            
    # If we exited the loop, it means we exhausted all retries
    raise RuntimeError(
        f"Failed to generate and render Manim video for prompt '{prompt}' "
        f"after {max_retries} retries.\nLast Error Feedback:\n{error_feedback}"
    )

if __name__ == "__main__":
    # Small test CLI
    test_prompt = input("Enter a test prompt for Manim video: ")
    if not test_prompt:
        test_prompt = "A red square rotating and transforming into a blue circle."
    print(f"Generating video for: '{test_prompt}'")
    try:
        path = generate_animation_video(test_prompt)
        print(f"SUCCESS! Rendered video saved at: {path}")
    except Exception as e:
        print(f"FAILURE: {e}")
