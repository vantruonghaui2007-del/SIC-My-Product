from __future__ import annotations
import uuid
import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
from fastapi import APIRouter, HTTPException, Request
from fastapi import UploadFile, File, Form
from pydantic import BaseModel
from ..mixscript import MixScript, Version, AudioClip, BeatClip, AmbienceClip, Source, SourceAnalysis
from ..store import version as get_version
from ..analysis.grid import estimate_grid
from ..audio_io import SR, rms_db, load_audio, write_wav, encode_mp3, waveform_peaks
from ..harmony import mashup_target_bpm
from ..sound import render_beat

router=APIRouter()

def get_project(request,pid):
    try:return request.app.state.store.load(pid)
    except Exception as e:raise HTTPException(404,"Không tìm thấy dự án.") from e

class MixRequest(BaseModel):
    mode:str="remix"
    prompt:str=""
    bpm:float=120
    style:str="house"

@router.post("/projects/{pid}/studio/patch")
def studio_patch(pid:str,body:MixRequest,request:Request):
    p=get_project(request,pid); store=request.app.state.store
    base=get_version(p,p.head); script=base.script.model_copy(deep=True)
    script.bpm=max(60,min(180,body.bpm))
    if body.mode=="add_beat":
        from ..mixscript import BeatClip
        script.clips.append(BeatClip(id=script.next_id('c'),lane='Beat',style=body.style,start_bar=0,length_bars=8,gain_db=-8))
    elif body.mode=="add_sample":
        raise HTTPException(422,"Dùng endpoint Sound-to-Music để xử lý sample.")
    elif body.mode!="tempo": raise HTTPException(422,"Thao tác studio chưa được hỗ trợ.")
    return commit_version(p,script,store,pid,prompt=body.prompt,provider='manual')

def commit_version(p,script,store,pid,prompt,provider,cards=None,selection=None):
    """Render ``script`` and append it as the new head version (every version has audio)."""
    vid='v_'+uuid.uuid4().hex[:10]
    v=Version(id=vid,parent=p.head,prompt=prompt,selection=selection,provider=provider,status='kept',script=script,cards=cards or [],render='pending')
    try:audio=render_script_audio(p,script,store,pid)
    except Exception as e:raise HTTPException(422,f"Không dựng được bản phối: {e}") from e
    path=store.render_dir(pid);path.mkdir(parents=True,exist_ok=True);dest=path/f"{vid}.wav";write_wav(dest,audio,'PCM_24')
    v.render_file=str(dest.relative_to(store.project_dir(pid)));v.render='ready';v.peaks=waveform_peaks(audio,1000)
    p.versions.append(v);p.head=vid;store.save(p);return v

@router.post("/projects/{pid}/sources/upload")
async def upload_source(pid:str,request:Request,file:UploadFile=File(...),rights_confirmed:bool=Form(...)):
    p=get_project(request,pid);store=request.app.state.store
    if not rights_confirmed:raise HTTPException(422,"Vui lòng xác nhận quyền sử dụng tệp.")
    if len(p.sources)>=(2 if p.mode=='mashup' else 1):raise HTTPException(422,"Đã đủ số nguồn cho dự án.")
    data=await file.read(request.app.state.settings.max_upload_mb*1024*1024+1)
    if len(data)>request.app.state.settings.max_upload_mb*1024*1024:raise HTTPException(413,"Tệp quá lớn.")
    sid=chr(ord('A')+len(p.sources));directory=store.source_dir(pid,sid);directory.mkdir(parents=True,exist_ok=True)
    original=directory/'upload';original.write_bytes(data)
    try:audio=load_audio(original)
    except Exception as e:original.unlink(missing_ok=True);raise HTTPException(422,"Không giải mã được âm thanh.") from e
    duration=audio.shape[1]/SR
    if duration<8 or duration>360:original.unlink(missing_ok=True);raise HTTPException(422,"Nguồn bài hát phải dài từ 8 đến 360 giây.")
    if rms_db(audio)<-65:original.unlink(missing_ok=True);raise HTTPException(422,"Tệp âm thanh im lặng.")
    write_wav(directory/'mix.wav',audio,'FLOAT')
    grid=estimate_grid(audio)
    bpm=round(grid.bpm,1) if grid.bpm else 120
    n_bars=max(1,int(duration*bpm/240))
    analysis=SourceAnalysis(duration_s=duration,bpm=grid.bpm,beats_s=grid.beats_s,downbeats_s=grid.downbeats_s,n_bars=n_bars,warnings=[] if grid.bpm else ["Chưa xác định BPM; đang dùng lưới 120 BPM làm mốc tạm."])
    source=Source(id=sid,name=Path(file.filename or sid).stem,sha256=hashlib.sha256(data).hexdigest(),rights_confirmed=True,status='ready',analysis=analysis)
    p.sources.append(source)
    if p.head=='v0' and p.mode=='remix':
        script=MixScript(bpm=bpm,clips=[AudioClip(id='c1',lane='Mix',source_id=sid,src_start_bar=0,start_bar=0,length_bars=n_bars)])
        p.versions[0].script=script
    elif p.head=='v0' and p.mode=='mashup':
        script=p.versions[0].script
        if len(p.sources)==1:script.bpm=bpm
        else:
            known=[s.analysis.bpm for s in p.sources if s.analysis and s.analysis.bpm]
            if len(known)==2:script.bpm=mashup_target_bpm(*known)
        # The second song sits a little lower so the first one stays the lead.
        script.clips.append(AudioClip(id=script.next_id('c'),lane=f"Nguồn {sid}",source_id=sid,start_bar=0,length_bars=n_bars,gain_db=0 if sid=='A' else -4))
    store.save(p)
    return source

