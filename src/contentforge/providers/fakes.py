"""Deterministic in-process fakes for tests and offline runs.

``FakeLLMProvider`` replays a script of turns and records what it was asked. ``FakeEmbeddingProvider``
hashes text into a small stable vector. Neither touches the network.
"""

from __future__ import annotations

import hashlib
import math
import struct
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

from pydantic import BaseModel

from .base import EmbeddingResult, LLMResult, ToolCall, ToolSpec

# A scripted turn is either a ScriptedResponse or a callable producing an LLMResult.
TurnFn = Callable[[Sequence[Mapping[str, Any]], Sequence[ToolSpec] | None, type[BaseModel] | None], LLMResult]


@dataclass
class ScriptedResponse:
    content: str | None = None
    tool_calls: Sequence[tuple[str, dict[str, Any]]] = ()
    tokens_in: int = 0
    tokens_out: int = 0
    finish_reason: str | None = None

    def to_result(self, model: str) -> LLMResult:
        calls = tuple(
            ToolCall(id=f"call_{i}", name=name, arguments=dict(args))
            for i, (name, args) in enumerate(self.tool_calls)
        )
        return LLMResult(
            content=self.content,
            tool_calls=calls,
            tokens_in=self.tokens_in,
            tokens_out=self.tokens_out,
            model=model,
            finish_reason=self.finish_reason or ("tool_calls" if calls else "stop"),
        )


@dataclass
class RecordedCall:
    messages: list[dict[str, Any]]
    tools: list[str]
    response_model: str | None
    model: str | None = None


class FakeLLMProvider:
    def __init__(
        self,
        script: Sequence[ScriptedResponse | TurnFn] | None = None,
        *,
        model: str = "fake-model",
    ) -> None:
        self._script: list[ScriptedResponse | TurnFn] = list(script or ())
        self.model = model
        self.calls: list[RecordedCall] = []

    def queue(self, *turns: ScriptedResponse | TurnFn) -> "FakeLLMProvider":
        self._script.extend(turns)
        return self

    def complete(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        tools: Sequence[ToolSpec] | None = None,
        response_model: type[BaseModel] | None = None,
        model: str | None = None,
        temperature: float | None = None,
    ) -> LLMResult:
        self.calls.append(
            RecordedCall(
                messages=[dict(m) for m in messages],
                tools=[t.name for t in (tools or ())],
                response_model=response_model.__name__ if response_model else None,
                model=model,
            )
        )
        if not self._script:
            raise AssertionError(
                f"FakeLLMProvider ran out of scripted turns after {len(self.calls)} call(s)"
            )
        turn = self._script.pop(0)
        if callable(turn):
            return turn(messages, tools, response_model)
        return turn.to_result(model or self.model)


class FakeEmbeddingProvider:
    def __init__(self, *, dim: int = 16, model: str = "fake-embed") -> None:
        self.dim = dim
        self.model = model
        self.embed_calls = 0

    def embed(self, texts: Sequence[str], *, model: str | None = None) -> EmbeddingResult:
        self.embed_calls += 1
        vectors = tuple(self._vector(t) for t in texts)
        tokens = sum(len(t.split()) for t in texts)
        return EmbeddingResult(vectors=vectors, tokens=tokens, model=model or self.model)

    def _vector(self, text: str) -> tuple[float, ...]:
        raw = hashlib.sha256(text.strip().lower().encode("utf-8")).digest()
        floats: list[float] = []
        while len(floats) < self.dim:
            chunk = raw[(len(floats) * 4) % len(raw) : (len(floats) * 4) % len(raw) + 4]
            if len(chunk) < 4:
                raw = hashlib.sha256(raw).digest()
                continue
            floats.append(struct.unpack("<I", chunk)[0] / 2**32 - 0.5)
        norm = math.sqrt(sum(f * f for f in floats)) or 1.0
        return tuple(f / norm for f in floats[: self.dim])
