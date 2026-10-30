import io
import zipfile

from fastapi.testclient import TestClient

from mixverse.api import create_app
from mixverse.config import Settings


def client(tmp_path):
    c = TestClient(create_app(Settings(data_dir=tmp_path)))
    return c, c.post('/api/projects', json={'mode': 'create'}).json()['id']


def test_recipe_endpoint_reports_what_it_understood(tmp_path):
    c, _ = client(tmp_path)
    r = c.post('/api/creator/recipe', json={'prompt': 'nhạc buồn có tiếng mưa, piano, 90 bpm'})
    assert r.status_code == 200
    body = r.json()
    assert body['recipe']['mood'] == 'sad' and body['recipe']['ambience'] == 'rain' and body['recipe']['bpm'] == 90
    assert {'kind': 'tempo', 'label': '90 BPM', 'source': '90 bpm'} in body['detected']
    options = c.get('/api/creator/music-options').json()
    assert {g['id'] for g in options['genres']} >= {'lofi', 'trap', 'cinematic'}


def test_local_text_music_takes_stems_and_midi(tmp_path):
    c, pid = client(tmp_path)
    r = c.post(f'/api/projects/{pid}/creator/text-music', json={'prompt': 'lofi chill có tiếng mưa', 'duration_s': 15, 'takes': 3, 'seed': 7})
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body['takes']) == 3 and body['detected']
    labels = {t['metadata']['label'] for t in body['takes']}
    assert len(labels) == 3 and all(l.startswith('Phương án') for l in labels)
    take = body['takes'][0]
    assert len(take['peaks']) == 400 and take['metadata']['key'] and take['metadata']['sections']
    assert c.get(take['audio_url']).content[:4] == b'RIFF'
    assert c.get(take['audio_url'] + '/download/mp3').status_code == 200
    midi = c.get(take['midi_url'])
    assert midi.status_code == 200 and midi.content[:4] == b'MThd' and '.mid' in midi.headers['content-disposition']
    stem_ids = [s['id'] for s in take['stems']]
    assert stem_ids == ['drums', 'bass', 'harmony', 'melody', 'ambience']
    drums = c.get(take['stems'][0]['url'])
    assert drums.status_code == 200 and drums.content[:4] == b'RIFF'
    archive = zipfile.ZipFile(io.BytesIO(c.get(take['stems_url']).content))
    names = archive.namelist()
    assert sum(n.endswith('.wav') for n in names) == 5 and any(n.endswith('.mid') for n in names)
    record = c.get(f"/api/projects/{pid}/creator/compositions/{take['composition_id']}").json()
    assert record['seed'] == 7 and record['recipe']['genre'] == 'lofi'


def test_explicit_recipe_overrides_prompt_and_is_validated(tmp_path):
    c, pid = client(tmp_path)
    recipe = c.post('/api/creator/recipe', json={'prompt': 'lofi'}).json()['recipe']
    recipe.update(genre='trap', mood='dark', bpm=140, key='F#', mode='minor', duration_s=15, instruments=['bell', 'bass'], ambience='none')
    r = c.post(f'/api/projects/{pid}/creator/text-music', json={'prompt': 'ignored', 'recipe': recipe, 'seed': 1})
    assert r.status_code == 200, r.text
    meta = r.json()['takes'][0]['metadata']
    assert meta['key'] == 'F# minor' and meta['bpm'] == 140 and 'ambience' not in meta['stems']
    bad = dict(recipe, duration_s=600)
    r = c.post(f'/api/projects/{pid}/creator/text-music', json={'prompt': '', 'recipe': bad})
    assert r.status_code == 422 and 'Thời lượng' in r.json()['detail']
    assert c.get(f'/api/projects/{pid}/creator/compositions/m_{"0" * 32}/midi').status_code == 404
    assert c.get(f'/api/projects/{pid}/creator/compositions/../midi').status_code == 404
