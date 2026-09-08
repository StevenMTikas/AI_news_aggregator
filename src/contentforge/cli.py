"""The ``contentforge`` command-line interface.

Subcommands call the library directly (no HTTP), so the database is opened/migrated on
startup. ``run()`` is kept for the ``python -c "from contentforge.main import run"`` path.
"""

from __future__ import annotations

from typing import List, Optional

import typer
from rich.console import Console
from rich.table import Table

from .corpus import CorpusSelection
from .db import backup as backup_mod
from .db import briefs as brief_store
from .db import documents as doc_store
from .db import init_db
from .db import runs as run_store
from .main import DEFAULT_SLUG, DEFAULT_TOPIC, OUTPUT_DIR, build_default_inputs, run_pipeline
from .projects import (
    ProjectNotFoundError,
    ProjectProfile,
    ProjectSlugConflictError,
    create_project,
    delete_project,
    get_project,
    list_projects,
)
from .run_service import default_run_service
from .schemas import LONGFORM_SCHEMAS

console = Console()
app = typer.Typer(help="ContentForge - multi-format content generation from persisted research.",
                  no_args_is_help=True, add_completion=False)
project_app = typer.Typer(help="Manage projects.", no_args_is_help=True)
runs_app = typer.Typer(help="Inspect run history.", no_args_is_help=True)
brief_app = typer.Typer(help="Inspect and update research briefs.", no_args_is_help=True)
app.add_typer(project_app, name="project")
app.add_typer(runs_app, name="runs")
app.add_typer(brief_app, name="brief")


@app.callback()
def _bootstrap() -> None:
    init_db()


def _require_project(slug: str) -> ProjectProfile:
    try:
        return get_project(slug)
    except ProjectNotFoundError:
        console.print(f"[red]No project '{slug}'.[/] Run `contentforge project list`.")
        raise typer.Exit(1)


# --------------------------------------------------------------------- generate


@app.command()
def generate(
    project_slug: str,
    topic: str,
    artifact: List[str] = typer.Option(["blog_post"], "--artifact", "-a",
                                       help="Repeat for several: blog_post, linkedin_post, social_thread, repurpose."),
    fresh: bool = typer.Option(False, "--fresh", help="Ignore any cached research brief."),
) -> None:
    """Run an atomic generation for a topic."""
    project = _require_project(project_slug)
    with console.status(f"Generating {', '.join(artifact)} for {topic!r}..."):
        result = default_run_service(output_dir=OUTPUT_DIR).run_atomic(
            project, topic, artifacts=artifact, force_fresh=fresh
        )
    console.print(f"[green]{'done' if not result.reused_brief else 'done (reused research)'}[/] "
                  f"- ${result.cost.usd:.4f}, {len(result.document_ids)} artifact(s)")
    for doc, path in result.documents:
        console.print(f"  {doc.type}: {path}")


@app.command("compile")
def compile_longform(
    project_slug: str,
    longform_type: str = typer.Argument(..., help=f"one of {sorted(LONGFORM_SCHEMAS)}"),
    run_id: List[str] = typer.Option([], "--run-id", "-r", help="Specific prior run(s) to draw on."),
    last_runs: Optional[int] = typer.Option(None, help="Fall back to the last N completed runs."),
    last_days: Optional[int] = typer.Option(None, help="Fall back to runs from the last N days."),
    angle: str = typer.Option("", help="Framing for the piece."),
) -> None:
    """Assemble a newsletter / podcast script / guide from prior work."""
    if longform_type not in LONGFORM_SCHEMAS:
        console.print(f"[red]longform_type must be one of {sorted(LONGFORM_SCHEMAS)}[/]")
        raise typer.Exit(1)
    project = _require_project(project_slug)
    selection = CorpusSelection(run_ids=run_id, last_n_runs=last_runs, last_n_days=last_days)
    with console.status(f"Compiling {longform_type}..."):
        result = default_run_service(output_dir=OUTPUT_DIR).start_compilation(
            project, longform_type, selection, angle=angle
        )
    console.print(f"[green]done[/] - ${result.cost.usd:.4f}\n  {result.primary_path}")


@app.command()
def render(document_id: str) -> None:
    """Re-render a stored document to disk (no LLM, no search)."""
    try:
        path = default_run_service(output_dir=OUTPUT_DIR).render_document(document_id)
    except KeyError:
        console.print(f"[red]No document '{document_id}'.[/]")
        raise typer.Exit(1)
    console.print(f"[green]rendered[/] {path}")


@app.command()
def backup() -> None:
    """Snapshot the SQLite database into data/backups/."""
    console.print(f"[green]backup written[/] {backup_mod.backup_database()}")


# ---------------------------------------------------------------------- project


@project_app.command("list")
def project_list() -> None:
    projects = list_projects()
    if not projects:
        console.print("No projects yet. `contentforge project add <slug>`.")
        return
    table = Table("slug", "name", "audience", "tone")
    for p in projects:
        table.add_row(p.slug, p.name, p.audience, p.tone)
    console.print(table)


