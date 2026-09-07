from src.contentforge.cost import CostEvent, CostLedger


def test_llm_event_priced_from_table():
    event = CostEvent("llm", "openai", "gpt-4o-mini", tokens_in=1_000_000, tokens_out=1_000_000)
    assert round(event.usd, 4) == round(0.15 + 0.60, 4)


def test_versioned_model_id_still_matches_prefix():
    event = CostEvent("llm", "openai", "gpt-4o-mini-2024-07-18", tokens_in=1_000_000, tokens_out=0)
    assert round(event.usd, 4) == 0.15


def test_unknown_model_is_free_not_an_error():
    assert CostEvent("llm", "openai", "some-future-model", tokens_in=9_999).usd == 0.0


def test_embedding_and_search_pricing():
    assert round(CostEvent("embedding", "openai", "text-embedding-3-small", tokens_in=1_000_000).usd, 4) == 0.02
    assert CostEvent("search", "serper", calls=5).usd == 5 * 0.001


def test_ledger_aggregates():
    ledger = CostLedger()
    ledger.record_llm("openai", "gpt-4o-mini", 1000, 500)
    ledger.record_llm("openai", "gpt-4o-mini", 200, 100)
    ledger.record_search("serper", calls=3)
    ledger.record_embedding("openai", "text-embedding-3-small", 400)

    assert ledger.tokens_in == 1200
    assert ledger.tokens_out == 600
    assert ledger.search_calls == 3
    assert ledger.usd > 0
