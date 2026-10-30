import numpy as np
from ..audio_io import SR

SWING = {"lofi": .18, "house": .06, "rnb": .12}


def render_beat(style: str, bpm: float, bars: float, seed: int = 0) -> np.ndarray:
    # Imported lazily: the music engine itself depends on this package for ambience beds.
    from ..music.compose import drum_hits
    from ..music.render import render_drums
    n = max(1, round(bars * 240 / bpm * SR))
    out = render_drums(drum_hits(style, bars, seed), 60 / bpm, n, SWING.get(style, 0))
    peak = max(float(np.max(np.abs(out))), 1e-8)
    return (out * (.5 / peak)).astype(np.float32)
