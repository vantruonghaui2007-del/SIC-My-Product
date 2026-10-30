"""Procedural instrument voices, drum kit and effects rendered with numpy/scipy."""
from __future__ import annotations

from functools import lru_cache

import numpy as np
from scipy.signal import butter, fftconvolve, sosfilt

from ..audio_io import SR
from .theory import midi_hz

TWO_PI = 2 * np.pi


def _t(n: int) -> np.ndarray:
    return np.arange(n, dtype=np.float32) / SR


def _release(n_hold: int, n_total: int, seconds: float) -> np.ndarray:
    env = np.ones(n_total, np.float32)
    tail = n_total - n_hold
    if tail > 0:
        env[n_hold:] = np.exp(-np.arange(tail, dtype=np.float32) / (SR * seconds / 5))
    return env


def _attack(n: int, seconds: float) -> np.ndarray:
    env = np.ones(n, np.float32)
    a = min(n, max(1, round(seconds * SR)))
    env[:a] = np.linspace(0, 1, a, dtype=np.float32)
    return env


def _additive(freq: float, t: np.ndarray, amps: np.ndarray, decays: np.ndarray, ratios: np.ndarray | None = None) -> np.ndarray:
    k = np.arange(1, len(amps) + 1, dtype=np.float32) if ratios is None else ratios.astype(np.float32)
    keep = k * freq < SR * .45  # drop partials above Nyquist margin to avoid aliasing
    k, amps, decays = k[keep], amps[keep], decays[keep]
    if not len(k):
        return np.zeros_like(t)
    phases = TWO_PI * freq * k[:, None] * t[None, :]
    return (amps[:, None] * np.sin(phases) * np.exp(-decays[:, None] * t[None, :])).sum(axis=0)


def piano(freq: float, hold: float) -> np.ndarray:
    n_hold = round(hold * SR)
    n = n_hold + round(.35 * SR)
    t = _t(n)
    k = np.arange(1, 9, dtype=np.float32)
    ratios = k * np.sqrt(1 + .0004 * k * k)
    brightness = (261.6 / freq) ** .25
    y = _additive(freq, t, (1 / k ** 1.5) * np.array([1, .8, .6, .5, .35, .25, .15, .1]), (1.1 + .9 * k) / brightness, ratios)
    return y * _attack(n, .003) * _release(n_hold, n, .3)


def epiano(freq: float, hold: float) -> np.ndarray:
    n_hold = round(hold * SR)
    n = n_hold + round(.3 * SR)
    t = _t(n)
    index = 1.6 * np.exp(-t * 3.5) + .25
    y = np.sin(TWO_PI * freq * t + index * np.sin(TWO_PI * freq * t)) * np.exp(-t * 1.2)
    if freq * 14 < SR * .45:
        y += .06 * np.sin(TWO_PI * freq * 14 * t) * np.exp(-t * 40)  # metallic tine attack
    return y * _attack(n, .004) * _release(n_hold, n, .25)


def guitar(freq: float, hold: float) -> np.ndarray:
    n_hold = round(min(hold, 2.5) * SR)
    n = n_hold + round(.2 * SR)
    t = _t(n)
    k = np.arange(1, 13, dtype=np.float32)
    amps = np.abs(np.sin(np.pi * k * .22)) / k
    return _additive(freq, t, amps, 1.6 + .55 * k * k ** .5) * _attack(n, .002) * _release(n_hold, n, .15)


def pluck(freq: float, hold: float) -> np.ndarray:
    n_hold = round(min(hold, 1.5) * SR)
    n = n_hold + round(.15 * SR)
    t = _t(n)
    k = np.arange(1, 11, dtype=np.float32)
    return _additive(freq, t, 1 / k, 4 + 2.2 * k) * _attack(n, .002) * _release(n_hold, n, .1)


def pad(freq: float, hold: float) -> np.ndarray:
    n_hold = round(hold * SR)
    n = n_hold + round(.9 * SR)
    t = _t(n)
    k = np.arange(1, 9, dtype=np.float32)
    amps = np.exp(-k * .45) / k
    y = sum(_additive(freq * 2 ** (c / 1200), t, amps, np.zeros_like(k)) for c in (-8, 0, 7))
    return y / 3 * _attack(n, .45) * _release(n_hold, n, .8)


def strings(freq: float, hold: float) -> np.ndarray:
    n_hold = round(hold * SR)
    n = n_hold + round(.6 * SR)
    t = _t(n)
    vibrato = 1 + .004 * np.sin(TWO_PI * 5.2 * t) * np.clip(t / .6, 0, 1)
    phase = TWO_PI * freq * np.cumsum(vibrato) / SR
    k = np.arange(1, 11, dtype=np.float32)
    k = k[k * freq < SR * .45]
    amps = np.exp(-k * .25) / k
    y = (amps[:, None] * np.sin(k[:, None] * phase[None, :])).sum(axis=0)
    return y * _attack(n, .28) * _release(n_hold, n, .5)


