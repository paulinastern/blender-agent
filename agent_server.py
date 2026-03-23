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
You are an AI planner for a Blender assistant.

Convert the user request into JSON.

Allowed operations:
- subdivide_mesh
- noise_terrain
- glossy_material
- toon_material
- hair_material_basic
- eye_material_basic
- water_material

Rules:
- Return ONLY JSON.
- Never explain.
- Choose only one allowed operation.

Examples:

subdivide mesh
{"operation":"subdivide_mesh"}

add terrain noise
{"operation":"noise_terrain"}

make this glossy
{"operation":"glossy_material"}

make this toon
{"operation":"toon_material"}

make this hair shiny
{"operation":"hair_material_basic"}

make this eye shiny
{"operation":"eye_material_basic"}

make this water
{"operation":"water_material"}

add ocean material
{"operation":"water_material"}
"""


# ------------------------
# HELPERS
# ------------------------

def extract_json(text):
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return match.group()
    return None


def fallback_plan(user_prompt: str):
    p = user_prompt.lower()

    # VERY IMPORTANT: order matters (specific → general)

    if any(word in p for word in ["water", "ocean", "liquid", "sea", "lake"]):
        return {"operation": "water_material", "source": "fallback"}

    if any(word in p for word in ["eye", "eyes", "iris", "pupil", "cornea"]):
        return {"operation": "eye_material_basic", "source": "fallback"}

    if any(word in p for word in ["hair", "bangs", "strands", "hair shader", "hair material"]):
        return {"operation": "hair_material_basic", "source": "fallback"}

    if any(word in p for word in ["toon", "anime", "stylized", "cartoon", "cel"]):
        return {"operation": "toon_material", "source": "fallback"}

    # glossy AFTER water so it doesn't hijack
    if any(word in p for word in ["glossy", "shiny", "reflective", "polished"]):
        return {"operation": "glossy_material", "source": "fallback"}

    if any(word in p for word in ["noise", "terrain", "hills", "mountain", "bumpy", "rocky"]):
        return {"operation": "noise_terrain", "source": "fallback"}

    if any(word in p for word in ["subdivide", "smooth", "smoother"]):
        return {"operation": "subdivide_mesh", "source": "fallback"}

    return {"operation": "unknown", "source": "fallback"}


# ------------------------
# LLM CALL
# ------------------------

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
        response.raise_for_status()

        data = response.json()
        text = data.get("response", "").strip()

        print("LLM response:", text)

        json_text = extract_json(text)
        if not json_text:
            return fallback_plan(user_prompt)

        parsed = json.loads(json_text)

        if "operation" not in parsed:
            return fallback_plan(user_prompt)

        parsed["source"] = "llm"
        return parsed

    except Exception as e:
        print("LLM error:", e)
        return fallback_plan(user_prompt)


# ------------------------
# ROUTE
# ------------------------

@app.post("/plan")
def plan_nodes(data: Prompt):
    print("Received prompt:", data.prompt)
    plan = call_llm(data.prompt)
    print("Plan:", plan)
    return plan
#uvicorn agent_server:app --reload
#Confirm these prompts route correctly:

#scatter rocks on terrain
#add terrain noise
#make this glossy  ; make this toon  ; make this hair shiny
#subdivide mesh