class PromptBody(BaseModel):
    text:str
    selection:dict|None=None

@router.post("/projects/{pid}/prompts",status_code=201)
def prompt(pid:str,body:PromptBody,request:Request):
    p=get_project(request,pid);store=request.app.state.store
    text=body.text.strip()
    if not text or len(text)>500:raise HTTPException(422,"Câu lệnh cần từ 1 đến 500 ký tự.")
    base=get_version(p,p.head);script=base.script.model_copy(deep=True);cards=[]
    folded=text.lower().replace('đ','d')
    nums=re.findall(r"\d+(?:\.\d+)?",text)
    lower=folded
    if ('bpm' in lower or 'tempo' in lower) and nums:
        old=script.bpm;script.bpm=max(60,min(180,float(nums[0])));cards.append({"kind":"tempo","title":f"Tempo {old:g} → {script.bpm:g} BPM","detail":"Đổi tempo dự án","start_bar":0,"end_bar":script.total_bars()})
    styles=('house','edm','lofi','trap','pop')
    style=next((s for s in styles if s in lower),None)
    if style and ('beat' in lower or 'trống' in lower or not p.sources):
        length=max(4,script.total_bars() or 8);clip=BeatClip(id=script.next_id('c'),lane='Beat',style=style,start_bar=0,length_bars=length,gain_db=-8);script.clips.append(clip);cards.append({"kind":"add","title":f"Thêm beat {style}","detail":f"Beat {style} ô 1–{length:g}","start_bar":0,"end_bar":length})
    if any(x in lower for x in ('mua','rain','vinyl','bien','ocean')):
        kind='rain' if 'mua' in lower or 'rain' in lower else 'vinyl' if 'vinyl' in lower else 'ocean'
        length=max(4,script.total_bars() or 8);clip=AmbienceClip(id=script.next_id('c'),lane='Nền',ambience=kind,start_bar=0,length_bars=length,gain_db=-18);script.clips.append(clip)
        cards.append({"kind":"add","title":f"Thêm ambience {kind}","detail":f"Lớp {kind} ô 1–{length:g}","start_bar":0,"end_bar":length})
    if any(word in lower for word in ('giam','reduce')) and ('gain' in lower or 'volume' in lower or 'am luong' in lower):
        clip=next((c for c in script.clips if c.kind=='beat'),None)
        if clip:
            amount=3 if not nums else min(12,float(nums[0]));old=clip.gain_db;clip.gain_db=max(-24,old-amount)
            cards.append({"kind":"gain","title":f"Giảm beat {amount:g} dB","detail":f"Âm lượng beat {old:g} → {clip.gain_db:g} dB","start_bar":clip.start_bar,"end_bar":clip.start_bar+clip.length_bars})
    if not cards:raise HTTPException(422,{"detail":"Chưa hiểu câu lệnh này. Hãy thử đổi BPM hoặc thêm beat house/lofi/trap.","examples":["Thêm beat lofi","Đổi tempo sang 100 BPM","Thêm beat trap 120 BPM"]})
    return commit_version(p,script,store,pid,prompt=text,provider='rules',cards=cards,selection=body.selection)

