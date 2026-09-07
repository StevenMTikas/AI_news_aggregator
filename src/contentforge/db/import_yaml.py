"""One-time importer for the pre-SQLite YAML project profiles.

Older versions stored one ``<slug>.yaml`` per project under
``src/contentforge/config/projects/``. Run this once to move them into the database:

    python -m contentforge.db.import_yaml [path/to/projects/]

Existing projects (matched by slug) are left untouched.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

from ..projects import ProjectProfile, ProjectSlugConflictError, create_project

_DEFAULT_DIR = Path(__file__).resolve().parents[1] / "config" / "projects"


def import_legacy_projects(directory: Optional[Path] = None) -> list[str]:
    directory = Path(directory) if directory else _DEFAULT_DIR
    if not directory.exists():
        return []
    try:
        import yaml
    except ImportError:  # pragma: no cover
        raise SystemExit("PyYAML is needed to import legacy projects: pip install pyyaml")

    imported: list[str] = []
    for path in sorted(directory.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        try:
            create_project(ProjectProfile(**data))
            imported.append(data["slug"])
        except ProjectSlugConflictError:
            continue
    return imported


if __name__ == "__main__":  # pragma: no cover
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    done = import_legacy_projects(target)
    print(f"imported {len(done)} project(s): {', '.join(done) or '(none)'}")
