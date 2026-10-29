from __future__ import annotations
import json
import uuid
from pathlib import Path
from datetime import datetime, timezone
import re
import shutil
from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ..audio_io import write_wav
from ..creator.service import CreatorService
from ..creator.providers.eleven_music import ElevenMusicProvider, MusicProviderError
from ..audio_io import load_audio

router = APIRouter()

def service(request: Request) -> CreatorService:
    if not hasattr(request.app.state, "creator"):
        request.app.state.creator = CreatorService(request.app.state.settings.data_dir)
    return request.app.state.creator

def pid_ok(request: Request, pid: str):
    try: request.app.state.store.load(pid)
    except Exception as e: raise HTTPException(404, "Không tìm thấy dự án.") from e

@router.post("/projects/{pid}/creator/assets", status_code=202)
async def upload_asset(pid: str, request: Request, file: UploadFile=File(...), kind: str=Form(...), rights_confirmed: bool=Form(...)):
    pid_ok(request,pid)
    limit=request.app.state.settings.max_upload_mb*1024*1024
    data=await file.read(limit+1)
    if len(data)>limit: raise HTTPException(413,"Tệp vượt quá dung lượng cho phép.")
    try: return service(request).import_asset(pid,data,file.filename or "audio",kind,rights_confirmed)
    except ValueError as e: raise HTTPException(422,str(e)) from e

@router.get("/projects/{pid}/creator/assets/{aid}")
def get_asset(pid: str, aid: str, request: Request):
    pid_ok(request,pid)
    try: return service(request).asset(pid,aid)
    except FileNotFoundError as e: raise HTTPException(404,str(e)) from e

@router.get("/projects/{pid}/creator/assets/{aid}/audio")
def asset_audio(pid: str, aid: str, request: Request):
    pid_ok(request,pid)
    s=service(request)
    try:
        s.asset(pid,aid)
        return FileResponse(s.project_dir(pid)/f"{aid}.wav",media_type="audio/wav")
    except FileNotFoundError as e: raise HTTPException(404,str(e)) from e

@router.post("/projects/{pid}/creator/assets/{aid}/analyze")
def analyze(pid: str, aid: str, request: Request):
    pid_ok(request,pid)
    try: return service(request).analyze_vocal(pid,aid)
    except (FileNotFoundError,ValueError) as e: raise HTTPException(422,str(e)) from e

class GridConfirmation(BaseModel):
    bpm: float
    first_downbeat_s: float=0

@router.patch("/projects/{pid}/creator/assets/{aid}/grid")
def confirm_grid(pid: str, aid: str, body: GridConfirmation, request: Request):
    pid_ok(request,pid)
    if not 60<=body.bpm<=180 or body.first_downbeat_s<0:raise HTTPException(422,"BPM cần trong 60–180 và mốc phách không âm.")
    s=service(request)
    try:
        result=s.analyze_vocal(pid,aid)
        asset=s.asset(pid,aid)
        if body.first_downbeat_s>=asset.duration_s:raise HTTPException(422,"Mốc phách nằm ngoài tệp vocal.")
        result.update({"selected_bpm":body.bpm,"selected_downbeat_s":body.first_downbeat_s,"needs_confirmation":False,"confirmed":True,"confidence":"user_confirmed"})
        path=s.project_dir(pid)/f"{aid}.analysis.json";path.write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8')
        return result
    except FileNotFoundError as e:raise HTTPException(404,str(e)) from e

class RapRequest(BaseModel):
    bpm: float
    style: str="trap"
    first_downbeat_s: float=0
    variant: int=0

@router.post("/projects/{pid}/creator/rap/{aid}/preview")
def rap_preview(pid: str, aid: str, body: RapRequest, request: Request):
    pid_ok(request,pid)
    if body.style not in {"house","edm","lofi","trap","pop"}: raise HTTPException(422,"Thể loại không hợp lệ.")
    try:
        meta,audio=service(request).arrange_rap(pid,aid,body.bpm,body.style,body.first_downbeat_s,body.variant)
        out=service(request).project_dir(pid)/f"preview_{uuid.uuid4().hex}.wav"
        write_wav(out,audio,"PCM_24")
        return {"metadata":meta,"audio_url":f"/api/projects/{pid}/creator/previews/{out.name}"}
    except (FileNotFoundError,ValueError) as e: raise HTTPException(422,str(e)) from e

