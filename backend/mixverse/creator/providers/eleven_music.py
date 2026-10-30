from __future__ import annotations
import json
from pathlib import Path
import time
from typing import Callable
import httpx
from . import MusicProviderError


class ElevenMusicProvider:
    """One-shot ElevenLabs Music API adapter. Never retries paid generation."""
    def __init__(self, api_key: str, model: str="music_v2_5", timeout_s: int=240, client: httpx.Client|None=None):
        self.api_key=api_key; self.model=model; self.timeout_s=timeout_s
        self.client=client or httpx.Client(timeout=timeout_s)

    @staticmethod
    def body(mode: str, prompt: str, duration_s: int, lyrics: str="", genre: str="", mood: str="") -> dict:
        if mode=="text_music":
            return {"prompt":prompt,"music_length_ms":duration_s*1000,"force_instrumental":True,"model_id":"music_v2_5"}
        if mode!="text_song" or not lyrics.strip(): raise ValueError("Cần lời bài hát để tạo Text-to-Song.")
        styles=[x for x in (genre,mood) if x]
        if not styles:
            styles=["pop", "melodic song", "clear lead vocal", "studio production", "memorable chorus", "warm arrangement"]
        return {"model_id":"music_v2_5","composition_plan":{"chunks":[{"text":lyrics,"duration_ms":duration_s*1000,"positive_styles":styles,"negative_styles":[],"context_adherence":"medium"}]}}

    def generate(self, mode: str, prompt: str, duration_s: int, out_path: Path, lyrics: str="", genre: str="", mood: str="", on_stage: Callable[[str],None]|None=None) -> dict:
        if not 15<=duration_s<=60: raise ValueError("Thời lượng cần từ 15 đến 60 giây.")
        if on_stage:on_stage("generating")
        payload=self.body(mode,prompt,duration_s,lyrics,genre,mood)
        payload["model_id"]=self.model
        start=time.perf_counter()
        try:
            with self.client.stream("POST","https://api.elevenlabs.io/v1/music",headers={"xi-api-key":self.api_key,"Accept":"audio/mpeg","Content-Type":"application/json"},json=payload,timeout=self.timeout_s) as response:
                if response.status_code in (401,403): raise MusicProviderError("MUSIC_PROVIDER_AUTH","Không xác thực được nhà cung cấp nhạc.")
                if response.status_code==429: raise MusicProviderError("MUSIC_PROVIDER_RATE_LIMIT","Nhà cung cấp đang giới hạn lượt tạo; hãy thử lại sau.")
                if response.status_code in (400,422):
                    response.read()
                    try:
                        detail = response.json().get('detail', {})
                        status = detail.get('status') if isinstance(detail, dict) else None
                    except (ValueError, AttributeError):
                        status = None
                    if status == 'api_key_id_used_as_api_key':
                        raise MusicProviderError('MUSIC_PROVIDER_AUTH', 'Bạn đang dùng API key ID thay vì API key ElevenLabs. Tạo hoặc xoay khóa, rồi điền khóa đầy đủ bắt đầu bằng sk_ vào ELEVENLABS_API_KEY ở backend.')
                    raise MusicProviderError("MUSIC_REQUEST_REJECTED","Yêu cầu tạo nhạc bị nhà cung cấp từ chối.")
                if response.status_code>=500: raise MusicProviderError("MUSIC_PROVIDER_UNAVAILABLE","Nhà cung cấp nhạc đang lỗi.")
                response.raise_for_status()
                out_path.parent.mkdir(parents=True,exist_ok=True)
                tmp=out_path.with_suffix(out_path.suffix+".part")
                with tmp.open("wb") as f:
                    for chunk in response.iter_bytes():
                        if chunk:f.write(chunk)
                if tmp.stat().st_size<1024:
                    tmp.unlink(missing_ok=True); raise MusicProviderError("MUSIC_BAD_OUTPUT","Nhà cung cấp trả về tệp âm thanh không hợp lệ.")
                tmp.replace(out_path)
                return {"provider":"elevenlabs","model":self.model,"elapsed_s":time.perf_counter()-start,"song_id":response.headers.get("song-id"),"content_type":response.headers.get("content-type","application/octet-stream")}
        except httpx.TimeoutException as e:
            raise MusicProviderError("MUSIC_RESULT_UNKNOWN","Hết thời gian chờ; yêu cầu có thể đã được tính phí. Không tự gửi lại.") from e
        except httpx.TransportError as e:
            raise MusicProviderError("MUSIC_RESULT_UNKNOWN","Mất kết nối; trạng thái yêu cầu chưa xác định. Không tự gửi lại.") from e
