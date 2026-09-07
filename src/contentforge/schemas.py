"""Structured outputs exchanged between agents and pipelines.

Shapes are kept compatible with OpenAI strict structured outputs: no open-ended
``dict[str, ...]`` maps (use a list of small records instead), and every nested type is a
``BaseModel``. Fields carry defaults so we can build them freely in code; the model is still
required to populate them all when a schema is used as a response format.
"""

from typing import List, Literal, Optional

from pydantic import BaseModel

Credibility = Literal["supported", "weak", "unsupported"]


# --------------------------------------------------------------------- blog output


class Section(BaseModel):
    heading: str
    body: str
    pull_quote: Optional[str] = None


class BlogContent(BaseModel):
    title: str
    meta_description: str
    hook: str
    sections: List[Section]
    key_points: List[str]
    call_to_action: Optional[str] = None
    tags: List[str]
    sources: List[str]


# --------------------------------------------------------------- short-form output

LinkPlacement = Literal["body", "first_comment"]


class LinkedInPost(BaseModel):
    """A LinkedIn post: short by length, original by structure (hook -> turn -> insight ->
    soft CTA). Composed from the ``ResearchBrief``, not by compressing a blog post.
    """

    hook: str = ""  # opens the post; the text shown above the ~1,300-char "see more" fold
    body: List[str] = []  # plain-text stanzas, blank-line separated; NO markdown
    cta: str = ""  # soft call to action
    hashtags: List[str] = []  # 3-5, not a blog-length tag list
    link_url: Optional[str] = None  # outbound link, if any
    link_placement: LinkPlacement = "first_comment"  # configurable; body-links may be demoted


# ------------------------------------------------------------------- keyword report


class KeywordReport(BaseModel):
    primary_keywords: List[str] = []
    long_tail: List[str] = []
    trending: List[str] = []
    related_terms: List[str] = []
    informational: List[str] = []
    commercial: List[str] = []
    notes: str = ""


# ----------------------------------------------------------------- research brief


class Source(BaseModel):
    url: str
    title: str = ""
    domain: str = ""
    published: Optional[str] = None
    takeaway: str = ""
    credibility: Optional[Credibility] = None


class KeywordCoverage(BaseModel):
    keyword: str
    covered_by: List[str] = []  # the key_findings that address this keyword


class ResearchBrief(BaseModel):
    topic: str
    summary: str = ""
    key_findings: List[str] = []
    trends: List[str] = []
    audience_impact: List[str] = []
    sources: List[Source] = []
    keyword_coverage: List[KeywordCoverage] = []


# --------------------------------------------------------------------- fact check


class ClaimVerdict(BaseModel):
    claim: str
    verdict: Credibility
    evidence_url: Optional[str] = None
    note: str = ""


class FactCheckReport(BaseModel):
    verdicts: List[ClaimVerdict] = []
    unsupported_claims: List[str] = []  # claims to cut or hedge
    overall: Literal["pass", "revise", "fail"] = "pass"


# ------------------------------------------------------------------------ critique


class CritiqueReport(BaseModel):
    confusing_passages: List[str] = []
    unexplained_terms: List[str] = []
    weak_spots: List[str] = []
    suggestions: List[str] = []


# ---------------------------------------------------------------------- metadata


class DocumentMetadata(BaseModel):
    title_options: List[str] = []
    meta_description: str = ""
    slug: str = ""
    tags: List[str] = []
    internal_links: List[str] = []  # suggestions referencing prior project documents
