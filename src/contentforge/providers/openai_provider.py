"""OpenAI-backed LLM and embedding providers.

Importing this module does not require an API key; the client is built lazily on first use.
"""

from __future__ import annotations

import json
import os
from typing import Any, Mapping, Sequence

from pydantic import BaseModel

from .base import EmbeddingResult, LLMResult, ToolCall, ToolSpec

DEFAULT_CHAT_MODEL = "gpt-4o-mini"
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"


def _tool_param(spec: ToolSpec) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": spec.name,
            "description": spec.description,
            "parameters": spec.parameters,
        },
    }


class _LazyClient:
    def __init__(self, api_key: str | None) -> None:
        self._api_key = api_key
        self._client: Any | None = None

    def get(self) -> Any:
        if self._client is None:
            from openai import OpenAI  # imported here so tests need not install a key

            self._client = OpenAI(api_key=self._api_key or os.getenv("OPENAI_API_KEY"))
        return self._client


class OpenAIProvider:
    def __init__(self, api_key: str | None = None, *, default_model: str = DEFAULT_CHAT_MODEL) -> None:
        self.default_model = default_model
        self._client = _LazyClient(api_key)

    def complete(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        tools: Sequence[ToolSpec] | None = None,
        response_model: type[BaseModel] | None = None,
        model: str | None = None,
        temperature: float | None = None,
    ) -> LLMResult:
        client = self._client.get()
        kwargs: dict[str, Any] = {
            "model": model or self.default_model,
            "messages": list(messages),
        }
        if tools:
            kwargs["tools"] = [_tool_param(t) for t in tools]
        if temperature is not None:
            kwargs["temperature"] = temperature

        if response_model is not None:
            completion = client.chat.completions.parse(response_format=response_model, **kwargs)
        else:
            completion = client.chat.completions.create(**kwargs)

        choice = completion.choices[0]
        message = choice.message
        calls = tuple(
            ToolCall(
                id=tc.id,
                name=tc.function.name,
                arguments=_loads(tc.function.arguments),
            )
            for tc in (message.tool_calls or ())
        )
        content = message.content
        parsed = getattr(message, "parsed", None)
        if parsed is not None and not calls:
            content = parsed.model_dump_json()

        usage = completion.usage
        return LLMResult(
            content=content,
            tool_calls=calls,
            tokens_in=getattr(usage, "prompt_tokens", 0) or 0,
            tokens_out=getattr(usage, "completion_tokens", 0) or 0,
            model=completion.model,
            finish_reason=choice.finish_reason or "stop",
        )


class OpenAIEmbeddingProvider:
    def __init__(self, api_key: str | None = None, *, default_model: str = DEFAULT_EMBEDDING_MODEL) -> None:
        self.default_model = default_model
        self._client = _LazyClient(api_key)

    def embed(self, texts: Sequence[str], *, model: str | None = None) -> EmbeddingResult:
        client = self._client.get()
        resp = client.embeddings.create(model=model or self.default_model, input=list(texts))
        return EmbeddingResult(
            vectors=tuple(tuple(d.embedding) for d in resp.data),
            tokens=getattr(resp.usage, "total_tokens", 0) or 0,
            model=resp.model,
        )


def _loads(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}
