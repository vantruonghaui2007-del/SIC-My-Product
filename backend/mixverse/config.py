from dataclasses import dataclass
import os
from pathlib import Path


def _load_backend_env() -> None:
    """Load backend/.env without overriding variables explicitly set by the shell."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False, encoding='utf-8-sig')


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).lower() in {"1", "true", "yes", "on"}


@dataclass(slots=True)
class Settings:
    data_dir: Path = Path("./data/mixverse")
    static_dir: Path | None = None
    demo_dir: Path | None = None
    ttl_hours: int = 24
    max_upload_mb: int = 100
    min_duration_s: float = 0.1
    max_duration_s: float = 360
    music_provider: str = "google"
    music_model: str = ""
    music_timeout_s: int = 240
    llm_provider: str = "rules"
    music_api_key: str | None = None
    provider_access_token: str | None = None

    @property
    def provider_model(self) -> str:
        return self.music_model.strip() or ('music_v2_5' if self.music_provider == 'elevenlabs' else 'lyria-3.5')

    @property
    def provider_label(self) -> str:
        return 'ElevenLabs' if self.music_provider == 'elevenlabs' else 'Google AI · Lyria'

    @property
    def provider_enabled(self) -> bool:
        from .creator.providers.google_music import GOOGLE_MODELS
        return bool(self.music_api_key and self.music_api_key.strip() and (
            self.music_provider == 'elevenlabs' or (self.music_provider == 'google' and self.provider_model in GOOGLE_MODELS)))

    @classmethod
    def from_env(cls) -> "Settings":
        _load_backend_env()
        provider = os.getenv('MIXVERSE_MUSIC_PROVIDER', 'google').strip().lower()
        key = ((os.getenv('GEMINI_API_KEY', '').strip() or os.getenv('GOOGLE_API_KEY', '').strip())
               if provider == 'google' else os.getenv('ELEVENLABS_API_KEY', '').strip() if provider == 'elevenlabs' else '')
        return cls(
            data_dir=Path(os.getenv("MIXVERSE_DATA_DIR", "./data/mixverse")),
            static_dir=Path(v) if (v := os.getenv("MIXVERSE_STATIC_DIR")) else None,
            demo_dir=Path(v) if (v := os.getenv("MIXVERSE_DEMO_DIR")) else None,
            ttl_hours=int(os.getenv("MIXVERSE_TTL_HOURS", "24")),
            max_upload_mb=int(os.getenv("MIXVERSE_MAX_UPLOAD_MB", "100")),
            min_duration_s=float(os.getenv("MIXVERSE_MIN_DURATION_S", "0.1")),
            max_duration_s=float(os.getenv("MIXVERSE_MAX_DURATION_S", "360")),
            music_provider=provider,
            music_model=os.getenv("MIXVERSE_MUSIC_MODEL", ""),
            music_timeout_s=int(os.getenv("MIXVERSE_MUSIC_TIMEOUT_S", "240")),
            llm_provider=os.getenv("MIXVERSE_LLM_PROVIDER", "rules"),
            music_api_key=key or None,
            provider_access_token=os.getenv('MIXVERSE_PROVIDER_ACCESS_TOKEN', '').strip() or None,
        )
