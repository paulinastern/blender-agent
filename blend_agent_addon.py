try:
    import bpy
except ImportError:
    pass

bl_info = {
    "name": "BlendAgent",
    "author": "Paulina Stern",
    "version": (0, 3, 10),
    "blender": (4, 0, 0),
    "category": "Object",
    "description": "Assistant (manifest tools) or Generation (bpy scripts); Ollama or OpenRouter",
}

import json
import math
import os
import re
import traceback
import urllib.error
import urllib.request

import bpy

# ---------------------------------------------------------------------------
# Manifest: prefer blendagent_tools.json next to this file; else embedded
# (single .py install on Windows works without extra files — keep JSON in sync)
# ---------------------------------------------------------------------------

_ADDON_DIR = os.path.dirname(os.path.realpath(__file__))

_EMBEDDED_MANIFEST_JSON = '{"version":1,"fallback_order":["water_material","eye_material_basic","hair_material_basic","hair_particles_vtuber","toon_material","glossy_material","skin_material_vtuber","mesh_preset_vtuber_head","mesh_preset_vtuber_body","lighting_lookdev_three_point","add_vtuber_armature","noise_terrain","subdivide_mesh","keyframe_loc_rot","vtuber_readiness_check","summarize_selection","list_material_nodes"],"tools":[{"id":"water_material","kind":"action","category":"material","requires":"active_object","description":"Water or ocean-like translucent material with bump","keywords":["water","ocean","liquid","sea","lake"],"example_user":"make this water"},{"id":"eye_material_basic","kind":"action","category":"material","requires":"active_object","description":"Stylized eye material with gradient","keywords":["eye","eyes","iris","pupil","cornea"],"example_user":"make this eye shiny"},{"id":"hair_material_basic","kind":"action","category":"material","requires":"active_object","description":"Stylized hair for mesh cards: anisotropic sheen, noise roughness, bump, rim + band streaks","keywords":["hair","bangs","strands","hair shader","hair material"],"example_user":"make this hair shiny"},{"id":"hair_particles_vtuber","kind":"action","category":"hair","requires":"active_mesh","description":"Particle hair on mesh: path strands, Principled strand material (EEVEE-friendly), radius_scale set for visibility","keywords":["particle hair","scalp hair","hair particles","strand hair","add hair particles","hair system"],"example_user":"add particle hair to this mesh"},{"id":"toon_material","kind":"action","category":"material","requires":"active_object","description":"Toon / cel-shaded look","keywords":["toon","anime","stylized","cartoon","cel"],"example_user":"make this toon"},{"id":"glossy_material","kind":"action","category":"material","requires":"active_object","description":"Glossy reflective surface with subtle noise bump","keywords":["glossy","shiny","reflective","polished"],"example_user":"make this glossy"},{"id":"skin_material_vtuber","kind":"action","category":"material","requires":"active_object","description":"VTuber-style skin: subsurface, subtle noise, softer than default grey","keywords":["skin","face skin","body skin","vtuber skin","subsurface skin","character skin"],"example_user":"apply vtuber skin material"},{"id":"mesh_preset_vtuber_head","kind":"action","category":"mesh","requires":"none","description":"Add a UV sphere scaled as a stylized head (VTuber blockout)","keywords":["head mesh","vtuber head","add head","head preset","face mesh"],"example_user":"add vtuber head mesh"},{"id":"mesh_preset_vtuber_body","kind":"action","category":"mesh","requires":"none","description":"Add a subdivided cube scaled as a stylized torso (VTuber blockout)","keywords":["body mesh","vtuber body","torso mesh","body preset","torso preset"],"example_user":"add vtuber body mesh"},{"id":"lighting_lookdev_three_point","kind":"action","category":"scene","requires":"none","description":"Replace prior BlendAgent lookdev lights; add 3 area lights (key/fill/rim) + subtle dark world","keywords":["three point lighting","studio lights","lookdev","lighting preset","rim light","key light","fill light","character lighting"],"example_user":"add three point lighting for lookdev"},{"id":"add_vtuber_armature","kind":"action","category":"rig","requires":"none","description":"Add a minimal humanoid armature (hips-spine-head, arms, legs) for VTuber-style posing","keywords":["armature","rig","bones","skeleton","vtuber rig","humanoid rig","add rig"],"example_user":"add a vtuber armature"},{"id":"noise_terrain","kind":"action","category":"geometry","requires":"active_mesh","description":"Displace mesh with procedural noise (geometry nodes)","keywords":["noise","terrain","hills","mountain","bumpy","rocky"],"example_user":"add terrain noise"},{"id":"subdivide_mesh","kind":"action","category":"geometry","requires":"active_mesh","description":"Subdivide the active mesh via geometry nodes","keywords":["subdivide","smooth","smoother"],"example_user":"subdivide mesh"},{"id":"summarize_selection","kind":"inspect","category":"scene","requires":"none","description":"Summarize active object and basic stats (read-only)","keywords":["summarize selection","summarize","describe selection","what is selected","scene summary"],"example_user":"summarize my selection"},{"id":"list_material_nodes","kind":"inspect","category":"scene","requires":"active_object","description":"List nodes in the active material node tree (read-only)","keywords":["list material nodes","list shader nodes","material nodes","node tree"],"example_user":"list material nodes"},{"id":"vtuber_readiness_check","kind":"inspect","category":"scene","requires":"none","description":"VTuber pipeline checklist: workspace, mode, mesh, materials, shape keys, armatures (read-only)","keywords":["vtuber check","vtuber readiness","character check","live3d","vrm prep","pipeline check"],"example_user":"vtuber readiness check"},{"id":"keyframe_loc_rot","kind":"action","category":"animation","requires":"active_object","description":"Insert location and rotation keyframes at the current frame (object or pose bones)","keywords":["keyframe","keyframes","key frame","animate transform","record keyframe"],"example_user":"keyframe location and rotation"}]}'


def _load_manifest():
    try:
        p = os.path.join(_ADDON_DIR, "blendagent_tools.json")
        if os.path.isfile(p):
            with open(p, encoding="utf-8") as f:
                return json.load(f)
    except Exception as exc:
        print("BlendAgent: external manifest:", exc)
    try:
        return json.loads(_EMBEDDED_MANIFEST_JSON)
    except Exception as exc:
        print("BlendAgent: embedded manifest failed:", exc)
        return {"tools": [], "fallback_order": []}


try:
    MANIFEST = _load_manifest()
except Exception as exc:
    print("BlendAgent: failed to load manifest:", exc)
    MANIFEST = {"tools": [], "fallback_order": []}


_EMBEDDED_PLAYBOOK_JSON = '{"version":1,"description":"Human-written workflow hints for the planner (not executable code). Ship beside the add-on or rely on embedded defaults.","tips":["One planner call maps to one manifest tool; chain steps with multiple Run invocations or manual tools.","For VTuber lookdev: blockout meshes -> lighting preset -> skin/eyes -> hair (mesh shader and/or scalp particles) -> armature -> weights.","Hair particles need a mesh scalp; use Rendered shading to preview strands.","Inspect tools (summarize_selection, vtuber_readiness_check) are read-only and good for debugging context."],"workflows":[{"id":"vtuber_lookdev","title":"VTuber-style lookdev (typical order)","steps":["Add head/body blockout meshes or import your character mesh.","Run lighting_lookdev_three_point so the viewport read matches materials.","Apply skin_material_vtuber on skin meshes; eye_material_basic on eyes.","Use hair_material_basic for mesh hair cards, or hair_particles_vtuber on the scalp mesh.","Add add_vtuber_armature, then weight paint and shape keys outside BlendAgent."],"tool_ids":["mesh_preset_vtuber_head","mesh_preset_vtuber_body","lighting_lookdev_three_point","skin_material_vtuber","eye_material_basic","hair_material_basic","hair_particles_vtuber","add_vtuber_armature","vtuber_readiness_check"]},{"id":"material_pass","title":"Quick material exploration","steps":["Select mesh, run water / glossy / toon / skin as needed.","Use list_material_nodes inspect if nodes look wrong."],"tool_ids":["water_material","glossy_material","toon_material","list_material_nodes"]}]}'


def _load_playbook():
    try:
        p = os.path.join(_ADDON_DIR, "blendagent_playbook.json")
        if os.path.isfile(p):
            with open(p, encoding="utf-8") as f:
                return json.load(f)
    except Exception as exc:
        print("BlendAgent: playbook file:", exc)
    try:
        return json.loads(_EMBEDDED_PLAYBOOK_JSON)
    except Exception as exc:
        print("BlendAgent: embedded playbook:", exc)
        return {"version": 1, "workflows": [], "tips": []}


def _compact_playbook_for_llm(playbook):
    """Small JSON-safe structure for planner context (token budget)."""
    if not isinstance(playbook, dict):
        return {"tips": [], "workflows": []}
    out = {"tips": list(playbook.get("tips") or [])[:16]}
    wfs = []
    for w in (playbook.get("workflows") or [])[:8]:
        if not isinstance(w, dict):
            continue
        wfs.append(
            {
                "id": w.get("id"),
                "title": w.get("title"),
                "steps": (w.get("steps") or [])[:16],
                "tool_ids": (w.get("tool_ids") or [])[:24],
            }
        )
    out["workflows"] = wfs
    return out


def _merge_playbook_into_context(ctx):
    pb = _compact_playbook_for_llm(_load_playbook())
    if ctx is None:
        return {"playbook": pb}
    if not isinstance(ctx, dict):
        return {"playbook": pb}
    merged = dict(ctx)
    merged["playbook"] = pb
    return merged


def _transcript_tail_lines(transcript, max_lines):
    lines = [ln.rstrip() for ln in (transcript or "").splitlines()]
    lines = [ln for ln in lines if ln.strip()]
    try:
        n = max(8, min(int(max_lines), 200))
    except Exception:
        n = 48
    return lines[-n:]


def merge_planner_context(scene, send_context):
    """Scene snapshot + playbook + bounded conversation memory for the planner."""
    ba = scene.blendagent
    ctx = build_scene_context(send_context)
    if getattr(ba, "agent_mode", "ASSISTANT") == "GENERATION":
        if not isinstance(ctx, dict):
            ctx = {} if ctx is None else {}
    else:
        ctx = _merge_playbook_into_context(ctx)
        if not isinstance(ctx, dict):
            ctx = {}
    tick = int(getattr(ba, "session_tick", 0) or 0)
    ctx["session_tick"] = tick
    if getattr(ba, "include_conversation_memory", True):
        ctx["memory"] = {
            "recent_transcript_lines": _transcript_tail_lines(
                ba.transcript or "",
                getattr(ba, "memory_max_lines", 48) or 48,
            ),
            "note": "Lines are newest at the end; older detail may be truncated. Prefer current scene context.",
        }
    else:
        ctx["memory"] = {"recent_transcript_lines": [], "note": "Conversation memory disabled."}
    return ctx


def _openrouter_model_id_from_scene(ba):
    fam = getattr(ba, "openrouter_model_family", None) or "GPT"
    return OPENROUTER_MODEL_ID.get(fam, OPENROUTER_MODEL_ID["GPT"])


def _store_generation_preview(ba, raw_text):
    if not raw_text:
        ba.generation_preview = ""
        return
    t = raw_text.strip().replace("\r\n", "\n")
    if len(t) > GENERATION_PREVIEW_MAX_CHARS:
        t = t[: GENERATION_PREVIEW_MAX_CHARS - 3] + "..."
    ba.generation_preview = t


