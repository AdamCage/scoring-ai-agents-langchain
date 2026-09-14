from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse

from creditlens.config import ROOT

router = APIRouter(prefix="/api/docs", tags=["docs"])
DOCS = ROOT / "docs"


@router.get("/architecture")
def list_architecture() -> dict:
    files = sorted((DOCS / "architecture").glob("*.mmd"))
    return {"files": [path.name for path in files]}


@router.get("/processes")
def list_processes() -> dict:
    files = sorted((DOCS / "processes").glob("*.md"))
    return {"files": [path.name for path in files]}


@router.get("/file/{kind}/{name}")
def get_doc(kind: str, name: str):
    if kind not in {"architecture", "processes", "screenshots"}:
        raise HTTPException(404)
    path = (DOCS / kind / name).resolve()
    if DOCS not in path.parents and path.parent != DOCS:
        raise HTTPException(404)
    if not path.exists():
        # allow nested screenshots
        nested = DOCS / kind
        matches = list(nested.rglob(name))
        if not matches:
            raise HTTPException(404, f"{name} not found")
        path = matches[0]
    if path.suffix in {".png", ".svg", ".jpg", ".webp"}:
        return FileResponse(path)
    return PlainTextResponse(path.read_text(encoding="utf-8"))
