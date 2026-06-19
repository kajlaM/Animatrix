import os
import re
from dotenv import load_dotenv
from google import genai

load_dotenv()

def clean_code(text):
    text = re.sub(r"```python", "", text)
    text = re.sub(r"```", "", text)
    return text.strip()

try:
    client = genai.Client(
        api_key=os.getenv("GEMINI_API_KEY")
    )
    prompt = input("Enter your prompt: ")
    response = client.models.generate_content(
        model="gemini-3-flash-preview",
        contents=f"""

        You are an expert Manim developer.

        Generate a complete Manim scene for the following request:

        {prompt}

        Rules:

        1. Return ONLY Python code.

        2. Do not include explanations.

        3. Do not use markdown.

        4. Output a complete runnable Manim scene.
        IMPORTANT:
        - Do NOT use MathTex.
        - Do NOT use Tex.
        - Use Text() objects only.
        - Return runnable code.
        """
    )
    print("\nGemini Response:\n")
    cleaned_code = clean_code(response.text)

    with open("generated_scene.py", "w") as f:
        f.write(cleaned_code)

    print("\nCode saved to generated_scene.py")

except Exception as e:
    print("\nERROR:\n")
    print(e)