from __future__ import annotations
import argparse
import json
import time
import urllib.error
import urllib.request

def req(base, path, method="GET", body=None):
    data=json.dumps(body).encode() if body is not None else None
    r=urllib.request.Request(base.rstrip('/')+path,data=data,method=method,headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(r,timeout=30) as x:return x.status,json.loads(x.read())

def main():
    p=argparse.ArgumentParser();p.add_argument('--base-url',required=True);a=p.parse_args()
    start=time.perf_counter();status,h=req(a.base_url,'/api/health');assert status==200 and h['ok']
    _,caps=req(a.base_url,'/api/creator/capabilities');assert caps['modes']['text_music']['enabled']
    _,project=req(a.base_url,'/api/projects','POST',{'mode':'create'})
    _,preview=req(a.base_url,f"/api/projects/{project['id']}/creator/text-music",'POST',{'prompt':'lofi rain','duration_s':15,'bpm':80})
    with urllib.request.urlopen(a.base_url.rstrip('/')+preview['audio_url'],timeout=30) as response:
        audio=response.read();assert audio[:4]==b'RIFF'
    print(f"PASS health + creator local audio; {len(audio)} bytes in {time.perf_counter()-start:.2f}s")

if __name__=='__main__':main()
