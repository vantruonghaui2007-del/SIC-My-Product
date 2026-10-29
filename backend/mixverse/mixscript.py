from __future__ import annotations
from datetime import datetime, timezone
from typing import Annotated, Literal
from pydantic import BaseModel, Field, ConfigDict

Stem = Literal["mix", "vocals", "drums", "bass", "other"]
SectionLabel = Literal["intro", "verse", "chorus", "bridge", "outro"]
BeatStyle = Literal["house", "edm", "lofi", "trap", "pop"]
AmbienceKind = Literal["rain", "vinyl", "ocean"]
TransitionStyle = Literal["cut", "echo_out", "riser", "filter_sweep", "crossfade"]
EffectKind = Literal["gain", "high_shelf", "lowpass", "highpass", "filter_sweep_up", "reverb", "echo", "riser"]


class Section(BaseModel):
    id: str
    label: SectionLabel
    start_bar: int
    end_bar: int


class SourceAnalysis(BaseModel):
    duration_s: float = 0
    bpm: float = 0
    beats_s: list[float] = Field(default_factory=list)
    downbeats_s: list[float] = Field(default_factory=list)
    n_bars: int = 0
    key: str = ""
    camelot: str = ""
    key_confidence: float = 0
    sections: list[Section] = Field(default_factory=list)
    bar_energy: list[float] = Field(default_factory=list)
    peaks: list[float] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class Source(BaseModel):
    id: str
    name: str
    sha256: str = ""
    rights_confirmed: bool = False
    uploaded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: Literal["analyzing", "ready", "error"] = "ready"
    error: str | None = None
    stems: list[Stem] = Field(default_factory=lambda: ["mix"])
    separation: Literal["none", "running", "done", "error"] = "none"
    separation_progress: float = 0
    analysis: SourceAnalysis | None = None


class AudioClip(BaseModel):
    kind: Literal["audio"] = "audio"
    id: str
    lane: str
    source_id: str
    stem: Stem = "mix"
    src_start_bar: float = 0
    start_bar: float = 0
    length_bars: float
    gain_db: float = 0
    muted: bool = False
    pitch_shift: int = 0


class BeatClip(BaseModel):
    kind: Literal["beat"] = "beat"
    id: str
    lane: str
    style: BeatStyle
    start_bar: float = 0
    length_bars: float
    gain_db: float = -3
    muted: bool = False


class AmbienceClip(BaseModel):
    kind: Literal["ambience"] = "ambience"
    id: str
    lane: str
    ambience: AmbienceKind
    start_bar: float = 0
    length_bars: float
    gain_db: float = -18
    muted: bool = False


Clip = Annotated[AudioClip | BeatClip | AmbienceClip, Field(discriminator="kind")]


class Transition(BaseModel):
    id: str
    from_clip: str
    to_clip: str
    style: TransitionStyle
    length_beats: int


class Effect(BaseModel):
    id: str
    lane: str
    start_bar: float
    end_bar: float
    kind: EffectKind
    amount: float
    group: str = ""


class MixScript(BaseModel):
    model_config = ConfigDict(validate_assignment=True)
    bpm: float = 120
    key: str = ""
    clips: list[Clip] = Field(default_factory=list)
    transitions: list[Transition] = Field(default_factory=list)
    effects: list[Effect] = Field(default_factory=list)

    def bar_s(self) -> float:
        return 240 / self.bpm

    def total_bars(self) -> float:
        return max((c.start_bar + c.length_bars for c in self.clips if not c.muted), default=0.0)

    def lanes(self) -> list[str]:
        return list(dict.fromkeys(c.lane for c in self.clips))

    def clip(self, clip_id: str) -> Clip:
        return next(c for c in self.clips if c.id == clip_id)

    def next_id(self, prefix: Literal["c", "t", "e"]) -> str:
        ids = [getattr(x, "id", "") for x in (*self.clips, *self.transitions, *self.effects)]
        nums = [int(i[1:]) for i in ids if i.startswith(prefix) and i[1:].isdigit()]
        return f"{prefix}{max(nums, default=0)+1}"


class ChangeCard(BaseModel):
    kind: str
    title: str
    detail: str
    start_bar: float = 0
    end_bar: float = 0
    reason: str = ""


class Selection(BaseModel):
    start_bar: float
    end_bar: float


class Version(BaseModel):
    id: str
    parent: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    prompt: str = ""
    selection: Selection | None = None
    provider: str = "manual"
    status: Literal["draft", "kept", "discarded"] = "kept"
    script: MixScript = Field(default_factory=MixScript)
    cards: list[ChangeCard] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    render: Literal["pending", "rendering", "ready", "error"] = "pending"
    render_file: str | None = None
    peaks: list[float] = Field(default_factory=list)
    bar_energy: list[float] = Field(default_factory=list)
    creator_take_id: str | None = None


class Event(BaseModel):
    type: str
    at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    version_id: str | None = None
    provider: str | None = None


class Project(BaseModel):
    id: str
    mode: Literal["mashup", "remix", "create"]
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    sources: list[Source] = Field(default_factory=list)
    versions: list[Version] = Field(default_factory=list)
    head: str = "v0"
    events: list[Event] = Field(default_factory=list)
    schema_version: int = 2
    creator_assets: dict = Field(default_factory=dict)
    creator_analyses: dict = Field(default_factory=dict)
    creator_patterns: dict = Field(default_factory=dict)
    creator_jobs: dict = Field(default_factory=dict)
    creator_takes: dict = Field(default_factory=dict)
    creator_imports: list[dict] = Field(default_factory=list)
