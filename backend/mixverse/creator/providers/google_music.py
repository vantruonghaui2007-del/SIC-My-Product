"""Google AI Studio/Lyria via Gemini Interactions. Never retry generation."""
from __future__ import annotations

import base64
import binascii
from contextlib import nullcontext
from pathlib import Path
import time
from typing import Callable

import httpx

from . import MusicProviderError

GOOGLE_MODELS = {'lyria-3.5', 'lyria-3-clip-preview'}
ENDPOINT = 'https://generativelanguage.googleapis.com/v1beta/interactions'


class GoogleMusicProvider:
    def __init__(self, api_key: str, model: str = 'lyria-3.5', timeout_s: int = 240, client: httpx.Client | None = None):
        self.api_key = api_key
        self.model = model
        self.timeout_s = timeout_s
        self.client = client

    def body(self, mode: str, prompt: str, duration_s: int, lyrics: str = '', genre: str = '', mood: str = '') -> dict:
        if self.model not in GOOGLE_MODELS:
            raise ValueError('Model Google chưa được hỗ trợ. Chọn lyria-3.5 hoặc lyria-3-clip-preview.')
        if not 15 <= duration_s <= 120:
            raise ValueError('Thời lượng cần từ 15 đến 120 giây.')
        if self.model == 'lyria-3-clip-preview' and duration_s != 30:
            raise ValueError('Lyria Clip chỉ tạo bản nhạc 30 giây; chọn 30 giây hoặc dùng Lyria 3.5.')
        if len(prompt) > 2000 or len(lyrics) > 4000:
            raise ValueError('Prompt tối đa 2.000 ký tự, lời bài hát tối đa 4.000 ký tự.')
        if mode == 'text_music' and prompt.strip():
            instruction = 'Create instrumental music only, without vocals or sung words.'
        elif mode == 'text_song' and lyrics.strip():
            instruction = 'Create a song with lead vocals singing the supplied lyrics. Preserve their language and words.'
        else:
            raise ValueError('Cần mô tả bản nhạc hoặc lời bài hát để gửi tới Google.')
        parts = [instruction, f'Target duration: {duration_s} seconds.']
        if genre: parts.append(f'Genre: {genre}')
        if mood: parts.append(f'Mood: {mood}')
        if prompt.strip(): parts.append(f'Musical direction:\n{prompt.strip()}')
        if mode == 'text_song': parts.append(f'Lyrics:\n{lyrics.strip()}')
        return {'model': self.model, 'input': '\n\n'.join(parts), 'store': False}

    def generate(self, mode: str, prompt: str, duration_s: int, out_path: Path, lyrics: str = '', genre: str = '', mood: str = '', on_stage: Callable[[str], None] | None = None) -> dict:
        payload = self.body(mode, prompt, duration_s, lyrics, genre, mood)
        if on_stage: on_stage('generating')
        start = time.perf_counter()
        context = nullcontext(self.client) if self.client is not None else httpx.Client(timeout=self.timeout_s)
        try:
            with context as client:
                response = client.post(ENDPOINT, headers={'x-goog-api-key': self.api_key}, json=payload, timeout=self.timeout_s)
            code = response.status_code
            errors = {
                400: ('MUSIC_REQUEST_REJECTED', 'Google từ chối yêu cầu tạo nhạc. Kiểm tra nội dung và cấu hình model.'),
                422: ('MUSIC_REQUEST_REJECTED', 'Google từ chối yêu cầu tạo nhạc.'),
                401: ('MUSIC_PROVIDER_AUTH', 'Google không chấp nhận API key. Kiểm tra khóa và quyền của project.'),
                403: ('MUSIC_PROVIDER_AUTH', 'API key hoặc project chưa có quyền dùng model Google này.'),
                402: ('MUSIC_PROVIDER_BILLING', 'Google yêu cầu kiểm tra Billing, credit hoặc số dư trả trước.'),
                404: ('MUSIC_MODEL_UNAVAILABLE', 'Model Lyria chưa khả dụng với project hoặc phiên bản API này.'),
                429: ('MUSIC_PROVIDER_RATE_LIMIT', 'Google đang giới hạn lượt gọi hoặc project đã hết hạn mức. Kiểm tra AI Studio.'),
            }
            if code in errors: raise MusicProviderError(*errors[code])
            if code >= 500: raise MusicProviderError('MUSIC_PROVIDER_UNAVAILABLE', 'Dịch vụ tạo nhạc Google đang lỗi; không tự gửi lại yêu cầu.')
            if not 200 <= code < 300: raise MusicProviderError('MUSIC_REQUEST_REJECTED', 'Không hoàn tất được yêu cầu tới Google.')
            try:
                result = response.json()
                if not isinstance(result, dict): raise ValueError('invalid interaction')
                if result.get('status') not in (None, 'completed'):
                    raise MusicProviderError('MUSIC_RESULT_UNKNOWN', 'Google chưa trả kết quả hoàn tất. Kiểm tra AI Studio trước khi tạo lại để tránh tính phí hai lần.')
                blocks = [block for step in result.get('steps', []) if isinstance(step, dict) and step.get('type') == 'model_output'
                          for block in step.get('content', []) if isinstance(block, dict) and block.get('type') == 'audio']
                block = blocks[-1]
                if block.get('mime_type') not in ('audio/mp3', 'audio/mpeg', 'audio/wav', 'audio/x-wav'):
                    raise ValueError('unsupported audio format')
                encoded = block['data']
                if not isinstance(encoded, str) or len(encoded) > 140_000_000: raise ValueError('invalid audio data')
                audio = base64.b64decode(encoded, validate=True)
                if len(audio) < 1024: raise ValueError('empty audio')
            except (ValueError, IndexError, KeyError, TypeError, binascii.Error) as exc:
                raise MusicProviderError('MUSIC_BAD_OUTPUT', 'Google không trả về file nhạc hợp lệ. Không tự gửi lại yêu cầu.') from exc
            out_path.parent.mkdir(parents=True, exist_ok=True)
            partial = out_path.with_suffix(out_path.suffix + '.part')
            try:
                partial.write_bytes(audio)
                partial.replace(out_path)
            finally:
                partial.unlink(missing_ok=True)
            return {'provider': 'google', 'model': self.model, 'elapsed_s': time.perf_counter() - start,
                    'song_id': result.get('id'), 'content_type': block['mime_type']}
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            raise MusicProviderError('MUSIC_RESULT_UNKNOWN', 'Mất kết nối hoặc hết thời gian chờ Google; yêu cầu có thể đã tính phí. Không tự gửi lại.') from exc
