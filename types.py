from typing import Literal
from datetime import datetime
# from typing_extensions import Literal



from langgraph.graph import MessagesState
from pydantic import BaseModel, Field, HttpUrl, field_serializer


class UnifiedDoc(BaseModel):
    title: str = Field(..., min_length=2)
    content: str | None = None
    url: HttpUrl
    source: Literal["yandex", "internal"]
    score_rank: float = 0.0
    published_at: datetime | None = None

    @field_serializer("url")
    def serialize_url(self, v: HttpUrl) -> str:
        return str(v)


class SearchResults(BaseModel):
    docs: list[UnifiedDoc] = []
    meta: dict[str, str] = {}


class AgentState(MessagesState, total=False):
    final_answer: str | None
    decision: Literal["TOOL_CALL", "FINAL"] | None
    diagnostics: dict[str, str]
    search_preference: Literal["yandex", "internal", "everywhere"]
