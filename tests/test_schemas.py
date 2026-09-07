"""Round-trip + default checks for the Phase 3 structured-output schemas, and a guard that
they stay compatible with OpenAI strict structured outputs (no open-ended dict maps).
"""

import pytest

from src.contentforge import schemas
from src.contentforge.schemas import (
    ClaimVerdict,
    CritiqueReport,
    DocumentMetadata,
    FactCheckReport,
    KeywordCoverage,
    KeywordReport,
    ResearchBrief,
    Source,
)

ALL_NEW = [KeywordReport, Source, KeywordCoverage, ResearchBrief, ClaimVerdict, FactCheckReport, CritiqueReport, DocumentMetadata]


def test_research_brief_round_trips():
    brief = ResearchBrief(
        topic="AI reservations",
        summary="s",
        key_findings=["f1"],
        sources=[Source(url="https://x.test", takeaway="t", credibility="supported")],
        keyword_coverage=[KeywordCoverage(keyword="ai booking", covered_by=["f1"])],
    )
    assert ResearchBrief.model_validate_json(brief.model_dump_json()) == brief


def test_minimal_construction_uses_defaults():
    assert KeywordReport().primary_keywords == []
    assert FactCheckReport().overall == "pass"
    assert ResearchBrief(topic="t").sources == []


def test_credibility_is_constrained():
    with pytest.raises(ValueError):
        ClaimVerdict(claim="c", verdict="probably-fine")


@pytest.mark.parametrize("model", ALL_NEW)
def test_no_open_ended_dict_maps_in_schema(model):
    """OpenAI strict mode rejects objects with additionalProperties; a dict[str, X] field
    would serialize to exactly that. Every property here must be a typed, closed shape.
    """
    stack = [model.model_json_schema()]
    seen_defs = model.model_json_schema().get("$defs", {})
    stack.extend(seen_defs.values())
    for schema in stack:
        for prop in schema.get("properties", {}).values():
            assert prop.get("type") != "object" or "properties" in prop or "$ref" in prop, prop


def test_module_exposes_blog_content_still():
    assert hasattr(schemas, "BlogContent") and hasattr(schemas, "Section")
