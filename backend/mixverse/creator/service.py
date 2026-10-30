from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import numpy as np
from pydantic import BaseModel, Field

from ..audio_io import SR, load_audio, write_wav, rms_db, waveform_peaks
from ..music import STEM_ORDER, Composition, Recipe, compose, render
from ..sound import render_beat


class Asset(BaseModel):
    id: str
    kind: Literal["vocal", "sound", "generated_music", "generated_song"]
    original_name: str
    sha256: str
    duration_s: float
    rights_confirmed: bool
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CreatorService:
    """Small, honest local Creator implementation; no claim of generative AI."""
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def project_dir(self, pid: str) -> Path:
        if not re.fullmatch(r"[0-9a-f]{32}", pid):
            raise ValueError("Dự án không hợp lệ.")
        p = self.root / pid / "creator"
        p.mkdir(parents=True, exist_ok=True)
        return p

    def import_asset(self, pid: str, data: bytes, name: str, kind: str, rights: bool) -> Asset:
        if not rights:
            raise ValueError("Vui lòng xác nhận bạn có quyền sử dụng tệp này.")
        if kind not in {"vocal", "sound"}:
            raise ValueError("Loại tài sản không hợp lệ.")
        d = self.project_dir(pid)
        aid = "a_" + uuid.uuid4().hex
        original = d / f"{aid}.upload"
        original.write_bytes(data)
        try:
            pcm = load_audio(original)
            duration = pcm.shape[1] / SR
            if np.max(np.abs(pcm)) < 1e-5 or rms_db(pcm) < -75:
                raise ValueError("Không phát hiện âm thanh rõ; hãy thu hoặc tải lại.")
            if kind == "vocal" and not 10 <= duration <= 60:
                raise ValueError("Vocal cần dài từ 10 đến 60 giây.")
            if kind == "sound" and not .1 <= duration <= 30:
                raise ValueError("Âm thanh cần dài từ 0,1 đến 30 giây.")
            pcm_path = d / f"{aid}.wav"
            write_wav(pcm_path, pcm, "FLOAT")
            asset = Asset(id=aid, kind=kind, original_name=Path(name).name, sha256=hashlib.sha256(data).hexdigest(), duration_s=duration, rights_confirmed=True)
            (d / f"{aid}.json").write_text(asset.model_dump_json(), encoding="utf-8")
            return asset
        except Exception:
            original.unlink(missing_ok=True)
            raise

    def asset(self, pid: str, aid: str) -> Asset:
        path = self.project_dir(pid) / f"{aid}.json"
        if not path.is_file():
            raise FileNotFoundError("Không tìm thấy tài sản trong dự án này.")
        return Asset.model_validate_json(path.read_text(encoding="utf-8"))

    def asset_audio(self, pid: str, aid: str) -> np.ndarray:
        self.asset(pid, aid)
        return load_audio(self.project_dir(pid) / f"{aid}.wav")

    LOCAL_WARNING = "Sáng tác bằng engine nhạc local (lý thuyết âm nhạc + synth), chưa phải mô hình sinh nhạc AI."

    def compose_takes(self, pid: str, recipe: Recipe, seeds: list[int]) -> list[dict]:
        """Compose and render one take per seed (in parallel threads) and store a re-renderable record."""
        d = self.project_dir(pid)

        def take(index_seed: tuple[int, int]) -> dict:
            index, seed = index_seed
            comp = compose(recipe, seed)
            master, _ = render(comp)
            cid = "m_" + uuid.uuid4().hex
            out = d / f"text_music_{cid}.wav"
            write_wav(out, master, "PCM_16")
            summary = comp.summary()
            record = {"id": cid, "recipe": recipe.model_dump(), "seed": seed, "audio_file": out.name, "summary": summary}
            (d / f"{cid}.json").write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
            label = f"Phương án {index + 1} · " + " – ".join(summary["progression"])
            return {"composition_id": cid, "file": out.name, "peaks": waveform_peaks(master),
                    "metadata": {**summary, "label": label, "recipe": recipe.model_dump(), "warning": self.LOCAL_WARNING, "warnings": [self.LOCAL_WARNING]}}

        with ThreadPoolExecutor(max_workers=min(3, len(seeds))) as pool:
            return list(pool.map(take, enumerate(seeds)))

    def composition(self, pid: str, cid: str) -> tuple[dict, Composition]:
        if not re.fullmatch(r"m_[0-9a-f]{32}", cid):
            raise FileNotFoundError("Không tìm thấy bản nhạc.")
        path = self.project_dir(pid) / f"{cid}.json"
        if not path.is_file():
            raise FileNotFoundError("Không tìm thấy bản nhạc.")
        record = json.loads(path.read_text(encoding="utf-8"))
        return record, compose(Recipe.model_validate(record["recipe"]), record["seed"])

    def stems(self, pid: str, cid: str) -> dict[str, Path]:
        """Render stems on first request; the composition is deterministic so they match the mix."""
        _, comp = self.composition(pid, cid)
        d = self.project_dir(pid)
        paths = {name: d / f"stem_{cid}_{name}.wav" for name in STEM_ORDER}
        existing = {k: v for k, v in paths.items() if v.is_file()}
        if existing:
            return existing
        _, stems = render(comp)
        for name, audio in stems.items():
            write_wav(paths[name], audio, "PCM_16")
        return {k: v for k, v in paths.items() if v.is_file()}

    def analyze_vocal(self, pid: str, aid: str) -> dict:
        asset = self.asset(pid, aid)
        if asset.kind != "vocal":
            raise ValueError("Chỉ tài sản vocal dùng được với Rap-to-Beat.")
        audio = self.asset_audio(pid, aid).mean(axis=0)
        hop = 441
        env = np.array([np.sqrt(np.mean(audio[i:i+hop]**2)) for i in range(0, len(audio)-hop, hop)])
        floor = max(float(np.percentile(env, 20)), 1e-5)
        active = env > floor * 2.5
        times = np.flatnonzero(active)
        onsets = []
        flux = np.maximum(np.diff(env, prepend=0), 0)
        threshold = max(float(np.percentile(flux, 85)), floor*.5)
        onsets = (np.flatnonzero(flux > threshold) * .01).round(3).tolist()
        # Voice material is ambiguous: provide candidates but require explicit user confirmation.
        first = onsets[0] if onsets else 0.0
        candidates = [{"bpm": b, "first_downbeat_s": first, "score": score, "half_double_group": f"{b/2:g}/{b:g}/{b*2:g}"} for b, score in tempo_candidates(audio)]
        if not candidates:
            candidates = [{"bpm": b, "first_downbeat_s": first, "score": 0.0, "half_double_group": f"{b:g}/{b*2:g}"} for b in (80., 100., 120.)]
        def regions(mask: np.ndarray, value: bool):
            edges=np.diff(np.r_[False,mask==value,False].astype(np.int8))
            return [[round(int(a)*.01,2),round(int(b)*.01,2)] for a,b in zip(np.flatnonzero(edges==1),np.flatnonzero(edges==-1)) if b-a>=18]
        return {"asset_id": aid, "onset_times_s": onsets, "active_regions_s": regions(active,True), "pause_regions_s": regions(active,False), "tempo_candidates": candidates, "selected_bpm": None, "selected_downbeat_s": None, "confidence":"low", "needs_confirmation":True, "confirmed":False, "warnings":["Ứng viên BPM là heuristic; vui lòng chọn BPM và mốc phách mạnh."]}

    def arrange_rap(self, pid: str, aid: str, bpm: float, style: str, first_downbeat_s: float = 0, variant: int = 0) -> tuple[dict, np.ndarray]:
        vocal_asset = self.asset(pid, aid)
        if vocal_asset.kind != "vocal":
            raise ValueError("Cần asset vocal.")
        vocal = self.asset_audio(pid, aid)
        n = vocal.shape[1]
        # Duration-locked vocal is copied at the exact absolute sample offset.
        offset = round(first_downbeat_s * SR)
        total = offset + n
        seeds=(5,19,41)
        beat = render_beat(style, bpm, max(1, total / SR * bpm / 240), seed=seeds[variant%3]) * 10 ** (-10 / 20)
        mix = np.zeros((2, max(total, beat.shape[1])), np.float32)
        mix[:, :beat.shape[1]] += beat
        mix[:, offset:offset+n] += vocal
        mix *= min(1, .89 / max(float(np.max(np.abs(mix))), 1e-8))
        return {"asset_id":aid,"anchor_s":first_downbeat_s,"duration_s":vocal_asset.duration_s,"bpm":bpm,"style":style,"variant":variant,"label":["Sparse","Balanced","Energetic"][variant%3],"lock_timing":True,"warnings":["Vocal gốc được giữ nguyên thời gian; pattern trống thay đổi theo seed, chưa phân tích flow nâng cao."]}, mix

    def arrange_sound(self, pid: str, aid: str, bpm: float, role: str = "percussion") -> tuple[dict, np.ndarray]:
        asset = self.asset(pid, aid)
        if asset.kind != "sound":
            raise ValueError("Cần asset âm thanh.")
        sample = self.asset_audio(pid, aid)
        if role == "texture":
            n = round(16 * 240 / bpm * SR)
            audio = np.tile(sample, (1, int(np.ceil(n/sample.shape[1]))))[:, :n]
        elif role == "percussion":
            bars = 4
            beat = render_beat("house", bpm, bars, seed=9)
            audio = beat
            interval = round(60/bpm*SR)
            clip = sample[:, :min(sample.shape[1], round(.5*SR))]
            for t in range(0, audio.shape[1], interval):
                m = min(clip.shape[1], audio.shape[1]-t)
                audio[:, t:t+m] += clip[:, :m] * .25
        else:
            raise ValueError("Vai trò phải percussion hoặc texture.")
        audio *= min(1, .9/max(float(np.max(np.abs(audio))), 1e-8))
        return {"asset_id":aid,"role":role,"source_sha256":asset.sha256,"bpm":bpm,"warnings":["Sample được lấy từ chính tệp bạn tải lên."]}, audio


