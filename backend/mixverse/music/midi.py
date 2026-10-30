"""Standard MIDI File (type 1) export so compositions can continue in any DAW."""
from __future__ import annotations

import struct

from .compose import Composition

PPQ = 480
GM_PROGRAM = {
    "piano": 0, "epiano": 4, "guitar": 25, "pad": 89, "strings": 48, "bell": 14,
    "pluck": 45, "lead": 80, "flute": 73, "bass": 33, "bass808": 38,
}
GM_DRUM = {"kick": 36, "snare": 38, "clap": 39, "chat": 42, "ohat": 46, "rim": 37, "crash": 49}
PART_NAMES = {"chords": "Chords", "pad": "Pad", "melody": "Melody", "arp": "Arp", "bass": "Bass"}


def _vlq(value: int) -> bytes:
    out = [value & 0x7F]
    value >>= 7
    while value:
        out.append((value & 0x7F) | 0x80)
        value >>= 7
    return bytes(reversed(out))


def _track(events: list[tuple[int, bytes]]) -> bytes:
    events.sort(key=lambda e: (e[0], e[1][0] & 0xF0 == 0x90))  # note-offs before note-ons at the same tick
    body, last = bytearray(), 0
    for tick, data in events:
        body += _vlq(tick - last) + data
        last = tick
    body += b"\x00\xff\x2f\x00"
    return b"MTrk" + struct.pack(">I", len(body)) + bytes(body)


def _name(text: str) -> bytes:
    raw = text.encode("ascii", "replace")
    return b"\xff\x03" + _vlq(len(raw)) + raw


def to_midi(comp: Composition) -> bytes:
    tempo = round(60_000_000 / comp.bpm)
    conductor = [(0, _name("MIXVERSE")), (0, b"\xff\x51\x03" + tempo.to_bytes(3, "big")), (0, b"\xff\x58\x04\x04\x02\x18\x08")]
    tracks = [_track(conductor)]
    channel = 0
    for part, instrument in comp.parts.items():
        ch = channel if channel < 9 else channel + 1
        channel += 1
        events = [(0, _name(PART_NAMES.get(part, part))), (0, bytes([0xC0 | ch, GM_PROGRAM.get(instrument, 0)]))]
        for note in comp.notes:
            if note.part != part:
                continue
            on = round(note.start * PPQ)
            off = on + max(1, round(note.dur * PPQ))
            vel = max(1, min(127, round(note.vel * 110)))
            events += [(on, bytes([0x90 | ch, note.midi, vel])), (off, bytes([0x80 | ch, note.midi, 0]))]
        tracks.append(_track(events))
    if comp.hits:
        events = [(0, _name("Drums"))]
        for hit in comp.hits:
            on = round(hit.start * PPQ)
            key = GM_DRUM[hit.piece]
            events += [(on, bytes([0x99, key, max(1, min(127, round(hit.vel * 115)))])), (on + PPQ // 8, bytes([0x89, key, 0]))]
        tracks.append(_track(events))
    header = b"MThd" + struct.pack(">IHHH", 6, 1, len(tracks), PPQ)
    return header + b"".join(tracks)
