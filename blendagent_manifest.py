"""
Shared tool manifest loader (no Blender imports).
Used by agent_server and can be loaded from blend_agent_addon via importlib.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional, Set

_MANIFEST_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "blendagent_tools.json")


def load_manifest(path: Optional[str] = None) -> Dict[str, Any]:
    p = path or _MANIFEST_PATH
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def tools_by_id(manifest: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {t["id"]: t for t in manifest["tools"]}


def allowed_operation_ids(manifest: Dict[str, Any]) -> Set[str]:
    return {t["id"] for t in manifest["tools"]}


def build_system_prompt(manifest: Dict[str, Any]) -> str:
    ids = [t["id"] for t in manifest["tools"]]
    lines = [
        "You are an AI planner for a Blender assistant.",
        "Convert the user request into JSON.",
        "",
        "Allowed operations:",
    ]
    for i in ids:
        lines.append(f"- {i}")
    lines.extend(
        [
            "",
            "Rules:",
            '- Return ONLY a single JSON object with keys: "operation" (string), "needs_clarification" (boolean), "reason" (string or null).',
            "- needs_clarification should be false unless the request is impossible to map.",
            "- reason is null unless needs_clarification is true.",
            "- Choose only one allowed operation.",
            "- Never explain outside the JSON.",
            "",
            "Examples:",
            "",
        ]
    )
    for t in manifest["tools"]:
        ex = t.get("example_user")
        if ex:
            lines.append(ex)
            lines.append(
                json.dumps(
                    {
                        "operation": t["id"],
                        "needs_clarification": False,
                        "reason": None,
                    },
                    separators=(",", ":"),
                )
            )
            lines.append("")
    return "\n".join(lines).strip() + "\n"


def fallback_plan(user_prompt: str, manifest: Dict[str, Any]) -> Dict[str, Any]:
    p = user_prompt.lower()
    by_id = tools_by_id(manifest)
    for tid in manifest.get("fallback_order", []):
        t = by_id.get(tid)
        if not t:
            continue
        keywords = t.get("keywords") or []
        for kw in keywords:
            if kw.lower() in p:
                return {
                    "operation": tid,
                    "source": "fallback",
                    "needs_clarification": False,
                    "reason": None,
                }
    return {
        "operation": "unknown",
        "source": "fallback",
        "needs_clarification": True,
        "reason": "Could not match request to a known operation.",
    }


def normalize_plan(
    raw: Dict[str, Any],
    manifest: Dict[str, Any],
    source: str,
    user_prompt: str,
) -> Dict[str, Any]:
    allowed = allowed_operation_ids(manifest)
    op = raw.get("operation")
    if not isinstance(op, str):
        return {**fallback_plan(user_prompt, manifest), "source": source}
    op = op.strip()
    if op not in allowed:
        return {**fallback_plan(user_prompt, manifest), "source": source}
    reason = raw.get("reason")
    if reason is not None and not isinstance(reason, str):
        reason = str(reason)
    return {
        "operation": op,
        "source": source,
        "needs_clarification": bool(raw.get("needs_clarification", False)),
        "reason": reason,
    }
