from typing import Literal
import numpy as np
from ..audio_io import SR

SectionLabel = Literal["intro", "verse", "chorus", "bridge", "outro"]
Stem = Literal["mix", "vocals", "drums", "bass", "other"]
_NOTES = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5, "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11}


def note_hz(name: str) -> float:
    names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    import re
    m = re.fullmatch(r"([A-G]#?)(-?\d+)", name)
    if not m:
        raise ValueError(name)
    midi = (int(m.group(2)) + 1) * 12 + _NOTES[m.group(1)]
    return 440 * 2 ** ((midi - 69) / 12)


def tone(freqs: list[float], seconds: float, amp: float = 0.2) -> np.ndarray:
    t = np.arange(round(seconds * SR)) / SR
    mono = sum(np.sin(2 * np.pi * f * t) for f in freqs) * (amp / max(1, len(freqs)))
    return np.repeat(mono.astype(np.float32)[None, :], 2, axis=0)


def chord(notes: list[str], seconds: float, amp: float = 0.2) -> np.ndarray:
    return tone([note_hz(n) for n in notes], seconds, amp)


def click_track(bpm: float, seconds: float, amp: float = 0.5) -> np.ndarray:
    n = round(seconds * SR)
    out = np.zeros(n, np.float32)
    step = round(60 / bpm * SR)
    for i in range(0, n, step):
        length = min(round(0.015 * SR), n - i)
        out[i:i + length] += amp * np.exp(-np.arange(length) / (SR * .004)).astype(np.float32)
    return np.repeat(out[None, :], 2, axis=0)


def groove(bpm: float, bars: int, pattern: Literal["boombap", "house"], lead_beats: int = 0, accent: bool = False, harmony: bool = True) -> tuple[np.ndarray, float]:
    seconds = bars * 240 / bpm
    out = np.zeros((2, round(seconds * SR)), np.float32)
    t0 = lead_beats * 60 / bpm
    beat_s = 60 / bpm
    for beat in range(bars * 4):
        t = t0 + beat * beat_s
        if t >= seconds:
            break
        if beat % 4 in ((0, 2) if pattern == "boombap" else (0, 1, 2, 3)):
            i = round(t * SR); size = min(round(.09 * SR), out.shape[1] - i)
            tt = np.arange(size) / SR
            out[:, i:i + size] += (.4 * np.sin(2*np.pi*(70-35*tt/.09)*tt) * np.exp(-tt*35)).astype(np.float32)
        if beat % 4 in (1, 3):
            i = round(t * SR); size = min(round(.04 * SR), out.shape[1] - i)
            rng = np.random.default_rng(beat)
            out[:, i:i + size] += (rng.standard_normal(size) * np.exp(-np.arange(size)/(SR*.008)) * .06).astype(np.float32)
        if accent and beat % 4 == 0:
            out[:, round(t*SR):round(t*SR)+min(round(.2*SR), out.shape[1]-round(t*SR))] += .04
    return out, t0


def song(bpm: float, layout: list[tuple[SectionLabel, int, float]], key: Literal["A minor", "C major"] = "A minor") -> np.ndarray:
    # Lightweight deterministic harmonic fixture; intended for tests, not production music.
    sec_per_bar = 240 / bpm
    chords = [[220, 261.63, 329.63], [174.61, 220, 261.63], [130.81, 164.81, 196], [196, 246.94, 293.66]]
    parts = []
    for _, bars, gain_db in layout:
        part = np.zeros((2, round(bars * sec_per_bar * SR)), np.float32)
        for i in range(bars):
            start = round(i * sec_per_bar * SR)
            end = min(part.shape[1], start + round(sec_per_bar * SR))
            part[:, start:end] = tone(chords[i % 4], (end-start)/SR, .1)[:, :end-start]
        part *= 10 ** (gain_db / 20)
        parts.append(part)
    return np.concatenate(parts, axis=1) if parts else np.zeros((2, 0), np.float32)


def stems_of(song_kwargs: dict) -> dict[Stem, np.ndarray]:
    mix = song(**song_kwargs)
    return {"mix": mix, "vocals": np.zeros_like(mix), "drums": np.zeros_like(mix), "bass": np.zeros_like(mix), "other": mix}