def _make_manual_tool_items():
    """Static enum items for RNA (Blender 4.0 fails PropertyGroup EnumProperty with items=callback)."""
    items = [("AUTO", "Natural language (plan)", "Ask the planner to choose a tool")]
    for t in MANIFEST.get("tools", []):
        tid = t.get("id")
        if not tid or not isinstance(tid, str):
            continue
        desc = (t.get("description") or "")[:2048]
        desc = desc.encode("ascii", "replace").decode("ascii")
        label = tid if t.get("kind") != "inspect" else tid + " (inspect)"
        items.append((tid, label, desc))
    return tuple(items)


# Built once at load; fixed sequence for bpy EnumProperty (no callback — Blender 4.0 PropertyGroup)
MANUAL_TOOL_ITEMS = _make_manual_tool_items()

PLANNER_MODE_ITEMS = (
    ("DIRECT", "Ollama (local)", "Ollama from Blender; no cloud API key"),
    ("FASTAPI", "Planner server", "Requires agent_server.py for developers or custom deployments"),
    ("OPENROUTER", "OpenRouter", "Cloud models; set API key in Edit → Preferences → Add-ons → BlendAgent"),
)

AGENT_MODE_ITEMS = (
    (
        "ASSISTANT",
        "Assistant",
        "Planner picks trusted manifest tools (Ollama, OpenRouter, or FastAPI)",
    ),
    (
        "GENERATION",
        "Generation",
        "OpenRouter only: cloud model writes a bpy script; add API key in Preferences",
    ),
)

GENERATED_TEXT_NAME = "BlendAgent_Generated"
OPENROUTER_CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"

# OpenRouter model ids (https://openrouter.ai/docs) — two fixed choices in the UI
OPENROUTER_MODEL_FAMILY_ITEMS = (
    ("GPT", "OpenAI GPT-4o", "General-purpose; strong at code"),
    ("CLAUDE", "Anthropic Claude 3.5 Sonnet", "Strong reasoning and instructions"),
)
OPENROUTER_MODEL_ID = {
    "GPT": "openai/gpt-4o",
    "CLAUDE": "anthropic/claude-3.5-sonnet",
}

GENERATION_PREVIEW_MAX_CHARS = 520


def _tools_by_id():
    return {t["id"]: t for t in MANIFEST.get("tools", [])}


def _extract_json(text):
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return match.group()
    return None


def _allowed_operation_ids(manifest):
    return {t["id"] for t in manifest["tools"]}


def _build_system_prompt(manifest):
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


def _fallback_plan(user_prompt, manifest):
    p = user_prompt.lower()
    by_id = {t["id"]: t for t in manifest["tools"]}
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


def _normalize_plan(raw, manifest, source, user_prompt):
    allowed = _allowed_operation_ids(manifest)
    op = raw.get("operation")
    if not isinstance(op, str):
        return {**_fallback_plan(user_prompt, manifest), "source": source}
    op = op.strip()
    if op not in allowed:
        return {**_fallback_plan(user_prompt, manifest), "source": source}
    reason = raw.get("reason")
    if reason is not None and not isinstance(reason, str):
        reason = str(reason)
    return {
        "operation": op,
        "source": source,
        "needs_clarification": bool(raw.get("needs_clarification", False)),
        "reason": reason,
    }


def _http_get_json(url, timeout=10):
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _http_post_json(url, payload, timeout=120):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _http_post_json_headers(url, payload, extra_headers, timeout=120):
    data = json.dumps(payload).encode("utf-8")
    hdrs = {"Content-Type": "application/json", **extra_headers}
    req = urllib.request.Request(url, data=data, headers=hdrs)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _prefs_openrouter_key():
    try:
        addon = bpy.context.preferences.addons.get(__name__)
        if addon and getattr(addon, "preferences", None):
            return (addon.preferences.openrouter_api_key or "").strip()
    except Exception:
        pass
    return ""


def _build_generation_system_prompt():
    return (
        "You are a Blender Python code generator for Blender 4.x.\n"
        "Write a single script using `import bpy` and the `bpy` API only.\n"
        "Rules:\n"
        "- Use only Python standard library plus `bpy`.\n"
        "- Do not import os, sys, subprocess, socket; do not read/write arbitrary files.\n"
        "- Prefer bpy.ops with context.view_layer.objects.active set when modifying the active object.\n"
        "- Use try/except around risky calls; on failure use print() with a clear message.\n"
        "- The fenced block must include `import bpy` or `from bpy import ...`.\n"
        "- Node sockets: NEVER use node.inputs[\"Specular\"], [\"Transmission\"], etc. without checking.\n"
        "  Blender 4.x Principled BSDF renames many sockets vs Blender 3.x tutorials.\n"
        "  Examples: use \"Specular IOR Level\" before \"Specular\"; \"Transmission Weight\" before \"Transmission\";\n"
        "  \"Subsurface Weight\" before old subsurface amount names. For specular strength use Specular IOR Level (float).\n"
        "  Pattern: `s = node.inputs.get(\"Specular IOR Level\") or node.inputs.get(\"Specular\")` then if s: s.default_value = ...\n"
        "Output format: respond with exactly one markdown fenced block:\n\n"
        "```python\n"
        "import bpy\n"
        "# ... your code ...\n"
        "```\n"
        "No prose before or after the fence."
    )


def _strip_reasoning_tags(text):
    """Remove common hidden-reasoning wrappers so fences can be found."""
    if not text:
        return text
    t = text
    t = re.sub(r"<think>[\s\S]*?</think>", "", t, flags=re.IGNORECASE)
    t = re.sub(r"<thinking>[\s\S]*?</thinking>", "", t, flags=re.IGNORECASE)
    return t.strip()


def _extract_generation_code(text):
    """Return extracted script or None if nothing usable."""
    if not text:
        return None
    t = _strip_reasoning_tags((text or "").strip())
    # 1) Markdown fences: prefer bpy-like block, else first non-empty block
    for pat in (
        r"```(?:python|py)\s*([\s\S]*?)```",
        r"```\s*([\s\S]*?)```",
    ):
        candidates = []
        for m in re.finditer(pat, t, re.IGNORECASE):
            block = (m.group(1) or "").strip()
            if block:
                candidates.append(block)
        for block in candidates:
            if _looks_like_bpy_script(block):
                return block
        if candidates:
            return candidates[0]
    # 2) JSON wrapper
    jt = _extract_json(t)
    if jt:
        try:
            parsed = json.loads(jt)
            if isinstance(parsed, dict):
                p = parsed.get("python") or parsed.get("code") or parsed.get("script")
                if isinstance(p, str) and p.strip():
                    return p.strip()
        except Exception:
            pass
    # 3) Raw script: import bpy / from bpy
    head = t[:2500]
    if "import bpy" in head or "from bpy" in head:
        return t
    if re.search(r"\bbpy\.(ops|context|data)\b", t[:2500]):
        return t
    return None


def _looks_like_bpy_script(s):
    if not s or len(s) < 12:
        return False
    return bool(
        re.search(r"^\s*(import bpy|from bpy\b)", s, re.MULTILINE)
        or re.search(r"\bbpy\.(ops|context|data)\b", s[:4000])
    )


def _extract_generation_code_with_reason(text):
    """Return (code, None) or (None, short reason for UI)."""
    code = _extract_generation_code(text)
    if code:
        return code, None
    if not (text or "").strip():
        return None, "Empty response from model."
    preview = (text or "").strip()
    if len(preview) > 240:
        preview = preview[:237] + "..."
    return None, (
        "Could not find Python in the reply (need ```python``` block or import bpy). "
        f"Start of reply: {preview!r}"
    )


def _openrouter_choice_message_text(choice):
    """OpenRouter returns message.content as str; some providers use a list of parts."""
    msg = choice.get("message") or {}
    content = msg.get("content")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for p in content:
            if isinstance(p, dict):
                if p.get("type") == "text" and isinstance(p.get("text"), str):
                    parts.append(p["text"])
                elif isinstance(p.get("content"), str):
                    parts.append(p["content"])
            elif isinstance(p, str):
                parts.append(p)
        return "\n".join(parts).strip()
    return ""


def _openrouter_chat_completion(messages, model, max_tokens=4096, timeout=120):
    key = _prefs_openrouter_key()
    if not key:
        raise ValueError("OpenRouter API key not set (Preferences → Add-ons → BlendAgent).")
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": max_tokens,
    }
    extra = {
        "Authorization": f"Bearer {key}",
        "HTTP-Referer": "https://github.com/blender/blender",
        "X-Title": "BlendAgent",
    }
    data = _http_post_json_headers(OPENROUTER_CHAT_URL, payload, extra, timeout=timeout)
    choices = data.get("choices") or []
    if not choices:
        raise ValueError("OpenRouter returned no choices.")
    text = _openrouter_choice_message_text(choices[0])
    if not text:
        raw = (choices[0].get("message") or {})
        finish = choices[0].get("finish_reason")
        raise ValueError(
            f"OpenRouter returned empty text (finish_reason={finish!r}, message keys={list(raw.keys())})."
        )
    return text


def _write_generated_text(code):
    name = GENERATED_TEXT_NAME
    text = bpy.data.texts.get(name)
    if text is None:
        text = bpy.data.texts.new(name)
    text.clear()
    text.write(code or "")


def plan_with_openrouter_assistant(scene, prompt, ctx):
    manifest = MANIFEST
    model = _openrouter_model_id_from_scene(scene.blendagent)
    system_prompt = _build_system_prompt(manifest)
    user = (
        f"User request:\n{prompt}\n\nContext (JSON):\n{json.dumps(ctx, indent=2)}\n\n"
        "Respond with a single JSON object only (no markdown)."
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user},
    ]
    try:
        text = _openrouter_chat_completion(messages, model, max_tokens=1024)
        json_text = _extract_json(text)
        if not json_text:
            return _fallback_plan(prompt, manifest), None
        parsed = json.loads(json_text)
        if not isinstance(parsed, dict) or "operation" not in parsed:
            return _fallback_plan(prompt, manifest), None
        if "needs_clarification" not in parsed:
            parsed["needs_clarification"] = False
        if "reason" not in parsed:
            parsed["reason"] = None
        normalized = _normalize_plan(parsed, manifest, "llm", prompt)
        return normalized, None
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if e.fp else ""
        return None, f"OpenRouter HTTP {e.code}: {body[:500]}"
    except urllib.error.URLError as e:
        r = e.reason if getattr(e, "reason", None) else str(e)
        return None, f"OpenRouter network error: {r}"
    except Exception as e:
        print("BlendAgent OpenRouter (assistant) error:", e)
        return None, str(e)


def plan_with_openrouter_generation(scene, prompt, ctx):
    ba = scene.blendagent
    model = _openrouter_model_id_from_scene(ba)
    system_prompt = _build_generation_system_prompt()
    user = (
        f"User request:\n{prompt}\n\nContext (JSON):\n{json.dumps(ctx, indent=2)}\n"
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user},
    ]
    try:
        text = _openrouter_chat_completion(messages, model, max_tokens=4096)
        _store_generation_preview(ba, text)
        code, reason = _extract_generation_code_with_reason(text)
        if not code:
            print("BlendAgent: could not parse Python from model reply. Head:\n", (text or "")[:900])
            return None, reason or "Model did not return a usable Python block. Try the other model or shorten the request."
        _write_generated_text(code)
        return {"mode": "generation", "operation": "__generation__", "source": "openrouter", "python": code}, None
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if e.fp else ""
        return None, f"OpenRouter HTTP {e.code}: {body[:500]}"
    except urllib.error.URLError as e:
        r = e.reason if getattr(e, "reason", None) else str(e)
        return None, f"OpenRouter network error: {r}"
    except Exception as e:
        print("BlendAgent OpenRouter (generation) error:", e)
        return None, str(e)


