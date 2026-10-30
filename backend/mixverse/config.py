from dataclasses import dataclass
import os
from pathlib import Path


def _load_backend_env() -> None:
    """Load backend/.env without overriding variables explicitly set by the shell."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)


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
    music_provider: str = "none"
    music_model: str = "music_v2_5"
    music_timeout_s: int = 240
    llm_provider: str = "rules"
    music_api_key: str | None = None

    @classmethod
    def from_env(cls) -> "Settings":
        _load_backend_env()
        return cls(
            data_dir=Path(os.getenv("MIXVERSE_DATA_DIR", "./data/mixverse")),
            static_dir=Path(v) if (v := os.getenv("MIXVERSE_STATIC_DIR")) else None,
            demo_dir=Path(v) if (v := os.getenv("MIXVERSE_DEMO_DIR")) else None,
            ttl_hours=int(os.getenv("MIXVERSE_TTL_HOURS", "24")),
            max_upload_mb=int(os.getenv("MIXVERSE_MAX_UPLOAD_MB", "100")),
            min_duration_s=float(os.getenv("MIXVERSE_MIN_DURATION_S", "0.1")),
            max_duration_s=float(os.getenv("MIXVERSE_MAX_DURATION_S", "360")),
            music_provider=os.getenv("MIXVERSE_MUSIC_PROVIDER", "none"),
            music_model=os.getenv("MIXVERSE_MUSIC_MODEL", "music_v2_5"),
            music_timeout_s=int(os.getenv("MIXVERSE_MUSIC_TIMEOUT_S", "240")),
            llm_provider=os.getenv("MIXVERSE_LLM_PROVIDER", "rules"),
            music_api_key=os.getenv("ELEVENLABS_API_KEY"),
        )
