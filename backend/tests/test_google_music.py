import base64
import io
import json

import httpx
import numpy as np
import pytest
import soundfile as sf
from fastapi.testclient import TestClient

from mixverse.api import create_app
from mixverse.config import Settings


def audio_bytes():
    stream = io.BytesIO()
    sf.write(stream, np.zeros((4410, 2), dtype=np.float32), 44100, format='WAV')
    return stream.getvalue()


def test_settings_loads_backend_env_with_windows_bom(monkeypatch, tmp_path):
    import mixverse.config as config_module
    backend = tmp_path / 'backend'
    (backend / 'mixverse').mkdir(parents=True)
    monkeypatch.setattr(config_module, '__file__', str(backend / 'mixverse' / 'config.py'))
    for name in ('MIXVERSE_MUSIC_PROVIDER', 'MIXVERSE_MUSIC_MODEL', 'GEMINI_API_KEY', 'GOOGLE_API_KEY', 'MIXVERSE_PROVIDER_ACCESS_TOKEN'):
        monkeypatch.delenv(name, raising=False)
    (tmp_path / '.env').write_text('MIXVERSE_MUSIC_PROVIDER=none\n', encoding='utf-8')
    (backend / '.env').write_text('MIXVERSE_MUSIC_PROVIDER=google\nGEMINI_API_KEY=backend-test-key\nMIXVERSE_PROVIDER_ACCESS_TOKEN=owner-code\n', encoding='utf-8-sig')
    settings = Settings.from_env()
    assert settings.provider_enabled
    assert settings.music_api_key == 'backend-test-key'
    assert settings.provider_access_token == 'owner-code'


def interaction(audio=None):
    return {'id': 'interaction-test', 'object': 'interaction', 'status': 'completed',
            'model': 'lyria-3.5', 'created': '2026-10-30T00:00:00Z',
            'steps': [{'type': 'model_output', 'content': [
                {'type': 'text', 'text': '[Intro]'},
                {'type': 'audio', 'mime_type': 'audio/wav',
                 'data': base64.b64encode(audio if audio is not None else audio_bytes()).decode()},
            ]}]}


def test_google_key_enables_google_without_elevenlabs_key(monkeypatch, tmp_path):
    monkeypatch.setattr('mixverse.config._load_backend_env', lambda: None)
    for name in ('MIXVERSE_MUSIC_PROVIDER', 'MIXVERSE_MUSIC_MODEL', 'GOOGLE_API_KEY'):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv('GEMINI_API_KEY', 'google-test-secret')
    monkeypatch.setenv('ELEVENLABS_API_KEY', 'unrelated-legacy-secret')
    settings = Settings.from_env()
    settings.data_dir = tmp_path
    client = TestClient(create_app(settings))
    caps = client.get('/api/creator/capabilities').json()['modes']
    assert caps['text_music']['provider_enabled'] is True
    assert caps['text_song']['enabled'] is True
    assert caps['text_music']['provider'] == 'google'
    assert caps['text_music']['provider_model'] == 'lyria-3.5'
    assert 'secret' not in client.get('/api/creator/capabilities').text


def test_whitespace_key_does_not_enable_google(monkeypatch, tmp_path):
    monkeypatch.setattr('mixverse.config._load_backend_env', lambda: None)
    monkeypatch.setenv('MIXVERSE_MUSIC_PROVIDER', 'google')
    monkeypatch.setenv('GEMINI_API_KEY', '   ')
    monkeypatch.delenv('GOOGLE_API_KEY', raising=False)
    monkeypatch.setenv('ELEVENLABS_API_KEY', 'legacy-key')
    settings = Settings.from_env()
    settings.data_dir = tmp_path
    caps = TestClient(create_app(settings)).get('/api/creator/capabilities').json()['modes']
    assert not caps['text_music']['provider_enabled']
    assert not caps['text_song']['enabled']
    assert 'GEMINI_API_KEY' in caps['text_music']['provider_reason']


