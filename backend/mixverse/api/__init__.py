from pathlib import Path
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from ..config import Settings
from ..store import ProjectStore, ProjectNotFound
from ..mixscript import Project
from .projects import router as projects_router
from .creator import router as creator_router
from .studio import router as studio_router
from .creator import purge_creator_assets


def create_app(settings: Settings | None = None, **kwargs) -> FastAPI:
    settings = settings or Settings.from_env()
    @asynccontextmanager
    async def lifespan(app):
        async def cleanup_loop():
            while True:
                await asyncio.sleep(600)
                app.state.store.purge_expired(ttl_hours=settings.ttl_hours)
                purge_creator_assets(settings.data_dir, settings.ttl_hours)
        task=asyncio.create_task(cleanup_loop())
        try: yield
        finally:
            task.cancel()
            try: await task
            except asyncio.CancelledError: pass
    app = FastAPI(title="MIXVERSE AI", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.store = ProjectStore(settings.data_dir)
    app.include_router(projects_router, prefix="/api")
    app.include_router(creator_router, prefix="/api")
    app.include_router(studio_router, prefix="/api")

    @app.get("/api/health")
    def health():
        return {"ok": True, "director": "rules", "separation": False, "music_provider": settings.music_provider if settings.provider_enabled else "none"}

    @app.get("/api/creator/capabilities")
    def capabilities():
        provider_enabled = settings.provider_enabled
        reason = ('Cấu hình MIXVERSE_MUSIC_PROVIDER=elevenlabs và ELEVENLABS_API_KEY ở backend.'
                  if settings.music_provider == 'elevenlabs' else
                  'Cấu hình MIXVERSE_MUSIC_PROVIDER=google, GEMINI_API_KEY và MIXVERSE_MUSIC_MODEL=lyria-3.5 ở backend.')
        provider_info = {'provider': settings.music_provider if settings.music_provider in ('google', 'elevenlabs') else None,
                         'provider_label': settings.provider_label, 'provider_model': settings.provider_model,
                         'provider_access_required': bool(settings.provider_access_token),
                         'provider_duration_note': ('Lyria Clip tạo đúng 30 giây.' if settings.provider_model == 'lyria-3-clip-preview' else
                             'Thời lượng là yêu cầu gửi đến Google; bản nhạc có thể dài hoặc ngắn hơn.' if settings.music_provider == 'google' else '')}
        return {"modes": {
            "remix": {"enabled": True, "method": "basic_studio", "reason": "Upload một nguồn, dựng beat và xuất WAV/MP3."},
            "mashup": {"enabled": True, "method": "basic_studio", "reason": "Upload tối đa hai nguồn; ghép nâng cao đang được hoàn thiện."},
            "text_music": {**provider_info, "enabled": True, "method": "local_engine", "provider_enabled": provider_enabled, "reason": "Engine nhạc local: hiểu prompt Việt/Anh, tự viết hợp âm, giai điệu, bass, trống; xuất WAV/MP3, stem và MIDI. Không phải mô hình AI.", "provider_reason": None if provider_enabled else reason},
            "text_song": {**provider_info, "enabled": provider_enabled, "reason": None if provider_enabled else reason},
            "rap_beat": {"enabled": True, "method": "local_pattern", "reason": "Beat local theo BPM; BPM chỉ là gợi ý và cần bạn xác nhận."},
            "sound_music": {"enabled": True, "method": "source_sample", "reason": "Dùng chính sample đầu vào; vai trò do bạn chọn."},
        }}

    @app.exception_handler(ProjectNotFound)
    async def not_found(_, exc):
        raise HTTPException(404, str(exc))

    if settings.static_dir and settings.static_dir.is_dir():
        app.mount("/", StaticFiles(directory=settings.static_dir, html=True), name="frontend")
    return app


def create_app_from_env() -> FastAPI:
    return create_app(Settings.from_env())
