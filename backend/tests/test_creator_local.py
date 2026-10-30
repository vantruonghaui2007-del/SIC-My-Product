import io
import numpy as np
import soundfile as sf
from fastapi.testclient import TestClient
from mixverse.api import create_app
from mixverse.config import Settings
from mixverse.audio_io import SR


def wav_bytes(seconds=12):
    t=np.arange(round(seconds*SR))/SR
    x=(.2*np.sin(2*np.pi*180*t)).astype(np.float32)
    b=io.BytesIO(); sf.write(b,x,SR,format='WAV'); return b.getvalue()

def project(client): return client.post('/api/projects',json={'mode':'create'}).json()['id']

def test_local_creator_text_music_is_real_audio(tmp_path):
    c=TestClient(create_app(Settings(data_dir=tmp_path)))
    pid=project(c)
    r=c.post(f'/api/projects/{pid}/creator/text-music',json={'prompt':'lofi piano rain','duration_s':15,'bpm':80})
    assert r.status_code==200 and 'chưa phải mô hình sinh nhạc AI' in r.json()['metadata']['warning']
    audio=c.get(r.json()['audio_url'])
    assert audio.status_code==200 and audio.content[:4]==b'RIFF'

def test_upload_sound_and_use_same_sample(tmp_path):
    c=TestClient(create_app(Settings(data_dir=tmp_path))); pid=project(c)
    r=c.post(f'/api/projects/{pid}/creator/assets',data={'kind':'sound','rights_confirmed':'true'},files={'file':('clap.wav',wav_bytes(.3),'audio/wav')})
    assert r.status_code==202, r.text
    aid=r.json()['id']
    p=c.post(f'/api/projects/{pid}/creator/sounds/{aid}/preview',json={'role':'texture','bpm':100})
    assert p.status_code==200 and p.json()['metadata']['source_sha256']==r.json()['sha256']
    assert c.get(p.json()['audio_url']).content[:4]==b'RIFF'

def test_vocal_requires_rights_and_timing_locked(tmp_path):
    c=TestClient(create_app(Settings(data_dir=tmp_path))); pid=project(c)
    no=c.post(f'/api/projects/{pid}/creator/assets',data={'kind':'vocal','rights_confirmed':'false'},files={'file':('rap.wav',wav_bytes(),'audio/wav')})
    assert no.status_code==422
    up=c.post(f'/api/projects/{pid}/creator/assets',data={'kind':'vocal','rights_confirmed':'true'},files={'file':('rap.wav',wav_bytes(),'audio/wav')})
    assert up.status_code==202
    aid=up.json()['id']
    assert c.post(f'/api/projects/{pid}/creator/assets/{aid}/analyze').json()['needs_confirmation']
    beat=c.post(f'/api/projects/{pid}/creator/rap/{aid}/preview',json={'bpm':140,'style':'trap'})
    assert beat.status_code==200 and beat.json()['metadata']['lock_timing']

def test_provider_request_shapes_are_intent_specific():
    from mixverse.creator.providers.eleven_music import ElevenMusicProvider
    inst=ElevenMusicProvider.body('text_music','dark lofi',15000)
    song=ElevenMusicProvider.body('text_song','',30,'Xin chào Việt Nam','pop','warm')
    assert inst['force_instrumental'] and 'composition_plan' not in inst
    assert 'composition_plan' in song and 'prompt' not in song and 'music_length_ms' not in song
    assert 'Xin chào Việt Nam' in song['composition_plan']['chunks'][0]['text']

def test_provider_disabled_and_consent_required(tmp_path):
    c=TestClient(create_app(Settings(data_dir=tmp_path)))
    pid=project(c)
    assert not c.get('/api/creator/capabilities').json()['modes']['text_music']['provider_enabled']
    denied=c.post(f'/api/projects/{pid}/creator/text-music',json={'prompt':'ambient','duration_s':15,'generation_method':'provider','provider_consent':True})
    assert denied.status_code==503
    configured=TestClient(create_app(Settings(data_dir=tmp_path/'configured',music_api_key='test-key',music_provider='elevenlabs')))
    pid2=project(configured)
    assert configured.get('/api/creator/capabilities').json()['modes']['text_music']['provider_enabled']
    denied=configured.post(f'/api/projects/{pid2}/creator/text-music',json={'prompt':'ambient','duration_s':15,'generation_method':'provider'})
    assert denied.status_code==422 and 'đồng ý' in denied.text

def test_three_rap_takes_are_unique_and_exportable(tmp_path):
    c=TestClient(create_app(Settings(data_dir=tmp_path)));pid=project(c)
    up=c.post(f'/api/projects/{pid}/creator/assets',data={'kind':'vocal','rights_confirmed':'true'},files={'file':('rap.wav',wav_bytes(),'audio/wav')})
    aid=up.json()['id']
    r=c.post(f'/api/projects/{pid}/creator/rap/{aid}/takes',json={'bpm':140,'style':'trap'})
    assert r.status_code==200 and len(r.json()['takes'])==3
    assert len({t['metadata']['label'] for t in r.json()['takes']})==3
    assert all(c.get(t['audio_url']).status_code==200 for t in r.json()['takes'])
    assert c.get(r.json()['takes'][0]['audio_url']+'/download/mp3').status_code==200
    assert c.get(f'/api/projects/{pid}/creator/credits').status_code==200


def test_rap_tempo_candidates_follow_the_material():
    from mixverse.creator.service import tempo_candidates
    from mixverse.testing.synth import click_track
    clicks=click_track(96,12)[0]
    candidates=tempo_candidates(clicks)
    assert candidates and abs(candidates[0][0]-96)<=3
    assert candidates[0][1]==1.0