def bell(freq: float, hold: float) -> np.ndarray:
    n = round((hold + 1.6) * SR)
    t = _t(n)
    y = np.sin(TWO_PI * freq * t + 2.2 * np.exp(-t * 2.5) * np.sin(TWO_PI * freq * 3.5 * t)) * np.exp(-t * 1.8)
    y += .25 * np.sin(TWO_PI * freq * 2 * t) * np.exp(-t * 3)
    return y * _attack(n, .002)


def lead(freq: float, hold: float) -> np.ndarray:
    n_hold = round(hold * SR)
    n = n_hold + round(.12 * SR)
    t = _t(n)
    vibrato = 1 + .005 * np.sin(TWO_PI * 5.5 * t) * np.clip((t - .15) / .3, 0, 1)
    phase = TWO_PI * freq * np.cumsum(vibrato) / SR
    k = np.array([1, 3, 5, 7, 9], np.float32)
    k = k[k * freq < SR * .45]
    y = ((np.exp(-k * .18) / k)[:, None] * np.sin(k[:, None] * phase[None, :])).sum(axis=0)
    return y * _attack(n, .012) * _release(n_hold, n, .1)


def flute(freq: float, hold: float) -> np.ndarray:
    n_hold = round(hold * SR)
    n = n_hold + round(.12 * SR)
    t = _t(n)
    vibrato = 1 + .006 * np.sin(TWO_PI * 5 * t) * np.clip((t - .2) / .3, 0, 1)
    phase = TWO_PI * freq * np.cumsum(vibrato) / SR
    y = np.sin(phase) + .22 * np.sin(2 * phase) + .06 * np.sin(3 * phase)
    breath = np.random.default_rng(int(freq)).standard_normal(n).astype(np.float32)
    breath = sosfilt(butter(2, [min(freq * 2, 8000), min(freq * 6, 15000)], "bandpass", fs=SR, output="sos"), breath)
    y += .05 * breath / (np.max(np.abs(breath)) + 1e-9)
    return y * _attack(n, .06) * _release(n_hold, n, .1)


def bass(freq: float, hold: float) -> np.ndarray:
    n_hold = round(hold * SR)
    n = n_hold + round(.06 * SR)
    t = _t(n)
    y = np.sin(TWO_PI * freq * t) + .35 * np.sin(TWO_PI * 2 * freq * t) * np.exp(-t * 6)
    env = .75 + .25 * np.exp(-t * 8)
    return np.tanh(1.4 * y * env) * _attack(n, .004) * _release(n_hold, n, .06)


def bass808(freq: float, hold: float) -> np.ndarray:
    n_hold = round(hold * SR)
    n = n_hold + round(.08 * SR)
    t = _t(n)
    f = freq * (1 + 1.2 * np.exp(-t * 40))
    y = np.sin(TWO_PI * np.cumsum(f) / SR) * np.exp(-t * .9)
    return np.tanh(1.8 * y) * _attack(n, .002) * _release(n_hold, n, .08)


VOICES = {
    "piano": piano, "epiano": epiano, "guitar": guitar, "pluck": pluck, "pad": pad, "strings": strings,
    "bell": bell, "lead": lead, "flute": flute, "bass": bass, "bass808": bass808,
}


@lru_cache(maxsize=384)
def _note(voice: str, midi: int, hold_ms: int) -> np.ndarray:
    y = VOICES[voice](midi_hz(midi), hold_ms / 1000).astype(np.float32)
    y /= max(float(np.max(np.abs(y))), 1e-9)
    y.setflags(write=False)
    return y


def note(voice: str, midi: int, hold_s: float) -> np.ndarray:
    """Normalised mono note; cached because chords and riffs repeat constantly."""
    return _note(voice, int(midi), int(round(hold_s * 1000 / 10) * 10))


# ---------------------------------------------------------------- drums

def _noise(n: int, seed: int) -> np.ndarray:
    return np.random.default_rng(seed).standard_normal(n).astype(np.float32)


def _filter(x: np.ndarray, kind: str, cutoff, order: int = 2) -> np.ndarray:
    return sosfilt(butter(order, cutoff, kind, fs=SR, output="sos"), x, axis=-1).astype(np.float32)