def tempo_candidates(mono: np.ndarray, limit: int = 3) -> list[tuple[float, float]]:
    """Strongest tempi (60–180 BPM) from the onset-strength tempogram, with relative scores."""
    try:
        import librosa
        y = librosa.resample(mono.astype(np.float32), orig_sr=SR, target_sr=22050)
        env = librosa.onset.onset_strength(y=y, sr=22050)
        if env.size < 32 or not np.any(env):
            return []
        strength = librosa.feature.tempogram(onset_envelope=env, sr=22050).mean(axis=1)
        bpms = librosa.tempo_frequencies(strength.size, sr=22050)
    except Exception:
        return []
    inside = np.flatnonzero((bpms >= 60) & (bpms <= 180))
    peaks = [i for i in inside if 0 < i < strength.size - 1 and strength[i] >= strength[i - 1] and strength[i] >= strength[i + 1]]
    peaks.sort(key=lambda i: strength[i], reverse=True)
    top = float(strength[peaks[0]]) if peaks else 1.0
    chosen: list[tuple[float, float]] = []
    for i in peaks:
        bpm = round(float(bpms[i]))
        if all(abs(bpm - b) > 4 for b, _ in chosen):
            chosen.append((float(bpm), round(float(strength[i]) / top, 2)))
        if len(chosen) == limit:
            break
    return chosen
