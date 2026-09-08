"""Persist a run's ``CostLedger`` into the ``cost_event`` table and read rollups back."""

from __future__ import annotations

from ..cost import CostLedger
from . import connection, utcnow


def save_ledger(run_id: str, ledger: CostLedger) -> None:
    now = utcnow()
    rows = [
        (run_id, e.kind, e.provider, e.model, e.tokens_in, e.tokens_out, e.calls, e.usd, now)
        for e in ledger.events
    ]
    if not rows:
        return
    with connection() as conn:
        conn.executemany(
            """INSERT INTO cost_event
                   (run_id, kind, provider, model, tokens_in, tokens_out, calls, usd, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            rows,
        )


def run_totals(run_id: str) -> dict:
    with connection() as conn:
        row = conn.execute(
            """SELECT COALESCE(SUM(usd), 0)                                    AS usd,
                      COALESCE(SUM(CASE WHEN kind='llm' THEN tokens_in END), 0) AS tokens_in,
                      COALESCE(SUM(CASE WHEN kind='llm' THEN tokens_out END), 0) AS tokens_out,
                      COALESCE(SUM(CASE WHEN kind='search' THEN calls END), 0)  AS search_calls
               FROM cost_event WHERE run_id = ?""",
            (run_id,),
        ).fetchone()
    return dict(row)


def run_breakdown(run_id: str) -> list[dict]:
    """Cost grouped by kind + model, for a run-detail view."""
    with connection() as conn:
        rows = conn.execute(
            """SELECT kind, model,
                      SUM(tokens_in) AS tokens_in, SUM(tokens_out) AS tokens_out,
                      SUM(calls) AS calls, SUM(usd) AS usd
               FROM cost_event WHERE run_id = ?
               GROUP BY kind, model ORDER BY usd DESC""",
            (run_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def project_totals(project_slug: str) -> dict:
    with connection() as conn:
        row = conn.execute(
            """SELECT COALESCE(SUM(c.usd), 0) AS usd,
                      COALESCE(SUM(CASE WHEN c.kind='search' THEN c.calls END), 0) AS search_calls,
                      COUNT(DISTINCT c.run_id) AS runs
               FROM cost_event c JOIN run r ON r.id = c.run_id
               WHERE r.project_slug = ?""",
            (project_slug,),
        ).fetchone()
    return dict(row)
