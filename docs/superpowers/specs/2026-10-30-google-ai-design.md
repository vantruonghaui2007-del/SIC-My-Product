# Google AI music integration

The user wants Google AI Studio music generation in place of ElevenLabs and has activated their Google billing benefit. Use Google Lyria through the documented Gemini Interactions REST API for instrumental music and supplied lyrics. Google AI Pro benefits do not prove that a model or API key is usable; do not claim live validation without a successful request.

Approaches: Gemini text models can interpret prompts but cannot replace the existing audio provider; Lyria directly produces audio and matches the requested replacement. Use the existing httpx dependency rather than introducing an SDK. Keep the explicit legacy ElevenLabs setting for compatibility, but make Google the default setup and update visible provider labels, consent, library credits, and setup instructions.

Key contract: backend-only GEMINI_API_KEY (GOOGLE_API_KEY fallback), MIXVERSE_MUSIC_PROVIDER=google, default model lyria-3.5. Configuration never returns secrets. A missing key disables Google generation while local music remains usable. A public link grants visitors access to the configured backend, so optional MIXVERSE_PROVIDER_ACCESS_TOKEN will restrict paid generation to users who supply that token; local generation remains public. The token is never stored in browser storage. This is proposed operational protection for this public demo, not an account system.

Only send a generation request after explicit prompt/lyrics consent. Never retry a POST after a timeout or transport error. Parse documented model_output audio blocks from steps, validate base64, decode audio through the existing pipeline, and serve existing WAV/MP3 downloads. Reject missing/unsupported output, unsupported model and invalid local inputs clearly. Lyria 3.5 duration is a prompt preference, not an exact guarantee; Clip is exactly 30 seconds. No stem/MIDI promises for provider audio.

Scope excludes broader Gemini chat, automatic billing setup, paid live calls, and deployment to Oracle. Add usage instructions and tests with a local HTTP transport. Do not read or publish credentials. Update the currently running task-owned local web after validation.