@pytest.mark.parametrize('mode,lyrics', [('text_music', ''), ('text_song', 'Xin chào Việt Nam')])
def test_google_adapter_sends_intent_and_saves_real_audio(tmp_path, mode, lyrics):
    from mixverse.creator.providers.google_music import GoogleMusicProvider
    observed = []
    def handle(request):
        observed.append(request)
        return httpx.Response(200, json=interaction())
    target = tmp_path / 'result.mp3'
    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        result = GoogleMusicProvider('test-key', client=client).generate(
            mode, 'piano nhẹ nhàng', 60, target, lyrics, 'ballad', 'sad')
    assert target.read_bytes() == audio_bytes()
    assert result['provider'] == 'google' and result['model'] == 'lyria-3.5'
    assert len(observed) == 1
    assert str(observed[0].url) == 'https://generativelanguage.googleapis.com/v1beta/interactions'
    assert observed[0].headers['x-goog-api-key'] == 'test-key'
    payload = json.loads(observed[0].content)
    assert payload['model'] == 'lyria-3.5'
    assert payload['store'] is False
    assert 'piano nhẹ nhàng' in payload['input'] and '60' in payload['input']
    assert ('Lyrics:\nXin chào Việt Nam' in payload['input']) if lyrics else ('instrumental' in payload['input'].lower())


@pytest.mark.parametrize('status,code', [(401, 'MUSIC_PROVIDER_AUTH'), (403, 'MUSIC_PROVIDER_AUTH'),
    (402, 'MUSIC_PROVIDER_BILLING'), (429, 'MUSIC_PROVIDER_RATE_LIMIT'),
    (400, 'MUSIC_REQUEST_REJECTED'), (404, 'MUSIC_MODEL_UNAVAILABLE'), (503, 'MUSIC_PROVIDER_UNAVAILABLE')])
def test_google_errors_are_sanitized_and_not_retried(tmp_path, status, code):
    from mixverse.creator.providers.google_music import GoogleMusicProvider
    from mixverse.creator.providers import MusicProviderError
    requests = []
    def handle(request):
        requests.append(request)
        return httpx.Response(status, json={'error': {'message': 'private-upstream-details'}})
    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(MusicProviderError) as caught:
            GoogleMusicProvider('secret', client=client).generate('text_music', 'lofi', 30, tmp_path/'bad.mp3')
    assert caught.value.code == code
    assert 'private-upstream-details' not in str(caught.value)
    assert len(requests) == 1
    assert not (tmp_path/'bad.mp3').exists()


def test_google_timeout_is_unknown_and_never_retried(tmp_path):
    from mixverse.creator.providers.google_music import GoogleMusicProvider
    from mixverse.creator.providers import MusicProviderError
    attempts = []
    def handle(request):
        attempts.append(request)
        raise httpx.ReadTimeout('private-details', request=request)
    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(MusicProviderError) as caught:
            GoogleMusicProvider('secret', client=client).generate('text_music', 'lofi', 30, tmp_path/'bad.mp3')
    assert caught.value.code == 'MUSIC_RESULT_UNKNOWN'
    assert len(attempts) == 1


@pytest.mark.parametrize('payload', [
    {'status': 'completed', 'steps': []},
    {'status': 'completed', 'steps': [{'type': 'model_output', 'content': [{'type': 'audio', 'mime_type': 'audio/mp3', 'data': '!!!'}]}]},
    {'status': 'completed', 'steps': [{'type': 'model_output', 'content': [{'type': 'audio', 'mime_type': 'audio/L16', 'data': 'AAAA'}]}]},
])
def test_google_invalid_audio_has_no_partial_file(tmp_path, payload):
    from mixverse.creator.providers.google_music import GoogleMusicProvider
    from mixverse.creator.providers import MusicProviderError
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload))) as client:
        with pytest.raises(MusicProviderError) as caught:
            GoogleMusicProvider('secret', client=client).generate('text_music', 'lofi', 30, tmp_path/'bad.mp3')
    assert caught.value.code == 'MUSIC_BAD_OUTPUT'
    assert list(tmp_path.iterdir()) == []


