import io
import numpy as np
import soundfile as sf
from fastapi.testclient import TestClient
from mixverse.api import create_app
from mixverse.config import Settings
from mixverse.audio_io import SR

def song_bytes(seconds=10):
    t=np.arange(seconds*SR)/SR;x=(.1*np.sin(2*np.pi*220*t)).astype(np.float32);b=io.BytesIO();sf.write(b,x,SR,format='WAV');return b.getvalue()

def test_remix_source_prompt_render_and_exports(tmp_path):
    c=TestClient(create_app(Settings(data_dir=tmp_path)))
    p=c.post('/api/projects',json={'mode':'remix'}).json();pid=p['id']
    up=c.post(f'/api/projects/{pid}/sources/upload',data={'rights_confirmed':'true'},files={'file':('source.wav',song_bytes(),'audio/wav')})
    assert up.status_code==200,up.text
    r=c.post(f'/api/projects/{pid}/prompts',json={'text':'Thêm beat lofi'})
    assert r.status_code==201,r.text
    assert r.json()['render']=='ready'
    assert c.get(f"/api/projects/{pid}/studio/versions/{r.json()['id']}/audio").content[:4]==b'RIFF'
    assert c.get(f"/api/projects/{pid}/studio/exports/{r.json()['id']}/mp3").status_code==200

def test_mashup_accepts_two_sources_and_combo_patch(tmp_path):
    c=TestClient(create_app(Settings(data_dir=tmp_path)));pid=c.post('/api/projects',json={'mode':'mashup'}).json()['id']
    for i in range(2):
        r=c.post(f'/api/projects/{pid}/sources/upload',data={'rights_confirmed':'true'},files={'file':(f'{i}.wav',song_bytes(),'audio/wav')})
        assert r.status_code==200,r.text
    patch=c.post(f'/api/projects/{pid}/prompts',json={'text':'Thêm beat house 120 BPM'})
    assert patch.status_code==201
    clips=patch.json()['script']['clips']
    assert [c['kind'] for c in clips]==['audio','audio','beat'] and {c['source_id'] for c in clips if c['kind']=='audio'}=={'A','B'}
    assert c.get(f"/api/projects/{pid}/studio/versions/{patch.json()['id']}/ab").status_code==200


def test_manual_edit_creates_rendered_version(tmp_path):
    c=TestClient(create_app(Settings(data_dir=tmp_path)));pid=c.post('/api/projects',json={'mode':'remix'}).json()['id']
    c.post(f'/api/projects/{pid}/sources/upload',data={'rights_confirmed':'true'},files={'file':('s.wav',song_bytes(),'audio/wav')})
    v=c.post(f'/api/projects/{pid}/prompts',json={'text':'Thêm beat trap'}).json()
    beat=next(x for x in v['script']['clips'] if x['kind']=='beat')
    edit=c.post(f'/api/projects/{pid}/studio/edits',json={'clip_id':beat['id'],'gain_db':-12})
    assert edit.status_code==200 and edit.json()['render_file'] and len(edit.json()['peaks'])==1000
    assert c.get(f"/api/projects/{pid}/studio/versions/{edit.json()['id']}/audio").content[:4]==b'RIFF'


def test_source_is_time_stretched_to_project_tempo(tmp_path):
    from mixverse.api.studio import source_at_tempo
    from mixverse.audio_io import write_wav
    d=tmp_path/'A';d.mkdir();audio=np.zeros((2,SR*4),np.float32);audio[:,::SR//2]=1;write_wav(d/'mix.wav',audio,'FLOAT')
    faster=source_at_tempo(d,120,150)
    assert abs(faster.shape[1]-SR*4*120/150)<SR*.05 and (d/'mix_150.wav').is_file()
    assert source_at_tempo(d,120,120.5).shape[1]==SR*4
