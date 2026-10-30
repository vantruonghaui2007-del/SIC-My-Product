---
title: MIXVERSE
emoji: 🎵
colorFrom: purple
colorTo: pink
sdk: docker
app_port: 7860
pinned: false
short_description: Sáng tác nhạc từ mô tả, xuất stems và MIDI
---

# MIXVERSE AI

MIXVERSE AI is a web music-creation/studio project with a FastAPI backend and React/Vite frontend. Most of it works fully offline with no API key: a rule-based local music engine composes complete tracks from Vietnamese/English prompts, and studio tools remix your own audio. An optional ElevenLabs Music adapter adds real generative AI (and is required for sung Text to Song).

## What works without any API

| Feature | What it does |
| --- | --- |
| **Text to Music (local engine)** | Reads the prompt (genre, mood, tempo, key, instruments, rain/ocean/vinyl ambience, "drums enter in the middle", duration) and shows every decision as editable chips. Composes diatonic chord progressions by mood, voice-led chords, bass lines, melody phrases and drums arranged into intro/verse/chorus/bridge/outro, synthesizes piano, electric piano, guitar, pad, strings, bell, pluck, lead, flute, bass/808 and a drum kit, then mixes to −14 LUFS. Up to 3 takes per request (different progressions). |
| **Downloads** | WAV and MP3 for every result; **stems** (drums, bass, harmony, melody, ambience) individually or as a ZIP; **MIDI** (one track per part plus GM drums) to keep working in any DAW. |
| **Rap to Beat** | Upload a vocal, get tempo candidates from its onset tempogram, confirm BPM/downbeat, receive three drum takes with the vocal timing untouched. |
| **Sound to Music** | Uses your own sample as percussion on the beat or as a looping texture. |
| **Remix / Mashup studio** | Rule-based prompts (add lofi/house/trap/edm/pop beat, rain/vinyl/ocean, change tempo, lower beat volume); sources are time-stretched to the project tempo; mashups place both songs on their own lanes; mixer with mute/gain; version history and undo. |
| **Library** | Every result is kept in the browser (localStorage) to replay and download until server files expire (24 h). |

The local engine is deterministic music theory and synthesis, **not** a generative AI model, and the UI says so wherever its output appears.

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

Public demo: see [DEPLOY.md](DEPLOY.md) (Hugging Face Spaces, free; the YAML block at the top of this README is the Space config).

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

- Backend: settings, audio I/O, atomic JSON project store with TTL purge, project/creator/studio APIs, and the `mixverse.music` package (`recipe` prompt interpreter → `compose` symbolic arrangement → `render` stems + master, `midi` export). Compositions are stored as `(recipe, seed)` and re-rendered on demand for stems/MIDI.
- Frontend: sidebar app with Text to Music, Text to Song, Rap to Beat, Sound to Music, Remix, Mashup and Library views; waveform player with seeking; responsive down to phone width.
- Text to Song (singing your lyrics) needs the ElevenLabs provider; without it the UI explains setup and points to the free local engine for an instrumental.
- Not done yet: stem separation of uploaded songs, key detection for sources, advanced Remix/Mashup editing (sections, transitions), background job persistence, quota/idempotency, licensed loop kits, provider listening validation and deployment benchmarks.
- No music provider credentials were detected during setup. Do not represent local or test audio as AI generation.

Copy `.env.example` to `.env` only for local configuration. Provider credentials must remain server-side.