def test_clip_duration_is_validated_before_request(tmp_path):
    from mixverse.creator.providers.google_music import GoogleMusicProvider
    with httpx.Client(transport=httpx.MockTransport(lambda _: pytest.fail('must not call Google'))) as client:
        with pytest.raises(ValueError, match='30'):
            GoogleMusicProvider('secret', model='lyria-3-clip-preview', client=client).generate('text_music', 'lofi', 60, tmp_path/'bad.mp3')


def test_google_route_requires_consent_and_access_before_call(monkeypatch, tmp_path):
    settings = Settings(data_dir=tmp_path, music_provider='google', music_api_key='key', provider_access_token='owner-code')
    client = TestClient(create_app(settings))
    pid = client.post('/api/projects', json={'mode': 'create'}).json()['id']
    monkeypatch.setattr('mixverse.api.creator.GoogleMusicProvider', lambda *a, **k: pytest.fail('must not call Google'))
    url = f'/api/projects/{pid}/creator/text-music'
    body = {'prompt': 'lofi', 'duration_s': 30, 'generation_method': 'provider'}
    assert client.post(url, json=body).status_code == 422
    body['provider_consent'] = True
    assert client.post(url, json=body).status_code == 403
    body['provider_access_token'] = 'mã sai'
    assert client.post(url, json=body).status_code == 403


def test_google_route_produces_playable_downloads(monkeypatch, tmp_path):
    from mixverse.creator.providers.google_music import GoogleMusicProvider
    import mixverse.api.creator as creator
    calls = []
    def handle(request):
        calls.append(json.loads(request.content))
        return httpx.Response(200, json=interaction())
    with httpx.Client(transport=httpx.MockTransport(handle)) as upstream:
        monkeypatch.setattr(creator, 'GoogleMusicProvider', lambda key, model, timeout: GoogleMusicProvider(key, model, timeout, client=upstream))
        settings = Settings(data_dir=tmp_path, music_provider='google', music_api_key='key', provider_access_token='owner-code')
        client = TestClient(create_app(settings))
        pid = client.post('/api/projects', json={'mode': 'create'}).json()['id']
        result = client.post(f'/api/projects/{pid}/creator/text-music', json={
            'prompt': 'lofi piano', 'duration_s': 30, 'generation_method': 'provider',
            'provider_consent': True, 'provider_access_token': 'owner-code'})
    assert result.status_code == 200, result.text
    assert result.json()['metadata']['provider'] == 'google'
    audio = result.json()['audio_url']
    assert client.get(audio).content[:4] == b'RIFF'
    assert client.get(audio+'/download/wav').content[:4] == b'RIFF'
    assert client.get(audio+'/download/mp3').status_code == 200
    assert len(calls) == 1
    assert 'owner-code' not in json.dumps(calls)
    assert 'owner-code' not in result.text and 'key' not in result.json()['metadata']


def test_bad_provider_audio_is_502_and_leaves_no_files(monkeypatch, tmp_path):
    def invalid_generate(self, mode, prompt, duration, output, *args):
        output.write_bytes(b'not-an-audio-file' * 100)
        return {'provider': 'google', 'model': 'lyria-3.5'}
    monkeypatch.setattr('mixverse.creator.providers.google_music.GoogleMusicProvider.generate', invalid_generate)
    client = TestClient(create_app(Settings(data_dir=tmp_path, music_provider='google', music_api_key='test-key')))
    pid = client.post('/api/projects', json={'mode': 'create'}).json()['id']
    response = client.post(f'/api/projects/{pid}/creator/text-music', json={
        'prompt': 'lofi', 'duration_s': 30, 'generation_method': 'provider', 'provider_consent': True})
    assert response.status_code == 502
    assert response.json()['detail']['code'] == 'MUSIC_BAD_OUTPUT'
    assert list(tmp_path.rglob('provider_*')) == []