def plan_with_ollama_direct(scene, prompt, ctx):
    manifest = MANIFEST
    ba = scene.blendagent
    base = (ba.ollama_url or DEFAULT_OLLAMA_URL).rstrip("/")
    model = ba.ollama_model or DEFAULT_OLLAMA_MODEL
    system_prompt = _build_system_prompt(manifest)
    ctx_block = ""
    if ctx:
        ctx_block = "\n\nContext (JSON):\n" + json.dumps(ctx, indent=2) + "\n"
    full_prompt = f"{system_prompt}\n\nUser request:\n{prompt}{ctx_block}\nJSON:\n"
    url = base + "/api/generate"
    try:
        data = _http_post_json(url, {"model": model, "prompt": full_prompt, "stream": False}, timeout=120)
        text = data.get("response", "").strip()
        json_text = _extract_json(text)
        if not json_text:
            return _fallback_plan(prompt, manifest), None
        parsed = json.loads(json_text)
        if not isinstance(parsed, dict) or "operation" not in parsed:
            return _fallback_plan(prompt, manifest), None
        if "needs_clarification" not in parsed:
            parsed["needs_clarification"] = False
        if "reason" not in parsed:
            parsed["reason"] = None
        normalized = _normalize_plan(parsed, manifest, "llm", prompt)
        return normalized, None
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if e.fp else ""
        return None, f"Ollama HTTP {e.code}: {body[:400]}"
    except urllib.error.URLError as e:
        reason = e.reason if getattr(e, "reason", None) else str(e)
        return None, f"Cannot reach Ollama ({reason}). Is it running? Model pulled?"
    except Exception as e:
        print("BlendAgent Ollama error:", e)
        out = _fallback_plan(prompt, manifest)
        out["error"] = str(e)
        return out, None


# ---------------------------------------------------------------------------
# Defaults (overridable in scene)
# ---------------------------------------------------------------------------

DEFAULT_API_BASE = "http://127.0.0.1:8000"
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"
DEFAULT_OLLAMA_MODEL = "llama3"


def _api_base(scene):
    base = scene.blendagent.api_base or DEFAULT_API_BASE
    return base.rstrip("/")


def _plan_url(scene):
    return _api_base(scene) + "/plan"


def _health_url(scene):
    return _api_base(scene) + "/health"


# ------------------------
# HELPERS
# ------------------------


def get_active_object():
    return bpy.context.active_object


def get_active_mesh():
    obj = get_active_object()
    if obj is None:
        return None
    if obj.type != "MESH":
        return None
    return obj


def clear_blendagent_modifiers(obj):
    for mod in list(obj.modifiers):
        if mod.type == "NODES" and mod.name.startswith("BlendAgent_"):
            obj.modifiers.remove(mod)


def create_geo_node_group(name):
    node_group = bpy.data.node_groups.new(name, "GeometryNodeTree")
    nodes = node_group.nodes
    links = node_group.links

    nodes.clear()

    input_node = nodes.new("NodeGroupInput")
    output_node = nodes.new("NodeGroupOutput")

    input_node.location = (-700, 0)
    output_node.location = (500, 0)

    try:
        node_group.interface.new_socket(
            name="Geometry",
            in_out="INPUT",
            socket_type="NodeSocketGeometry",
        )
        node_group.interface.new_socket(
            name="Geometry",
            in_out="OUTPUT",
            socket_type="NodeSocketGeometry",
        )
    except Exception:
        pass

    return node_group, nodes, links, input_node, output_node


def get_unique_material_for_object(obj, base_name):
    safe_obj_name = obj.name.replace(" ", "_")
    mat_name = f"{base_name}_{safe_obj_name}"

    mat = bpy.data.materials.get(mat_name)
    if mat is None:
        mat = bpy.data.materials.new(name=mat_name)

    mat.use_nodes = True
    return mat


def assign_material_to_object(obj, mat):
    if obj is None:
        return False

    if not hasattr(obj.data, "materials"):
        return False

    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)

    return True


def set_material_display_color(mat, rgba):
    try:
        mat.diffuse_color = rgba
    except Exception as e:
        print("Diffuse color set error:", e)


# ------------------------
# GEOMETRY NODE BUILDERS
# ------------------------


def create_subdivide_nodes():
    obj = get_active_mesh()
    if not obj:
        return False

    clear_blendagent_modifiers(obj)

    modifier = obj.modifiers.new(name="BlendAgent_Subdivide", type="NODES")
    node_group, nodes, links, input_node, output_node = create_geo_node_group("BlendAgent_SubdivideNodes")
    modifier.node_group = node_group

    subdivide = nodes.new("GeometryNodeSubdivideMesh")
    subdivide.location = (0, 0)

    if "Level" in subdivide.inputs:
        subdivide.inputs["Level"].default_value = 2

    try:
        links.new(input_node.outputs[0], subdivide.inputs[0])
        links.new(subdivide.outputs[0], output_node.inputs[0])
    except Exception as e:
        print("Subdivide link error:", e)
        return False

    return True


def create_noise_terrain_nodes():
    obj = get_active_mesh()
    if not obj:
        return False

    clear_blendagent_modifiers(obj)

    modifier = obj.modifiers.new(name="BlendAgent_NoiseTerrain", type="NODES")
    node_group, nodes, links, input_node, output_node = create_geo_node_group("BlendAgent_NoiseTerrainNodes")
    modifier.node_group = node_group

    set_position = nodes.new("GeometryNodeSetPosition")
    position = nodes.new("GeometryNodeInputPosition")
    noise = nodes.new("ShaderNodeTexNoise")
    multiply = nodes.new("ShaderNodeMath")
    combine_xyz = nodes.new("ShaderNodeCombineXYZ")

    set_position.location = (160, 0)
    position.location = (-520, -160)
    noise.location = (-320, -160)
    multiply.location = (-120, -160)
    combine_xyz.location = (40, -160)
    output_node.location = (380, 0)

    multiply.operation = "MULTIPLY"

    if "Scale" in noise.inputs:
        noise.inputs["Scale"].default_value = 2.5
    if "Detail" in noise.inputs:
        noise.inputs["Detail"].default_value = 8.0
    if "Roughness" in noise.inputs:
        noise.inputs["Roughness"].default_value = 0.55

    if len(multiply.inputs) > 1:
        multiply.inputs[1].default_value = 0.8

    try:
        links.new(input_node.outputs[0], set_position.inputs[0])
        links.new(position.outputs[0], noise.inputs[0])
        links.new(noise.outputs[0], multiply.inputs[0])
        links.new(multiply.outputs[0], combine_xyz.inputs[2])
        links.new(combine_xyz.outputs[0], set_position.inputs[3])
        links.new(set_position.outputs[0], output_node.inputs[0])
    except Exception as e:
        print("Noise terrain link error:", e)
        return False

    return True


# ------------------------
# MATERIAL BUILDERS
# ------------------------


def create_glossy_material():
    obj = get_active_object()
    if obj is None:
        return False

    mat = get_unique_material_for_object(obj, "BlendAgent_Glossy")
    set_material_display_color(mat, (0.72, 0.84, 1.0, 1.0))

    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    output = nodes.new(type="ShaderNodeOutputMaterial")
    principled = nodes.new(type="ShaderNodeBsdfPrincipled")
    bump = nodes.new(type="ShaderNodeBump")
    noise = nodes.new(type="ShaderNodeTexNoise")
    mapping = nodes.new(type="ShaderNodeMapping")
    texcoord = nodes.new(type="ShaderNodeTexCoord")

    texcoord.location = (-800, -120)
    mapping.location = (-600, -120)
    noise.location = (-380, -120)
    bump.location = (-120, -140)
    principled.location = (80, 0)
    output.location = (340, 0)

    if "Base Color" in principled.inputs:
        principled.inputs["Base Color"].default_value = (0.72, 0.84, 1.0, 1.0)
    if "Roughness" in principled.inputs:
        principled.inputs["Roughness"].default_value = 0.03
    if "Metallic" in principled.inputs:
        principled.inputs["Metallic"].default_value = 0.0
    if "Specular IOR Level" in principled.inputs:
        principled.inputs["Specular IOR Level"].default_value = 1.0
    elif "Specular" in principled.inputs:
        principled.inputs["Specular"].default_value = 0.9

    if "Scale" in noise.inputs:
        noise.inputs["Scale"].default_value = 18.0
    if "Detail" in noise.inputs:
        noise.inputs["Detail"].default_value = 8.0
    if "Roughness" in noise.inputs:
        noise.inputs["Roughness"].default_value = 0.45

    if "Strength" in bump.inputs:
        bump.inputs["Strength"].default_value = 0.08
    if "Distance" in bump.inputs:
        bump.inputs["Distance"].default_value = 0.03

    try:
        links.new(texcoord.outputs["Object"], mapping.inputs["Vector"])
        links.new(mapping.outputs["Vector"], noise.inputs["Vector"])
        links.new(noise.outputs["Fac"], bump.inputs["Height"])
        if "Normal" in principled.inputs:
            links.new(bump.outputs["Normal"], principled.inputs["Normal"])
        links.new(principled.outputs["BSDF"], output.inputs["Surface"])
    except Exception as e:
        print("Glossy material link error:", e)
        return False

    return assign_material_to_object(obj, mat)


def create_toon_material():
    obj = get_active_object()
    if obj is None:
        return False

    mat = get_unique_material_for_object(obj, "BlendAgent_Toon")
    set_material_display_color(mat, (1.0, 0.25, 0.95, 1.0))

    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    output = nodes.new(type="ShaderNodeOutputMaterial")
    diffuse = nodes.new(type="ShaderNodeBsdfDiffuse")
    shader_to_rgb = nodes.new(type="ShaderNodeShaderToRGB")
    ramp = nodes.new(type="ShaderNodeValToRGB")
    emission = nodes.new(type="ShaderNodeEmission")

    diffuse.location = (-500, 0)
    shader_to_rgb.location = (-280, 0)
    ramp.location = (-60, 0)
    emission.location = (180, 0)
    output.location = (420, 0)

    try:
        ramp.color_ramp.elements[0].position = 0.35
        ramp.color_ramp.elements[0].color = (0.06, 0.06, 0.08, 1.0)
        ramp.color_ramp.elements[1].position = 0.62
        ramp.color_ramp.elements[1].color = (1.0, 0.25, 0.95, 1.0)
    except Exception:
        pass

    if "Strength" in emission.inputs:
        emission.inputs["Strength"].default_value = 1.2
    if "Color" in emission.inputs:
        emission.inputs["Color"].default_value = (1.0, 0.25, 0.95, 1.0)

    try:
        links.new(diffuse.outputs["BSDF"], shader_to_rgb.inputs["Shader"])
        links.new(shader_to_rgb.outputs["Color"], ramp.inputs["Fac"])
        links.new(ramp.outputs["Color"], emission.inputs["Color"])
        links.new(emission.outputs["Emission"], output.inputs["Surface"])
    except Exception as e:
        print("Toon material link error:", e)
        return False

    return assign_material_to_object(obj, mat)


