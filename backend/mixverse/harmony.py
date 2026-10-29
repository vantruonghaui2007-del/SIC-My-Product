import math

def tempo_match(src_bpm: float, target_bpm: float):
    choices = [(m, target_bpm/(src_bpm*m)) for m in (1, .5, 2)]
    m, stretch = min(choices, key=lambda x: abs(math.log(x[1])))
    return type("TempoMatch", (), {"multiplier": m, "stretch": stretch, "warning": not .8 <= stretch <= 1.25})()

def mashup_target_bpm(a_bpm: float, b_bpm: float) -> float:
    m = tempo_match(b_bpm, a_bpm).multiplier
    return round(2 * math.sqrt(a_bpm * b_bpm * m)) / 2
