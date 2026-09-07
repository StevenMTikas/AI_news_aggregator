#!/usr/bin/env python
import warnings
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple

from dotenv import load_dotenv

from .projects import ProjectProfile
from .run_service import RunResult, default_run_service

load_dotenv()
warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")

DEFAULT_TOPIC = "Best AI Tools for Restaurants to Boost Reservations"
DEFAULT_SLUG = "Best AI Tools for Restaurants to Boost Reservations"
OUTPUT_DIR = Path(__file__).resolve().parents[2] / "output"


def build_default_inputs(
    topic: str,
    project: ProjectProfile,
    topic_slug: Optional[str] = None,
    now: Optional[datetime] = None,
) -> Dict[str, str]:
    current_time = now or datetime.now()
    return {
        "topic": topic,
        "topic_slug": topic_slug or topic,
        "current_year": str(current_time.year),
        "current_date": current_time.strftime("%Y-%m-%d"),
        "current_date_and_time": current_time.strftime("%Y-%m-%d %H:%M:%S"),
        "project_name": project.name,
        "audience": project.audience,
        "tone": project.tone,
        "author": project.author,
        "category_tags": ", ".join(project.category_tags),
        "target_word_count": str(project.target_word_count),
    }


def run_pipeline(
    inputs: Dict[str, str], project: ProjectProfile, output_dir: Optional[Path] = None
) -> Tuple[RunResult, Path]:
    service = default_run_service(output_dir=output_dir or OUTPUT_DIR)
    result = service.run_atomic(
        project,
        inputs["topic"],
        current_date=inputs.get("current_date"),
    )
    return result, result.primary_path


def run(project_slug: str, topic: str = DEFAULT_TOPIC, topic_slug: str = DEFAULT_SLUG):
    from .cli import run as cli_run

    return cli_run(project_slug=project_slug, topic=topic, topic_slug=topic_slug)
