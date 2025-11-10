#!/usr/bin/env python
"""
FastAPI Web Application for AI News Aggregator
Provides a web interface for generating AI blog posts
"""
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv

from src.ai_news_aggregator.main import build_default_inputs, run_pipeline

load_dotenv('.env')

app = FastAPI(
    title="AI News Aggregator",
    description="Generate AI-powered blog posts with a beautiful web interface",
    version="1.0.0"
)

tasks: Dict[str, Dict] = {}

OUTPUT_DIR = Path(__file__).resolve().parent / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

STATIC_DIR = Path(__file__).resolve().parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)


class BlogRequest(BaseModel):
    topic: str
    topic_slug: Optional[str] = None


class TaskStatus(BaseModel):
    task_id: str
    status: str
    message: str
    progress: int
    result: Optional[str] = None
    download_url: Optional[str] = None
    created_at: str


def run_blog_generation(task_id: str, topic: str, topic_slug: Optional[str] = None):
    try:
        tasks[task_id]["status"] = "processing"
        tasks[task_id]["progress"] = 10
        tasks[task_id]["message"] = "Initializing AI agents..."
        
        slug = topic_slug or topic
        inputs = build_default_inputs(topic=topic, topic_slug=slug)
        
        tasks[task_id]["progress"] = 30
        tasks[task_id]["message"] = "Researching keywords and content..."
        
        result, output_path = run_pipeline(inputs, output_dir=OUTPUT_DIR)
        
        tasks[task_id]["progress"] = 90
        tasks[task_id]["message"] = "Finalizing blog post..."
        
        tasks[task_id]["status"] = "completed"
        tasks[task_id]["progress"] = 100
        tasks[task_id]["message"] = "Blog post generated successfully!"
        tasks[task_id]["result"] = str(result.raw)
        tasks[task_id]["download_url"] = f"/download/{output_path.name}"
        tasks[task_id]["output_file"] = str(output_path)
    except Exception as e:
        tasks[task_id]["status"] = "failed"
        tasks[task_id]["progress"] = 0
        tasks[task_id]["message"] = f"Error: {str(e)}"


@app.get("/", response_class=HTMLResponse)
async def read_root():
    html_file = STATIC_DIR / "index.html"
    if html_file.exists():
        return HTMLResponse(content=html_file.read_text(encoding='utf-8'), status_code=200)
    return HTMLResponse(content="<h1>AI News Aggregator</h1><p>Please run setup first.</p>")


@app.post("/api/generate", response_model=TaskStatus)
async def generate_blog(request: BlogRequest, background_tasks: BackgroundTasks):
    if not request.topic or len(request.topic.strip()) < 3:
        raise HTTPException(status_code=400, detail="Topic must be at least 3 characters")
    
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
    
    background_tasks.add_task(run_blog_generation, task_id=task_id, topic=request.topic, topic_slug=request.topic_slug)
    return TaskStatus(**tasks[task_id])


@app.get("/api/status/{task_id}", response_model=TaskStatus)
async def get_status(task_id: str):
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskStatus(**tasks[task_id])


@app.get("/api/result/{task_id}")
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

