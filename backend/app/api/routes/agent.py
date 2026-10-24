"""REST + Server-Sent Events API for the Newsletter Agent."""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse, StreamingResponse

from ...schemas.request import ReviseRequest, RunRequest
from ...schemas.response import RunCreated, RunListItem, RunStatus
from ...services.llm_base import LLMNotConfiguredError
from ...services.run_manager import TERMINAL, WAITING, RunConflict, RunNotFound, get_manager

router = APIRouter(prefix="/api/agent", tags=["agent"])


def _status_payload(record: dict) -> dict:
    downloads = {}
    if (record.get("result") or {}).get("output"):
        base = f"/api/agent/{record['run_id']}/download"
        downloads = {"html": f"{base}?format=html", "markdown": f"{base}?format=markdown", "json": f"{base}?format=json"}
    return {**record, "result": record.get("result") or {}, "downloads": downloads}


def _get_or_404(run_id: str) -> dict:
    try:
        return get_manager().get(run_id)
    except RunNotFound:
        raise HTTPException(status_code=404, detail="Run not found")


@router.post("/run", response_model=RunCreated, status_code=202)
def start_run(body: RunRequest):
    try:
        record = get_manager().start(body.goal, body.model_dump(exclude={"goal"}))
    except LLMNotConfiguredError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"run_id": record["run_id"], "status": record["status"]}


@router.get("/runs", response_model=list[RunListItem])
def list_runs(limit: int = Query(20, ge=1, le=100)):
    return get_manager().store.list(limit)


@router.get("/{run_id}", response_model=RunStatus)
def get_run(run_id: str):
    return _status_payload(_get_or_404(run_id))


@router.get("/{run_id}/events")
async def stream_events(run_id: str, request: Request, after: int = Query(0, ge=0)):
    """Stream real workflow progress with Server-Sent Events."""
    _get_or_404(run_id)
    manager = get_manager()

    async def generator():
        index, last_status, idle = after, None, 0.0
        while True:
            if await request.is_disconnected():
                break
            record = manager.get(run_id)
            events = record["events"][index:]
            for event in events:
                yield f"id: {event.get('id', index)}\nevent: progress\ndata: {json.dumps(event, default=str)}\n\n"
                index += 1
            if record["status"] != last_status:
                last_status = record["status"]
                yield f"event: status\ndata: {json.dumps({'status': last_status, 'error': record.get('error')})}\n\n"
            if record["status"] in TERMINAL | WAITING and not events:
                yield f"event: end\ndata: {json.dumps({'status': record['status']})}\n\n"
                break
            if events:
                idle = 0.0
            else:
                idle += 0.5
                if idle >= 15:
                    idle = 0.0
                    yield ": keep-alive\n\n"
            await asyncio.sleep(0.5)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/{run_id}/approve", response_model=RunStatus)
def approve_run(run_id: str):
    _get_or_404(run_id)
    try:
        return _status_payload(get_manager().approve(run_id))
    except RunConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.post("/{run_id}/revise", response_model=RunStatus)
def revise_run(run_id: str, body: ReviseRequest):
    _get_or_404(run_id)
    try:
        return _status_payload(get_manager().revise(run_id, body.feedback))
    except RunConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.get("/{run_id}/download")
def download(run_id: str, format: str = Query("html", pattern="^(html|markdown|md|json)$")):
    _get_or_404(run_id)
    try:
        path = get_manager().output_path(run_id, format)
    except RunConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    media = {"html": "text/html", "markdown": "text/markdown", "md": "text/markdown", "json": "application/json"}[format]
    return FileResponse(path, media_type=media, filename=path.name)


@router.delete("/{run_id}")
def delete_run(run_id: str):
    _get_or_404(run_id)
    get_manager().delete(run_id)
    return {"status": "deleted", "run_id": run_id}
