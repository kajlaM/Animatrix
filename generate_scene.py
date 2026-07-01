import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)

def ask_gemini(user_prompt):

    system_prompt = """
You are an expert Python and Manim developer.

IMPORTANT RULES:
- Return ONLY executable Python code.
- Do NOT include explanations.
- Do NOT include markdown fences.
- Output one complete Manim Scene class.
- Use only Text() for labels.
- Never use Tex() or MathTex().
- Include self.wait() calls.
- The response must start with: from manim import *
"""

    full_prompt = system_prompt + "\n\n" + user_prompt

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=full_prompt
    )

    return response.text


if __name__ == "__main__":

    prompt = input("Enter your prompt:\n")

    result = ask_gemini(prompt)

    with open("generated_scene.py", "w") as f:
        f.write(result)

    print("\nSaved to generated_scene.py")