def create_hair_material_basic():
    """Stylized mesh hair: anisotropic sheen, noise-driven roughness, bump, rim + band streaks."""
    obj = get_active_object()
    if obj is None:
        return False

    mat = get_unique_material_for_object(obj, "BlendAgent_Hair")
    set_material_display_color(mat, (0.22, 0.10, 0.04, 1.0))

    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    out = nodes.new(type="ShaderNodeOutputMaterial")
    principled = nodes.new(type="ShaderNodeBsdfPrincipled")
    texcoord = nodes.new(type="ShaderNodeTexCoord")
    mapping = nodes.new(type="ShaderNodeMapping")
    noise_r = nodes.new(type="ShaderNodeTexNoise")
    noise_b = nodes.new(type="ShaderNodeTexNoise")
    bump = nodes.new(type="ShaderNodeBump")
    map_range = nodes.new(type="ShaderNodeMapRange")
    layer_weight = nodes.new(type="ShaderNodeLayerWeight")
    ramp = nodes.new(type="ShaderNodeValToRGB")
    wave = nodes.new(type="ShaderNodeTexWave")
    mixrgb = nodes.new(type="ShaderNodeMixRGB")

    texcoord.location = (-1100, -40)
    mapping.location = (-900, -40)
    noise_r.location = (-620, -200)
    noise_b.location = (-620, -420)
    map_range.location = (-360, -200)
    bump.location = (-360, -420)
    layer_weight.location = (-620, 140)
    ramp.location = (-380, 140)
    wave.location = (-620, 40)
    mixrgb.location = (-120, 20)
    principled.location = (200, 0)
    out.location = (480, 0)

    if "Scale" in noise_r.inputs:
        noise_r.inputs["Scale"].default_value = 28.0
    if "Detail" in noise_r.inputs:
        noise_r.inputs["Detail"].default_value = 8.0
    if "Roughness" in noise_r.inputs:
        noise_r.inputs["Roughness"].default_value = 0.55

    if "Scale" in noise_b.inputs:
        noise_b.inputs["Scale"].default_value = 90.0
    if "Detail" in noise_b.inputs:
        noise_b.inputs["Detail"].default_value = 6.0
    if "Strength" in bump.inputs:
        bump.inputs["Strength"].default_value = 0.14
    if "Distance" in bump.inputs:
        bump.inputs["Distance"].default_value = 0.02

    if "From Min" in map_range.inputs:
        map_range.inputs["From Min"].default_value = 0.0
    if "From Max" in map_range.inputs:
        map_range.inputs["From Max"].default_value = 1.0
    if "To Min" in map_range.inputs:
        map_range.inputs["To Min"].default_value = 0.18
    if "To Max" in map_range.inputs:
        map_range.inputs["To Max"].default_value = 0.52

    try:
        wave.wave_type = "BANDS"
    except Exception:
        pass
    if "Scale" in wave.inputs:
        wave.inputs["Scale"].default_value = 14.0
    if "Distortion" in wave.inputs:
        wave.inputs["Distortion"].default_value = 2.4
    if "Detail" in wave.inputs:
        wave.inputs["Detail"].default_value = 4.0

    if "Blend" in layer_weight.inputs:
        layer_weight.inputs["Blend"].default_value = 0.22

    try:
        ramp.color_ramp.elements[0].position = 0.08
        ramp.color_ramp.elements[0].color = (0.015, 0.008, 0.004, 1.0)
        ramp.color_ramp.elements[1].position = 0.88
        ramp.color_ramp.elements[1].color = (0.52, 0.28, 0.10, 1.0)
    except Exception:
        pass

    if "Fac" in mixrgb.inputs:
        mixrgb.inputs["Fac"].default_value = 0.52
    if "Roughness" in principled.inputs:
        principled.inputs["Roughness"].default_value = 0.38
    if "Metallic" in principled.inputs:
        principled.inputs["Metallic"].default_value = 0.0
    if "Specular IOR Level" in principled.inputs:
        principled.inputs["Specular IOR Level"].default_value = 0.55
    elif "Specular" in principled.inputs:
        principled.inputs["Specular"].default_value = 0.55
    if "Anisotropic" in principled.inputs:
        principled.inputs["Anisotropic"].default_value = 0.78
    if "Anisotropic Rotation" in principled.inputs:
        principled.inputs["Anisotropic Rotation"].default_value = 0.22
    if "Sheen Weight" in principled.inputs:
        principled.inputs["Sheen Weight"].default_value = 0.18
    if "Sheen Roughness" in principled.inputs:
        principled.inputs["Sheen Roughness"].default_value = 0.45

    try:
        links.new(texcoord.outputs["Object"], mapping.inputs["Vector"])
        links.new(mapping.outputs["Vector"], noise_r.inputs["Vector"])
        links.new(mapping.outputs["Vector"], noise_b.inputs["Vector"])
        links.new(mapping.outputs["Vector"], wave.inputs["Vector"])
        v_in = map_range.inputs.get("Value", map_range.inputs[0])
        links.new(noise_r.outputs["Fac"], v_in)
        mr_out = map_range.outputs.get("Result") or map_range.outputs[0]
        links.new(mr_out, principled.inputs["Roughness"])
        links.new(noise_b.outputs["Fac"], bump.inputs["Height"])
        if "Normal" in principled.inputs:
            links.new(bump.outputs["Normal"], principled.inputs["Normal"])
        links.new(layer_weight.outputs["Facing"], ramp.inputs["Fac"])
        c1 = mixrgb.inputs.get("Color1", mixrgb.inputs[1])
        c2 = mixrgb.inputs.get("Color2", mixrgb.inputs[2])
        links.new(ramp.outputs["Color"], c1)
        links.new(wave.outputs["Color"], c2)
        links.new(mixrgb.outputs["Color"], principled.inputs["Base Color"])
        links.new(principled.outputs["BSDF"], out.inputs["Surface"])
    except Exception as e:
        print("Hair material link error:", e)
        return False

    return assign_material_to_object(obj, mat)


def create_eye_material_basic():
    obj = get_active_object()
    if obj is None:
        return False

    mat = get_unique_material_for_object(obj, "BlendAgent_Eye")
    set_material_display_color(mat, (0.0, 0.65, 1.0, 1.0))

    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    output = nodes.new(type="ShaderNodeOutputMaterial")
    principled = nodes.new(type="ShaderNodeBsdfPrincipled")
    gradient = nodes.new(type="ShaderNodeTexGradient")
    mapping = nodes.new(type="ShaderNodeMapping")
    texcoord = nodes.new(type="ShaderNodeTexCoord")
    ramp = nodes.new(type="ShaderNodeValToRGB")

    texcoord.location = (-980, -120)
    mapping.location = (-760, -120)
    gradient.location = (-540, -120)
    ramp.location = (-300, -120)
    principled.location = (20, 0)
    output.location = (280, 0)

    try:
        ramp.color_ramp.elements[0].position = 0.05
        ramp.color_ramp.elements[0].color = (0.02, 0.02, 0.02, 1.0)
        ramp.color_ramp.elements[1].position = 0.80
        ramp.color_ramp.elements[1].color = (0.0, 0.65, 1.0, 1.0)
    except Exception:
        pass

    if "Roughness" in principled.inputs:
        principled.inputs["Roughness"].default_value = 0.02
    if "Specular IOR Level" in principled.inputs:
        principled.inputs["Specular IOR Level"].default_value = 1.0
    elif "Specular" in principled.inputs:
        principled.inputs["Specular"].default_value = 1.0

    try:
        links.new(texcoord.outputs["Object"], mapping.inputs["Vector"])
        links.new(mapping.outputs["Vector"], gradient.inputs["Vector"])
        links.new(gradient.outputs["Fac"], ramp.inputs["Fac"])
        links.new(ramp.outputs["Color"], principled.inputs["Base Color"])
        links.new(principled.outputs["BSDF"], output.inputs["Surface"])
    except Exception as e:
        print("Eye material link error:", e)
        return False

    return assign_material_to_object(obj, mat)


def create_water_material():
    obj = get_active_object()
    if obj is None:
        return False

    mat = get_unique_material_for_object(obj, "BlendAgent_Water")
    set_material_display_color(mat, (0.16, 0.45, 0.90, 0.65))

    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    output = nodes.new(type="ShaderNodeOutputMaterial")
    principled = nodes.new(type="ShaderNodeBsdfPrincipled")
    noise = nodes.new(type="ShaderNodeTexNoise")
    bump = nodes.new(type="ShaderNodeBump")
    mapping = nodes.new(type="ShaderNodeMapping")
    texcoord = nodes.new(type="ShaderNodeTexCoord")

    texcoord.location = (-900, -120)
    mapping.location = (-680, -120)
    noise.location = (-450, -120)
    bump.location = (-180, -120)
    principled.location = (80, 0)
    output.location = (340, 0)

    if "Base Color" in principled.inputs:
        principled.inputs["Base Color"].default_value = (0.10, 0.38, 0.85, 1.0)
    if "Roughness" in principled.inputs:
        principled.inputs["Roughness"].default_value = 0.03
    if "IOR" in principled.inputs:
        principled.inputs["IOR"].default_value = 1.333
    if "Transmission Weight" in principled.inputs:
        principled.inputs["Transmission Weight"].default_value = 1.0
    elif "Transmission" in principled.inputs:
        principled.inputs["Transmission"].default_value = 1.0
    if "Specular IOR Level" in principled.inputs:
        principled.inputs["Specular IOR Level"].default_value = 1.0
    elif "Specular" in principled.inputs:
        principled.inputs["Specular"].default_value = 0.9

    if "Scale" in noise.inputs:
        noise.inputs["Scale"].default_value = 8.0
    if "Detail" in noise.inputs:
        noise.inputs["Detail"].default_value = 10.0
    if "Roughness" in noise.inputs:
        noise.inputs["Roughness"].default_value = 0.55

    if "Strength" in bump.inputs:
        bump.inputs["Strength"].default_value = 0.08
    if "Distance" in bump.inputs:
        bump.inputs["Distance"].default_value = 0.02

    try:
        links.new(texcoord.outputs["Object"], mapping.inputs["Vector"])
        links.new(mapping.outputs["Vector"], noise.inputs["Vector"])
        links.new(noise.outputs["Fac"], bump.inputs["Height"])
        if "Normal" in principled.inputs:
            links.new(bump.outputs["Normal"], principled.inputs["Normal"])
        links.new(principled.outputs["BSDF"], output.inputs["Surface"])
    except Exception as e:
        print("Water material link error:", e)
        return False

    try:
        mat.blend_method = "BLEND"
    except Exception:
        pass

    return assign_material_to_object(obj, mat)


def create_skin_material_vtuber():
    obj = get_active_object()
    if obj is None:
        return False

    mat = get_unique_material_for_object(obj, "BlendAgent_VTuberSkin")
    # Warm peach (clearly not default grey)
    set_material_display_color(mat, (0.92, 0.72, 0.62, 1.0))

    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    output = nodes.new(type="ShaderNodeOutputMaterial")
    principled = nodes.new(type="ShaderNodeBsdfPrincipled")
    texcoord = nodes.new(type="ShaderNodeTexCoord")
    mapping = nodes.new(type="ShaderNodeMapping")
    noise = nodes.new(type="ShaderNodeTexNoise")
    bump = nodes.new(type="ShaderNodeBump")

    texcoord.location = (-620, -80)
    mapping.location = (-420, -80)
    noise.location = (-200, -80)
    bump.location = (40, -140)
    principled.location = (220, 0)
    output.location = (520, 0)

    if "Scale" in noise.inputs:
        noise.inputs["Scale"].default_value = 22.0
    if "Detail" in noise.inputs:
        noise.inputs["Detail"].default_value = 8.0
    if "Roughness" in noise.inputs:
        noise.inputs["Roughness"].default_value = 0.52
    if "Strength" in bump.inputs:
        bump.inputs["Strength"].default_value = 0.06
    if "Distance" in bump.inputs:
        bump.inputs["Distance"].default_value = 0.025

    if "Base Color" in principled.inputs:
        principled.inputs["Base Color"].default_value = (0.92, 0.72, 0.62, 1.0)
    if "Roughness" in principled.inputs:
        principled.inputs["Roughness"].default_value = 0.36
    if "Metallic" in principled.inputs:
        principled.inputs["Metallic"].default_value = 0.0
    if "Specular IOR Level" in principled.inputs:
        principled.inputs["Specular IOR Level"].default_value = 0.45
    elif "Specular" in principled.inputs:
        principled.inputs["Specular"].default_value = 0.45

    if "Subsurface Weight" in principled.inputs:
        principled.inputs["Subsurface Weight"].default_value = 0.48
    if "Subsurface Radius" in principled.inputs:
        principled.inputs["Subsurface Radius"].default_value = (1.15, 0.42, 0.28)
    elif "Subsurface" in principled.inputs:
        try:
            principled.inputs["Subsurface"].default_value = 0.45
        except Exception:
            pass
    if "Sheen Weight" in principled.inputs:
        principled.inputs["Sheen Weight"].default_value = 0.12
    if "Sheen Roughness" in principled.inputs:
        principled.inputs["Sheen Roughness"].default_value = 0.65

    try:
        links.new(texcoord.outputs["Object"], mapping.inputs["Vector"])
        links.new(mapping.outputs["Vector"], noise.inputs["Vector"])
        links.new(noise.outputs["Fac"], bump.inputs["Height"])
        if "Normal" in principled.inputs:
            links.new(bump.outputs["Normal"], principled.inputs["Normal"])
        links.new(principled.outputs["BSDF"], output.inputs["Surface"])
    except Exception as e:
        print("VTuber skin material link error:", e)
        return False

    return assign_material_to_object(obj, mat)


