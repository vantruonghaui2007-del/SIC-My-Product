import numpy as np
from ..audio_io import SR

def render_ambience(kind: str, seconds: float, seed: int = 0) -> np.ndarray:
    n=max(1,round(seconds*SR)); rng=np.random.default_rng(seed); white=rng.standard_normal(n).astype(np.float32)
    if kind=="rain":
        kernel=np.ones(24,dtype=np.float32)/24; x=np.convolve(white,kernel,mode="same")
    elif kind=="vinyl":
        x=white*.01
    elif kind=="ocean":
        x=np.cumsum(white)*.001
        x*=.6+.4*np.sin(2*np.pi*np.arange(n)/SR/8)
    else: raise ValueError("Ambience không được hỗ trợ.")
    fade=min(round(.05*SR),n//2)
    if fade:
        x[:fade]*=np.linspace(0,1,fade); x[-fade:]*=np.linspace(1,0,fade)
    x=x/(np.sqrt(np.mean(x*x))+1e-9)*10**(-20/20)
    return np.repeat(x[None,:],2,axis=0).astype(np.float32)
