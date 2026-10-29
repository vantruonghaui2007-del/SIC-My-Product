import numpy as np
from ..audio_io import SR

def render_beat(style: str, bpm: float, bars: float, seed: int = 0) -> np.ndarray:
    n = max(1, round(bars * 240 / bpm * SR))
    out = np.zeros((2,n), np.float32)
    rng=np.random.default_rng(seed)
    step=60/bpm/4
    patterns={"house":([0,4,8,12],[4,12],[2,6,10,14]),"edm":([0,4,8,12],[4,12],list(range(16))),"lofi":([0,10],[4,12],list(range(0,16,2))),"trap":([0,7,10],[8],list(range(16))),"pop":([0,8,10],[4,12],list(range(0,16,2)))}
    kick,snare,hat=patterns.get(style,patterns["lofi"])
    total_steps=int(np.ceil(bars*16))
    for s in range(total_steps):
        pos=round(s*step*SR)
        if pos>=n: continue
        barstep=s%16
        if barstep in kick:
            length=min(round(.12*SR),n-pos); t=np.arange(length)/SR
            sig=.6*np.sin(2*np.pi*(85*np.exp(-t/.04)+42)*t)*np.exp(-t*28)
            out[:,pos:pos+length]+=sig.astype(np.float32)
        if barstep in snare:
            length=min(round(.09*SR),n-pos); noise=rng.standard_normal(length).astype(np.float32)*np.exp(-np.arange(length)/(SR*.025))*.16
            out[:,pos:pos+length]+=noise
        if barstep in hat:
            length=min(round(.025*SR),n-pos); noise=rng.standard_normal(length).astype(np.float32)*np.exp(-np.arange(length)/(SR*.006))*.035
            out[:,pos:pos+length]+=noise
    peak=max(float(np.max(np.abs(out))),1e-8)
    return (out*(.5/peak)).astype(np.float32)
