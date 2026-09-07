import pytest

from src.contentforge.providers.base import SearchBudget, SearchResult
from src.contentforge.providers.fakes import FakeEmbeddingProvider, FakeLLMProvider, ScriptedResponse
from src.contentforge.providers.serper import (
    InMemorySearchCache,
    NullSearchProvider,
    SearchBudgetExceeded,
    SerperSearchProvider,
    cache_key,
    normalize_query,
)

ORGANIC = {
    "organic": [
        {"title": "A", "link": "https://www.example.com/a", "snippet": "sa", "date": "2026-09-01"},
        {"title": "B", "link": "https://reddit.com/r/x/b", "snippet": "sb"},
        {"title": "C", "link": "https://sevenrooms.com/c", "snippet": "sc"},
    ]
}
NEWS = {"news": [{"title": "N", "link": "https://news.site/n", "snippet": "sn", "source": "News Site", "date": "1h ago"}]}


class RecordingTransport:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, url, payload, headers):
        self.calls.append({"url": url, "payload": payload, "headers": headers})
        return self.responses.pop(0) if self.responses else {}


# --------------------------------------------------------------------- normalize


@pytest.mark.parametrize(
    "query,expected",
    [
        ("AI tools for Restaurants", "ai for restaurants tools"),
        ("restaurants,  AI tools", "ai restaurants tools"),
        ("  Multiple   Spaces  ", "multiple spaces"),
    ],
)
def test_normalize_query_sorts_and_strips(query, expected):
    assert normalize_query(query) == expected


def test_cache_key_is_word_order_independent():
    assert cache_key("ai tools restaurants", kind="organic", limit=8) == cache_key(
        "restaurants ai tools", kind="organic", limit=8
    )
    assert cache_key("x", kind="organic", limit=8) != cache_key("x", kind="news", limit=8)


# ------------------------------------------------------------------------- cache


def test_in_memory_cache_round_trips_and_skips_empty():
    cache = InMemorySearchCache()
    cache.put("k", [SearchResult(title="t", url="u")])
    assert cache.get("k")[0].url == "u"
    cache.put("empty", [])
    assert cache.get("empty") is None
    assert len(cache) == 1


# ------------------------------------------------------------------------- null


def test_null_provider_returns_canned_filtered_by_kind_and_limit():
    provider = NullSearchProvider(
        [SearchResult("a", "u1"), SearchResult("b", "u2"), SearchResult("n", "u3", kind="news")]
    )
    assert [r.url for r in provider.search("anything", limit=1)] == ["u1"]
    assert [r.url for r in provider.search("anything", kind="news")] == ["u3"]


# ------------------------------------------------------------------------ serper


def test_serper_parses_organic_and_applies_domain_rules():
    transport = RecordingTransport(ORGANIC)
    provider = SerperSearchProvider(
        "key",
        exclude_domains=["reddit.com"],
        prefer_domains=["sevenrooms.com"],
        transport=transport,
    )
    results = provider.search("ai restaurants", limit=5)

    assert [r.url for r in results] == [
        "https://sevenrooms.com/c",  # preferred, sorted first
        "https://www.example.com/a",
    ]
    assert transport.calls[0]["payload"] == {"q": "ai restaurants", "num": 5}


def test_serper_news_kind_sets_endpoint_and_parses_news():
    transport = RecordingTransport(NEWS)
    provider = SerperSearchProvider("key", transport=transport)
    results = provider.search("topic", kind="news", recency_days=1)

    assert transport.calls[0]["url"].endswith("/news")
    assert transport.calls[0]["payload"]["tbs"] == "qdr:d"
    assert results[0].source == "News Site" and results[0].kind == "news"


def test_serper_uses_cache_on_second_call():
    transport = RecordingTransport(ORGANIC)
    cache = InMemorySearchCache()
    provider = SerperSearchProvider("key", cache=cache, transport=transport)

    first = provider.search("ai restaurants tools", limit=8)
    second = provider.search("restaurants tools ai", limit=8)  # reordered -> same key

    assert len(transport.calls) == 1
    assert [r.url for r in first] == [r.url for r in second]


def test_serper_budget_blocks_live_calls_but_not_cache_hits():
    transport = RecordingTransport(ORGANIC, ORGANIC)
    cache = InMemorySearchCache()
    budget = SearchBudget(max_calls=1)
    provider = SerperSearchProvider("key", cache=cache, budget=budget, transport=transport)

    provider.search("query one", limit=8)
    assert budget.calls_made == 1

    with pytest.raises(SearchBudgetExceeded):
        provider.search("query two", limit=8)

    # a repeat of the first (cached) query still works even though the budget is spent
    assert provider.search("one query", limit=8)
    assert len(transport.calls) == 1


def test_serper_does_not_cache_empty_response():
    transport = RecordingTransport({"organic": []}, ORGANIC)
    cache = InMemorySearchCache()
    provider = SerperSearchProvider("key", cache=cache, transport=transport)

    assert provider.search("q", limit=8) == []
    provider.search("q", limit=8)
    assert len(transport.calls) == 2  # second call went live, empty was not cached


# ------------------------------------------------------------------------- fakes


def test_fake_llm_records_calls_and_exhausts():
    llm = FakeLLMProvider([ScriptedResponse(content="{}")])
    llm.complete([{"role": "user", "content": "hi"}])
    assert llm.calls[0].messages[0]["content"] == "hi"
    with pytest.raises(AssertionError):
        llm.complete([{"role": "user", "content": "again"}])


def test_fake_embedding_is_deterministic_and_normalized():
    embed = FakeEmbeddingProvider(dim=16)
    a = embed.embed(["hello world"]).vectors[0]
    b = embed.embed(["hello world"]).vectors[0]
    c = embed.embed(["different"]).vectors[0]
    assert a == b and a != c
    assert abs(sum(x * x for x in a) ** 0.5 - 1.0) < 1e-9