def render_script_audio(project,script,store,pid):
    end=max(script.total_bars(),1);n=round(end*script.bar_s()*SR);mix=np.zeros((2,n),np.float32)
    for clip in script.clips:
        if clip.muted:continue
        start=round(clip.start_bar*script.bar_s()*SR)
        length=min(n-start,round(clip.length_bars*script.bar_s()*SR))
        if length<=0:continue
        if clip.kind=='beat':audio=render_beat(clip.style,script.bpm,clip.length_bars,seed=0)*10**(clip.gain_db/20)
        elif clip.kind=='ambience':
            from ..sound import render_ambience
            audio=render_ambience(clip.ambience,clip.length_bars*script.bar_s(),seed=0)*10**(clip.gain_db/20)
        elif clip.kind=='audio':
            src=next((s for s in project.sources if s.id==clip.source_id),None)
            if src is None:continue
            audio=source_at_tempo(store.source_dir(pid,clip.source_id),src.analysis.bpm if src.analysis else 0,script.bpm)
            a=round(clip.src_start_bar*script.bar_s()*SR);audio=audio[:,a:min(audio.shape[1],a+length)]
            if audio.shape[1]<length:audio=np.pad(audio,((0,0),(0,length-audio.shape[1])))
            audio=audio*10**(clip.gain_db/20)
        elif clip.kind=='sample':
            asset_path=store.project_dir(pid)/'creator'/f"{clip.asset_id}.wav"
            if not asset_path.is_file():continue
            sample=load_audio(asset_path);audio=np.zeros((2,length),np.float32)
            if getattr(clip,'event_beats',None):
                for beat_i,vel in zip(clip.event_beats,clip.velocities):
                    pos=round((beat_i*60/script.bpm)*SR)
                    if 0<=pos<length:
                        count=min(sample.shape[1],length-pos);audio[:,pos:pos+count]+=sample[:,:count]*vel
            else:
                reps=int(np.ceil(length/sample.shape[1]));audio=np.tile(sample,(1,reps))[:,:length]
            audio*=10**(clip.gain_db/20)
        else:continue
        common=min(length,audio.shape[1]);mix[:,start:start+common]+=audio[:,:common]
    mix*=min(1,10**(-1/20)/max(float(np.max(np.abs(mix))),1e-9))
    return mix

def source_at_tempo(directory:Path,source_bpm:float,target_bpm:float):
    """Source audio time-stretched to the project tempo (cached per tempo)."""
    if not source_bpm or abs(target_bpm/source_bpm-1)<.015:return load_audio(directory/'mix.wav')
    rate=target_bpm/source_bpm
    while rate>1.5:rate/=2   # prefer half/double-time over extreme stretching
    while rate<.67:rate*=2
    cached=directory/f"mix_{target_bpm:g}.wav"
    if cached.is_file():return load_audio(cached)
    import librosa
    audio=load_audio(directory/'mix.wav')
    stretched=np.stack([librosa.effects.time_stretch(ch,rate=rate) for ch in audio]).astype(np.float32)
    write_wav(cached,stretched,'FLOAT');return stretched

@router.get("/projects/{pid}/studio/head/audio")
def head_audio(pid:str,request:Request):
    p=get_project(request,pid)
    try:v=get_version(p,p.head)
    except StopIteration as e:raise HTTPException(404,"Chưa có bản phối.") from e
    if not v.render_file:raise HTTPException(404,"Bản phối chưa có audio.")
    return {"audio_url":f"/api/projects/{pid}/studio/versions/{v.id}/audio"}

@router.get("/projects/{pid}/studio/versions/{vid}/audio")
def version_audio(pid:str,vid:str,request:Request):
    p=get_project(request,pid)
    try:v=get_version(p,vid)
    except StopIteration as e:raise HTTPException(404,"Không tìm thấy phiên bản.") from e
    path=request.app.state.store.project_dir(pid)/v.render_file
    if not path.is_file():raise HTTPException(404,"Không có audio đã render.")
    from fastapi.responses import FileResponse
    return FileResponse(path,media_type='audio/wav')

class EditBody(BaseModel):
    clip_id:str
    gain_db:float|None=None
    muted:bool|None=None

