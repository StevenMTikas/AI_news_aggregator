#!/usr/bin/env python
"""
FastAPI Web Application for AI News Aggregator
Provides a web interface for generating AI blog posts
"""
import os
import uuid
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from src.ai_news_aggregator.main import OUTPUT_DIR, build_default_inputs, run_pipeline
from src.ai_news_aggregator.schemas import BlogContent
from src.ai_news_aggregator.projects import (
    ProjectNotFoundError,
    ProjectProfile,
    ProjectSlugConflictError,
    create_project,
    delete_project,
    get_project,
    list_projects,
    update_project,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv('.env')

# Check for required environment variables
required_env_vars = ['OPENAI_API_KEY', 'SERPER_API_KEY']
missing_vars = [var for var in required_env_vars if not os.getenv(var)]
if missing_vars:
    logger.warning(f"Missing environment variables: {', '.join(missing_vars)}")
    logger.warning("The application may not function correctly without these variables.")
else:
    logger.info("All required environment variables are set.")

app = FastAPI(
    title="AI News Aggregator",
    description="Generate AI-powered blog posts with a beautiful web interface",
    version="1.0.0"
)

# Add CORS middleware for production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this to your domain in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

tasks: Dict[str, Dict] = {}

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

STATIC_DIR = Path(__file__).resolve().parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)


class BlogRequest(BaseModel):
    topic: str
    project_slug: str
    topic_slug: Optional[str] = None


class TaskStatus(BaseModel):
    task_id: str
    status: str
    message: str
    progress: int
    result: Optional[dict] = None
    download_url: Optional[str] = None
    created_at: str


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


def run_blog_generation(task_id: str, topic: str, project_slug: str, topic_slug: Optional[str] = None):
    try:
        logger.info(f"Starting blog generation for task {task_id}, topic: {topic}, project: {project_slug}")
        tasks[task_id]["status"] = "processing"
        tasks[task_id]["progress"] = 10
        tasks[task_id]["message"] = "Initializing AI agents..."

        # Check for API keys before starting
        if not os.getenv('OPENAI_API_KEY'):
            raise ValueError("OPENAI_API_KEY is not set. Please configure your environment variables.")
        if not os.getenv('SERPER_API_KEY'):
            raise ValueError("SERPER_API_KEY is not set. Please configure your environment variables.")

        project = get_project(project_slug)
        slug = topic_slug or topic
        inputs = build_default_inputs(topic=topic, project=project, topic_slug=slug)

        tasks[task_id]["progress"] = 30
        tasks[task_id]["message"] = "Researching keywords and content..."

        result, output_path = run_pipeline(inputs, project)

        tasks[task_id]["progress"] = 90
        tasks[task_id]["message"] = "Finalizing blog post..."

        tasks[task_id]["status"] = "completed"
        tasks[task_id]["progress"] = 100
        tasks[task_id]["message"] = "Blog post generated successfully!"
        tasks[task_id]["result"] = result.pydantic.model_dump() if result.pydantic else None
        tasks[task_id]["download_url"] = f"/download/{output_path.name}"
        logger.info(f"Blog generation completed for task {task_id}")
    except ProjectNotFoundError:
        logger.error(f"Blog generation failed for task {task_id}: unknown project {project_slug}")
        tasks[task_id]["status"] = "failed"
        tasks[task_id]["progress"] = 0
        tasks[task_id]["message"] = f"Unknown project: {project_slug}"
    except Exception as e:
        error_message = str(e)
        logger.error(f"Blog generation failed for task {task_id}: {error_message}")
        tasks[task_id]["status"] = "failed"
        tasks[task_id]["progress"] = 0
        tasks[task_id]["message"] = f"Error: {error_message}"


def serve_static_page(filename: str, fallback_html: str) -> HTMLResponse:
    html_file = STATIC_DIR / filename
    if html_file.exists():
        return HTMLResponse(content=html_file.read_text(encoding='utf-8'), status_code=200)
    return HTMLResponse(content=fallback_html)


@app.get("/", response_class=HTMLResponse)
async def read_root():
    return serve_static_page("index.html", "<h1>AI News Aggregator</h1><p>Please run setup first.</p>")


@app.get("/admin", response_class=HTMLResponse)
async def read_admin():
    return serve_static_page("admin.html", "<h1>Admin</h1><p>admin.html not found.</p>")


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


@app.post("/api/generate", response_model=TaskStatus)
async def generate_blog(request: BlogRequest, background_tasks: BackgroundTasks):
    if not request.topic or len(request.topic.strip()) < 3:
        raise HTTPException(status_code=400, detail="Topic must be at least 3 characters")

    try:
        get_project(request.project_slug)
    except ProjectNotFoundError:
        raise HTTPException(status_code=400, detail=f"Unknown project: {request.project_slug}")

    task_id = str(uuid.uuid4())
    tasks[task_id] = {
        "task_id": task_id,
        "status": "pending",
        "progress": 0,
        "message": "Task created, starting soon...",
        "result": None,
        "download_url": None,
        "created_at": datetime.now().isoformat()
    }

    background_tasks.add_task(
        run_blog_generation,
        task_id=task_id,
        topic=request.topic,
        project_slug=request.project_slug,
        topic_slug=request.topic_slug,
    )
    return TaskStatus(**tasks[task_id])


@app.get("/api/status/{task_id}", response_model=TaskStatus)
async def get_status(task_id: str):
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskStatus(**tasks[task_id])


@app.get("/api/result/{task_id}", response_model=ResultResponse)
async def get_result(task_id: str):
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    task = tasks[task_id]
    if task["status"] != "completed":
        raise HTTPException(status_code=400, detail="Task not completed yet")
    return {"task_id": task_id, "content": task["result"], "download_url": task["download_url"]}


@app.get("/download/{filename}")
async def download_file(filename: str):
    file_path = OUTPUT_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path=file_path, filename=filename, media_type="text/markdown")


@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat(), "active_tasks": len([t for t in tasks.values() if t["status"] == "processing"])}


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

