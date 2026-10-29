from dataclasses import dataclass
import numpy as np
from ..audio_io import SR


@dataclass
class Grid:
    bpm: float
    beats_s: list[float]
    downbeats_s: list[float]


def estimate_grid(audio: np.ndarray) -> Grid:
    mono = np.asarray(audio).mean(axis=0)
    if mono.size < SR * 2 or np.max(np.abs(mono)) < 1e-5:
        return Grid(0.0, [], [])
    try:
        import librosa
        tempo, beats = librosa.beat.beat_track(y=mono.astype(np.float32), sr=SR, hop_length=512, units="time", trim=False)
        bpm = float(np.asarray(tempo).reshape(-1)[0])
        beat_times = np.asarray(beats, dtype=float)
        if beat_times.size < 4 or not np.isfinite(bpm) or bpm <= 0:
            return Grid(0.0, [], [])
        period = 60 / bpm
        phase = beat_times[0] % (4 * period)
        downbeats = np.arange(phase, mono.size / SR, 4 * period).tolist()
        return Grid(bpm, beat_times.tolist(), downbeats)
    except Exception:
        return Grid(0.0, [], [])


def shift_downbeats(grid: Grid, beats: int) -> Grid:
    period = 60 / grid.bpm if grid.bpm else 0
    ds = [t + beats * period for t in grid.downbeats_s]
    return Grid(grid.bpm, grid.beats_s, ds)