@router.post("/projects/{pid}/studio/edits")
def edit(pid:str,body:EditBody,request:Request):
    p=get_project(request,pid); base=get_version(p,p.head); script=base.script.model_copy(deep=True)
    try:clip=script.clip(body.clip_id)
    except StopIteration as e:raise HTTPException(404,"Không tìm thấy clip.") from e
    if body.gain_db is not None:clip.gain_db=max(-24,min(6,body.gain_db))
    if body.muted is not None:clip.muted=body.muted
    return commit_version(p,script,request.app.state.store,pid,prompt='Chỉnh tay',provider='manual')

@router.post("/projects/{pid}/studio/versions/{vid}/keep")
def keep_version(pid:str,vid:str,request:Request):
    p=get_project(request,pid)
    try:v=get_version(p,vid)
    except StopIteration as e:raise HTTPException(404,"Không tìm thấy phiên bản.") from e
    if v.render!='ready':raise HTTPException(409,"Bản phối chưa sẵn sàng.")
    v.status='kept';p.head=vid;request.app.state.store.save(p);return p

@router.post("/projects/{pid}/studio/versions/{vid}/discard")
def discard_version(pid:str,vid:str,request:Request):
    p=get_project(request,pid)
    try:v=get_version(p,vid)
    except StopIteration as e:raise HTTPException(404,"Không tìm thấy phiên bản.") from e
    v.status='discarded';request.app.state.store.save(p);return p

@router.post("/projects/{pid}/studio/head")
def set_head(pid:str,request:Request,body:dict):
    p=get_project(request,pid);vid=body.get('version_id')
    try:v=get_version(p,vid)
    except StopIteration as e:raise HTTPException(404,"Không tìm thấy phiên bản.") from e
    if v.status!='kept':raise HTTPException(409,"Chỉ có thể quay về phiên bản đã giữ.")
    p.head=vid;request.app.state.store.save(p);return p

@router.post("/projects/{pid}/undo")
def undo(pid:str,request:Request):
    p=get_project(request,pid)
    try:current=get_version(p,p.head)
    except StopIteration as e:raise HTTPException(409,"Không có phiên bản để hoàn tác.") from e
    if not current.parent:raise HTTPException(409,"Không còn phiên bản trước.")
    p.head=current.parent;request.app.state.store.save(p);return p

@router.get("/projects/{pid}/studio/versions/{vid}/ab")
def ab_info(pid:str,vid:str,request:Request):
    p=get_project(request,pid)
    try:v=get_version(p,vid)
    except StopIteration as e:raise HTTPException(404,"Không tìm thấy phiên bản.") from e
    parent=get_version(p,v.parent) if v.parent else None
    focus=min((c.start_bar for c in v.cards),default=0)
    return {"a_url":f"/api/projects/{pid}/studio/versions/{parent.id}/audio" if parent and parent.render_file else None,"b_url":f"/api/projects/{pid}/studio/versions/{vid}/audio","focus_bar":focus,"focus_time_s":focus*v.script.bar_s(),"level_match_db":0}

@router.get("/projects/{pid}/credits")
def credits(pid:str,request:Request):
    p=get_project(request,pid)
    return {"notice":"Chỉ dùng nguồn bạn có quyền sử dụng. Tách stem/generation có thể tạo artefact và tuân theo license/provider.","sources":[{"name":s.name,"sha256":s.sha256,"rights_confirmed":s.rights_confirmed,"uploaded_at":s.uploaded_at} for s in p.sources],"versions":[{"id":v.id,"prompt":v.prompt,"provider":v.provider,"cards":[c.title for c in v.cards]} for v in p.versions if v.status=='kept']}

@router.get("/projects/{pid}/studio/exports/{vid}/{fmt}")
def export(pid:str,vid:str,fmt:str,request:Request):
    if fmt not in {'wav','mp3'}:raise HTTPException(422,'Định dạng không hỗ trợ.')
    p=get_project(request,pid)
    try:v=get_version(p,vid)
    except StopIteration as e:raise HTTPException(404,'Không tìm thấy phiên bản.') from e
    if not v.render_file:raise HTTPException(409,'Bản phối chưa có audio.')
    src=request.app.state.store.project_dir(pid)/v.render_file
    audio=load_audio(src);dest=request.app.state.store.project_dir(pid)/f"mixverse_{vid}.{fmt}"
    if fmt=='wav':write_wav(dest,audio); 
    else:encode_mp3(src,dest,{'title':f'MIXVERSE {vid}','comment':'AI-assisted (MIXVERSE AI)'})
    from fastapi.responses import FileResponse
    return FileResponse(dest,filename=dest.name,media_type='audio/wav' if fmt=='wav' else 'audio/mpeg')