def add_vtuber_armature():
    try:
        if bpy.context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
    except Exception:
        pass
    try:
        bpy.ops.object.armature_add(location=(0, 0, 0))
    except Exception as e:
        print("armature_add error:", e)
        return False

    arm = bpy.context.active_object
    if not arm or arm.type != "ARMATURE":
        return False

    arm.name = "BlendAgent_VTuberRig"
    arm.data.name = "BlendAgent_VTuberRig"

    bpy.ops.object.mode_set(mode="EDIT")
    eb = arm.data.edit_bones

    h = eb[0]
    h.name = "Hips"
    h.head = (0, 0, 0.92)
    h.tail = (0, 0, 1.02)

    spine = eb.new("Spine")
    spine.parent = h
    spine.use_connect = True
    spine.head = h.tail
    spine.tail = (0, 0, 1.18)

    chest = eb.new("Chest")
    chest.parent = spine
    chest.use_connect = True
    chest.head = spine.tail
    chest.tail = (0, 0, 1.30)

    neck = eb.new("Neck")
    neck.parent = chest
    neck.use_connect = True
    neck.head = chest.tail
    neck.tail = (0, 0, 1.42)

    head_b = eb.new("Head")
    head_b.parent = neck
    head_b.use_connect = True
    head_b.head = neck.tail
    head_b.tail = (0, 0, 1.65)

    ua_l = eb.new("UpperArm_L")
    ua_l.parent = chest
    ua_l.use_connect = False
    ua_l.head = (0.05, 0, 1.28)
    ua_l.tail = (0.38, 0, 1.28)

    ua_r = eb.new("UpperArm_R")
    ua_r.parent = chest
    ua_r.use_connect = False
    ua_r.head = (-0.05, 0, 1.28)
    ua_r.tail = (-0.38, 0, 1.28)

    ul_l = eb.new("UpperLeg_L")
    ul_l.parent = h
    ul_l.use_connect = False
    ul_l.head = (0.08, 0, 0.92)
    ul_l.tail = (0.08, 0, 0.52)

    ul_r = eb.new("UpperLeg_R")
    ul_r.parent = h
    ul_r.use_connect = False
    ul_r.head = (-0.08, 0, 0.92)
    ul_r.tail = (-0.08, 0, 0.52)

    bpy.ops.object.mode_set(mode="OBJECT")
    return True


def mesh_preset_vtuber_head():
    try:
        if bpy.context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
    except Exception:
        pass
    try:
        bpy.ops.mesh.primitive_uv_sphere_add(
            segments=32,
            ring_count=16,
            radius=0.14,
            location=(0.0, 0.0, 1.58),
        )
    except Exception as e:
        print("mesh_preset_vtuber_head:", e)
        return False
    obj = bpy.context.active_object
    if not obj or obj.type != "MESH":
        return False
    obj.name = "VTuber_Head"
    obj.data.name = "VTuber_Head"
    return True


def mesh_preset_vtuber_body():
    try:
        if bpy.context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
    except Exception:
        pass
    try:
        bpy.ops.mesh.primitive_cube_add(size=0.38, location=(0.0, 0.0, 1.05))
    except Exception as e:
        print("mesh_preset_vtuber_body:", e)
        return False
    obj = bpy.context.active_object
    if not obj or obj.type != "MESH":
        return False
    obj.name = "VTuber_Body"
    obj.data.name = "VTuber_Body"
    obj.scale = (0.58, 0.34, 1.02)
    try:
        bpy.ops.object.transform_apply(scale=True)
    except Exception:
        pass
    try:
        mod = obj.modifiers.new("BlendAgent_Subdiv", "SUBSURF")
        mod.levels = 1
        mod.render_levels = 2
    except Exception:
        pass
    return True


def _create_particle_strand_material():
    """Principled BSDF only: Principled Hair BSDF is Cycles-oriented and often invisible/black in EEVEE."""
    name = "BlendAgent_HairStrands"
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    try:
        mat.blend_method = "OPAQUE"
    except Exception:
        pass
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    out.location = (320, 0)
    pr = nodes.new("ShaderNodeBsdfPrincipled")
    pr.location = (0, 0)
    if "Base Color" in pr.inputs:
        pr.inputs["Base Color"].default_value = (0.22, 0.09, 0.04, 1.0)
    if "Roughness" in pr.inputs:
        pr.inputs["Roughness"].default_value = 0.42
    if "Specular IOR Level" in pr.inputs:
        pr.inputs["Specular IOR Level"].default_value = 0.45
    elif "Specular" in pr.inputs:
        pr.inputs["Specular"].default_value = 0.45
    if "Sheen Weight" in pr.inputs:
        pr.inputs["Sheen Weight"].default_value = 0.35
    if "Sheen Roughness" in pr.inputs:
        pr.inputs["Sheen Roughness"].default_value = 0.55
    links.new(pr.outputs["BSDF"], out.inputs["Surface"])
    return mat


def hair_particles_vtuber():
    obj = get_active_mesh()
    if not obj:
        return False
    try:
        if bpy.context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
    except Exception:
        pass
    bpy.context.view_layer.objects.active = obj
    for m in list(obj.modifiers):
        if m.type == "PARTICLE_SYSTEM" and m.name == "BlendAgent_Hair_PS":
            obj.modifiers.remove(m)

    try:
        mat = _create_particle_strand_material()
        idx = None
        for i, slot in enumerate(obj.data.materials):
            if slot and slot.name == mat.name:
                idx = i
                break
        if idx is None:
            obj.data.materials.append(mat)
            idx = len(obj.data.materials) - 1

        bpy.ops.object.modifier_add(type="PARTICLE_SYSTEM")
        ob = bpy.context.view_layer.objects.active
        mod = ob.modifiers[-1]
        mod.name = "BlendAgent_Hair_PS"
        mod.show_viewport = True
        mod.show_render = True
        psys = ob.particle_systems[-1]
        psys.name = "BlendAgent_Hair"
        p = psys.settings
        p.type = "HAIR"
        p.count = 800
        p.hair_length = 0.42
        p.hair_step = 7
        p.emit_from = "FACE"
        p.use_emit_random = True
        p.use_even_distribution = True
        p.render_type = "PATH"
        p.display_percentage = 100
        p.display_method = "RENDER"
        if hasattr(p, "render_step"):
            p.render_step = 4
        if hasattr(p, "display_step"):
            p.display_step = 4
        p.physics_type = "NO"
        p.rotation_mode = "NOR"
        p.child_type = "NONE"
        p.clump_factor = 0.08
        p.kink = "NO"
        # Default radius_scale is 0.01 — strands become nearly invisible without raising this.
        if hasattr(p, "radius_scale"):
            p.radius_scale = 1.0
        if hasattr(p, "root_radius"):
            p.root_radius = 0.45
        if hasattr(p, "tip_radius"):
            p.tip_radius = 0.06
        if hasattr(p, "particle_size"):
            p.particle_size = 0.12
        if hasattr(p, "display_size"):
            p.display_size = 0.2
        if hasattr(p, "use_strand_primitive"):
            p.use_strand_primitive = True
        if hasattr(p, "use_parent_particles"):
            p.use_parent_particles = True
        if hasattr(p, "use_close_tip"):
            p.use_close_tip = False
        # RNA: material slot index is 1-based (first slot = 1)
        p.material = idx + 1
        ob.particle_systems.active_index = len(ob.particle_systems) - 1
    except Exception as e:
        print("hair_particles_vtuber:", e)
        return False
    return True


def lighting_lookdev_three_point():
    scene = bpy.context.scene
    for o in list(scene.objects):
        if o.name.startswith("BlendAgent_Lookdev_"):
            try:
                bpy.data.objects.remove(o, do_unlink=True)
            except Exception:
                pass

    def _add_area(name, loc, rot_deg, energy, size):
        bpy.ops.object.light_add(type="AREA", location=loc)
        L = bpy.context.active_object
        L.name = name
        L.rotation_euler = (
            math.radians(rot_deg[0]),
            math.radians(rot_deg[1]),
            math.radians(rot_deg[2]),
        )
        d = L.data
        if hasattr(d, "energy"):
            d.energy = energy
        if hasattr(d, "size"):
            d.size = size
        return L

    try:
        _add_area("BlendAgent_Lookdev_Key", (2.3, -2.9, 3.7), (52, 0, 26), 880, 1.85)
        _add_area("BlendAgent_Lookdev_Fill", (-3.1, -1.1, 2.35), (48, 0, -32), 300, 2.6)
        _add_area("BlendAgent_Lookdev_Rim", (-0.9, 2.7, 3.05), (42, 0, 158), 510, 1.35)
    except Exception as e:
        print("lighting_lookdev_three_point lights:", e)
        return False

    try:
        world = scene.world
        if world is None:
            world = bpy.data.worlds.new("BlendAgent_Lookdev_World")
            scene.world = world
        world.use_nodes = True
        nt = world.node_tree
        nodes = nt.nodes
        links = nt.links
        bg = nodes.get("Background")
        if bg is None:
            bg = nodes.new("ShaderNodeBackground")
            bg.location = (0, 0)
        outn = nodes.get("World Output")
        if outn is None:
            outn = nodes.new("ShaderNodeOutputWorld")
            outn.location = (260, 0)
        if "Color" in bg.inputs:
            bg.inputs["Color"].default_value = (0.038, 0.042, 0.055, 1.0)
        if "Strength" in bg.inputs:
            bg.inputs["Strength"].default_value = 0.4
        if "Background" in bg.outputs and "Surface" in outn.inputs:
            linked = False
            for l in links:
                if l.to_socket == outn.inputs["Surface"]:
                    linked = True
                    break
            if not linked:
                links.new(bg.outputs["Background"], outn.inputs["Surface"])
    except Exception as e:
        print("lighting_lookdev_three_point world:", e)
        return False

    return True


# ------------------------
# INSPECT + ANIMATION (trusted bpy)
# ------------------------


def inspect_summarize_selection():
    ctx = bpy.context
    obj = ctx.active_object
    lines = []
    if not obj:
        lines.append("Active object: none")
        lines.append(f"Scene: {ctx.scene.name}")
        return True, "\n".join(lines)

    lines.append(f"Active object: {obj.name} ({obj.type})")
    if obj.type == "MESH" and obj.data:
        mesh = obj.data
        lines.append(f"Verts: {len(mesh.vertices)}  Faces: {len(mesh.polygons)}")
    if hasattr(obj.data, "materials") and obj.data.materials:
        lines.append(f"Material slots: {len(obj.data.materials)}")
        m0 = obj.data.materials[0]
        lines.append(f"First slot material: {m0.name if m0 else '(empty)'}")
    if obj.type == "ARMATURE" and obj.data:
        lines.append(f"Bones: {len(obj.data.bones)}")
    lines.append(f"Mode: {obj.mode}  Frame: {ctx.scene.frame_current}")
    return True, "\n".join(lines)


