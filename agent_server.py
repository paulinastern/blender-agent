from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional

import requests
from fastapi import FastAPI
from pydantic import BaseModel, Field

from blendagent_manifest import (
    build_system_prompt,
    fallback_plan,
    load_manifest,
    normalize_plan,
)

app = FastAPI(title="BlendAgent planner", version="2")

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3"

_MANIFEST = load_manifest()
SYSTEM_PROMPT = build_system_prompt(_MANIFEST)


class PlanRequest(BaseModel):
    prompt: str = Field(..., min_length=1, description="User natural-language request")
    context: Optional[Dict[str, Any]] = None
    send_context: bool = False


class PlanResponse(BaseModel):
    operation: str
    source: str
    needs_clarification: bool = False
    reason: Optional[str] = None
    error: Optional[str] = None


def extract_json(text: str) -> Optional[str]:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return match.group()
    return None


def call_llm(user_prompt: str, context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    ctx_block = ""
    if context:
        ctx_block = "\n\nContext (JSON):\n" + json.dumps(context, indent=2) + "\n"

    prompt = f"""
{SYSTEM_PROMPT}

User request:
{user_prompt}
{ctx_block}
JSON:
"""

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL,
                "prompt": prompt,
                "stream": False,
            },
            timeout=60,
        )
        response.raise_for_status()

        data = response.json()
        text = data.get("response", "").strip()

        print("LLM response:", text)

        json_text = extract_json(text)
        if not json_text:
            return fallback_plan(user_prompt, _MANIFEST)

        parsed = json.loads(json_text)
        if not isinstance(parsed, dict):
            return fallback_plan(user_prompt, _MANIFEST)

        if "operation" not in parsed:
            return fallback_plan(user_prompt, _MANIFEST)

        if "needs_clarification" not in parsed:
            parsed["needs_clarification"] = False
        if "reason" not in parsed:
            parsed["reason"] = None

        normalized = normalize_plan(parsed, _MANIFEST, "llm", user_prompt)
        return normalized

    except Exception as e:
        print("LLM error:", e)
        out = fallback_plan(user_prompt, _MANIFEST)
        out["error"] = str(e)
        return out


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok", "model": MODEL}


@app.post("/plan", response_model=PlanResponse)
def plan_nodes(data: PlanRequest) -> PlanResponse:
    print("Received prompt:", data.prompt)
    ctx = None
    if data.send_context and data.context is not None:
        ctx = data.context

    plan = call_llm(data.prompt.strip(), ctx)
    print("Plan:", plan)

    if not isinstance(plan, dict):
        fb = fallback_plan(data.prompt, _MANIFEST)
        return PlanResponse(**fb, error="Invalid plan payload")

    err = plan.pop("error", None)

    try:
        return PlanResponse(**plan, error=err)
    except Exception as e:
        fb = fallback_plan(data.prompt, _MANIFEST)
        return PlanResponse(**fb, error=str(e))
