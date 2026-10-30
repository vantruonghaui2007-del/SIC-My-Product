# Google AI Studio music in MIXVERSE

Google Lyria replaces the default ElevenLabs setup for Text to Music and Text to Song. Local music remains available without an API key. The optional legacy ElevenLabs setting still works when explicitly configured.

## Configure the backend

Copy `backend/.env.example` to `backend/.env` and fill in:

```dotenv
MIXVERSE_MUSIC_PROVIDER=google
MIXVERSE_MUSIC_MODEL=lyria-3.5
GEMINI_API_KEY=your_private_google_key
MIXVERSE_PROVIDER_ACCESS_TOKEN=choose_a_long_private_access_code
```

Use a key from https://aistudio.google.com/api-keys belonging to the project with the intended Billing account. `GOOGLE_API_KEY` is also accepted when `GEMINI_API_KEY` is absent or blank. Restart the backend after changes. Shell variables take precedence over `.env`; remove an old `MIXVERSE_MUSIC_PROVIDER=none` or `elevenlabs` override when switching to Google.

The API key remains on the server. The access code is different from the Google API key: enter the access code into the web's **Mã truy cập AI** field. Only share that code with people allowed to use your paid music quota. The browser does not persist the code in its library. With no access code configured, anyone able to reach the API can generate using your configured account.

For Docker, provide these variables at runtime with `--env-file /path/to/private.env`, stored outside the repository. Root and nested `.env` files are excluded from the build context. Do not put credentials into a Dockerfile, image, frontend, Git commit, or chat message.

## Generate

- **Text to Music:** write the musical direction, select **AI Provider · Google AI · Lyria**, enter the private access code if required, agree to send the prompt, then click **Sinh nhạc bằng AI**.
- **Text to Song:** enter lyrics with optional [Verse]/[Chorus] labels, choose style and target duration, review the lyrics, enter the access code, agree to send lyrics to Google, then click **Sinh bài hát**.
- Play the result and download WAV or MP3. Provider output does not include MIDI or separated stems.

Lyria 3.5 accepts duration guidance through the prompt, so actual audio length can differ from the selected target. To use `lyria-3-clip-preview`, select exactly 30 seconds. The app rejects other Clip durations before making an API call.

## Billing and failures

Google AI Pro membership or a listed model is not proof that paid generation will work. The project also needs model access, available quota and appropriate Billing/credits. Check current pricing and actual credit eligibility in your Google account.

The app sends one generation POST per click. It does not automatically retry a timeout, network error, or failed response. On an uncertain result, check Google AI Studio usage before clicking again. Authentication, Billing, quota and model-access failures produce separate user messages without exposing upstream response bodies.

This integration uses the documented Interactions API JSON `steps`/`model_output` audio blocks. Automated tests use in-memory HTTP responses and real WAV/MP3 decoding; they do not incur API charges. A live paid generation must be verified separately.

References: https://ai.google.dev/gemini-api/docs/music-generation, https://ai.google.dev/gemini-api/docs/api-key, https://ai.google.dev/gemini-api/docs/pricing.
