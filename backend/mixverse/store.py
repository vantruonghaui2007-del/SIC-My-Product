from __future__ import annotations
import json
import re
import shutil
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from .mixscript import Project, Version, MixScript


class ProjectNotFound(LookupError):
    pass


class ProjectStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._locks: dict[str, threading.RLock] = {}
        self._guard = threading.Lock()

    def lock(self, pid: str) -> threading.RLock:
        with self._guard:
            return self._locks.setdefault(pid, threading.RLock())

    def project_dir(self, pid: str) -> Path:
        self._validate(pid)
        return self.root / pid

    def source_dir(self, pid: str, sid: str) -> Path:
        return self.project_dir(pid) / "sources" / sid

    def render_dir(self, pid: str) -> Path:
        return self.project_dir(pid) / "renders"

    def stem_cache_dir(self, sha256: str) -> Path:
        return self.root / "stem_cache" / sha256

    @staticmethod
    def _validate(pid: str) -> None:
        if not re.fullmatch(r"[0-9a-f]{32}", pid):
            raise ProjectNotFound("Không tìm thấy dự án.")

    def create(self, mode: str, now: datetime | None = None) -> Project:
        if mode not in {"mashup", "remix", "create"}:
            raise ValueError("Chế độ dự án không hợp lệ.")
        now = now or datetime.now(timezone.utc)
        pid = uuid.uuid4().hex
        project = Project(id=pid, mode=mode, created_at=now, versions=[Version(id="v0", status="kept", script=MixScript(), render="ready")], events=[])
        self.save(project)
        return project

    def load(self, pid: str) -> Project:
        path = self.project_dir(pid) / "project.json"
        try:
            return Project.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ProjectNotFound("Không tìm thấy dự án.") from exc

    def save(self, project: Project) -> None:
        directory = self.project_dir(project.id)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "project.json"
        temp = path.with_suffix(".json.tmp")
        temp.write_text(project.model_dump_json(indent=2), encoding="utf-8")
        temp.replace(path)

    def purge_expired(self, now: datetime | None = None, ttl_hours: int = 24) -> list[str]:
        now = now or datetime.now(timezone.utc)
        removed = []
        for path in self.root.iterdir():
            if path.name == "stem_cache" or not path.is_dir() or not re.fullmatch(r"[0-9a-f]{32}", path.name):
                continue
            try:
                project = self.load(path.name)
                created = project.created_at
                if created.tzinfo is None:
                    created = created.replace(tzinfo=timezone.utc)
                if (now - created).total_seconds() > ttl_hours * 3600:
                    shutil.rmtree(path)
                    removed.append(path.name)
            except ProjectNotFound:
                continue
        return removed


def version(project: Project, vid: str) -> Version:
    return next(v for v in project.versions if v.id == vid)


def head_script(project: Project) -> MixScript:
    return version(project, project.head).script