@router.post("/projects/{pid}/creator/rap/{aid}/takes")
def rap_takes(pid: str, aid: str, body: RapRequest, request: Request):
    pid_ok(request,pid)
    if body.style not in {"house","edm","lofi","trap","pop"}: raise HTTPException(422,"Thể loại không hợp lệ.")
    results=[]
    try:
        for index in range(3):
            meta,audio=service(request).arrange_rap(pid,aid,body.bpm,body.style,body.first_downbeat_s,index)
            out=service(request).project_dir(pid)/f"preview_{uuid.uuid4().hex}.wav"
            write_wav(out,audio,"PCM_24")
            results.append({"metadata":meta,"audio_url":f"/api/projects/{pid}/creator/previews/{out.name}"})
        return {"takes":results}
    except (FileNotFoundError,ValueError) as e: raise HTTPException(422,str(e)) from e

class SoundRequest(BaseModel):
    bpm: float=100
    role: str="percussion"

@router.post("/projects/{pid}/creator/sounds/{aid}/preview")
def sound_preview(pid: str, aid: str, body: SoundRequest, request: Request):
    pid_ok(request,pid)
    try:
        meta,audio=service(request).arrange_sound(pid,aid,body.bpm,body.role)
        out=service(request).project_dir(pid)/f"preview_{uuid.uuid4().hex}.wav"
        write_wav(out,audio,"PCM_24")
        return {"metadata":meta,"audio_url":f"/api/projects/{pid}/creator/previews/{out.name}"}
    except (FileNotFoundError,ValueError) as e: raise HTTPException(422,str(e)) from e

class TextMusicRequest(BaseModel):
    prompt: str
    duration_s: int=30
    bpm: float=80
    generation_method: str="loops"
    lyrics: str=""
    genre: str=""
    mood: str=""
    provider_consent: bool=False

@router.post("/projects/{pid}/creator/text-music")
def text_music(pid: str, body: TextMusicRequest, request: Request):
    pid_ok(request,pid)
    if body.generation_method=="provider":
        settings=request.app.state.settings
        if not settings.music_api_key or settings.music_provider!="elevenlabs":
            raise HTTPException(503,"Provider sinh nhạc chưa được cấu hình.")
        if body.lyrics and not body.provider_consent:
            raise HTTPException(422,"Cần đồng ý gửi lời bài hát tới nhà cung cấp.")
        if not body.lyrics and not body.provider_consent:
            raise HTTPException(422,"Cần đồng ý gửi prompt tới nhà cung cấp.")
        mode="text_song" if body.lyrics else "text_music"
        if mode=="text_song" and len(body.lyrics)>4000: raise HTTPException(422,"Lời bài hát vượt quá 4.000 ký tự.")
        s=service(request); out=s.project_dir(pid)/f"provider_{uuid.uuid4().hex}.mp3"
        try:
            provider=ElevenMusicProvider(settings.music_api_key,settings.music_model,settings.music_timeout_s)
            result=provider.generate(mode,body.prompt,body.duration_s,out,body.lyrics,body.genre,body.mood)
            # Validate/decode provider output before exposing it.
            pcm=load_audio(out)
            wav=out.with_suffix('.wav'); write_wav(wav,pcm,'PCM_24')
            return {"metadata":{"provider":result["provider"],"model":result["model"],"duration_s":pcm.shape[1]/44100,"warning":"Được sinh bởi nhà cung cấp bên ngoài."},"audio_url":f"/api/projects/{pid}/creator/previews/{wav.name}"}
        except MusicProviderError as e: raise HTTPException(502,{"code":e.code,"detail":str(e)}) from e
        except Exception as e: raise HTTPException(502,"Không giải mã/kiểm tra được kết quả từ provider.") from e
    if body.generation_method not in {"loops", "local", "provider"}:
        raise HTTPException(422,"Phương thức tạo không hợp lệ.")
    try:
        meta,audio=service(request).arrange_text_music(body.prompt,body.duration_s,body.bpm)
        out=service(request).project_dir(pid)/f"text_music_{uuid.uuid4().hex}.wav"
        write_wav(out,audio,"PCM_24")
        return {"metadata":meta,"audio_url":f"/api/projects/{pid}/creator/previews/{out.name}"}
    except ValueError as e: raise HTTPException(422,str(e)) from e