def inspect_list_material_nodes():
    obj = bpy.context.active_object
    if not obj:
        return False, "No active object."
    mat = None
    if hasattr(obj.data, "materials") and obj.data.materials:
        mat = obj.data.materials[0]
    if mat is None:
        return True, "No material in slot 0. Assign a material first."
    if not mat.use_nodes:
        return True, f"Material '{mat.name}' does not use nodes."

    nt = mat.node_tree
    lines = [f"Material: {mat.name}", f"Nodes ({len(nt.nodes)}):"]
    for n in nt.nodes:
        lines.append(f"  - {n.bl_idname} | {n.name}")
    return True, "\n".join(lines)


def inspect_vtuber_readiness():
    ctx = bpy.context
    scene = ctx.scene
    lines = []
    lines.append("=== VTuber pipeline check (read-only) ===")

    try:
        ws = ctx.window.workspace.name if ctx.window and ctx.window.workspace else None
    except Exception:
        ws = None
    lines.append(f"Workspace: {ws or 'unknown'}")
    lines.append(f"Context mode: {ctx.mode}")
    try:
        lines.append(f"Active area: {ctx.area.type if ctx.area else 'none'}")
    except Exception:
        lines.append("Active area: (error)")

    arms = [o for o in scene.objects if o.type == "ARMATURE"]
    meshes = [o for o in scene.objects if o.type == "MESH"]
    lines.append(f"Objects: {len(scene.objects)}  |  Meshes: {len(meshes)}  |  Armatures: {len(arms)}")

    obj = ctx.active_object
    if not obj:
        lines.append("Active object: none")
        lines.append("Tip: select a mesh for skin/eye/hair materials.")
        return True, "\n".join(lines)

    lines.append(f"Active: {obj.name} ({obj.type})")
    if obj.type == "MESH" and obj.data:
        mesh = obj.data
        lines.append(f"Verts: {len(mesh.vertices)}  Faces: {len(mesh.polygons)}")
        if mesh.shape_keys:
            lines.append(f"Shape keys: {len(mesh.shape_keys.key_blocks)}")
        else:
            lines.append("Shape keys: none (add basis for face/expression work)")
        if hasattr(mesh, "materials") and mesh.materials:
            lines.append(f"Material slots: {len(mesh.materials)}")
    if obj.type == "ARMATURE" and obj.data:
        lines.append(f"Bones: {len(obj.data.bones)}")
        if ctx.mode == "POSE":
            lines.append(f"Selected pose bones: {len(ctx.selected_pose_bones)}")

    lines.append("")
    lines.append("Suggested workflow:")
    lines.append("- Modeling / Sculpt: body & head mesh")
    lines.append("- Lighting: lighting_lookdev_three_point for viewport readability")
    lines.append("- Shading: skin, eyes; mesh hair shader and/or hair_particles_vtuber on scalp")
    lines.append("- Add armature (tool) or import rig; then Weight Paint / Pose")
    lines.append("- Animation: test keyframes; export per Live3D / VRM pipeline")

    return True, "\n".join(lines)


def create_keyframe_loc_rot():
    obj = bpy.context.active_object
    if not obj:
        return False

    try:
        if obj.type == "ARMATURE" and bpy.context.mode == "POSE":
            bones = list(bpy.context.selected_pose_bones)
            if not bones and bpy.context.active_pose_bone:
                bones = [bpy.context.active_pose_bone]
            if not bones:
                return False
            for b in bones:
                b.keyframe_insert(data_path="location")
                if b.rotation_mode == "QUATERNION":
                    b.keyframe_insert(data_path="rotation_quaternion")
                else:
                    b.keyframe_insert(data_path="rotation_euler")
            return True

        obj.keyframe_insert(data_path="location")
        if obj.rotation_mode == "QUATERNION":
            obj.keyframe_insert(data_path="rotation_quaternion")
        else:
            obj.keyframe_insert(data_path="rotation_euler")
        return True
    except Exception as e:
        print("Keyframe error:", e)
        return False


TOOL_BUILDERS = {
    "water_material": create_water_material,
    "eye_material_basic": create_eye_material_basic,
    "hair_material_basic": create_hair_material_basic,
    "toon_material": create_toon_material,
    "glossy_material": create_glossy_material,
    "skin_material_vtuber": create_skin_material_vtuber,
    "mesh_preset_vtuber_head": mesh_preset_vtuber_head,
    "mesh_preset_vtuber_body": mesh_preset_vtuber_body,
    "hair_particles_vtuber": hair_particles_vtuber,
    "lighting_lookdev_three_point": lighting_lookdev_three_point,
    "add_vtuber_armature": add_vtuber_armature,
    "noise_terrain": create_noise_terrain_nodes,
    "subdivide_mesh": create_subdivide_nodes,
    "summarize_selection": inspect_summarize_selection,
    "list_material_nodes": inspect_list_material_nodes,
    "vtuber_readiness_check": inspect_vtuber_readiness,
    "keyframe_loc_rot": create_keyframe_loc_rot,
}


def build_scene_context(send_context):
    if not send_context:
        return None
    ctx = bpy.context
    scene = ctx.scene
    out = {
        "scene_name": scene.name,
        "frame_current": scene.frame_current,
        "frame_start": scene.frame_start,
        "frame_end": scene.frame_end,
    }
    try:
        out["workspace_name"] = (
            ctx.window.workspace.name if ctx.window and ctx.window.workspace else None
        )
    except Exception:
        out["workspace_name"] = None
    out["context_mode"] = ctx.mode
    try:
        out["active_area_type"] = ctx.area.type if ctx.area else None
    except Exception:
        out["active_area_type"] = None

    obj = ctx.active_object
    if obj:
        ao = {
            "name": obj.name,
            "type": obj.type,
            "mode": getattr(obj, "mode", None),
        }
        if obj.type == "MESH" and obj.data:
            mesh = obj.data
            ao["mesh"] = {
                "vertices": len(mesh.vertices),
                "faces": len(mesh.polygons),
            }
            if mesh.shape_keys:
                ao["shape_key_count"] = len(mesh.shape_keys.key_blocks)
        if hasattr(obj.data, "materials") and obj.data.materials:
            ao["material_slots"] = len(obj.data.materials)
            ao["material_slot_names"] = [(m.name if m else None) for m in obj.data.materials[:8]]
        if obj.type == "ARMATURE" and obj.data:
            ao["armature"] = {
                "bone_count": len(obj.data.bones),
                "pose_bones": len(obj.pose.bones) if obj.pose else 0,
            }
            if ctx.mode == "POSE":
                ao["selected_pose_bones"] = [b.name for b in ctx.selected_pose_bones][:16]
                if ctx.active_pose_bone:
                    ao["active_pose_bone"] = ctx.active_pose_bone.name
        out["active_object"] = ao
    else:
        out["active_object"] = None
    return out


def check_requires(tool_id):
    by = _tools_by_id()
    spec = by.get(tool_id)
    if not spec:
        return False, "Unknown tool."
    req = spec.get("requires", "active_object")
    obj = bpy.context.active_object
    if req == "none":
        return True, None
    if req == "active_object":
        if not obj:
            return False, "This tool needs an active object."
        return True, None
    if req == "active_mesh":
        if not obj or obj.type != "MESH":
            return False, "This tool needs an active mesh object."
        return True, None
    return True, None


def run_tool(tool_id):
    spec = _tools_by_id().get(tool_id)
    if not spec:
        return "error", False, "Unknown operation."

    ok_req, req_msg = check_requires(tool_id)
    if not ok_req:
        return "error", False, req_msg

    fn = TOOL_BUILDERS.get(tool_id)
    if not fn:
        return "error", False, "No builder registered for this tool."

    kind = spec.get("kind", "action")

    if kind == "inspect":
        try:
            success, text = fn()
            if text is None:
                text = ""
            st = "ok" if success else "error"
            return st, success, text
        except Exception:
            return "error", False, traceback.format_exc()

    try:
        success = bool(fn())
        if success:
            return "ok", True, None
        return "error", False, "Operation failed (see system console for details)."
    except Exception:
        return "error", False, traceback.format_exc()


def _finish_tool_run(scene, op_id, plan_source="manual"):
    """Run a manifest tool and update scene.blendagent status fields."""
    ba = scene.blendagent
    status, success, detail = run_tool(op_id)
    spec = _tools_by_id().get(op_id, {})
    kind = spec.get("kind", "action")

    if kind == "inspect":
        ba.inspect_result = detail or ""
        if success:
            ba.last_status = f"Inspect OK: {op_id}"
            append_transcript(scene, f"[INSPECT {op_id}]\n{detail or ''}")
            return True, f"Inspect: {op_id}"
        ba.last_status = f"Inspect failed: {op_id}"
        ba.last_error = detail or "Inspect failed."
        append_transcript(scene, f"[FAIL] {op_id}: {ba.last_error}")
        return False, ba.last_error

    if status == "ok" and success:
        ba.last_status = f"Applied {op_id} ({plan_source})"
        append_transcript(scene, f"[OK] Applied {op_id}")
        return True, f"Applied: {op_id}"

    ba.last_status = f"Failed: {op_id}"
    ba.last_error = detail or "Operation failed."
    append_transcript(scene, f"[FAIL] {op_id}: {ba.last_error}")
    return False, ba.last_error


def get_node_plan(scene, prompt):
    ba = scene.blendagent
    send_ctx = bool(ba.send_context)
    ctx = merge_planner_context(scene, send_ctx)
    mode = ba.planner_mode
    agent_mode = getattr(ba, "agent_mode", "ASSISTANT") or "ASSISTANT"

    if agent_mode == "GENERATION":
        if not _prefs_openrouter_key():
            return (
                None,
                "Generation requires an OpenRouter API key. Edit → Preferences → Add-ons → BlendAgent.",
            )
        return plan_with_openrouter_generation(scene, prompt, ctx)

    payload = {
        "prompt": prompt,
        "send_context": send_ctx,
        "context": ctx,
    }
    if mode == "FASTAPI":
        try:
            plan = _http_post_json(_plan_url(scene), payload, timeout=120)
            print("Agent plan:", plan)
            return plan, None
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace") if e.fp else ""
            return None, f"Planner HTTP {e.code}: {body[:400]}"
        except urllib.error.URLError as e:
            r = e.reason if getattr(e, "reason", None) else str(e)
            return None, str(r)
        except Exception as e:
            print("Planner server error:", e)
            return None, str(e)
    if mode == "OPENROUTER":
        return plan_with_openrouter_assistant(scene, prompt, ctx)
    return plan_with_ollama_direct(scene, prompt, ctx)


def append_transcript(scene, text):
    ba = scene.blendagent
    cur = (ba.transcript or "") + text + "\n"
    max_len = 12000
    if len(cur) > max_len:
        cur = cur[-max_len:]
    ba.transcript = cur


class BlendAgentPreferences(bpy.types.AddonPreferences):
    bl_idname = __name__

    openrouter_api_key: bpy.props.StringProperty(
        name="OpenRouter API key",
        description="Stored in Blender preferences (not saved inside .blend files). Get a key at https://openrouter.ai",
        default="",
        subtype="PASSWORD",
    )

    def draw(self, context):
        layout = self.layout
        box = layout.box()
        box.label(text="OpenRouter", icon="WORLD")
        box.prop(self, "openrouter_api_key")
        box.label(text="Required for Generation mode. Also used when Assistant + Planner = OpenRouter.")


