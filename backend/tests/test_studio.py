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
    assert patch.status_code==201 and len(patch.json()['script']['clips'])==1
    assert c.get(f"/api/projects/{pid}/studio/versions/{patch.json()['id']}/ab").status_code==200