@router.get("/projects/{pid}/creator/previews/{filename}")
def preview(pid: str, filename: str, request: Request):
    pid_ok(request,pid)
    if not filename.startswith(("preview_","text_music_","provider_")) or "/" in filename or "\\" in filename: raise HTTPException(404,"Không tìm thấy bản nghe thử.")
    path=service(request).project_dir(pid)/filename
    if not path.is_file(): raise HTTPException(404,"Không tìm thấy bản nghe thử.")
    return FileResponse(path,media_type="audio/wav")

@router.get("/projects/{pid}/creator/previews/{filename}/download/{fmt}")
def download_preview(pid: str, filename: str, fmt: str, request: Request):
    pid_ok(request,pid)
    if fmt not in {"wav","mp3"}: raise HTTPException(422,"Định dạng không hỗ trợ.")
    if not filename.startswith(("preview_","text_music_","provider_")) or "/" in filename or "\\" in filename: raise HTTPException(404,"Không tìm thấy bản nghe thử.")
    source=service(request).project_dir(pid)/filename
    if not source.is_file(): raise HTTPException(404,"Không tìm thấy bản nghe thử.")
    if source.suffix.lower()==".wav": wav=source
    else:
        pcm=load_audio(source);wav=source.with_suffix(".wav");write_wav(wav,pcm,"PCM_24")
    if fmt=="wav": path=wav
    else:
        path=wav.with_suffix(".mp3")
        from ..audio_io import encode_mp3
        encode_mp3(wav,path,{"title":"MIXVERSE Creator preview","comment":"AI-assisted (MIXVERSE AI); local arrangement unless provider metadata says otherwise"})
    return FileResponse(path,filename=f"mixverse_creator.{fmt}",media_type="audio/wav" if fmt=="wav" else "audio/mpeg")

@router.get("/projects/{pid}/creator/credits")
def creator_credits(pid: str, request: Request):
    pid_ok(request,pid)
    d=service(request).project_dir(pid)
    assets=[]
    for path in d.glob("a_*.json"):
        try: assets.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError,json.JSONDecodeError): pass
    return {"notice":"Đầu ra local được tổng hợp bằng MIXVERSE; đầu ra provider tuân theo điều khoản tài khoản nhà cung cấp.","assets":[{"name":a["original_name"],"sha256":a["sha256"],"rights_confirmed":a["rights_confirmed"],"kind":a["kind"]} for a in assets]}

@router.post("/projects/{pid}/creator/lyrics")
def lyrics_unavailable(pid: str, request: Request):
    pid_ok(request,pid)
    raise HTTPException(503,"Chưa cấu hình AI Director để gợi ý lời. Bạn vẫn có thể tự nhập lời và duyệt trước khi gửi provider.")

def purge_creator_assets(root: Path, ttl_hours: int=24):
    now=datetime.now(timezone.utc); removed=[]
    if not root.exists():return removed
    for project_dir in root.iterdir():
        creator=project_dir/"creator"
        if not creator.is_dir():continue
        for path in creator.iterdir():
            try:
                age=(now-datetime.fromtimestamp(path.stat().st_mtime,timezone.utc)).total_seconds()
                if age>ttl_hours*3600:
                    if path.is_dir():shutil.rmtree(path)
                    else:path.unlink(missing_ok=True)
                    removed.append(str(path))
            except OSError:continue
    return removed
