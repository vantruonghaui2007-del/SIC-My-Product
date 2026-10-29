from datetime import datetime, timezone
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from ..store import ProjectNotFound

router = APIRouter()

class CreateProject(BaseModel):
    mode: str

@router.post("/projects", status_code=201)
def create_project(body: CreateProject, request: Request):
    store = request.app.state.store
    store.purge_expired(ttl_hours=request.app.state.settings.ttl_hours)
    try:
        return store.create(body.mode)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


@router.get("/projects/{pid}")
def get_project(pid: str, request: Request):
    try:
        return request.app.state.store.load(pid)
    except ProjectNotFound as e:
        raise HTTPException(404, str(e)) from e

@router.delete("/projects/{pid}", status_code=204)
def delete_project(pid: str, request: Request):
    store = request.app.state.store
    try:
        path = store.project_dir(pid)
        if not path.exists():
            raise ProjectNotFound("Không tìm thấy dự án.")
        import shutil
        shutil.rmtree(path)
    except ProjectNotFound as e:
        raise HTTPException(404, str(e)) from e
