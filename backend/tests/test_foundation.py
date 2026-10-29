import numpy as np
import soundfile as sf
from fastapi.testclient import TestClient
from mixverse.audio_io import SR, load_audio, peak_db, write_wav
from mixverse.config import Settings
from mixverse.mixscript import AudioClip, BeatClip, MixScript
from mixverse.store import ProjectStore, ProjectNotFound
from mixverse.api import create_app
from mixverse.testing.synth import tone, groove


def test_audio_roundtrip(tmp_path):
    p = tmp_path / "mono.wav"
    sf.write(p, np.zeros(SR, np.float32), SR)
    audio = load_audio(p)
    assert audio.shape == (2, SR)


def test_store_roundtrip_and_pid_validation(tmp_path):
    store = ProjectStore(tmp_path)
    p = store.create("create")
    assert store.load(p.id).versions[0].id == "v0"
    try:
        store.load("../x")
        assert False
    except ProjectNotFound:
        pass


def test_mixscript_discriminator_and_muted_length():
    s = MixScript(clips=[BeatClip(id="c1", lane="Beat", style="house", length_bars=8), AudioClip(id="c2", lane="A", source_id="A", length_bars=4, muted=True)])
    assert s.total_bars() == 8 and s.clip("c1").kind == "beat"


def test_project_api(tmp_path):
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    assert client.get("/api/health").json()["ok"]
    p = client.post("/api/projects", json={"mode": "create"})
    assert p.status_code == 201
    assert client.get(f"/api/projects/{p.json()['id']}").status_code == 200


def test_synth_stereo():
    assert tone([440], 0.25).shape == (2, round(SR * 0.25))
    assert groove(120, 2, "house")[0].shape[0] == 2
