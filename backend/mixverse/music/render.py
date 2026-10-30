"""Render a symbolic Composition into stereo stems and a mastered mix."""
from __future__ import annotations

import numpy as np

from ..audio_io import SR
from ..sound.ambience import render_ambience
from . import synth
from .compose import STEM_OF_PART, STEM_ORDER, STEP, Composition, Hit

STEM_LABELS = {"drums": "Trống", "bass": "Bass", "harmony": "Hoà âm", "melody": "Giai điệu", "ambience": "Âm nền"}
# part -> (gain dB, pan, reverb send)
PART_MIX = {
    "chords": (-10, -.12, .22),
    "pad": (-16, 0, .35),
    "melody": (-10, .14, .26),
    "arp": (-17, .3, .2),
    "bass": (-8, 0, 0),
}
INSTRUMENT_TRIM = {"bell": -3, "lead": -4, "pluck": -2, "strings": -1, "pad": 0, "guitar": -1, "flute": -2, "bass808": -1}
STEM_SEND = {"harmony": 1, "melody": 1, "drums": .25}
LOUDNESS_TARGET = -14.0


def _db(value: float) -> float:
    return 10 ** (value / 20)


def _seconds(beat: float, beat_s: float, swing: float) -> float:
    step = beat / STEP
    if swing and abs(step - round(step)) < 1e-3 and round(step) % 2 == 1:
        beat += swing * STEP
    return beat * beat_s


def _place(buffer: np.ndarray, wave: np.ndarray, start: int, gain: float) -> None:
    if start >= buffer.shape[-1] or start < 0:
        return
    end = min(buffer.shape[-1], start + wave.shape[-1])
    buffer[..., start:end] += wave[..., :end - start] * gain


def render_drums(hits: list[Hit], beat_s: float, n: int, swing: float = 0) -> np.ndarray:
    kit = synth.drum_kit()
    out = np.zeros((2, n), np.float32)
    panned = {piece: synth.pan(sample, synth.DRUM_PAN[piece]) for piece, sample in kit.items()}
    for hit in hits:
        start = round(_seconds(hit.start, beat_s, swing) * SR)
        _place(out, panned[hit.piece], start, synth.DRUM_LEVEL[hit.piece] * hit.vel)
    return out


def _loudness_gain(audio: np.ndarray) -> float:
    try:
        import pyloudnorm
        loudness = pyloudnorm.Meter(SR).integrated_loudness(audio.T.astype(np.float64))
    except Exception:
        loudness = float("nan")
    if not np.isfinite(loudness):
        rms = float(np.sqrt(np.mean(audio.astype(np.float64) ** 2))) or 1e-9
        loudness = 20 * np.log10(rms) - 3
    return _db(LOUDNESS_TARGET - loudness)


def render(comp: Composition) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    beat_s = comp.beat_s
    tail_s = max(3.0, 4 * beat_s)
    n = round((comp.duration_s + tail_s) * SR)
    part_buffers: dict[str, np.ndarray] = {part: np.zeros(n, np.float32) for part in comp.parts}
    for note in comp.notes:
        wave = synth.note(note.instrument, note.midi, note.dur * beat_s)
        start = round(_seconds(note.start, beat_s, comp.swing) * SR)
        _place(part_buffers[note.part], wave, start, note.vel)

    stems: dict[str, np.ndarray] = {}
    for part, mono in part_buffers.items():
        gain, position, _ = PART_MIX[part]
        gain += INSTRUMENT_TRIM.get(comp.parts[part], 0)
        stereo = synth.widen(mono, 14) if part == "pad" else synth.pan(mono, position)
        if part == "bass":
            stereo = synth.lowpass(stereo, 1600 if comp.parts[part] == "bass808" else 1100)
        stem = STEM_OF_PART[part]
        stems.setdefault(stem, np.zeros((2, n), np.float32))
        stems[stem] += stereo * _db(gain)

    if comp.hits:
        drums = render_drums(comp.hits, beat_s, n, comp.swing) * _db(-5)
        if comp.recipe.genre == "lofi":
            drums = synth.lowpass(drums, 9000)
        stems["drums"] = drums

    # Shared reverb per stem, sized to the genre.
    room = {"ambient": 4.5, "cinematic": 3.5, "ballad": 2.8, "lofi": 1.6, "trap": 1.8}.get(comp.recipe.genre, 2.2)
    for stem, send in STEM_SEND.items():
        if stem in stems:
            wet = {"harmony": .3, "melody": .32, "drums": .08}[stem] * send
            if comp.recipe.genre in {"ambient", "cinematic"}:
                wet *= 1.6
            stems[stem] = stems[stem] + synth.reverb_tail(stems[stem], room if stem != "drums" else .9) * wet
    if "melody" in stems and comp.recipe.genre in {"edm", "pop", "trap", "ambient"}:
        stems["melody"] = synth.echo(stems["melody"], beat_s * .75, .35, .18)

    if comp.recipe.ambience != "none":
        seconds = n / SR
        if comp.recipe.ambience == "vinyl":
            bed = synth.vinyl(seconds, seed=comp.seed) * _db(-26)
        else:
            bed = render_ambience(comp.recipe.ambience, seconds, seed=comp.seed) * _db(-9)
        stems["ambience"] = bed[:, :n]

    if comp.recipe.genre == "lofi":
        for stem in ("harmony", "melody"):
            if stem in stems:
                stems[stem] = synth.lowpass(stems[stem], 6500)

    # Fade the very end so tails never cut off abruptly.
    fade = round(1.5 * SR)
    curve = np.linspace(1, 0, fade, dtype=np.float32)
    for stem in stems.values():
        stem[:, -fade:] *= curve

    mix = sum(stems.values())
    mix = synth.highpass(mix, 28)
    gain = _loudness_gain(mix)
    stems = {name: stems[name] * gain for name in STEM_ORDER if name in stems}
    master = synth.soft_limit(mix * gain)
    master *= min(1.0, .89 / max(float(np.max(np.abs(master))), 1e-9))
    for name, stem in stems.items():
        peak = float(np.max(np.abs(stem)))
        if peak > .98:
            stems[name] = stem * (.98 / peak)
    return master.astype(np.float32), {k: v.astype(np.float32) for k, v in stems.items()}
