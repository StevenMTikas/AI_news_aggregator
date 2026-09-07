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
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from src.contentforge.db import init_db
from src.contentforge.db import documents as doc_store
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
from src.contentforge.run_service import default_run_service
from src.contentforge.schemas import BlogContent

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
    yield


app = FastAPI(
    title="ContentForge",
    description="Generate structured content from research",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # locked down in Phase 9
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
STATIC_DIR = Path(__file__).resolve().parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------------------------- models


class BlogRequest(BaseModel):
    topic: str
    project_slug: str
    topic_slug: Optional[str] = None
    force_fresh: bool = False


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


class ProjectCreateRequest(ProjectFields):
    slug: str


class ProjectUpdateRequest(ProjectFields):
    pass


class ResultResponse(BaseModel):
    task_id: str
    content: Optional[BlogContent] = None
    download_url: Optional[str] = None


# --------------------------------------------------------------------- helpers


def _download_url(rendered_path: Optional[str]) -> Optional[str]:
    return f"/download/{Path(rendered_path).name}" if rendered_path else None


def _task_status(run: Run) -> TaskStatus:
    result = None
    download_url = None
    if run.status in {"completed", "partial"}:
        docs = doc_store.list_documents(run_id=run.id)
        if docs:
            result = json.loads(docs[0].content_json)
            download_url = _download_url(docs[0].rendered_path)
    return TaskStatus(
        task_id=run.id,
        status=run.status,
        message=run.message,
        progress=run.progress,
        result=result,
        download_url=download_url,
        created_at=run.created_at,
    )


def run_blog_generation(run_id: str, topic: str, project_slug: str, topic_slug: Optional[str] = None) -> None:
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


@app.post("/api/projects", response_model=ProjectProfile, status_code=201)
async def create_project_route(body: ProjectCreateRequest):
    try:
        return create_project(ProjectProfile(**body.model_dump()))
    except ProjectSlugConflictError:
        raise HTTPException(status_code=409, detail=f"Project '{body.slug}' already exists")


@app.put("/api/projects/{slug}", response_model=ProjectProfile)
async def update_project_route(slug: str, body: ProjectUpdateRequest):
    try:
        return update_project(slug, ProjectProfile(slug=slug, **body.model_dump()))
    except ProjectNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")


@app.delete("/api/projects/{slug}", status_code=204)
async def delete_project_route(slug: str):
    try:
        delete_project(slug)
    except ProjectNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")


# --------------------------------------------------------------------- generation


@app.post("/api/generate", response_model=TaskStatus)
async def generate_blog(request: BlogRequest, background_tasks: BackgroundTasks):
    if not request.topic or len(request.topic.strip()) < 3:
        raise HTTPException(status_code=400, detail="Topic must be at least 3 characters")
    try:
        get_project(request.project_slug)
    except ProjectNotFoundError:
        raise HTTPException(status_code=400, detail=f"Unknown project: {request.project_slug}")

    run = run_store.create_run(
        project_slug=request.project_slug,
        topic=request.topic,
        topic_slug=request.topic_slug or request.topic,
        params={"artifacts": ["blog_post"], "force_fresh": request.force_fresh},
    )
    background_tasks.add_task(
        run_blog_generation,
        run_id=run.id,
        topic=request.topic,
        project_slug=request.project_slug,
        topic_slug=request.topic_slug,
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


@app.get("/api/runs", response_model=List[RunSummary])
async def list_runs_route(project_slug: Optional[str] = None, limit: int = 50):
    return [RunSummary(**r.model_dump()) for r in run_store.list_runs(project_slug=project_slug, limit=limit)]


@app.get("/api/runs/{run_id}/documents")
async def run_documents_route(run_id: str):
    if run_store.get_run(run_id) is None:
        raise HTTPException(status_code=404, detail="Run not found")
    docs = doc_store.list_documents(run_id=run_id)
    return [
        {"id": d.id, "type": d.type, "title": d.title, "download_url": _download_url(d.rendered_path)}
        for d in docs
    ]


@app.post("/api/documents/{document_id}/render")
async def render_document_route(document_id: str):
    try:
        service = default_run_service(output_dir=OUTPUT_DIR)
        path = service.render_document(document_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"document_id": document_id, "download_url": _download_url(str(path))}


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
