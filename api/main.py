"""FastAPI backend.

    pip install "fastapi[standard]" python-multipart
    uvicorn api.main:app --reload

Long runs are executed as background jobs so the upload request returns
immediately with a run_id the client can poll.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import threading
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from brs2sprint import store                                  # noqa: E402
from brs2sprint.config import settings                        # noqa: E402
from brs2sprint.llm import get_client                         # noqa: E402
from brs2sprint.pipeline import PipelineOptions, run_pipeline  # noqa: E402
from brs2sprint.schemas import to_json                        # noqa: E402

app = FastAPI(title="brs2sprint", version="0.1.0",
              description="BRS -> SRS -> design -> tickets -> sprint plan")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

JOBS: dict[str, dict] = {}
_LOCK = threading.Lock()
ALLOWED = {".pdf", ".docx", ".md", ".txt", ".markdown"}


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "provider": settings.llm_provider, "model": settings.llm_model}


@app.post("/runs")
async def create_run(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    velocity: int = Query(default=settings.team_velocity, ge=1, le=200),
    max_sprints: int = Query(default=settings.max_sprints, ge=1, le=52),
    stop_after: int = Query(default=9, ge=1, le=9),
    provider: str | None = Query(default=None),
) -> dict:
    """Upload a BRS and start a pipeline run. Returns a job_id to poll."""
    suffix = Path(file.filename or "brs.md").suffix.lower()
    if suffix not in ALLOWED:
        raise HTTPException(400, f"unsupported file type {suffix}; allowed: {sorted(ALLOWED)}")

    tmp_dir = Path(tempfile.mkdtemp(prefix="brs2sprint-"))
    tmp_path = tmp_dir / Path(file.filename or "brs").name
    with tmp_path.open("wb") as fh:
        shutil.copyfileobj(file.file, fh)

    job_id = uuid.uuid4().hex[:12]
    with _LOCK:
        JOBS[job_id] = {"job_id": job_id, "status": "queued", "events": [], "run_id": None}

    def work() -> None:
        def progress(phase: str, msg: str) -> None:
            with _LOCK:
                JOBS[job_id]["events"].append({"phase": phase, "message": msg})
                JOBS[job_id]["status"] = "running"
        try:
            result = run_pipeline(
                str(tmp_path), client=get_client(provider),
                options=PipelineOptions(velocity=velocity, max_sprints=max_sprints,
                                        stop_after=stop_after),
                progress=progress,
            )
            with _LOCK:
                JOBS[job_id].update(status="done", run_id=result.run_id)
        except Exception as exc:
            with _LOCK:
                JOBS[job_id].update(status="error", error=f"{type(exc).__name__}: {exc}")
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    background.add_task(work)
    return {"job_id": job_id, "status": "queued"}


@app.get("/jobs/{job_id}")
def job_status(job_id: str) -> dict:
    with _LOCK:
        job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "unknown job_id")
    return job


@app.get("/runs")
def list_runs() -> list[dict]:
    return store.list_runs()


@app.get("/runs/{run_id}")
def get_run(run_id: str) -> JSONResponse:
    data = store.load_run(run_id)
    if data is None:
        raise HTTPException(404, "unknown run_id")
    return JSONResponse(data)


@app.get("/runs/{run_id}/board")
def get_board(run_id: str) -> dict:
    if store.load_run(run_id) is None:
        raise HTTPException(404, "unknown run_id")
    return store.board(run_id)


@app.get("/runs/{run_id}/srs")
def get_srs(run_id: str) -> dict:
    data = store.load_run(run_id)
    if data is None:
        raise HTTPException(404, "unknown run_id")
    return data.get("srs") or {}


@app.get("/runs/{run_id}/download/{kind}")
def download(run_id: str, kind: str) -> FileResponse:
    names = {"json": f"{run_id}_full.json",
             "markdown": f"{run_id}_delivery_pack.md",
             "csv": f"{run_id}_tickets.csv",
             "docx": f"{run_id}_SRS.docx"}
    if kind not in names:
        raise HTTPException(400, f"kind must be one of {sorted(names)}")
    path = Path(settings.output_dir) / names[kind]
    if not path.exists():
        raise HTTPException(404, f"{names[kind]} was not generated for this run")
    return FileResponse(str(path), filename=path.name)


@app.delete("/runs/{run_id}")
def delete_run(run_id: str) -> dict:
    with store.connect() as conn:
        cur = conn.execute("DELETE FROM runs WHERE run_id = ?", (run_id,))
    if cur.rowcount == 0:
        raise HTTPException(404, "unknown run_id")
    return {"deleted": run_id}
