"""Turn a Recipe into a symbolic arrangement: sections, chords, notes and drum hits.

Times are in beats (quarter notes); one bar is four beats and one step is a 16th note.
The same (recipe, seed) always yields the same composition, so audio, stems and MIDI
can be regenerated on demand instead of stored.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .recipe import GENRES, Recipe
from .theory import chord_name, diatonic_chord, nearest, pitch_class, progression_for, scale_pcs, voice_chord

STEP = .25
SECTION_ENERGY = {"intro": .3, "verse": .6, "chorus": 1.0, "bridge": .5, "outro": .3}
SECTION_LABELS = {"intro": "Intro", "verse": "Verse", "chorus": "Chorus", "bridge": "Bridge", "outro": "Outro"}
CHORD_INSTRUMENTS = ["epiano", "piano", "guitar", "strings", "pad", "pluck", "bell"]
MELODY_INSTRUMENTS = ["flute", "lead", "bell", "pluck", "guitar", "piano", "epiano", "strings"]
STEM_OF_PART = {"chords": "harmony", "pad": "harmony", "melody": "melody", "arp": "melody", "bass": "bass"}
STEM_ORDER = ["drums", "bass", "harmony", "melody", "ambience"]

# Drum grooves as 16-step strings: X = accent, x = normal, o = ghost.
GROOVES = {
    "lofi": {"kick": "X.....x...X.x...", "snare": "....X.......X...", "chat": "x.o.x.o.x.o.x.oo"},
    "trap": {"kick": "X......x..X.....", "clap": "........X.......", "chat": "x.x.x.x.x.x.x.x."},
    "house": {"kick": "X...X...X...X...", "clap": "....X.......X...", "chat": "o.o.o.o.o.o.o.o.", "ohat": "..x...x...x...x."},
    "edm": {"kick": "X...X...X...X...", "clap": "....X.......X...", "chat": "xoxoxoxoxoxoxoxo", "ohat": "..x...x...x...x."},
    "pop": {"kick": "X.......X.x.....", "snare": "....X.......X...", "chat": "x.x.x.x.x.x.x.x."},
    "ballad": {"kick": "X.......x.......", "rim": "....x.......x...", "chat": "x...x...x...x..."},
    "rnb": {"kick": "X..x......X.....", "snare": "....X.......X..o", "chat": "x.xox.x.x.xox.x."},
}
VELOCITY = {"X": 1.0, "x": .78, "o": .45}

# Rhythm templates for one bar: (step, length in steps).
MELODY_RHYTHMS = {
    "sparse": [[(0, 8), (8, 8)], [(0, 12)], [(4, 4), (8, 8)], [(0, 6), (8, 8)]],
    "medium": [[(0, 4), (4, 2), (6, 2), (8, 6)], [(0, 6), (6, 2), (8, 4), (12, 4)], [(2, 2), (4, 2), (6, 4), (10, 6)], [(0, 3), (3, 3), (6, 2), (8, 8)]],
    "dense": [[(0, 2), (2, 2), (4, 4), (10, 2), (12, 4)], [(0, 4), (4, 2), (6, 2), (8, 2), (10, 2), (12, 4)], [(0, 3), (3, 3), (6, 2), (8, 3), (11, 3), (14, 2)]],
    "ending": [[(0, 4), (4, 4), (8, 8)], [(0, 6), (6, 2), (8, 8)]],
}
BASS_RHYTHMS = {
    "lofi": [(0, 6), (6, 2), (10, 4)], "trap": [(0, 7), (7, 3), (10, 6)], "house": [(2, 2), (6, 2), (10, 2), (14, 2)],
    "edm": [(0, 2), (2, 2), (4, 2), (6, 2), (8, 2), (10, 2), (12, 2), (14, 2)], "pop": [(0, 4), (4, 2), (8, 4), (12, 2), (14, 2)],
    "ballad": [(0, 8), (8, 8)], "rnb": [(0, 3), (3, 3), (10, 2), (12, 4)], "ambient": [(0, 16)], "cinematic": [(0, 16)],
}


@dataclass(slots=True)
class Note:
    part: str
    instrument: str
    midi: int
    start: float
    dur: float
    vel: float


@dataclass(slots=True)
class Hit:
    piece: str
    start: float
    vel: float


@dataclass(slots=True)
class Section:
    label: str
    start_bar: int
    bars: int
    energy: float
    chords: list[str] = field(default_factory=list)


@dataclass
class Composition:
    recipe: Recipe
    seed: int
    bars: int
    swing: float
    sections: list[Section]
    notes: list[Note]
    hits: list[Hit]
    parts: dict[str, str]  # part -> instrument

    @property
    def bpm(self) -> float:
        return self.recipe.bpm

    @property
    def beat_s(self) -> float:
        return 60 / self.recipe.bpm

    @property
    def duration_s(self) -> float:
        return self.bars * 4 * self.beat_s

    def summary(self) -> dict:
        progression = next((s.chords for s in self.sections if s.label in {"verse", "chorus"}), self.sections[0].chords)
        return {
            "seed": self.seed,
            "bpm": self.bpm,
            "key": self.recipe.key_name,
            "bars": self.bars,
            "duration_s": round(self.duration_s, 2),
            "progression": progression,
            "sections": [{"label": s.label, "name": SECTION_LABELS[s.label], "start_bar": s.start_bar, "bars": s.bars, "energy": s.energy, "chords": s.chords} for s in self.sections],
            "parts": [{"part": p, "instrument": i, "stem": STEM_OF_PART.get(p, p)} for p, i in self.parts.items()],
            "stems": self.stems,
            "drums": self.recipe.drums,
            "ambience": self.recipe.ambience,
        }

    @property
    def stems(self) -> list[str]:
        present = {STEM_OF_PART[p] for p in self.parts}
        if self.hits:
            present.add("drums")
        if self.recipe.ambience != "none":
            present.add("ambience")
        return [s for s in STEM_ORDER if s in present]


def plan_sections(bars: int) -> list[Section]:
    if bars < 8:
        intro = outro = 1
    elif bars < 16:
        intro = outro = 2
    else:
        intro = outro = 4
    middle = bars - intro - outro
    chunks = [4] * (middle // 4)
    if not chunks:
        chunks = [middle]
    else:
        chunks[0] += middle % 4
    n = len(chunks)
    if n == 1:
        labels = ["chorus"]
    elif n == 2:
        labels = ["verse", "chorus"]
    elif n == 3:
        labels = ["verse", "chorus", "chorus"]
    elif n < 6:
        labels = (["verse", "chorus"] * 3)[:n - 1] + ["chorus"]
    else:
        labels = (["verse", "chorus"] * n)[:n - 3] + ["bridge", "chorus", "chorus"]
    plan = [("intro", intro)] + list(zip(labels, chunks)) + [("outro", outro)]
    merged: list[list] = []
    for label, length in plan:
        if merged and merged[-1][0] == label:
            merged[-1][1] += length
        else:
            merged.append([label, length])
    sections, start = [], 0
    for label, length in merged:
        sections.append(Section(label=label, start_bar=start, bars=length, energy=SECTION_ENERGY[label]))
        start += length
    return sections


def assign_parts(recipe: Recipe) -> dict[str, str]:
    instruments = list(recipe.instruments)
    melodic = [i for i in instruments if i != "bass"]
    parts: dict[str, str] = {}
    chords = next((i for i in CHORD_INSTRUMENTS if i in melodic), None)
    if chords:
        parts["chords"] = chords
    remaining = [i for i in melodic if i != chords]
    for layer in ("pad", "strings"):
        if layer in remaining and layer != parts.get("chords"):
            parts["pad"] = layer
            remaining.remove(layer)
            break
    if recipe.melody:
        lead = next((i for i in MELODY_INSTRUMENTS if i in remaining), None) or chords
        if lead:
            parts["melody"] = lead
            if lead in remaining:
                remaining.remove(lead)
    if "pluck" in remaining and recipe.genre in {"edm", "trap", "house", "pop"}:
        parts["arp"] = "pluck"
    if "bass" in instruments:
        parts["bass"] = "bass808" if recipe.genre == "trap" else "bass"
    return parts


class _Composer:
    def __init__(self, recipe: Recipe, seed: int):
        self.r = recipe
        self.seed = seed
        self.rng = np.random.default_rng(seed)
        self.preset = GENRES[recipe.genre]
        self.root = pitch_class(recipe.key)
        self.scale = scale_pcs(self.root, recipe.mode)
        self.sevenths = self.preset["sevenths"]
        self.notes: list[Note] = []
        self.hits: list[Hit] = []
        self.parts = assign_parts(recipe)
        base = seed % 3  # consecutive seeds (takes) always get different progressions
        self.progressions = {
            "intro": progression_for(recipe.mode, recipe.mood, base),
            "verse": progression_for(recipe.mode, recipe.mood, base),
            "chorus": progression_for(recipe.mode, recipe.mood, base + 1),
            "bridge": progression_for(recipe.mode, recipe.mood, base + 2),
            "outro": progression_for(recipe.mode, recipe.mood, base),
        }
        self.phrases: dict[str, list[tuple[int, int, int, float]]] = {}

    # ------------------------------------------------------------ helpers
    def chord_pcs(self, degree: int) -> list[int]:
        return diatonic_chord(self.root, self.r.mode, degree, self.sevenths)

    def add(self, part: str, midi: int, start: float, dur: float, vel: float) -> None:
        jitter = float(self.rng.normal(0, .006)) if part != "pad" else 0.0
        self.notes.append(Note(part, self.parts[part], int(midi), max(0.0, start + jitter), dur, float(np.clip(vel * self.rng.uniform(.92, 1.05), .05, 1))))

    def snap(self, midi: int) -> int:
        return min(self.scale_notes(midi - 2, midi + 2), key=lambda m: (abs(m - midi), m))

    def scale_notes(self, low: int, high: int) -> list[int]:
        return [m for m in range(low, high + 1) if m % 12 in self.scale]

    # ------------------------------------------------------------ parts
    def chords(self, section: Section, bar: int, pcs: list[int], previous: list[int] | None) -> list[int]:
        instrument = self.parts["chords"]
        center = {"pad": 60, "strings": 62, "guitar": 57, "bell": 72, "pluck": 67}.get(instrument, 62)
        voicing = voice_chord(pcs, center, previous)
        start = bar * 4
        e = section.energy
        if instrument in {"pad", "strings"} or section.label in {"intro", "outro"}:
            hits = [(0, 16)]
        elif self.r.genre == "house":
            hits = [(2, 2), (6, 2), (10, 2), (14, 2)] if e >= .6 else [(0, 16)]
        elif instrument == "guitar":
            hits = [(0, 4), (6, 2), (8, 4), (14, 2)] if e >= .6 else [(0, 8), (8, 8)]
        elif self.r.genre in {"lofi", "rnb"}:
            hits = [(0, 10), (10, 6)] if e < 1 else [(0, 6), (6, 4), (10, 6)]
        elif self.r.genre in {"ballad", "cinematic"} and instrument == "piano":
            # Broken-chord arpeggio in eighth notes.
            seq = [voicing[0] - 12] + voicing + voicing[-2:0:-1]
            for i in range(8):
                self.add("chords", seq[i % len(seq)], start + i * .5, .9, .55 + .2 * e)
            return voicing
        else:
            hits = [(0, 4), (4, 4), (8, 4), (12, 4)] if e >= 1 else [(0, 8), (8, 8)]
        strum = .03 if instrument == "guitar" else .012 if instrument in {"epiano", "piano"} else 0
        for step, length in hits:
            for i, midi in enumerate(voicing):
                self.add("chords", midi, start + step * STEP + i * strum, length * STEP * .95, (.45 + .35 * e) * (1 if step % 8 == 0 else .85))
        return voicing

    def pad_layer(self, bar: int, pcs: list[int], previous: list[int] | None) -> list[int]:
        voicing = voice_chord(pcs[:3], 55, previous)
        for midi in voicing:
            self.add("pad", midi, bar * 4, 4, .5)
        return voicing

    def bass(self, section: Section, bar: int, pcs: list[int]) -> None:
        low, high = (33, 45) if self.parts["bass"] == "bass808" else (36, 50)
        root = nearest(pcs[0], (low + high) / 2, low, high)
        fifth = nearest(pcs[2], root + 7, low, high + 7)
        pattern = BASS_RHYTHMS.get(self.r.genre, BASS_RHYTHMS["pop"])
        if section.energy < .5:
            pattern = [(0, 16)]
        for i, (step, length) in enumerate(pattern):
            midi = root
            if self.r.genre == "edm" and i % 2 == 1:
                midi = root + 12
            elif self.r.genre in {"lofi", "pop", "rnb"} and step >= 10 and self.rng.random() < .35:
                midi = fifth
            self.add("bass", midi, bar * 4 + step * STEP, length * STEP * .92, .85 if step % 8 == 0 else .7)

    def phrase(self, label: str) -> list[tuple[int, int, int, float]]:
        """A four-bar melody (step, length, midi, velocity) over the section's progression."""
        if label in self.phrases:
            return self.phrases[label]
        lead = self.parts["melody"]
        center = {"bell": 76, "flute": 74, "lead": 72, "pluck": 72}.get(lead, 70)
        if label == "chorus":
            center += 3
        pool = self.scale_notes(center - 10, center + 12)
        density = "sparse" if self.r.genre in {"ambient", "cinematic"} or label == "bridge" else "dense" if label == "chorus" and self.r.genre in {"pop", "edm", "house"} else "medium"
        prog = self.progressions[label]
        current = nearest(self.chord_pcs(prog[0])[0], center)
        phrase = []
        for bar, degree in enumerate(prog):
            pcs = self.chord_pcs(degree)
            options = MELODY_RHYTHMS["ending" if bar == len(prog) - 1 else density]
            rhythm = options[int(self.rng.integers(0, len(options)))]
            for i, (step, length) in enumerate(rhythm):
                last = bar == len(prog) - 1 and i == len(rhythm) - 1
                if last:
                    current = nearest(pcs[0], current, pool[0], pool[-1])
                elif step % 8 == 0:
                    tones = sorted((m for m in pool if m % 12 in pcs), key=lambda m: abs(m - current))
                    current = tones[int(self.rng.integers(0, min(2, len(tones))))]
                else:
                    move = int(self.rng.choice([-2, -1, -1, 1, 1, 2, 0]))
                    idx = min(range(len(pool)), key=lambda j: abs(pool[j] - current))
                    idx = idx + move
                    if idx < 0 or idx >= len(pool):
                        idx = idx - 2 * move
                    current = pool[max(0, min(len(pool) - 1, idx))]
                phrase.append((bar * 16 + step, length, current, .9 if step % 8 == 0 else .75))
        self.phrases[label] = phrase
        return phrase

    def melody(self, section: Section) -> None:
        if section.label in {"intro", "outro"}:
            return
        phrase = self.phrase(section.label)
        for cycle_start in range(0, section.bars, 4):
            for step, length, midi, vel in phrase:
                bar_in_cycle = step // 16
                if cycle_start + bar_in_cycle >= section.bars:
                    continue
                if cycle_start and bar_in_cycle == 3 and self.rng.random() < .5:
                    midi = self.snap(midi + int(self.rng.choice([-2, 2, 0])))  # light variation on repeats
                start = (section.start_bar + cycle_start) * 4 + step * STEP
                self.add("melody", midi, start, length * STEP * .9, vel * (.8 + .2 * section.energy))

    def arp(self, section: Section, bar: int, pcs: list[int]) -> None:
        if section.energy < 1:
            return
        tones = voice_chord(pcs[:3], 67)
        seq = tones + [tones[0] + 12]
        for step in range(16):
            self.add("arp", seq[step % len(seq)], bar * 4 + step * STEP, STEP * .8, .55 if step % 4 else .7)

    def drums(self, section: Section, drums_from_bar: int) -> None:
        style = self.preset["drums"] or "pop"
        groove = GROOVES[style]
        e = section.energy
        four_floor = style in {"house", "edm"}
        for bar in range(section.start_bar, section.start_bar + section.bars):
            if bar < drums_from_bar:
                continue
            last_bar = bar == section.start_bar + section.bars - 1
            if e < .35 and not four_floor:
                continue
            for piece, pattern in groove.items():
                if e < .35 and piece not in {"kick", "chat"}:
                    continue
                if piece == "ohat" and e < 1:
                    continue
                for step, ch in enumerate(pattern):
                    if ch == ".":
                        continue
                    if last_bar and step >= 12 and piece in {"snare", "clap"} and self.next_is_chorus(section):
                        continue  # make room for the fill
                    if style == "trap" and piece == "chat" and e >= 1 and self.rng.random() < .18:
                        rolls = int(self.rng.choice([3, 4]))
                        for r in range(rolls):
                            self.hits.append(Hit("chat", bar * 4 + (step + r / rolls) * STEP, .55))
                        continue
                    self.hits.append(Hit(piece, bar * 4 + step * STEP, VELOCITY[ch] * (.75 + .25 * e)))
            if last_bar and self.next_is_chorus(section):
                fill = "snare" if "snare" in groove else "clap"
                for step in range(12, 16):
                    self.hits.append(Hit(fill, bar * 4 + step * STEP, .5 + .12 * (step - 12)))
        if section.label == "chorus" and section.start_bar >= drums_from_bar:
            self.hits.append(Hit("crash", section.start_bar * 4, .8))

    def next_is_chorus(self, section: Section) -> bool:
        index = self.sections.index(section)
        return index + 1 < len(self.sections) and self.sections[index + 1].label == "chorus"

    # ------------------------------------------------------------ main
    def run(self) -> Composition:
        bars = max(4, round(self.r.duration_s * self.r.bpm / 240))
        self.sections = plan_sections(bars)
        drums_from = 0
        if self.r.drums_entry == "middle":
            drums_from = next((s.start_bar for s in self.sections if s.start_bar >= bars // 2 - 1 and s.label != "outro"), bars // 2)
        for section in self.sections:
            prog = self.progressions[section.label]
            prev_chords = prev_pad = None
            for i in range(section.bars):
                bar = section.start_bar + i
                pcs = self.chord_pcs(prog[i % len(prog)])
                if i < len(prog):
                    section.chords.append(chord_name(pcs))
                if "chords" in self.parts:
                    prev_chords = self.chords(section, bar, pcs, prev_chords)
                if "pad" in self.parts and section.energy >= .3:
                    prev_pad = self.pad_layer(bar, pcs, prev_pad)
                if "bass" in self.parts and section.label != "intro":
                    self.bass(section, bar, pcs)
                if "arp" in self.parts:
                    self.arp(section, bar, pcs)
            if "melody" in self.parts:
                self.melody(section)
            if self.r.drums:
                self.drums(section, drums_from)
        # Final sustained tonic so the piece resolves instead of stopping mid-phrase.
        end = bars * 4
        tonic = self.chord_pcs(1)
        if "chords" in self.parts:
            for midi in voice_chord(tonic, 60):
                self.add("chords", midi, end, 3, .5)
        if "bass" in self.parts:
            self.add("bass", nearest(tonic[0], 40, 33, 50), end, 2, .6)
        self.notes.sort(key=lambda n: n.start)
        self.hits.sort(key=lambda h: h.start)
        return Composition(self.r, self.seed, bars, self.preset["swing"], self.sections, self.notes, self.hits, self.parts)


def compose(recipe: Recipe, seed: int = 0) -> Composition:
    return _Composer(recipe, seed).run()


def drum_hits(style: str, bars: float, seed: int = 0) -> list[Hit]:
    """Full-energy groove for ``bars`` bars, used by the studio/rap beat generator."""
    groove = GROOVES.get(style, GROOVES["pop"])
    rng = np.random.default_rng(seed)
    hits: list[Hit] = []
    total = int(np.ceil(bars))
    for bar in range(total):
        fill_bar = bar % 4 == 3
        for piece, pattern in groove.items():
            for step, ch in enumerate(pattern):
                if ch == "." or (fill_bar and step >= 12 and piece in {"snare", "clap"}):
                    continue
                if ch == "o" and rng.random() < .3:
                    continue
                if style == "trap" and piece == "chat" and rng.random() < .15:
                    for r in range(3):
                        hits.append(Hit("chat", bar * 4 + (step + r / 3) * STEP, .5))
                    continue
                hits.append(Hit(piece, bar * 4 + step * STEP, VELOCITY[ch] * rng.uniform(.9, 1)))
        if fill_bar:
            fill = "snare" if "snare" in groove else "clap"
            for step in range(12, 16):
                if rng.random() < .8:
                    hits.append(Hit(fill, bar * 4 + step * STEP, .5 + .1 * (step - 12)))
    return [h for h in hits if h.start < bars * 4]
