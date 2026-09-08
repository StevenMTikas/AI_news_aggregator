#!/usr/bin/env python
"""FastAPI web application for ContentForge."""
import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from src.contentforge.db import briefs as brief_store
from src.contentforge.db import documents as doc_store
from src.contentforge.db import init_db
from src.contentforge.db import runs as run_store
from src.contentforge.db.runs import Run
from src.contentforge.main import OUTPUT_DIR
from src.contentforge.projects import (
    ProjectNotFoundError,
    ProjectProfile,
    ProjectSlugConflictError,
    create_project,
    delete_project,
    get_project,
    list_projects,
    update_project,
)
from src.contentforge.corpus import CorpusSelection
from src.contentforge.run_service import default_run_service
from src.contentforge.schemas import LONGFORM_SCHEMAS
from src.contentforge.security import (
    api_key_configured,
    cors_origins,
    generation_limiter,
    require_api_key,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

load_dotenv(".env")

required_env_vars = ["OPENAI_API_KEY", "SERPER_API_KEY"]
missing_vars = [v for v in required_env_vars if not os.getenv(v)]
if missing_vars:
    logger.warning("Missing environment variables: %s", ", ".join(missing_vars))

@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    if api_key_configured():
        logger.info("API-key auth is ON for mutating routes")
    yield


app = FastAPI(
    title="ContentForge",
    description="Generate structured content from research",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# guards every mutating / generating route; a no-op until CONTENTFORGE_API_KEY is set
protected = Depends(require_api_key)

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
STATIC_DIR = Path(__file__).resolve().parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------------------------- models


class BlogRequest(BaseModel):
    topic: str
    project_slug: str
    topic_slug: Optional[str] = None
    force_fresh: bool = False
    artifacts: List[str] = Field(default_factory=lambda: ["blog_post"])


class TaskStatus(BaseModel):
    task_id: str
    status: str
    message: str
    progress: int
    result: Optional[dict] = None
    download_url: Optional[str] = None
    created_at: str


class RunSummary(BaseModel):
    id: str
    project_slug: Optional[str]
    kind: str
    status: str
    topic: str
    cost_usd: float
    search_calls: int
    created_at: str
    finished_at: Optional[str]


class ProjectFields(BaseModel):
    name: str
    audience: str
    tone: str
    category_tags: List[str] = Field(default_factory=list)
    author: str
    target_word_count: int = 800
    notes: Optional[str] = None
    subject_focus: str = ""
    style_guide: str = ""
    banned_phrases: List[str] = Field(default_factory=list)
    recency_days: Optional[int] = None
    min_sources: int = 5
    prefer_domains: List[str] = Field(default_factory=list)
    exclude_domains: List[str] = Field(default_factory=list)
    default_model: Optional[str] = None
    length_overrides: dict = Field(default_factory=dict)


class ProjectCreateRequest(ProjectFields):
    slug: str


class ProjectUpdateRequest(ProjectFields):
    pass


class CompileRequest(BaseModel):
    project_slug: str
    longform_type: str  # newsletter | podcast_script | guide
    angle: str = ""
    run_ids: List[str] = Field(default_factory=list)
    last_n_runs: Optional[int] = None
    last_n_days: Optional[int] = None


class ResultResponse(BaseModel):
    task_id: str
    content: Optional[dict] = None
    download_url: Optional[str] = None


# --------------------------------------------------------------------- helpers


def _download_url(rendered_path: Optional[str]) -> Optional[str]:
    return f"/download/{Path(rendered_path).name}" if rendered_path else None


def _primary_doc(run_id: str):
    docs = [d for d in doc_store.list_documents(run_id=run_id) if d.type != "metadata"]
    if not docs:
        return None
    return next((d for d in docs if d.type == "blog_post"), docs[0])


def _task_status(run: Run) -> TaskStatus:
    result = None
    download_url = None
    if run.status in {"completed", "partial"}:
        doc = _primary_doc(run.id)
        if doc is not None:
            result = json.loads(doc.content_json)
            download_url = _download_url(doc.rendered_path)
    return TaskStatus(
        task_id=run.id,
        status=run.status,
        message=run.message,
        progress=run.progress,
        result=result,
        download_url=download_url,
        created_at=run.created_at,
    )


def run_blog_generation(run_id: str, topic: str, project_slug: str,
                        topic_slug: Optional[str] = None,
                        artifacts: Optional[List[str]] = None) -> None:
    try:
        project = get_project(project_slug)
    except ProjectNotFoundError:
        run_store.update_run(run_id, status="failed", progress=0,
                             message=f"Unknown project: {project_slug}", error="project not found")
        return
    if not os.getenv("OPENAI_API_KEY") or not os.getenv("SERPER_API_KEY"):
        run_store.update_run(run_id, status="failed", progress=0,
                             message="OPENAI_API_KEY and SERPER_API_KEY must be set", error="missing api keys")
        return
    try:
        service = default_run_service(output_dir=OUTPUT_DIR)
        service.run_atomic(
            project, topic, run_id=run_id, topic_slug=topic_slug,
            artifacts=artifacts or ["blog_post"],
            current_date=datetime.now().strftime("%Y-%m-%d"),
        )
    except Exception as exc:
        logger.error("Blog generation failed for run %s: %s", run_id, exc)
        run = run_store.get_run(run_id)
        if run is not None and run.status not in {"completed", "failed", "partial"}:
            run_store.update_run(run_id, status="failed", progress=0,
                                 message=f"Error: {exc}", error=str(exc))


# --------------------------------------------------------------------- pages


def serve_static_page(filename: str, fallback_html: str) -> HTMLResponse:
    html_file = STATIC_DIR / filename
    if html_file.exists():
        return HTMLResponse(content=html_file.read_text(encoding="utf-8"), status_code=200)
    return HTMLResponse(content=fallback_html)


@app.get("/", response_class=HTMLResponse)
async def read_root():
    return serve_static_page("index.html", "<h1>ContentForge</h1><p>Please run setup first.</p>")


@app.get("/admin", response_class=HTMLResponse)
async def read_admin():
    return serve_static_page("admin.html", "<h1>Admin</h1><p>admin.html not found.</p>")


@app.get("/compile", response_class=HTMLResponse)
async def read_compile():
    return serve_static_page("compile.html", "<h1>Compile</h1><p>compile.html not found.</p>")


@app.get("/runs", response_class=HTMLResponse)
async def read_runs():
    return serve_static_page("runs.html", "<h1>Runs</h1><p>runs.html not found.</p>")


# --------------------------------------------------------------------- projects


@app.get("/api/projects", response_model=List[ProjectProfile])
async def list_projects_route():
    return list_projects()


@app.get("/api/projects/{slug}", response_model=ProjectProfile)
async def get_project_route(slug: str):
    try:
        return get_project(slug)
    except ProjectNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")


@app.post("/api/projects", response_model=ProjectProfile, status_code=201, dependencies=[protected])
async def create_project_route(body: ProjectCreateRequest):
    try:
        return create_project(ProjectProfile(**body.model_dump()))
    except ProjectSlugConflictError:
        raise HTTPException(status_code=409, detail=f"Project '{body.slug}' already exists")


@app.put("/api/projects/{slug}", response_model=ProjectProfile, dependencies=[protected])
async def update_project_route(slug: str, body: ProjectUpdateRequest):
    try:
        return update_project(slug, ProjectProfile(slug=slug, **body.model_dump()))
    except ProjectNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")


@app.delete("/api/projects/{slug}", status_code=204, dependencies=[protected])
async def delete_project_route(slug: str):
    try:
        delete_project(slug)
    except ProjectNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")


# --------------------------------------------------------------------- generation


@app.post("/api/generate", response_model=TaskStatus, dependencies=[protected])
async def generate_blog(request: BlogRequest, background_tasks: BackgroundTasks):
    generation_limiter.check()
    if not request.topic or len(request.topic.strip()) < 3:
        raise HTTPException(status_code=400, detail="Topic must be at least 3 characters")
    try:
        get_project(request.project_slug)
    except ProjectNotFoundError:
        raise HTTPException(status_code=400, detail=f"Unknown project: {request.project_slug}")

    artifacts = request.artifacts or ["blog_post"]
    run = run_store.create_run(
        project_slug=request.project_slug,
        topic=request.topic,
        topic_slug=request.topic_slug or request.topic,
        params={"artifacts": artifacts, "force_fresh": request.force_fresh},
    )
    background_tasks.add_task(
        run_blog_generation,
        run_id=run.id,
        topic=request.topic,
        project_slug=request.project_slug,
        topic_slug=request.topic_slug,
        artifacts=artifacts,
    )
    return _task_status(run)


def _run_compilation(run_id: str, project_slug: str, longform_type: str,
                     selection: dict, angle: str) -> None:
    try:
        project = get_project(project_slug)
    except ProjectNotFoundError:
        run_store.update_run(run_id, status="failed", progress=0,
                             message=f"Unknown project: {project_slug}", error="project not found")
        return
    if not os.getenv("OPENAI_API_KEY"):
        run_store.update_run(run_id, status="failed", progress=0,
                             message="OPENAI_API_KEY must be set", error="missing api key")
        return
    try:
        default_run_service(output_dir=OUTPUT_DIR).start_compilation(
            project, longform_type, CorpusSelection(**selection), angle=angle, run_id=run_id,
            current_date=datetime.now().strftime("%Y-%m-%d"),
        )
    except Exception as exc:
        logger.error("Compilation failed for run %s: %s", run_id, exc)
        run = run_store.get_run(run_id)
        if run is not None and run.status not in {"completed", "failed", "partial"}:
            run_store.update_run(run_id, status="failed", progress=0,
                                 message=f"Error: {exc}", error=str(exc))


@app.post("/api/compile", response_model=TaskStatus, dependencies=[protected])
async def compile_longform(request: CompileRequest, background_tasks: BackgroundTasks):
    generation_limiter.check()
    if request.longform_type not in LONGFORM_SCHEMAS:
        raise HTTPException(status_code=400,
                            detail=f"longform_type must be one of {sorted(LONGFORM_SCHEMAS)}")
    try:
        get_project(request.project_slug)
    except ProjectNotFoundError:
        raise HTTPException(status_code=400, detail=f"Unknown project: {request.project_slug}")

    selection = {"run_ids": request.run_ids, "last_n_runs": request.last_n_runs,
                 "last_n_days": request.last_n_days}
    run = run_store.create_run(
        project_slug=request.project_slug, kind="compilation",
        topic=f"{request.longform_type}: {request.angle or 'compilation'}",
        params={"longform_type": request.longform_type, "selection": selection, "angle": request.angle},
    )
    background_tasks.add_task(
        _run_compilation, run.id, request.project_slug, request.longform_type, selection, request.angle,
    )
    return _task_status(run)


@app.get("/api/status/{task_id}", response_model=TaskStatus)
async def get_status(task_id: str):
    run = run_store.get_run(task_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return _task_status(run)


@app.get("/api/result/{task_id}", response_model=ResultResponse)
async def get_result(task_id: str):
    run = run_store.get_run(task_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if run.status not in {"completed", "partial"}:
        raise HTTPException(status_code=400, detail="Task not completed yet")
    status = _task_status(run)
    return {"task_id": task_id, "content": status.result, "download_url": status.download_url}


@app.get("/api/status/{task_id}/stream")
async def stream_status(task_id: str):
    if run_store.get_run(task_id) is None:
        raise HTTPException(status_code=404, detail="Task not found")

    async def events():
        for _ in range(600):  # ~10 minutes at 1s
            run = await asyncio.to_thread(run_store.get_run, task_id)
            if run is None:
                break
            yield f"data: {_task_status(run).model_dump_json()}\n\n"
            if run.status in {"completed", "failed", "partial"}:
                break
            await asyncio.sleep(1)

    return StreamingResponse(events(), media_type="text/event-stream")


# --------------------------------------------------------------------- run history


@app.get("/api/briefs/fresh")
async def fresh_brief_route(project_slug: str, topic: str):
    from src.contentforge.providers.serper import normalize_query

    hit = brief_store.find_fresh_brief(project_slug, normalize_query(topic))
    return {"fresh": hit is not None, "created_at": hit.created_at if hit else None}


@app.get("/api/costs")
async def costs_route(project_slug: str):
    from src.contentforge.db import costs as cost_store

    return cost_store.project_totals(project_slug)


@app.get("/api/runs", response_model=List[RunSummary])
async def list_runs_route(project_slug: Optional[str] = None, limit: int = 50,
                          kind: Optional[str] = None):
    kinds = (kind,) if kind else None
    return [
        RunSummary(**r.model_dump())
        for r in run_store.list_runs(project_slug=project_slug, limit=limit, kinds=kinds)
    ]


@app.get("/api/runs/{run_id}/documents")
async def run_documents_route(run_id: str):
    if run_store.get_run(run_id) is None:
        raise HTTPException(status_code=404, detail="Run not found")
    docs = doc_store.list_documents(run_id=run_id)
    return [
        {"id": d.id, "type": d.type, "title": d.title, "download_url": _download_url(d.rendered_path)}
        for d in docs
    ]


@app.post("/api/documents/{document_id}/render", dependencies=[protected])
async def render_document_route(document_id: str):
    try:
        service = default_run_service(output_dir=OUTPUT_DIR)
        path = service.render_document(document_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"document_id": document_id, "download_url": _download_url(str(path))}


def _update_brief_task(brief_id: str, project_slug: str) -> None:
    try:
        project = get_project(project_slug)
    except ProjectNotFoundError:
        return
    try:
        default_run_service(output_dir=OUTPUT_DIR).update_brief(project, brief_id)
    except Exception as exc:
        logger.error("Brief update failed for %s: %s", brief_id, exc)


@app.post("/api/briefs/{brief_id}/update", dependencies=[protected])
async def update_brief_route(brief_id: str, background_tasks: BackgroundTasks):
    stored = brief_store.get_brief(brief_id)
    if stored is None:
        raise HTTPException(status_code=404, detail="Brief not found")
    background_tasks.add_task(_update_brief_task, brief_id, stored.project_slug or "")
    return {"brief_id": brief_id, "status": "updating", "topic": stored.brief.topic}


@app.get("/download/{filename}")
async def download_file(filename: str):
    file_path = OUTPUT_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path=file_path, filename=filename, media_type="text/markdown")


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "active_tasks": run_store.count_active(),
    }


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
