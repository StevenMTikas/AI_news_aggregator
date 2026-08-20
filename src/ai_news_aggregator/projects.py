import re
from pathlib import Path
from typing import List, Optional

import yaml
from pydantic import BaseModel, Field

PROJECTS_DIR = Path(__file__).resolve().parent / "config" / "projects"


class ProjectProfile(BaseModel):
    slug: str
    name: str
    audience: str
    tone: str
    category_tags: List[str] = Field(default_factory=list)
    author: str
    target_word_count: int = 800
    notes: Optional[str] = None


class ProjectNotFoundError(KeyError):
    pass


class ProjectSlugConflictError(ValueError):
    pass


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "project"


def _path_for(slug: str) -> Path:
    return PROJECTS_DIR / f"{slug}.yaml"


def list_projects() -> List[ProjectProfile]:
    if not PROJECTS_DIR.exists():
        return []
    profiles = [
        ProjectProfile(**yaml.safe_load(path.read_text(encoding="utf-8")))
        for path in sorted(PROJECTS_DIR.glob("*.yaml"))
    ]
    return profiles


def get_project(slug: str) -> ProjectProfile:
    path = _path_for(slug)
    if not path.exists():
        raise ProjectNotFoundError(slug)
    return ProjectProfile(**yaml.safe_load(path.read_text(encoding="utf-8")))


def create_project(profile: ProjectProfile) -> ProjectProfile:
    path = _path_for(profile.slug)
    if path.exists():
        raise ProjectSlugConflictError(profile.slug)
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(profile.model_dump(), sort_keys=False), encoding="utf-8")
    return profile


def update_project(slug: str, profile: ProjectProfile) -> ProjectProfile:
    path = _path_for(slug)
    if not path.exists():
        raise ProjectNotFoundError(slug)
    updated = profile.model_copy(update={"slug": slug})
    path.write_text(yaml.safe_dump(updated.model_dump(), sort_keys=False), encoding="utf-8")
    return updated


def delete_project(slug: str) -> None:
    path = _path_for(slug)
    if not path.exists():
        raise ProjectNotFoundError(slug)
    path.unlink()
