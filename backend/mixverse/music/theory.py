"""Small music-theory toolkit: keys, diatonic chords, progressions and voicing."""
from __future__ import annotations

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
_FLATS = {"DB": "C#", "EB": "D#", "GB": "F#", "AB": "G#", "BB": "A#", "CB": "B", "FB": "E"}
SCALES = {
    "major": [0, 2, 4, 5, 7, 9, 11],
    "minor": [0, 2, 3, 5, 7, 8, 10],
}

# Scale degrees (1-based) per mode and mood. Several options per mood give takes variety.
PROGRESSIONS: dict[str, dict[str, list[list[int]]]] = {
    "major": {
        "happy": [[1, 5, 6, 4], [1, 4, 5, 4], [4, 1, 5, 6]],
        "romantic": [[1, 6, 4, 5], [6, 4, 1, 5], [1, 3, 4, 5]],
        "dreamy": [[1, 3, 6, 4], [4, 5, 3, 6], [1, 5, 4, 4]],
        "chill": [[2, 5, 1, 6], [4, 3, 2, 1], [1, 6, 2, 5]],
        "energetic": [[1, 5, 6, 4], [6, 4, 1, 5], [4, 5, 6, 6]],
        "sad": [[6, 4, 1, 5], [1, 3, 6, 4], [4, 5, 3, 6]],
        "epic": [[6, 4, 1, 5], [1, 5, 6, 4], [4, 5, 6, 6]],
        "dark": [[6, 3, 4, 1], [6, 5, 4, 5], [6, 4, 1, 5]],
    },
    "minor": {
        "sad": [[1, 6, 3, 7], [1, 4, 6, 5], [6, 4, 1, 5]],
        "dark": [[1, 6, 4, 5], [1, 7, 6, 7], [1, 4, 1, 5]],
        "epic": [[1, 6, 3, 7], [6, 7, 1, 1], [1, 7, 6, 7]],
        "energetic": [[1, 6, 3, 7], [6, 4, 1, 7], [1, 7, 6, 7]],
        "chill": [[1, 4, 7, 3], [2, 5, 1, 1], [1, 6, 4, 7]],
        "dreamy": [[1, 3, 6, 7], [6, 3, 7, 1], [1, 4, 7, 3]],
        "romantic": [[1, 6, 3, 7], [6, 7, 1, 4], [1, 4, 7, 3]],
        "happy": [[6, 7, 1, 1], [3, 7, 1, 6], [1, 6, 3, 7]],
    },
}


def midi_hz(midi: float) -> float:
    return 440.0 * 2 ** ((midi - 69) / 12)


def pitch_class(name: str) -> int:
    key = name.strip().upper().replace("♯", "#").replace("♭", "B")
    key = _FLATS.get(key, key)
    if key not in NOTE_NAMES:
        raise ValueError(f"Nốt không hợp lệ: {name}")
    return NOTE_NAMES.index(key)


def scale_pcs(root_pc: int, mode: str) -> list[int]:
    return [(root_pc + i) % 12 for i in SCALES[mode]]


def diatonic_chord(root_pc: int, mode: str, degree: int, sevenths: bool = False) -> list[int]:
    """Pitch classes of the chord built by stacking scale thirds on ``degree`` (1-7)."""
    scale = scale_pcs(root_pc, mode)
    size = 4 if sevenths else 3
    return [scale[(degree - 1 + 2 * i) % 7] for i in range(size)]


def chord_name(pcs: list[int]) -> str:
    root = pcs[0]
    third = (pcs[1] - root) % 12
    fifth = (pcs[2] - root) % 12
    seventh = (pcs[3] - root) % 12 if len(pcs) > 3 else None
    name = NOTE_NAMES[root]
    if fifth == 6 and third == 3:
        return name + ("m7b5" if seventh == 10 else "dim")
    minor = third == 3
    if seventh is None:
        return name + ("m" if minor else "")
    if minor:
        return name + "m7"
    return name + ("maj7" if seventh == 11 else "7")


def nearest(pc: int, target: float, low: int = 0, high: int = 127) -> int:
    """MIDI note with pitch class ``pc`` closest to ``target`` inside [low, high]."""
    options = [m for m in range(low, high + 1) if m % 12 == pc]
    return min(options, key=lambda m: (abs(m - target), m))


def voice_chord(pcs: list[int], center: float, previous: list[int] | None = None) -> list[int]:
    """Close voicing near ``center``; when a previous voicing exists, minimise movement."""
    anchor = sum(previous) / len(previous) if previous else center
    anchor = (anchor + center) / 2
    notes = sorted(nearest(pc, anchor) for pc in pcs)
    # Keep the cluster within roughly an octave and a half so it stays a playable chord.
    while notes[-1] - notes[0] > 16:
        notes[-1] -= 12
        notes.sort()
    return notes


def progression_for(mode: str, mood: str, index: int) -> list[int]:
    options = PROGRESSIONS[mode].get(mood) or PROGRESSIONS[mode]["sad" if mode == "minor" else "happy"]
    return options[index % len(options)]
