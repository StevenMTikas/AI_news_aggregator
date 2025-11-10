#!/usr/bin/env python
import re
import warnings
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from dotenv import load_dotenv

from .crew import AiNewsAggregator

load_dotenv()
warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")

DEFAULT_TOPIC = "Best AI Tools for Restaurants to Boost Reservations"
DEFAULT_SLUG = "Best AI Tools for Restaurants to Boost Reservations"
OUTPUT_DIR = Path(__file__).resolve().parents[2] / "output"


def build_default_inputs(
    topic: str = DEFAULT_TOPIC,
    topic_slug: str = DEFAULT_SLUG,
    now: Optional[datetime] = None,
) -> Dict[str, str]:
    current_time = now or datetime.now()
    return {
        "topic": topic,
        "topic_slug": topic_slug,
        "current_year": str(current_time.year),
        "current_date": current_time.strftime("%Y-%m-%d"),
        "current_date_and_time": current_time.strftime("%Y-%m-%d %H:%M:%S"),
    }


def slugify_title(blog_content: str, default: str = "ai-blog-post") -> str:
    # Remove markdown wrapper if present
    if blog_content.startswith('```markdown'):
        blog_content = blog_content[11:]  # Remove '```markdown'
        if blog_content.endswith('```'):
            blog_content = blog_content[:-3]  # Remove trailing ```
    
    # Try to find title in front matter
    match = re.search(
        r'title:\s*(?:["\']([^"\']+)["\']|([^\n\r]+))', blog_content, re.IGNORECASE
    )
    if not match:
        return default

    title = (match.group(1) or match.group(2) or "").strip()
    if not title:
        return default

    # Clean up the title for filename
    keyword_title = re.sub(r"[^a-zA-Z0-9\s-]", "", title.lower())
    keyword_title = re.sub(r"\s+", "-", keyword_title.strip())[:50]
    return keyword_title or default


def save_blog_post(
    result: Any, current_date: str, output_dir: Optional[Path] = None
) -> Path:
    output_path = output_dir or OUTPUT_DIR
    output_path.mkdir(parents=True, exist_ok=True)

    blog_content = str(result.raw)
    keyword_title = slugify_title(blog_content)
    filename = f"{current_date}-{keyword_title}-blog-post.md"
    file_path = output_path / filename
    file_path.write_text(blog_content, encoding="utf-8")
    return file_path


def run_pipeline(
    inputs: Dict[str, str], output_dir: Optional[Path] = None
) -> Tuple[Any, Path]:
    result = AiNewsAggregator().crew().kickoff(inputs=inputs)
    output_path = save_blog_post(result, inputs["current_date"], output_dir=output_dir)
    return result, output_path


def run(topic: str = DEFAULT_TOPIC, topic_slug: str = DEFAULT_SLUG):
    from .cli import run as cli_run

    return cli_run(topic=topic, topic_slug=topic_slug)
