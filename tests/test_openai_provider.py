"""OpenAIProvider mapping logic, exercised against a hand-rolled fake client so no network
or API key is needed.
"""

from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from src.contentforge.providers import openai_provider as op
from src.contentforge.providers.openai_provider import (
    OpenAIEmbeddingProvider,
    OpenAIProvider,
    _loads,
    _tool_param,
)
from src.contentforge.providers.base import ToolSpec


class Out(BaseModel):
    value: str


def _completion(*, content=None, parsed=None, tool_calls=(), model="gpt-4o-mini"):
    message = SimpleNamespace(content=content, parsed=parsed, tool_calls=list(tool_calls))
    choice = SimpleNamespace(message=message, finish_reason="tool_calls" if tool_calls else "stop")
    usage = SimpleNamespace(prompt_tokens=11, completion_tokens=7)
    return SimpleNamespace(choices=[choice], usage=usage, model=model)


class FakeChatCompletions:
    def __init__(self, result):
        self._result = result
        self.parse_calls = []
        self.create_calls = []

    def parse(self, **kwargs):
        self.parse_calls.append(kwargs)
        return self._result

    def create(self, **kwargs):
        self.create_calls.append(kwargs)
        return self._result


class FakeClient:
    def __init__(self, result):
        self.chat = SimpleNamespace(completions=FakeChatCompletions(result))


@pytest.fixture
def patched(monkeypatch):
    def _install(result):
        client = FakeClient(result)
        monkeypatch.setattr(op._LazyClient, "get", lambda self: client)
        return OpenAIProvider(api_key=None), client

    return _install


def test_tool_param_shape():
    spec = ToolSpec(name="s", description="d", parameters={"type": "object"})
    assert _tool_param(spec) == {
        "type": "function",
        "function": {"name": "s", "description": "d", "parameters": {"type": "object"}},
    }


@pytest.mark.parametrize("raw,expected", [(None, {}), ("", {}), ("{bad", {}), ('["x"]', {}), ('{"a":1}', {"a": 1})])
def test_loads_is_forgiving(raw, expected):
    assert _loads(raw) == expected


def test_parsed_structured_output_becomes_json_content(patched):
    provider, client = patched(_completion(parsed=Out(value="hi")))
    result = provider.complete(
        [{"role": "user", "content": "q"}],
        response_model=Out,
        tools=[ToolSpec("t", "d", {"type": "object"})],
    )

    assert result.content == '{"value":"hi"}'
    assert result.tool_calls == ()
    assert result.tokens_in == 11 and result.tokens_out == 7
    assert client.chat.completions.parse_calls[0]["tools"][0]["function"]["name"] == "t"


def test_tool_calls_are_mapped(patched):
    tc = SimpleNamespace(id="call_1", function=SimpleNamespace(name="web_search", arguments='{"query": "x"}'))
    provider, _ = patched(_completion(tool_calls=[tc]))

    result = provider.complete([{"role": "user", "content": "q"}], response_model=Out)

    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].name == "web_search"
    assert result.tool_calls[0].arguments == {"query": "x"}


def test_no_response_model_uses_create(patched):
    provider, client = patched(_completion(content="plain"))
    result = provider.complete([{"role": "user", "content": "q"}])
    assert result.content == "plain"
    assert client.chat.completions.create_calls and not client.chat.completions.parse_calls


def test_embedding_provider_maps_vectors(monkeypatch):
    resp = SimpleNamespace(
        data=[SimpleNamespace(embedding=[0.1, 0.2]), SimpleNamespace(embedding=[0.3, 0.4])],
        usage=SimpleNamespace(total_tokens=9),
        model="text-embedding-3-small",
    )
    client = SimpleNamespace(embeddings=SimpleNamespace(create=lambda **kw: resp))
    monkeypatch.setattr(op._LazyClient, "get", lambda self: client)

    result = OpenAIEmbeddingProvider().embed(["a", "b"])
    assert result.vectors == ((0.1, 0.2), (0.3, 0.4))
    assert result.tokens == 9


def test_construction_without_key_does_not_raise():
    OpenAIProvider()
    OpenAIEmbeddingProvider()
