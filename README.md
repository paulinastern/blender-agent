# BlendAgent

BlendAgent maps natural language to **trusted, prewritten** Blender tools (materials, geometry nodes, inspect helpers, simple keyframes). In **Assistant** mode, the planner only **chooses** which registered tool to run; it does **not** invent arbitrary `bpy` code paths (Ollama local, OpenRouter cloud planner, or optional FastAPI server).

## How people install and use it

| You have… | What to do |
|-----------|------------|
| **This GitHub repo** (clone or ZIP) | Same as below: in Blender, **Edit → Preferences → Add-ons → Install…** and pick **`blend_agent_addon.py`**. You do **not** install the folder as a zip package unless you repackage the add-on that way; the supported path is **install the single `.py` file**. |
| **Only the add-on file** | Enough for most users. The manifest is **embedded** in the script. |

Optional next to the `.py` (same folder is fine if you browse to the file): **`blendagent_tools.json`** (override tool list) and **`blendagent_playbook.json`** (workflow hints for the planner). If those files are absent, embedded defaults are used.

**API key:** Only if you use **OpenRouter** (Assistant with planner **OpenRouter**, or **Generation** mode). Set it in **Edit → Preferences → Add-ons →** find **BlendAgent** → expand → **OpenRouter API key** (stored in Blender preferences, not inside `.blend` files). **Ollama (local)** and **Planner server** do not use that key.

After install: enable the add-on, open **View3D → Sidebar (N) → BlendAgent**, pick modes as below, then prompt and **Run**.

## Modes (N-panel)

**Agent mode** (what BlendAgent *does* with your prompt):

| Mode | Behavior | API key |
|------|----------|---------|
| **Assistant** | Planner returns one **manifest** `operation`; the add-on runs the matching **registered** Python tool only. Safest default. | Only if **Planner** is **OpenRouter** |
| **Generation** | A cloud model (via **OpenRouter**) writes a **Python script** into a Text datablock (`BlendAgent_Generated`). You should **read the script**, then use **Run generated script** if you accept it. Flexible but **treat like untrusted code**. | **Required** (OpenRouter) |

**Planner** (Assistant only — *how* the tool is chosen):

| Planner | Best for | Notes |
|---------|----------|--------|
| **Ollama (local)** | Default; privacy; no extra services | Ollama must be running; model pulled (e.g. `llama3`). |
| **OpenRouter** | Cloud models for planning only | Same manifest tools as Ollama; prompts go to OpenRouter. |
| **Planner server** | Developers / custom hosts | Run `agent_server.py` (or `Start_BlendAgent_Planner.bat` on Windows); set **Planner API base** to e.g. `http://127.0.0.1:8000`. |

Generation mode ignores the Planner dropdown for *planning*; it always uses OpenRouter to produce script text.

## Cautions

- **Save your `.blend` often.** Tools modify the scene; there is no full “sandbox”.
- **Assistant** = bounded tool set. **Generation** = model-authored `bpy`; only run it if you understand or trust the script (it runs with full Blender Python access when you click **Run generated script**).
- **Cloud paths** send your prompt (and optional scene context) over the network to OpenRouter or your self-hosted planner.
- After **upgrading** the add-on: **disable → restart Blender → enable** to avoid stale registration.

## Artist setup (no terminal)

1. Install **[Ollama](https://ollama.com/)** and start it (system tray on Windows).
2. Pull a model (example): `ollama pull llama3`
3. In Blender: **Edit → Preferences → Add-ons → Install…** and select **`blend_agent_addon.py`** (that single file is the add-on module).

The add-on embeds the tool list, so **you do not need extra files** next to the script on Windows single-file installs. If you ship `blendagent_tools.json` beside the add-on, that file is used instead (handy for forks).

Settings are stored on the scene as **`scene.blendagent`** (a property group), not as loose attributes on `Scene`.

If you upgraded from an older BlendAgent build, **disable the add-on, restart Blender, then enable again** so registration stays clean.

4. Open **View3D → Sidebar (N) → BlendAgent**.
5. Leave **Agent mode** on **Assistant** and **Planner** on **Ollama (local)** (default).
6. Click **Check Ollama** — you should see a reachable / OK style message.
7. Select an object if the tool needs one, type a prompt (e.g. “make this water”), **Run**.

You do **not** need Python, `uvicorn`, or a second terminal for this path.

## Advanced: FastAPI planner (developers)

The optional `agent_server.py` service is for development or custom deployments. **Windows:** double-click **`Start_BlendAgent_Planner.bat`** in this repo (installs deps and starts the server on port 8000). In Blender, set **Planner** to **Planner server (advanced)** and **API base** to `http://127.0.0.1:8000`, then **Check server**.

Manual start:

```bash
pip install -r requirements.txt
uvicorn agent_server:app --reload --host 127.0.0.1 --port 8000
```

- Health: `GET http://127.0.0.1:8000/health`
- Plan: `POST http://127.0.0.1:8000/plan`

## Tool manifest

Authoritative list for development: [`blendagent_tools.json`](blendagent_tools.json). If you change tools, update that file **and** the embedded string `_EMBEDDED_MANIFEST_JSON` at the top of [`blend_agent_addon.py`](blend_agent_addon.py) (or rely on the external JSON only).

**Playbook (workflow hints):** [`blendagent_playbook.json`](blendagent_playbook.json) lists suggested tool order and tips for the planner (not executable code). The add-on loads it from disk when present, otherwise uses `_EMBEDDED_PLAYBOOK_JSON` inside [`blend_agent_addon.py`](blend_agent_addon.py). It is merged into **Context** on every planner call (Ollama or FastAPI), alongside scene snapshot when **Send scene context** is on.

### VTuber demo (v0.3.4)

When **Send scene context** is on, `/plan` receives workspace name, `context_mode`, active area type, and mesh extras (e.g. shape key count). The N-panel **VTuber (one-click)** row runs the same tools without natural language.

| Tool | Purpose |
|------|---------|
| `mesh_preset_vtuber_head` | UV-sphere blockout head (named `VTuber_Head`) |
| `mesh_preset_vtuber_body` | Scaled cube + Subdivision blockout torso (named `VTuber_Body`) |
| `skin_material_vtuber` | Warm peach Principled skin, noise bump, subsurface (needs active mesh) |
| `hair_material_basic` | Stylized mesh hair: anisotropic sheen, noise roughness, bump, rim + bands |
| `hair_particles_vtuber` | Particle hair on selected mesh (scalp): Hair BSDF, path render, simple children |
| `lighting_lookdev_three_point` | Removes prior `BlendAgent_Lookdev_*` lights; adds key/fill/rim areas + dark world |
| `add_vtuber_armature` | Minimal humanoid armature (hips chain, head, arms, legs) |
| `vtuber_readiness_check` | Inspect-only checklist and scene summary for a VTuber-style pipeline |

Eyes still use `eye_material_basic`. This is a **starting point** for a showcase—not a full Live3D/VRM export pipeline.

## Design

- **Intent**: Ollama returns JSON (`operation`, `needs_clarification`, `reason`) or keyword fallback.
- **Execution**: Add-on runs registered Python builders only.
- **Networking**: The add-on uses the Python **standard library** (`urllib`) so Blender does not need the `requests` package.
