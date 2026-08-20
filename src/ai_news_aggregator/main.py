#!/usr/bin/env python
import warnings
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from dotenv import load_dotenv

from .crew import AiNewsAggregator
from .projects import ProjectProfile, slugify
from .schemas import BlogContent

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


def render_jekyll_markdown(
    content: BlogContent, project: ProjectProfile, current_date: str
) -> str:
    front_matter_tags = ", ".join(project.category_tags)
    body_sections = "\n\n".join(
        f"## {section.heading}\n\n{section.body}"
        + (f"\n\n> {section.pull_quote}" if section.pull_quote else "")
        for section in content.sections
    )
    key_points = "\n".join(f"- {point}" for point in content.key_points)
    cta = f"\n\n{content.call_to_action}" if content.call_to_action else ""
    return f"""---
title: "{content.title}"
date: {current_date}
categories: [{front_matter_tags}]
author: {project.author}
layout: post
---

{content.hook}

{body_sections}

## Key Takeaways

{key_points}{cta}
"""


def save_blog_post(
    result: Any,
    project: ProjectProfile,
    current_date: str,
    output_dir: Optional[Path] = None,
) -> Path:
    output_path = output_dir or OUTPUT_DIR
    output_path.mkdir(parents=True, exist_ok=True)

    content = result.pydantic
    if content is None:
        raise ValueError("Crew result did not contain structured BlogContent output")

    markdown = render_jekyll_markdown(content, project, current_date)
    keyword_title = slugify(content.title)[:50]
    filename = f"{current_date}-{keyword_title}-blog-post.md"
    file_path = output_path / filename
    file_path.write_text(markdown, encoding="utf-8")
    return file_path


def run_pipeline(
    inputs: Dict[str, str], project: ProjectProfile, output_dir: Optional[Path] = None
) -> Tuple[Any, Path]:
    result = AiNewsAggregator().crew().kickoff(inputs=inputs)
    output_path = save_blog_post(
        result, project, inputs["current_date"], output_dir=output_dir
    )
    return result, output_path


def run(project_slug: str, topic: str = DEFAULT_TOPIC, topic_slug: str = DEFAULT_SLUG):
    from .cli import run as cli_run

    return cli_run(project_slug=project_slug, topic=topic, topic_slug=topic_slug)
