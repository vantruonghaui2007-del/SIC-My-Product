# MIXVERSE AI

MIXVERSE AI is a web music-creation/studio project with a FastAPI backend and React/Vite frontend. It includes local audio previews and a configurable ElevenLabs Music provider adapter. Remix/Mashup and local Creator workflows are still prototypes, not full AI production tools.

## Local development

Requirements: Python 3.12+ (tested with Python 3.13; Python 3.9 is not supported by the current dependencies), Node.js 22+, npm, and FFmpeg with `libmp3lame`.

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m uvicorn mixverse.api:create_app_from_env --factory --reload --port 8002
```

In a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

The frontend proxies `/api` to `localhost:8002`. In a second terminal, run `cd frontend; npm install; npm run dev -- --port 5173` and open `http://localhost:5173`. Run tests with `python -m pytest backend/tests -q` and build the web app with `cd frontend; npm run build`.

Docker: `docker build -t mixverse .` then `docker run --rm -p 7860:7860 -v mixverse-data:/data/mixverse mixverse`. The image currently targets Python 3.13 because that is the runtime available in the workspace; plan deployment target 3.12 compatibility still needs a separate CI verification. Smoke check with `python scripts/smoke.py --base-url http://localhost:7860`.

### Enable real AI music generation

The local preview is not AI. To call the configured ElevenLabs Music provider, create `backend/.env` (copy `backend/.env.example`) and enter:

```dotenv
MIXVERSE_MUSIC_PROVIDER=elevenlabs
ELEVENLABS_API_KEY=your_api_key
MIXVERSE_MUSIC_MODEL=music_v2_5
```

`backend/.env` is ignored by Git and must never be committed. Alternatively, set the same variables in the backend process environment:

```powershell
$env:MIXVERSE_MUSIC_PROVIDER = "elevenlabs"
$env:ELEVENLABS_API_KEY = "your_api_key"
$env:MIXVERSE_MUSIC_MODEL = "music_v2_5"
python -m uvicorn mixverse.api:create_app_from_env --factory --app-dir backend --port 8002
```

Restart the backend after changing variables. The capability endpoint should then report `provider_enabled: true` for Text-to-Music and Text-to-Song. In the UI, select **AI Music Provider**, agree to send the prompt, and submit once. Provider usage may be billed. A timeout/connection error is not retried because the provider may already have accepted the request. This workspace has not verified a paid live call; provider API/schema changes should be checked against current ElevenLabs docs before production use.

## Current scope/status

- Implemented settings, audio I/O, synthetic fixtures, project/script models, atomic JSON store with TTL purge, project create/read/delete API, health/capability endpoint, and a responsive Creator interface.
- Local Text-to-Music produces an audible procedural arrangement, explicitly labelled as a local synth (not generative AI/Loop Kit). Rap-to-Beat accepts rights-confirmed vocal uploads, reports heuristic onset/tempo hints that require user BPM confirmation, preserves vocal timing, and produces three seeded local drum patterns. Sound-to-Music uses the uploaded sample in percussion or texture previews, traceable by source hash.
- Text-to-Song has a server-side ElevenLabs adapter, consent gate, no automatic retries, and provider capability remains disabled until `MIXVERSE_MUSIC_PROVIDER=elevenlabs` and `ELEVENLABS_API_KEY` are configured.
- Basic studio edit/export API scaffolding exists; full project-source analysis, Remix/Mashup editing, timeline/version flow, background job persistence, quota/idempotency, advanced analysis, true licensed Loop Kit, provider listening validation, deployment, and acceptance benchmarks remain incomplete.
- No music provider credentials were detected during initial setup. Do not represent mock/test audio as live generation.

Copy `.env.example` to `.env` only for local configuration. Provider credentials must remain server-side.
