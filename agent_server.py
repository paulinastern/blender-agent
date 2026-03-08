from fastapi import FastAPI
from pydantic import BaseModel
import requests
import json
import re

app = FastAPI()

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3"


class Prompt(BaseModel):
    prompt: str


SYSTEM_PROMPT = """
You are an AI planner for a Blender procedural modeling tool.

Convert the user request into JSON.

Allowed operations:
- subdivide_mesh
- scatter_objects

Return ONLY JSON.

Examples:

subdivide mesh
{"operation":"subdivide_mesh","level":2}

scatter rocks on terrain
{"operation":"scatter_objects","density":20}
"""


def extract_json(text):

    match = re.search(r"\{.*\}", text, re.DOTALL)

    if match:
        return match.group()

    return None


def call_llm(user_prompt):

    prompt = f"""
{SYSTEM_PROMPT}

User request:
{user_prompt}

JSON:
"""

    try:

        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL,
                "prompt": prompt,
                "stream": False
            },
            timeout=60
        )

        data = response.json()

        text = data.get("response", "").strip()

        print("LLM response:", text)

        json_text = extract_json(text)

        if not json_text:
            return {"operation": "unknown"}

        return json.loads(json_text)

    except Exception as e:

        print("LLM error:", e)

        return {"operation": "unknown"}


@app.post("/plan")
def plan_nodes(data: Prompt):

    print("Received prompt:", data.prompt)

    plan = call_llm(data.prompt)

    print("Plan:", plan)

    return plan