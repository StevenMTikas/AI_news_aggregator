from typing import List, Optional

from pydantic import BaseModel


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