@lru_cache(maxsize=1)
def drum_kit() -> dict[str, np.ndarray]:
    kit: dict[str, np.ndarray] = {}
    n = round(.45 * SR); t = _t(n)
    f = 48 + 110 * np.exp(-t * 32)
    body = np.sin(TWO_PI * np.cumsum(f) / SR) * np.exp(-t * 8)
    click = _filter(_noise(n, 1), "highpass", 2500) * np.exp(-t * 400) * .4
    kit["kick"] = np.tanh(1.6 * (body + click))
    n = round(.25 * SR); t = _t(n)
    tone = (np.sin(TWO_PI * 185 * t) + .5 * np.sin(TWO_PI * 330 * t)) * np.exp(-t * 28)
    rattle = _filter(_noise(n, 2), "bandpass", [1200, 9000]) * np.exp(-t * 17)
    kit["snare"] = .55 * tone + rattle * 1.3
    n = round(.3 * SR); t = _t(n)
    burst = np.zeros(n, np.float32)
    for offset in (0, .011, .022):
        o = round(offset * SR)
        burst[o:] += np.exp(-np.arange(n - o, dtype=np.float32) / SR * 90)
    burst += .5 * np.exp(-t * 13)
    kit["clap"] = _filter(_noise(n, 3), "bandpass", [900, 5000]) * burst
    n = round(.07 * SR); t = _t(n)
    kit["chat"] = _filter(_noise(n, 4), "highpass", 7000) * np.exp(-t * 70)
    n = round(.4 * SR); t = _t(n)
    kit["ohat"] = _filter(_noise(n, 5), "highpass", 6500) * np.exp(-t * 8)
    n = round(.05 * SR); t = _t(n)
    kit["rim"] = (np.sin(TWO_PI * 820 * t) + .6 * np.sin(TWO_PI * 1650 * t)) * np.exp(-t * 130)
    n = round(2.2 * SR); t = _t(n)
    kit["crash"] = _filter(_noise(n, 6), "highpass", 4500) * np.exp(-t * 2.3)
    for name, y in kit.items():
        y = y.astype(np.float32) / max(float(np.max(np.abs(y))), 1e-9)
        y.setflags(write=False)
        kit[name] = y
    return kit


DRUM_LEVEL = {"kick": 1.0, "snare": .7, "clap": .62, "chat": .26, "ohat": .2, "rim": .4, "crash": .22}
DRUM_PAN = {"kick": 0, "snare": .05, "clap": -.05, "chat": .3, "ohat": .35, "rim": -.25, "crash": -.2}


# ---------------------------------------------------------------- effects / mixing

def pan(mono: np.ndarray, position: float) -> np.ndarray:
    angle = (position + 1) * np.pi / 4
    return np.stack([mono * np.cos(angle), mono * np.sin(angle)]).astype(np.float32) * np.sqrt(2)


def widen(mono: np.ndarray, delay_ms: float = 12) -> np.ndarray:
    d = round(delay_ms / 1000 * SR)
    right = np.concatenate([np.zeros(d, np.float32), mono[:-d]]) if d else mono
    return np.stack([mono, right]).astype(np.float32)


def lowpass(x: np.ndarray, cutoff: float) -> np.ndarray:
    return _filter(x, "lowpass", min(cutoff, SR * .45))


def highpass(x: np.ndarray, cutoff: float) -> np.ndarray:
    return _filter(x, "highpass", cutoff)


@lru_cache(maxsize=8)
def _impulse(seconds: float, damp: float) -> np.ndarray:
    n = round(seconds * SR)
    t = _t(n)
    ir = np.stack([_noise(n, 11), _noise(n, 12)]) * np.exp(-t * 6.9 / seconds)
    ir = lowpass(ir, damp)
    ir[:, :round(.012 * SR)] = 0  # pre-delay
    ir /= np.sqrt(np.sum(ir ** 2, axis=1, keepdims=True)) + 1e-9
    return ir.astype(np.float32)


def reverb_tail(stereo: np.ndarray, seconds: float = 2.0, damp: float = 6000) -> np.ndarray:
    ir = _impulse(round(seconds, 2), damp)
    return np.stack([fftconvolve(stereo[i], ir[i])[:stereo.shape[1]] for i in range(2)]).astype(np.float32)


def reverb(stereo: np.ndarray, seconds: float = 2.0, wet: float = .25, damp: float = 6000) -> np.ndarray:
    if wet <= 0:
        return stereo
    return stereo * (1 - wet * .5) + reverb_tail(stereo, seconds, damp) * wet


def echo(stereo: np.ndarray, delay_s: float, feedback: float = .35, wet: float = .2) -> np.ndarray:
    out = stereo.copy()
    d = round(delay_s * SR)
    gain = wet
    for i in range(1, 5):
        shift = d * i
        if shift >= stereo.shape[1]:
            break
        side = (i % 2)  # ping-pong between channels
        out[side, shift:] += stereo[side, :-shift] * gain
        gain *= feedback
    return out


def vinyl(seconds: float, seed: int = 0) -> np.ndarray:
    n = max(1, round(seconds * SR))
    rng = np.random.default_rng(seed)
    hiss = lowpass(highpass(rng.standard_normal(n).astype(np.float32), 900), 7000) * .05
    crackle = np.zeros(n, np.float32)
    for pos in rng.integers(0, n, size=int(seconds * 14)):
        length = int(rng.integers(20, 120))
        end = min(n, pos + length)
        crackle[pos:end] += rng.uniform(.2, 1) * np.exp(-np.arange(end - pos) / 12) * rng.choice([-1, 1])
    y = hiss + highpass(crackle, 1500) * .6
    return widen(y / (np.max(np.abs(y)) + 1e-9), 7)


def soft_limit(x: np.ndarray, ceiling: float = .89) -> np.ndarray:
    knee = ceiling * .7
    over = np.abs(x) > knee
    y = x.copy()
    y[over] = np.sign(x[over]) * (knee + (ceiling - knee) * np.tanh((np.abs(x[over]) - knee) / (ceiling - knee)))
    return y
