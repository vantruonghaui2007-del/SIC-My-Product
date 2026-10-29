from pathlib import Path
import json
import shutil
import subprocess
import tempfile

import numpy as np
import soundfile as sf

SR = 44100


class AudioDecodeError(ValueError):
    pass


def load_audio(path: Path) -> np.ndarray:
    try:
        data, sr = sf.read(path, dtype="float32", always_2d=True)
        if not len(data):
            raise ValueError("empty")
        if sr != SR:
            from scipy.signal import resample_poly
            from math import gcd
            g = gcd(SR, sr)
            data = resample_poly(data, SR // g, sr // g, axis=0).astype(np.float32)
        if data.shape[1] == 1:
            data = np.repeat(data, 2, axis=1)
        elif data.shape[1] > 2:
            data = data[:, :2]
        return np.ascontiguousarray(data.T, dtype=np.float32)
    except Exception:
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            raise AudioDecodeError("Không đọc được tệp âm thanh.")
        try:
            raw = subprocess.run([ffmpeg, "-v", "error", "-i", str(path), "-f", "f32le", "-ac", "2", "-ar", str(SR), "pipe:1"], check=True, capture_output=True, timeout=60).stdout
            if not raw or len(raw) % 8:
                raise ValueError("empty/invalid")
            return np.frombuffer(raw, dtype="<f4").reshape(-1, 2).T.copy()
        except Exception as exc:
            raise AudioDecodeError("Không đọc được tệp âm thanh.") from exc


def write_wav(path: Path, audio: np.ndarray, subtype: str = "PCM_24") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(path, np.asarray(audio).T, SR, subtype=subtype)


def write_flac(path: Path, audio: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(path, np.asarray(audio).T, SR, format="FLAC")


def encode_mp3(wav_path: Path, mp3_path: Path, metadata: dict[str, str]) -> None:
    args = ["ffmpeg", "-y", "-v", "error", "-i", str(wav_path), "-codec:a", "libmp3lame", "-b:a", "320k"]
    for k, v in metadata.items():
        args += ["-metadata", f"{k}={v}"]
    args.append(str(mp3_path))
    subprocess.run(args, check=True, capture_output=True)


def tag_wav(path: Path, metadata: dict[str, str]) -> None:
    # WAV INFO metadata is not consistently preserved by every decoder; use ffmpeg when available.
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return
    with tempfile.NamedTemporaryFile(suffix=".wav", dir=path.parent, delete=False) as tmp:
        temp = Path(tmp.name)
    try:
        args = [ffmpeg, "-y", "-v", "error", "-i", str(path), "-c", "copy"]
        for k, v in metadata.items():
            args += ["-metadata", f"{k}={v}"]
        args.append(str(temp))
        subprocess.run(args, check=True, capture_output=True)
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def rms_db(audio: np.ndarray) -> float:
    rms = float(np.sqrt(np.mean(np.square(audio, dtype=np.float64)))) if audio.size else 0.0
    return 20 * np.log10(max(rms, 1e-12))


def peak_db(audio: np.ndarray) -> float:
    return 20 * np.log10(max(float(np.max(np.abs(audio))) if audio.size else 0.0, 1e-12))
