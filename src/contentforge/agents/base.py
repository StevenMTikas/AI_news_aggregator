"""The ``Agent`` value type, the ``Tool`` wrapper, a per-agent budget, and a search tool."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

from pydantic import BaseModel

from ..providers.base import SearchProvider, SearchResult, ToolSpec
from ..providers.serper import SearchBudgetExceeded


class _SoftMap(dict):
    """format_map helper: leave unknown ``{placeholders}`` untouched instead of raising."""

    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def render_prompt(template: str, context: Mapping[str, Any]) -> str:
    """Fill ``{name}`` placeholders from ``context``; unknown names pass through unchanged.

    Literal braces still need doubling (``{{`` / ``}}``), same as ``str.format``.
    """
    return template.format_map(_SoftMap(context))


@dataclass
class Tool:
    spec: ToolSpec
    fn: Callable[..., Any]

    def run(self, **kwargs: Any) -> str:
        out = self.fn(**kwargs)
        return out if isinstance(out, str) else json.dumps(out, default=str)


@dataclass
class AgentBudget:
    max_iterations: int = 6
    max_tool_calls: int = 8
    tool_calls_made: int = 0

    @property
    def tool_calls_left(self) -> int:
        return max(0, self.max_tool_calls - self.tool_calls_made)

    def record_tool_call(self, n: int = 1) -> None:
        self.tool_calls_made += n


@dataclass(frozen=True)
class Agent:
    name: str
    system_prompt: str
    output_schema: type[BaseModel]
    model: str | None = None
    tools: tuple[Tool, ...] = ()
    temperature: float | None = None
    instructions: str | None = None  # optional extra user-turn framing

    def render_system_prompt(self, context: Mapping[str, Any]) -> str:
        return render_prompt(self.system_prompt, context)

    def tool_specs(self) -> list[ToolSpec]:
        return [t.spec for t in self.tools]


# --------------------------------------------------------------------- search tool


def _format_results(results: Sequence[SearchResult]) -> str:
    if not results:
        return "No results."
    lines: list[str] = []
    for i, r in enumerate(results, 1):
        meta = ", ".join(p for p in (r.source, r.published) if p)
        head = f"{i}. {r.title}" + (f" ({meta})" if meta else "")
        lines.append(f"{head}\n   {r.url}\n   {r.snippet}".rstrip())
    return "\n".join(lines)


def search_tool(
    provider: SearchProvider,
    *,
    name: str = "web_search",
    default_kind: str = "organic",
    recency_days: int | None = None,
    limit: int = 8,
) -> Tool:
    """Wrap a :class:`SearchProvider` as a model-callable tool.

    A spent :class:`SearchBudget` is reported back to the model as text (so it finishes from
    what it has) rather than raising out of the loop.
    """

    spec = ToolSpec(
        name=name,
        description=(
            "Search the web for current information. Use specific queries; call again with "
            "different wording to broaden coverage."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "the search query"},
                "kind": {
                    "type": "string",
                    "enum": ["organic", "news"],
                    "description": "'news' for recent headlines, 'organic' otherwise",
                },
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    )

    def _run(query: str, kind: str | None = None) -> str:
        try:
            results = provider.search(
                query,
                kind=kind or default_kind,
                recency_days=recency_days,
                limit=limit,
            )
        except SearchBudgetExceeded:
            return "Search budget exhausted. Answer using the information already gathered."
        return _format_results(results)

    return Tool(spec=spec, fn=_run)