class BLENDAGENT_PG_scene(bpy.types.PropertyGroup):
    """All BlendAgent settings live under scene.blendagent (stable RNA path)."""

    agent_mode: bpy.props.EnumProperty(
        name="Mode",
        description="Assistant uses manifest tools only; Generation writes a bpy script for you to run",
        items=AGENT_MODE_ITEMS,
        default="ASSISTANT",
    )
    session_tick: bpy.props.IntProperty(
        name="Session tick",
        description="Increments each Run; sent to the planner with scene context for continuity",
        default=0,
        min=0,
    )
    memory_max_lines: bpy.props.IntProperty(
        name="Memory lines",
        description="Max transcript lines to include in planner context",
        default=48,
        min=8,
        max=200,
    )
    include_conversation_memory: bpy.props.BoolProperty(
        name="Include conversation memory",
        description="Send recent transcript lines with scene context (bounded; oldest lines drop off)",
        default=True,
    )
    planner_mode: bpy.props.EnumProperty(
        name="Planner mode",
        description="How BlendAgent chooses a tool from your prompt",
        items=PLANNER_MODE_ITEMS,
        default="DIRECT",
    )
    openrouter_model_family: bpy.props.EnumProperty(
        name="Cloud model",
        description="OpenAI or Anthropic via OpenRouter (same key for both)",
        items=OPENROUTER_MODEL_FAMILY_ITEMS,
        default="GPT",
    )
    openrouter_status: bpy.props.StringProperty(name="OpenRouter status", default="")
    generation_preview: bpy.props.StringProperty(
        name="Last model reply",
        description="Short excerpt from the last cloud response (code is in the Text editor)",
        default="",
    )
    ollama_url: bpy.props.StringProperty(
        name="Ollama URL",
        description="Ollama HTTP API base (same machine: 127.0.0.1:11434)",
        default=DEFAULT_OLLAMA_URL,
    )
    ollama_model: bpy.props.StringProperty(
        name="Ollama model",
        description="Model name as shown in ollama list",
        default=DEFAULT_OLLAMA_MODEL,
    )
    ollama_status: bpy.props.StringProperty(name="Ollama status", default="")
    api_base: bpy.props.StringProperty(
        name="Planner API base",
        description="Base URL for the FastAPI planner (no trailing slash)",
        default=DEFAULT_API_BASE,
    )
    prompt: bpy.props.StringProperty(
        name="Prompt",
        description="Describe what to run when using natural language",
        default="make this water",
    )
    send_context: bpy.props.BoolProperty(
        name="Send scene context",
        description="Send a compact selection snapshot to the planner (Ollama or FastAPI)",
        default=True,
    )
    manual_tool: bpy.props.EnumProperty(
        name="Tool",
        description="Override: run a specific tool without asking the planner",
        items=MANUAL_TOOL_ITEMS,
        default="AUTO",
    )
    server_status: bpy.props.StringProperty(name="Server status", default="Unknown")
    last_status: bpy.props.StringProperty(name="Last status", default="")
    last_error: bpy.props.StringProperty(name="Last error", default="")
    inspect_result: bpy.props.StringProperty(name="Inspect result", default="")
    transcript: bpy.props.StringProperty(
        name="Transcript",
        description="Recent turns (user, plan, result)",
        default="",
    )
    ui_expand_connection: bpy.props.BoolProperty(
        name="Show planner connection",
        description="Ollama URL, model, or FastAPI base",
        default=False,
    )
    ui_expand_transcript: bpy.props.BoolProperty(
        name="Show transcript",
        default=False,
    )
    ui_expand_help: bpy.props.BoolProperty(
        name="Show example phrases",
        default=False,
    )


# ------------------------
# OPERATORS
# ------------------------


class BLENDAGENT_OT_check_server(bpy.types.Operator):
    bl_idname = "blendagent.check_server"
    bl_label = "Check planner server"
    bl_options = {"REGISTER"}

    def execute(self, context):
        scene = context.scene
        ba = scene.blendagent
        try:
            js = _http_get_json(_health_url(scene), timeout=5)
            ba.server_status = f"OK ({js.get('status', 'ok')})"
            self.report({"INFO"}, "Planner server reachable.")
        except Exception as e:
            ba.server_status = f"Error: {e}"
            self.report({"WARNING"}, "Planner server not reachable.")
        return {"FINISHED"}


class BLENDAGENT_OT_check_ollama(bpy.types.Operator):
    bl_idname = "blendagent.check_ollama"
    bl_label = "Check Ollama"
    bl_options = {"REGISTER"}

    def execute(self, context):
        scene = context.scene
        ba = scene.blendagent
        base = (ba.ollama_url or DEFAULT_OLLAMA_URL).rstrip("/")
        try:
            _http_get_json(base + "/api/tags", timeout=5)
            ba.ollama_status = "OK (Ollama is running)"
            self.report({"INFO"}, "Ollama is reachable.")
        except Exception as e:
            ba.ollama_status = f"Error: {e}"
            self.report({"WARNING"}, "Cannot reach Ollama. Start the Ollama app and pull a model.")
        return {"FINISHED"}


