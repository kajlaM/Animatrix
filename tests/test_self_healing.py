"""
test_self_healing.py
Tests the LLM self-healing render loop.
Injects a broken first response with an invalid function name on the first attempt,
then allows the real Gemini model to receive the stderr traceback and correct the code on attempt 1.
Verifies that the render succeeds and task status is 'completed'.

Resume Claim Backed:
"Engineered an LLM self-healing render loop with FastAPI and subprocess,
 feeding Manim render errors to the LLM for correction."
"""

import os
import sys
import uuid
from unittest.mock import patch

# Add repo root to Python path
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from database import SessionLocal, init_db
from models import User, Task
import generate_scene
from generate_scene import generate_animation_video

# Intentionally broken Manim code for the first attempt
BROKEN_FIRST_ATTEMPT_CODE = """
from manim import *

class BrokenSelfHealingScene(Scene):
    def construct(self):
        # Valid circle
        circle = Circle(color=BLUE)
        # Intentionally invalid function name to trigger a real Python NameError in Manim
        self.play(NonExistentBrokenTransformMethod(circle))
        self.wait(1)
"""

def run_self_healing_test():
    print("=" * 60)
    print("Testing LLM Self-Healing Render Loop")
    print("=" * 60)

    # Initialize DB
    init_db()
    db = SessionLocal()

    # Ensure a test user exists
    test_user = db.query(User).filter(User.username == "test_healing_user").first()
    if not test_user:
        test_user = User(username="test_healing_user", hashed_password="hashed_pw_dummy")
        db.add(test_user)
        db.commit()
        db.refresh(test_user)

    task_id = str(uuid.uuid4())
    prompt = "Create a blue circle and animate it"

    # Create task
    task = Task(
        id=task_id,
        user_id=test_user.id,
        prompt=prompt,
        status="processing"
    )
    db.add(task)
    db.commit()
    db.close()

    original_ask_ai = generate_scene.ask_ai_for_manim_code
    call_count = 0

    def mock_ask_ai(prompt_arg, error_feedback=None, previous_code=None):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            print(f"\n[Test Mock] Attempt 0: Injected broken code with invalid function 'NonExistentBrokenTransformMethod'")
            return f"```python\n{BROKEN_FIRST_ATTEMPT_CODE}\n```"
        else:
            print(f"\n[Test Real LLM] Attempt {call_count - 1}: Passing error feedback and stderr back to real Gemini API...")
            print(f"[Error Feedback Passed to Gemini]:\n{error_feedback[:200]}...")
            return original_ask_ai(prompt_arg, error_feedback, previous_code)

    with patch("generate_scene.ask_ai_for_manim_code", side_effect=mock_ask_ai):
        print(f"[Action] Launching pipeline for task {task_id}...")
        generate_animation_video(prompt, task_id)

    # Verify task state in database
    db = SessionLocal()
    updated_task = db.query(Task).filter(Task.id == task_id).first()

    print("\n" + "-" * 50)
    print("Self-Healing Test Results:")
    print(f"Task ID: {updated_task.id}")
    print(f"Final Status: {updated_task.status}")
    print(f"Total LLM calls made: {call_count} (Expected: 2 -> 1 broken + 1 healed)")
    print(f"Video Path: {updated_task.video_path}")
    print(f"Error Field: {updated_task.error}")
    print("-" * 50)

    assert call_count >= 2, f"Expected at least 2 LLM calls, but got {call_count}"
    assert updated_task.status == "completed", f"Task did not reach 'completed' status! Status: {updated_task.status}, Error: {updated_task.error}"
    assert updated_task.video_path and os.path.exists(updated_task.video_path), "Rendered video file does not exist!"
    assert "NonExistentBrokenTransformMethod" not in updated_task.code, "Broken function name was not removed by Gemini!"

    print("\n[SUCCESS] Self-Healing Test Passed! The LLM successfully caught the render error and healed the code.")
    db.close()

if __name__ == "__main__":
    run_self_healing_test()