@project_app.command("show")
def project_show(slug: str) -> None:
    console.print_json(_require_project(slug).model_dump_json())


@project_app.command("add")
def project_add(
    slug: str,
    name: str = typer.Option(..., prompt=True),
    audience: str = typer.Option(..., prompt=True),
    tone: str = typer.Option("clear and direct", prompt=True),
    author: str = typer.Option(..., prompt=True),
) -> None:
    try:
        create_project(ProjectProfile(slug=slug, name=name, audience=audience, tone=tone, author=author))
    except ProjectSlugConflictError:
        console.print(f"[red]Project '{slug}' already exists.[/]")
        raise typer.Exit(1)
    console.print(f"[green]created[/] {slug} - edit the rest at /admin or via the API")


@project_app.command("rm")
def project_rm(slug: str, yes: bool = typer.Option(False, "--yes", "-y")) -> None:
    if not yes:
        typer.confirm(f"Delete project '{slug}'? Generated content is untouched.", abort=True)
    try:
        delete_project(slug)
    except ProjectNotFoundError:
        console.print(f"[red]No project '{slug}'.[/]")
        raise typer.Exit(1)
    console.print(f"[green]deleted[/] {slug}")


# ------------------------------------------------------------------------- runs


@runs_app.command("list")
def runs_list(project_slug: Optional[str] = typer.Option(None, "--project", "-p"),
              limit: int = 20) -> None:
    table = Table("id", "kind", "status", "topic", "cost", "created")
    for r in run_store.list_runs(project_slug=project_slug, limit=limit):
        table.add_row(r.id[:8], r.kind, r.status, r.topic[:48], f"${r.cost_usd:.4f}", r.created_at[:16])
    console.print(table)


@runs_app.command("show")
def runs_show(run_id: str) -> None:
    run = run_store.get_run(run_id) or _run_by_prefix(run_id)
    if run is None:
        console.print(f"[red]No run '{run_id}'.[/]")
        raise typer.Exit(1)
    console.print_json(run.model_dump_json())
    docs = doc_store.list_documents(run_id=run.id)
    if docs:
        table = Table("document id", "type", "review", "rendered")
        for d in docs:
            table.add_row(d.id[:8], d.type, d.review_status, d.rendered_path or "-")
        console.print(table)


def _run_by_prefix(prefix: str):
    return next((r for r in run_store.list_runs(limit=200) if r.id.startswith(prefix)), None)


# ----------------------------------------------------------------------- briefs


@brief_app.command("list")
def brief_list(project_slug: Optional[str] = typer.Option(None, "--project", "-p")) -> None:
    table = Table("id", "topic", "created", "expires")
    for b in brief_store.list_briefs(project_slug=project_slug):
        table.add_row(b.id[:8], b.brief.topic[:48], b.created_at[:16], (b.expires_at or "-")[:16])
    console.print(table)


@brief_app.command("show")
def brief_show(brief_id: str) -> None:
    stored = brief_store.get_brief(brief_id) or _brief_by_prefix(brief_id)
    if stored is None:
        console.print(f"[red]No brief '{brief_id}'.[/]")
        raise typer.Exit(1)
    console.print_json(stored.brief.model_dump_json())


@brief_app.command("update")
def brief_update(brief_id: str) -> None:
    stored = brief_store.get_brief(brief_id) or _brief_by_prefix(brief_id)
    if stored is None or not stored.project_slug:
        console.print(f"[red]No brief '{brief_id}'.[/]")
        raise typer.Exit(1)
    project = _require_project(stored.project_slug)
    with console.status("Re-researching..."):
        updated = default_run_service(output_dir=OUTPUT_DIR).update_brief(project, stored.id)
    console.print(f"[green]updated[/] - {len(updated.key_findings)} findings now")


def _brief_by_prefix(prefix: str):
    return next((b for b in brief_store.list_briefs(limit=200) if b.id.startswith(prefix)), None)


# --------------------------------------------------------- legacy python -c path

BANNER_WIDTH = 80


def run(project_slug: str, topic: str = DEFAULT_TOPIC, topic_slug: str = DEFAULT_SLUG):
    """Generate a blog post for the given project (used by ``main.run``)."""
    try:
        project = get_project(project_slug)
        inputs = build_default_inputs(topic, project, topic_slug)
        print("=" * BANNER_WIDTH)
        print(f"ContentForge - {inputs['topic']}  ({inputs['current_date_and_time']})")
        print("=" * BANNER_WIDTH)
        result, output_path = run_pipeline(inputs, project)
    except Exception as exc:  # pragma: no cover - CLI friendly output
        print("=" * BANNER_WIDTH)
        print(f"ERROR: {exc}")
        print("=" * BANNER_WIDTH)
        raise RuntimeError("An error occurred while generating the blog post.") from exc
    print(f"SUCCESS: {output_path}")
    return result


def print_error(exc: Exception) -> None:  # kept for tests / callers
    print(f"ERROR: {exc}")


if __name__ == "__main__":
    app()