class BLENDAGENT_OT_check_openrouter(bpy.types.Operator):
    bl_idname = "blendagent.check_openrouter"
    bl_label = "Check OpenRouter"
    bl_options = {"REGISTER"}

    def execute(self, context):
        ba = context.scene.blendagent
        key = _prefs_openrouter_key()
        if not key:
            ba.openrouter_status = "No API key (Preferences)"
            self.report(
                {"WARNING"},
                "Set OpenRouter API key in Edit → Preferences → Add-ons → BlendAgent.",
            )
            return {"CANCELLED"}
        try:
            req = urllib.request.Request(
                OPENROUTER_MODELS_URL,
                headers={"Authorization": f"Bearer {key}"},
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                if resp.status == 200:
                    ba.openrouter_status = "OK (API key accepted)"
                    self.report({"INFO"}, "OpenRouter API key works.")
                    return {"FINISHED"}
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace") if e.fp else ""
            ba.openrouter_status = f"HTTP {e.code}"
            self.report({"WARNING"}, f"OpenRouter HTTP {e.code}: {body[:200]}")
            return {"CANCELLED"}
        except Exception as e:
            ba.openrouter_status = str(e)
            self.report({"WARNING"}, str(e))
            return {"CANCELLED"}
        return {"FINISHED"}


class BLENDAGENT_OT_execute_generated(bpy.types.Operator):
    bl_idname = "blendagent.execute_generated"
    bl_label = "Run generated script"
    bl_options = {"REGISTER"}

    def execute(self, context):
        scene = context.scene
        text = bpy.data.texts.get(GENERATED_TEXT_NAME)
        if not text:
            self.report(
                {"WARNING"},
                f"No Text datablock '{GENERATED_TEXT_NAME}'. Use Run in Generation mode first.",
            )
            return {"CANCELLED"}
        code = text.as_string()
        if not (code or "").strip():
            self.report({"WARNING"}, "Generated script is empty.")
            return {"CANCELLED"}
        try:
            ns = {"bpy": bpy, "__name__": "__main__"}
            exec(compile(code, GENERATED_TEXT_NAME, "exec"), ns)
        except Exception as e:
            scene.blendagent.last_status = "Generated script failed"
            scene.blendagent.last_error = str(e)
            append_transcript(scene, f"[EXEC FAIL] {e}")
            self.report({"ERROR"}, f"Script error: {e}")
            return {"CANCELLED"}
        scene.blendagent.last_error = ""
        scene.blendagent.last_status = "Executed generated script"
        append_transcript(scene, "[EXEC OK] generated script")
        self.report({"INFO"}, "Executed generated script.")
        return {"FINISHED"}


class BLENDAGENT_OT_clear_transcript(bpy.types.Operator):
    bl_idname = "blendagent.clear_transcript"
    bl_label = "Clear transcript"
    bl_options = {"REGISTER"}

    def execute(self, context):
        context.scene.blendagent.transcript = ""
        return {"FINISHED"}


class BLENDAGENT_OT_generate(bpy.types.Operator):
    bl_idname = "blendagent.generate"
    bl_label = "Run BlendAgent"
    bl_options = {"REGISTER"}

    def execute(self, context):
        scene = context.scene
        ba = scene.blendagent
        prompt = (ba.prompt or "").strip()
        manual = ba.manual_tool
        agent_mode = getattr(ba, "agent_mode", "ASSISTANT") or "ASSISTANT"

        ba.last_error = ""
        ba.inspect_result = ""

        if agent_mode == "GENERATION":
            if not _prefs_openrouter_key():
                ba.last_status = "Missing API key"
                ba.last_error = (
                    "Generation needs an OpenRouter API key. "
                    "Edit → Preferences → Add-ons → BlendAgent → OpenRouter API key."
                )
                self.report({"WARNING"}, ba.last_error)
                return {"CANCELLED"}
            if manual != "AUTO":
                self.report(
                    {"WARNING"},
                    "Manual tools are only for Assistant mode. Set Tool to Natural language (plan).",
                )
                return {"CANCELLED"}

        ba.session_tick = int(getattr(ba, "session_tick", 0) or 0) + 1

        if not prompt and manual == "AUTO":
            msg = "Enter a prompt or choose a manual tool."
            ba.last_status = "Idle"
            ba.last_error = msg
            self.report({"WARNING"}, msg)
            return {"CANCELLED"}

        op_id = None
        plan_source = "manual"
        server_err = None

        if manual != "AUTO":
            op_id = manual
            append_transcript(scene, f"[USER] (manual tool) {op_id}")
        else:
            if not prompt:
                msg = "Enter a prompt."
                ba.last_error = msg
                self.report({"WARNING"}, msg)
                return {"CANCELLED"}
            append_transcript(scene, f"[USER] {prompt}")
            plan, server_err = get_node_plan(scene, prompt)
            if plan is None:
                ba.last_status = "Planner unreachable"
                ba.last_error = server_err or "Unknown error"
                append_transcript(scene, f"[PLANNER] error: {ba.last_error}")
                mode = ba.planner_mode
                if agent_mode == "GENERATION":
                    self.report(
                        {"WARNING"},
                        "OpenRouter request failed. Check API key, internet, and credits at openrouter.ai.",
                    )
                elif mode == "FASTAPI":
                    self.report(
                        {"WARNING"},
                        "Planner server not reachable. Set API base and use Check server, or switch planner.",
                    )
                elif mode == "OPENROUTER":
                    self.report(
                        {"WARNING"},
                        "OpenRouter failed. Set API key in Preferences → Add-ons → BlendAgent.",
                    )
                else:
                    self.report(
                        {"WARNING"},
                        "Cannot reach Ollama. Start Ollama, run ollama pull llama3, then Check Ollama.",
                    )
                return {"CANCELLED"}

            if plan.get("mode") == "generation":
                plan_source = str(plan.get("source", ""))
                py = plan.get("python") or ""
                ba.last_status = (
                    f"Generated script ({plan_source}) — Text '{GENERATED_TEXT_NAME}'"
                )
                append_transcript(
                    scene,
                    f"[GENERATION] source={plan_source} chars={len(py)}",
                )
                self.report(
                    {"INFO"},
                    f"Script written to Text '{GENERATED_TEXT_NAME}'. Review it, then Run generated script.",
                )
                return {"FINISHED"}

            op_id = str(plan.get("operation", "")).strip()
            plan_source = str(plan.get("source", ""))
            if plan.get("error"):
                ba.last_error = str(plan["error"])
            append_transcript(
                scene,
                f"[PLAN] operation={op_id} source={plan_source} clarification={plan.get('needs_clarification', False)}",
            )

        if not op_id or op_id == "unknown":
            msg = f"Unknown or empty operation: {op_id!r}"
            ba.last_status = "No operation"
            ba.last_error = msg
            append_transcript(scene, f"[FAIL] {msg}")
            self.report({"WARNING"}, msg)
            return {"CANCELLED"}

        ok, msg = _finish_tool_run(scene, op_id, plan_source)
        if ok:
            self.report({"INFO"}, msg)
            return {"FINISHED"}
        self.report({"WARNING"}, msg)
        return {"CANCELLED"}


class BLENDAGENT_OT_vtuber_quick(bpy.types.Operator):
    bl_idname = "blendagent.vtuber_quick"
    bl_label = "VTuber quick"
    bl_options = {"REGISTER", "UNDO"}

    tool_id: bpy.props.StringProperty(name="Tool id", default="", options={"HIDDEN"})

    def execute(self, context):
        tid = (self.tool_id or "").strip()
        if not tid:
            self.report({"WARNING"}, "No tool id.")
            return {"CANCELLED"}
        scene = context.scene
        ba = scene.blendagent
        ba.last_error = ""
        ba.inspect_result = ""
        append_transcript(scene, f"[USER] (VTuber) {tid}")
        ok, msg = _finish_tool_run(scene, tid, "VTuber")
        if ok:
            self.report({"INFO"}, msg)
            return {"FINISHED"}
        self.report({"WARNING"}, msg)
        return {"CANCELLED"}


# ------------------------
# UI PANEL
# ------------------------


class BLENDAGENT_PT_panel(bpy.types.Panel):
    bl_label = "BlendAgent"
    bl_idname = "BLENDAGENT_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "BlendAgent"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        try:
            ba = scene.blendagent
        except (AttributeError, TypeError):
            layout.label(text="BlendAgent: enable add-on in Edit > Preferences", icon="ERROR")
            return
        obj = context.active_object

        layout.prop(ba, "agent_mode", text="Mode")

        if ba.agent_mode == "GENERATION":
            layout.label(text="Generation uses OpenRouter only (cloud LLM).", icon="WORLD")
            layout.label(text="Without an API key, Run cannot contact any model.", icon="INFO")

            key = _prefs_openrouter_key()
            kr = layout.box()
            kr.label(text="OpenRouter API key", icon="KEYINGSET")
            kr.label(text="Edit → Preferences → Add-ons → BlendAgent → paste key")
            row = kr.row(align=True)
            row.operator("blendagent.check_openrouter", text="Verify key")
            st = ba.openrouter_status or ("Key set" if key else "No key in Preferences")
            kr.label(text=st, icon="CHECKMARK" if key else "ERROR")
            if not key:
                kr.label(text="Add a key before testing Generation.", icon="ERROR")

            kr.prop(ba, "openrouter_model_family", text="Model")

            pq = layout.box()
            pq.label(text="Prompt", icon="TEXT")
            pq.prop(ba, "prompt", text="")
            pq.prop(ba, "send_context", text="Send scene context")

            ex = layout.box()
            ex.label(text="Last model reply (short excerpt)", icon="TEXT")
            ex.prop(ba, "generation_preview", text="")
            ex.label(text="Full Python script is in the Text data-block (see below).", icon="INFO")

            row = layout.row()
            row.scale_y = 1.2
            row.operator("blendagent.generate", text="Generate script", icon="PLAY")

            run = layout.box()
            run.label(text="Script: Text Editor → " + GENERATED_TEXT_NAME, icon="TEXT")
            run.operator("blendagent.execute_generated", text="Run generated script", icon="SCRIPT")

            fb = layout.box()
            fb.label(text="Status", icon="CHECKMARK")
            fb.label(text=ba.last_status or "-")
            err = ba.last_error
            if err:
                fb.label(text=f"Error: {err[:200]}", icon="ERROR")

            layout.prop(ba, "ui_expand_transcript", text="Transcript")
            if ba.ui_expand_transcript:
                tr = layout.box()
                tr.prop(ba, "transcript", text="Log")
                tr.operator("blendagent.clear_transcript", text="Clear")
            return

        layout.label(text="Assistant: trusted manifest tools", icon="INFO")
        layout.prop(ba, "planner_mode", text="Planner")
        mode = ba.planner_mode

        layout.prop(ba, "ui_expand_connection", text="Connection settings (URLs, check)")
        if ba.ui_expand_connection:
            if mode == "FASTAPI":
                srv = layout.box()
                srv.label(text="Planner server", icon="URL")
                srv.prop(ba, "api_base", text="API base")
                row = srv.row(align=True)
                row.operator("blendagent.check_server", text="Check server")
                srv.label(text=ba.server_status or "-", icon="WORLD")
            elif mode == "OPENROUTER":
                ob = layout.box()
                ob.label(text="OpenRouter", icon="WORLD")
                ob.prop(ba, "openrouter_model_family", text="Model")
                row = ob.row(align=True)
                row.operator("blendagent.check_openrouter", text="Check key")
                ob.label(text=ba.openrouter_status or "-", icon="WORLD")
                ob.label(text="API key: Edit → Preferences → Add-ons → BlendAgent", icon="KEYINGSET")
            else:
                oll = layout.box()
                oll.label(text="Ollama", icon="SHADERFX")
                oll.prop(ba, "ollama_url", text="URL")
                oll.prop(ba, "ollama_model", text="Model")
                row = oll.row(align=True)
                row.operator("blendagent.check_ollama", text="Check Ollama")
                oll.label(text=ba.ollama_status or "-", icon="WORLD")

        vt = layout.box()
        vt.label(text="VTuber (one-click)", icon="OUTLINER_OB_ARMATURE")
        r1 = vt.row(align=True)
        o = r1.operator("blendagent.vtuber_quick", text="Head")
        o.tool_id = "mesh_preset_vtuber_head"
        o = r1.operator("blendagent.vtuber_quick", text="Body")
        o.tool_id = "mesh_preset_vtuber_body"
        r2 = vt.row(align=True)
        o = r2.operator("blendagent.vtuber_quick", text="Armature")
        o.tool_id = "add_vtuber_armature"
        o = r2.operator("blendagent.vtuber_quick", text="Skin")
        o.tool_id = "skin_material_vtuber"
        r3 = vt.row(align=True)
        o = r3.operator("blendagent.vtuber_quick", text="Readiness")
        o.tool_id = "vtuber_readiness_check"
        r4 = vt.row(align=True)
        o = r4.operator("blendagent.vtuber_quick", text="Hair (particles)")
        o.tool_id = "hair_particles_vtuber"
        o = r4.operator("blendagent.vtuber_quick", text="Lights")
        o.tool_id = "lighting_lookdev_three_point"
        vt.label(text="Head/Body = blockout; Skin + Hair need mesh. Lights = 3-point lookdev.")

        sel = layout.box()
        sel.label(text="Selection", icon="RESTRICT_SELECT_OFF")
        if obj:
            sel.label(text=f"{obj.name}  ({obj.type})")
            manual = ba.manual_tool
            spec = _tools_by_id()
            if manual != "AUTO" and manual in spec:
                sel.label(text=f"Tool needs: {spec[manual].get('requires', '')}")
        else:
            sel.label(text="No active object")

        req = layout.box()
        req.label(text="Request", icon="TEXT")
        req.prop(ba, "manual_tool", text="Tool")
        req.prop(ba, "prompt", text="Prompt")
        req.prop(ba, "send_context", text="Send scene context")
        req.prop(ba, "include_conversation_memory", text="Conversation memory")
        sub = req.row()
        sub.enabled = ba.include_conversation_memory
        sub.prop(ba, "memory_max_lines", text="Max lines")

        row = layout.row()
        row.scale_y = 1.2
        row.operator("blendagent.generate", text="Run", icon="PLAY")

        fb = layout.box()
        fb.label(text="Last run", icon="CHECKMARK")
        fb.label(text=ba.last_status or "-")
        err = ba.last_error
        if err:
            fb.label(text=f"Error: {err}", icon="ERROR")

        ir = ba.inspect_result
        if ir:
            ib = layout.box()
            ib.label(text="Inspect output", icon="TEXT")
            for line in ir.split("\n")[:40]:
                ib.label(text=line[:120])

        layout.prop(ba, "ui_expand_transcript", text="Transcript")
        if ba.ui_expand_transcript:
            tr = layout.box()
            tr.prop(ba, "transcript", text="Log")
            tr.operator("blendagent.clear_transcript", text="Clear")

        layout.prop(ba, "ui_expand_help", text="Example phrases")
        if ba.ui_expand_help:
            help_box = layout.box()
            help_box.label(text="Try saying", icon="HELP")
            help_box.label(text="• make this water / glossy / eyes / hair")
            help_box.label(text="• VTuber row, or head mesh / body / skin")
            help_box.label(text="• add terrain noise / subdivide mesh")
            help_box.label(text="• summarize / list material nodes / keyframe")
            help_box.label(text="• Switch to Generation for full bpy scripts (OpenRouter key required)")


# ------------------------
# LEGACY Scene.blendagent_* (flat) -> scene.blendagent.* (older builds / .blend files)
# ------------------------

_LEGACY_SCENE_OPTS = {"HIDDEN"}


def _legacy_str_get(attr):
    def getter(self):
        return getattr(self.blendagent, attr)

    return getter


def _legacy_str_set(attr):
    def setter(self, value):
        setattr(self.blendagent, attr, value)

    return setter


def _legacy_send_context_get(self):
    return self.blendagent.send_context


def _legacy_send_context_set(self, value):
    self.blendagent.send_context = value


def register_legacy_scene_aliases():
    pairs = [
        ("blendagent_ollama_status", "ollama_status"),
        ("blendagent_server_status", "server_status"),
        ("blendagent_last_status", "last_status"),
        ("blendagent_last_error", "last_error"),
        ("blendagent_inspect_result", "inspect_result"),
        ("blendagent_transcript", "transcript"),
        ("blendagent_prompt", "prompt"),
        ("blendagent_ollama_url", "ollama_url"),
        ("blendagent_ollama_model", "ollama_model"),
        ("blendagent_api_base", "api_base"),
    ]
    for legacy, attr in pairs:
        setattr(
            bpy.types.Scene,
            legacy,
            bpy.props.StringProperty(
                name=legacy,
                get=_legacy_str_get(attr),
                set=_legacy_str_set(attr),
                options=_LEGACY_SCENE_OPTS,
            ),
        )
    bpy.types.Scene.blendagent_send_context = bpy.props.BoolProperty(
        name="blendagent_send_context",
        get=_legacy_send_context_get,
        set=_legacy_send_context_set,
        options=_LEGACY_SCENE_OPTS,
    )


def unregister_legacy_scene_aliases():
    for name in (
        "blendagent_ollama_status",
        "blendagent_server_status",
        "blendagent_last_status",
        "blendagent_last_error",
        "blendagent_inspect_result",
        "blendagent_transcript",
        "blendagent_prompt",
        "blendagent_ollama_url",
        "blendagent_ollama_model",
        "blendagent_api_base",
        "blendagent_send_context",
    ):
        if hasattr(bpy.types.Scene, name):
            delattr(bpy.types.Scene, name)


# ------------------------
# REGISTER
# ------------------------

classes = (
    BLENDAGENT_OT_check_server,
    BLENDAGENT_OT_check_ollama,
    BLENDAGENT_OT_check_openrouter,
    BLENDAGENT_OT_execute_generated,
    BLENDAGENT_OT_clear_transcript,
    BLENDAGENT_OT_generate,
    BLENDAGENT_OT_vtuber_quick,
    BLENDAGENT_PT_panel,
)


def register():
    bpy.utils.register_class(BlendAgentPreferences)
    bpy.utils.register_class(BLENDAGENT_PG_scene)
    bpy.types.Scene.blendagent = bpy.props.PointerProperty(type=BLENDAGENT_PG_scene)
    register_legacy_scene_aliases()
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    unregister_legacy_scene_aliases()
    try:
        del bpy.types.Scene.blendagent
    except Exception:
        pass
    bpy.utils.unregister_class(BLENDAGENT_PG_scene)
    bpy.utils.unregister_class(BlendAgentPreferences)


if __name__ == "__main__":
    register()
