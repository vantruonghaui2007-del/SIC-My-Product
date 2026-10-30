import numpy as np
import pytest

from mixverse.audio_io import SR
from mixverse.music import Recipe, compose, parse_prompt, render, to_midi
from mixverse.music.compose import plan_sections
from mixverse.music.theory import chord_name, diatonic_chord, pitch_class, scale_pcs


def kinds(parsed, kind):
    return [d for d in parsed.detected if d.kind == kind]


def test_vietnamese_demo_prompt_is_understood():
    parsed = parse_prompt("Tạo một đoạn nhạc lofi 30 giây, có tiếng mưa, piano nhẹ nhàng và trống xuất hiện ở đoạn giữa")
    r = parsed.recipe
    assert r.genre == "lofi" and r.mood == "chill"
    assert r.duration_s == 30 and r.ambience == "rain"
    assert "piano" in r.instruments and "bass" in r.instruments
    assert r.drums and r.drums_entry == "middle"
    assert kinds(parsed, "genre")[0].source == "lofi"


def test_prompt_without_diacritics_and_english():
    r = parse_prompt("nhac buon, tieng mua, piano va violin, cham").recipe
    assert r.mood == "sad" and r.mode == "minor" and r.ambience == "rain"
    assert {"piano", "strings"} <= set(r.instruments)
    assert r.bpm < 72  # "chậm" slows the ballad default
    r = parse_prompt("epic cinematic trailer in D minor at 100 bpm, no drums").recipe
    assert (r.genre, r.mood, r.key, r.mode, r.bpm, r.drums) == ("cinematic", "epic", "D", "minor", 100, False)


def test_ambiguous_words_need_diacritics():
    r = parse_prompt("tôi muốn một bản nhạc trong trẻo").recipe
    assert r.mood != "dark" and r.drums_entry == "start"
    assert parse_prompt("nhạc tối và u ám").recipe.mood == "dark"


def test_key_detection_variants():
    assert parse_prompt("ballad Am").recipe.key_name == "A minor"
    assert parse_prompt("pop đô trưởng").recipe.key_name == "C major"
    assert parse_prompt("house in Bb major").recipe.key == "A#"


def test_limits_are_clamped_with_notes():
    parsed = parse_prompt("trap 300 bpm 10 phut")
    assert parsed.recipe.bpm == 180 and parsed.recipe.duration_s == 120 and len(parsed.notes) == 2


def test_theory_basics():
    assert scale_pcs(pitch_class("A"), "minor") == [9, 11, 0, 2, 4, 5, 7]
    assert chord_name(diatonic_chord(0, "major", 2, True)) == "Dm7"
    assert chord_name(diatonic_chord(0, "major", 5, True)) == "G7"
    assert chord_name(diatonic_chord(0, "major", 1, True)) == "Cmaj7"


@pytest.mark.parametrize("bars", [4, 7, 10, 16, 23, 40])
def test_sections_cover_every_bar(bars):
    sections = plan_sections(bars)
    assert sections[0].label == "intro" and sections[-1].label == "outro"
    assert sum(s.bars for s in sections) == bars
    assert all(a.start_bar + a.bars == b.start_bar for a, b in zip(sections, sections[1:]))
    assert any(s.label == "chorus" for s in sections)


def test_composition_is_deterministic_and_in_key():
    recipe = Recipe(genre="pop", mood="happy", bpm=110, key="G", mode="major", duration_s=30, instruments=["piano", "bass", "lead"])
    a, b, c = compose(recipe, 1), compose(recipe, 1), compose(recipe, 2)
    assert [(n.midi, n.start) for n in a.notes] == [(n.midi, n.start) for n in b.notes]
    assert [(n.midi, n.start) for n in a.notes] != [(n.midi, n.start) for n in c.notes]
    scale = set(scale_pcs(pitch_class("G"), "major"))
    assert all(n.midi % 12 in scale for n in a.notes)
    assert {"chords", "melody", "bass"} <= set(a.parts)
    assert a.summary()["key"] == "G major" and len(a.summary()["progression"]) == 4


def test_drums_enter_in_the_middle():
    recipe = parse_prompt("lofi 30 giây, trống vào ở đoạn giữa").recipe
    comp = compose(recipe, 0)
    first_hit_bar = min(h.start for h in comp.hits) / 4
    assert first_hit_bar >= comp.bars // 2 - 1


def test_render_produces_loud_stereo_mix_and_stems():
    recipe = parse_prompt("lofi chill 15 giây có tiếng mưa").recipe
    comp = compose(recipe, 3)
    master, stems = render(comp)
    assert master.shape[0] == 2 and master.dtype == np.float32
    assert master.shape[1] / SR == pytest.approx(comp.duration_s + 3, abs=.2)
    assert {"drums", "bass", "harmony", "melody", "ambience"} <= set(stems)
    assert .5 < float(np.max(np.abs(master))) <= .9
    assert all(np.isfinite(s).all() for s in stems.values())


def test_midi_export_has_a_track_per_part():
    comp = compose(parse_prompt("edm sôi động").recipe, 0)
    data = to_midi(comp)
    assert data[:4] == b"MThd"
    tracks = int.from_bytes(data[10:12], "big")
    assert tracks == 1 + len(comp.parts) + 1
    assert data.count(b"MTrk") == tracks
