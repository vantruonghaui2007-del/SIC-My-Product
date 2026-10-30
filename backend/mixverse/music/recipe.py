"""Rule-based prompt understanding (Vietnamese + English) into an editable music recipe.

This is deliberately not AI: it is a transparent keyword/regex interpreter whose every
decision is reported back as a "detected" chip, so users can see and override it.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from .theory import NOTE_NAMES, pitch_class

Genre = Literal["lofi", "trap", "house", "edm", "pop", "ambient", "ballad", "rnb", "cinematic"]
Mood = Literal["chill", "happy", "sad", "dark", "epic", "romantic", "energetic", "dreamy"]
Instrument = Literal["piano", "epiano", "guitar", "pad", "strings", "bass", "bell", "pluck", "lead", "flute"]
Ambience = Literal["none", "rain", "ocean", "vinyl"]

GENRES: dict[str, dict] = {
    "lofi": {"label": "Lofi", "bpm": 80, "mood": "chill", "instruments": ["epiano", "bass", "guitar"], "drums": "lofi", "swing": .18, "sevenths": True, "ambience": "vinyl"},
    "trap": {"label": "Trap", "bpm": 140, "mood": "dark", "instruments": ["bell", "bass", "pad"], "drums": "trap", "swing": 0, "sevenths": False, "ambience": "none"},
    "house": {"label": "House", "bpm": 124, "mood": "energetic", "instruments": ["piano", "bass", "pad"], "drums": "house", "swing": .06, "sevenths": True, "ambience": "none"},
    "edm": {"label": "EDM", "bpm": 128, "mood": "energetic", "instruments": ["pluck", "lead", "bass", "pad"], "drums": "edm", "swing": 0, "sevenths": False, "ambience": "none"},
    "pop": {"label": "Pop", "bpm": 108, "mood": "happy", "instruments": ["piano", "bass", "pluck"], "drums": "pop", "swing": 0, "sevenths": False, "ambience": "none"},
    "ambient": {"label": "Ambient", "bpm": 70, "mood": "dreamy", "instruments": ["pad", "bell", "strings"], "drums": None, "swing": 0, "sevenths": True, "ambience": "none"},
    "ballad": {"label": "Ballad", "bpm": 72, "mood": "romantic", "instruments": ["piano", "strings", "bass"], "drums": "ballad", "swing": 0, "sevenths": False, "ambience": "none"},
    "rnb": {"label": "R&B", "bpm": 88, "mood": "romantic", "instruments": ["epiano", "bass", "pad"], "drums": "rnb", "swing": .12, "sevenths": True, "ambience": "none"},
    "cinematic": {"label": "Cinematic", "bpm": 90, "mood": "epic", "instruments": ["strings", "piano", "pad", "bass"], "drums": None, "swing": 0, "sevenths": False, "ambience": "none"},
}
MOODS: dict[str, dict] = {
    "chill": {"label": "Chill", "mode": "major", "genre": "lofi"},
    "happy": {"label": "Vui tươi", "mode": "major", "genre": "pop"},
    "sad": {"label": "Buồn", "mode": "minor", "genre": "ballad"},
    "dark": {"label": "U tối", "mode": "minor", "genre": "trap"},
    "epic": {"label": "Hùng tráng", "mode": "minor", "genre": "cinematic"},
    "romantic": {"label": "Lãng mạn", "mode": "major", "genre": "rnb"},
    "energetic": {"label": "Sôi động", "mode": "minor", "genre": "edm"},
    "dreamy": {"label": "Mơ màng", "mode": "major", "genre": "ambient"},
}
INSTRUMENTS: dict[str, str] = {
    "piano": "Piano", "epiano": "Electric piano", "guitar": "Guitar", "pad": "Synth pad", "strings": "Dàn dây",
    "bass": "Bass", "bell": "Bell", "pluck": "Pluck", "lead": "Synth lead", "flute": "Sáo",
}
AMBIENCES = {"none": "Không", "rain": "Tiếng mưa", "ocean": "Sóng biển", "vinyl": "Vinyl crackle"}
DEFAULT_KEYS = {"major": ["C", "F", "G", "D", "A#"], "minor": ["A", "D", "E", "C", "F#"]}


class Recipe(BaseModel):
    genre: Genre = "lofi"
    mood: Mood = "chill"
    bpm: float = Field(80, ge=60, le=180)
    key: str = "C"
    mode: Literal["major", "minor"] = "major"
    duration_s: int = Field(30, ge=15, le=120)
    instruments: list[Instrument] = Field(default_factory=lambda: ["epiano", "bass", "guitar"])
    drums: bool = True
    drums_entry: Literal["start", "middle"] = "start"
    melody: bool = True
    ambience: Ambience = "vinyl"

    @field_validator("key")
    @classmethod
    def _key(cls, value: str) -> str:
        return NOTE_NAMES[pitch_class(value)]

    @field_validator("instruments")
    @classmethod
    def _instruments(cls, value: list[str]) -> list[str]:
        value = list(dict.fromkeys(value))
        if not value:
            raise ValueError("Cần ít nhất một nhạc cụ.")
        return value

    @property
    def key_name(self) -> str:
        return f"{self.key} {'major' if self.mode == 'major' else 'minor'}"


class Detected(BaseModel):
    kind: Literal["genre", "mood", "tempo", "key", "instrument", "ambience", "structure", "duration"]
    label: str
    source: str  # the matched words, or "mặc định" when inferred


class ParsedPrompt(BaseModel):
    recipe: Recipe
    detected: list[Detected]
    notes: list[str] = Field(default_factory=list)


def fold(text: str) -> str:
    """Lowercase and strip Vietnamese diacritics (đ → d)."""
    text = text.lower().replace("đ", "d")
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


# Words that are ambiguous once diacritics are removed (e.g. "trống" drums vs "trong" in,
# "mưa" rain vs "mua" buy, "tối" dark vs "tôi" I). These must be typed with diacritics.
_AMBIGUOUS = {"trong", "toi", "mua", "sao", "song", "bien", "em", "ngu", "quay", "tram"}

GENRE_WORDS = {
    "lofi": ["lofi", "lo-fi", "lo fi", "chillhop"],
    "trap": ["trap", "drill", "808"],
    "house": ["house", "deep house"],
    "edm": ["edm", "dance", "điện tử", "electronic", "future bass", "bass house", "remix sàn", "bay phòng"],
    "pop": ["pop", "vpop", "v-pop", "kpop", "k-pop", "nhạc trẻ"],
    "ambient": ["ambient", "thiền", "meditation", "yoga", "spa"],
    "ballad": ["ballad", "bolero", "acoustic"],
    "rnb": ["r&b", "rnb", "soul", "neo soul"],
    "cinematic": ["cinematic", "nhạc phim", "soundtrack", "film", "trailer", "orchestral", "giao hưởng", "dàn nhạc"],
}
MOOD_WORDS = {
    "chill": ["chill", "thư giãn", "nhẹ nhàng", "relax", "êm", "êm dịu", "học bài", "study", "ngủ", "sleep", "cà phê", "cafe", "coffee", "bình yên", "peaceful"],
    "happy": ["vui", "vui tươi", "happy", "tươi sáng", "rộn ràng", "yêu đời", "upbeat", "hạnh phúc"],
    "sad": ["buồn", "sad", "tâm trạng", "cô đơn", "melancholy", "chia tay", "nhớ nhung", "khóc"],
    "dark": ["u ám", "dark", "huyền bí", "ma mị", "bí ẩn", "tối", "đen tối", "kinh dị", "horror", "mysterious"],
    "epic": ["hùng tráng", "hoành tráng", "epic", "anh hùng", "heroic", "chiến đấu", "battle"],
    "romantic": ["lãng mạn", "romantic", "tình yêu", "love", "hẹn hò", "ngọt ngào"],
    "energetic": ["sôi động", "energetic", "quẩy", "mạnh mẽ", "party", "tiệc", "gym", "workout", "bùng nổ", "hype"],
    "dreamy": ["mơ màng", "dreamy", "bay bổng", "huyền ảo", "lơ lửng", "không gian", "space", "vũ trụ"],
}
# Order matters: specific phrases first so "electric piano" doesn't also count as "piano".
INSTRUMENT_WORDS = [
    ("epiano", ["electric piano", "e-piano", "epiano", "rhodes", "piano điện", "keys"]),
    ("piano", ["piano", "dương cầm"]),
    ("guitar", ["guitar", "ghi ta", "ghi-ta", "ghita", "đàn ghi ta"]),
    ("strings", ["strings", "string", "violin", "cello", "vĩ cầm", "dàn dây", "đàn dây", "orchestra"]),
    ("lead", ["synth lead", "lead"]),
    ("pad", ["synth pad", "pad", "synth", "lớp nền"]),
    ("bass", ["bass", "808", "sub bass", "đàn trầm"]),
    ("bell", ["bell", "chuông", "music box", "hộp nhạc", "glockenspiel", "kalimba"]),
    ("pluck", ["pluck", "arp", "arpeggio"]),
    ("flute", ["flute", "sáo", "sáo trúc"]),
]
AMBIENCE_WORDS = {
    "rain": ["mưa", "rain", "tiếng mưa", "trời mưa", "mưa rơi"],
    "ocean": ["biển", "ocean", "sea", "waves", "sóng", "sóng biển", "bãi biển"],
    "vinyl": ["vinyl", "đĩa than", "crackle", "băng cassette", "cassette"],
}
NO_AMBIENCE = ["không tiếng nền", "no ambience", "không nền", "sạch", "clean"]
DRUM_WORDS = ["trống", "drum", "drums", "beat", "tiếng trống", "bộ gõ", "percussion"]
NO_DRUM_WORDS = ["không trống", "không có trống", "không beat", "no drums", "no drum", "without drums", "không bộ gõ", "chỉ có piano"]
MIDDLE_WORDS = ["ở giữa", "đoạn giữa", "giữa bài", "giữa", "middle", "halfway", "later", "về sau", "đoạn sau", "drop"]
NO_MELODY_WORDS = ["không giai điệu", "no melody", "chỉ hợp âm", "chords only", "không melody"]
SOLO_WORDS = ["solo", "chỉ có", "only", "độc tấu"]
SLOW_WORDS = ["chậm", "slow", "thong thả", "chậm rãi", "lững lờ"]
FAST_WORDS = ["nhanh", "fast", "dồn dập", "gấp gáp", "upbeat"]


def _pattern(word: str) -> re.Pattern:
    return re.compile(r"(?<![\w&-])" + re.escape(word) + r"(?![\w&-])")


class _Matcher:
    def __init__(self, text: str):
        self.lower = text.lower()
        self.folded = fold(text)

    def find(self, words: list[str]) -> str | None:
        for word in words:
            folded = fold(word)
            if word != folded and folded in _AMBIGUOUS:
                hit = _pattern(word.lower()).search(self.lower)
            else:
                hit = _pattern(folded).search(self.folded)
            if hit:
                return word
        return None

    def remove(self, word: str) -> None:
        self.lower = _pattern(word.lower()).sub(" ", self.lower)
        self.folded = _pattern(fold(word)).sub(" ", self.folded)


_VN_NOTES = {"đô": "C", "rê": "D", "mi": "E", "fa": "F", "son": "G", "sol": "G", "la": "A", "si": "B"}


def _find_key(text: str) -> tuple[str, str, str] | None:
    m = re.search(r"(?<![\w#])([A-Ga-g])\s?(#|b|♯|♭)?\s?(major|minor|maj|min)(?![\w])", text, re.IGNORECASE)
    if m:
        mode = "major" if m.group(3).lower().startswith("maj") else "minor"
        return m.group(1).upper() + (m.group(2) or "").replace("♯", "#").replace("♭", "b"), mode, m.group(0)
    m = re.search(r"(?<![\w#])([A-G])(#|b)?m(?![a-zA-Z0-9])", text)
    if m:
        return m.group(1) + (m.group(2) or ""), "minor", m.group(0)
    m = re.search(r"(?<!\w)(đô|rê|mi|fa|son|sol|la|si)\s+(trưởng|thứ)(?!\w)", text.lower())
    if m:
        return _VN_NOTES[m.group(1)], "major" if m.group(2) == "trưởng" else "minor", m.group(0)
    return None


def parse_prompt(prompt: str, duration_s: int | None = None, bpm: float | None = None) -> ParsedPrompt:
    text = (prompt or "").strip()
    match = _Matcher(text)
    detected: list[Detected] = []
    notes: list[str] = []

    genre = mood = None
    for name, words in GENRE_WORDS.items():
        if (hit := match.find(words)):
            genre = name
            detected.append(Detected(kind="genre", label=GENRES[name]["label"], source=hit))
            break
    for name, words in MOOD_WORDS.items():
        if (hit := match.find(words)):
            mood = name
            detected.append(Detected(kind="mood", label=MOODS[name]["label"], source=hit))
            break
    if genre is None:
        genre = MOODS[mood]["genre"] if mood else "lofi"
        detected.append(Detected(kind="genre", label=GENRES[genre]["label"], source="mặc định"))
    preset = GENRES[genre]
    if mood is None:
        mood = preset["mood"]
        detected.append(Detected(kind="mood", label=MOODS[mood]["label"], source="mặc định"))

    found_key = _find_key(text)
    if found_key:
        key, mode, source = found_key
        detected.append(Detected(kind="key", label=f"{NOTE_NAMES[pitch_class(key)]} {mode}", source=source))
    else:
        mode = MOODS[mood]["mode"]
        key = DEFAULT_KEYS[mode][sum(map(ord, genre + mood)) % len(DEFAULT_KEYS[mode])]
        detected.append(Detected(kind="key", label=f"{key} {mode}", source="mặc định"))

    tempo = float(preset["bpm"])
    tempo_source = "mặc định"
    if bpm is not None:
        tempo, tempo_source = float(bpm), "tuỳ chọn"
    elif (m := re.search(r"(?<!\d)(\d{2,3})\s*bpm", match.folded)):
        tempo, tempo_source = float(m.group(1)), m.group(0)
    elif (hit := match.find(SLOW_WORDS)):
        tempo, tempo_source = round(tempo * .85), hit
    elif (hit := match.find(FAST_WORDS)):
        tempo, tempo_source = round(tempo * 1.15), hit
    if not 60 <= tempo <= 180:
        notes.append("Tempo được giới hạn trong 60–180 BPM.")
        tempo = min(180, max(60, tempo))
    detected.append(Detected(kind="tempo", label=f"{tempo:g} BPM", source=tempo_source))

    length = duration_s
    if (m := re.search(r"(?<!\d)(\d{1,3})\s*(giay|s|sec|secs|second|seconds)(?![\w])", match.folded)):
        length = int(m.group(1))
        detected.append(Detected(kind="duration", label=f"{length} giây", source=m.group(0)))
    elif (m := re.search(r"(?<!\d)(\d{1,2})\s*(phut|min|mins|minute|minutes)(?![\w])", match.folded)):
        length = int(m.group(1)) * 60
        detected.append(Detected(kind="duration", label=f"{length} giây", source=m.group(0)))
    length = 30 if length is None else length
    if not 15 <= length <= 120:
        notes.append("Thời lượng được giới hạn trong 15–120 giây.")
        length = min(120, max(15, length))

    instruments: list[str] = []
    for name, words in INSTRUMENT_WORDS:
        if (hit := match.find(words)):
            instruments.append(name)
            match.remove(hit)
            detected.append(Detected(kind="instrument", label=INSTRUMENTS[name], source=hit))
    if instruments == ["bass"]:
        instruments = list(dict.fromkeys(preset["instruments"] + ["bass"]))
    elif instruments:
        # Keep the genre's foundation (bass) unless the user asked for a solo instrument.
        if "bass" not in instruments and "bass" in preset["instruments"] and not match.find(SOLO_WORDS):
            instruments.append("bass")
    else:
        instruments = list(preset["instruments"])
        for name in instruments:
            detected.append(Detected(kind="instrument", label=INSTRUMENTS[name], source="mặc định"))

    ambience = preset["ambience"]
    ambience_source = "mặc định"
    for name, words in AMBIENCE_WORDS.items():
        if (hit := match.find(words)):
            ambience, ambience_source = name, hit
            break
    if match.find(NO_AMBIENCE):
        ambience, ambience_source = "none", "không nền"
    if ambience != "none":
        detected.append(Detected(kind="ambience", label=AMBIENCES[ambience], source=ambience_source))

    drums = preset["drums"] is not None
    drums_entry = "start"
    if (hit := match.find(NO_DRUM_WORDS)):
        drums = False
        detected.append(Detected(kind="structure", label="Không trống", source=hit))
    else:
        drum_hit = match.find(DRUM_WORDS)
        if drum_hit and not drums:
            drums = True
            detected.append(Detected(kind="structure", label="Có trống", source=drum_hit))
        if drum_hit and (hit := match.find(MIDDLE_WORDS)):
            drums_entry = "middle"
            detected.append(Detected(kind="structure", label="Trống vào giữa bài", source=f"{drum_hit} … {hit}"))
    melody = True
    if (hit := match.find(NO_MELODY_WORDS)):
        melody = False
        detected.append(Detected(kind="structure", label="Không giai điệu", source=hit))

    recipe = Recipe(genre=genre, mood=mood, bpm=tempo, key=key, mode=mode, duration_s=length, instruments=instruments,
                    drums=drums, drums_entry=drums_entry, melody=melody, ambience=ambience)
    return ParsedPrompt(recipe=recipe, detected=detected, notes=notes)


def options() -> dict:
    return {
        "genres": [{"id": k, "label": v["label"], "bpm": v["bpm"]} for k, v in GENRES.items()],
        "moods": [{"id": k, "label": v["label"]} for k, v in MOODS.items()],
        "instruments": [{"id": k, "label": v} for k, v in INSTRUMENTS.items()],
        "ambiences": [{"id": k, "label": v} for k, v in AMBIENCES.items()],
        "keys": NOTE_NAMES,
        "modes": [{"id": "major", "label": "Major (trưởng)"}, {"id": "minor", "label": "Minor (thứ)"}],
        "duration_s": {"min": 15, "max": 120},
        "bpm": {"min": 60, "max": 180},
    }
