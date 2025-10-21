from pydantic import BaseModel, Field, HttpUrl, field_serializer


class SearchDocument(BaseModel):
    """Документ для отображения в UI."""

    title: str = Field(description="Заголовок документа")
    url: HttpUrl = Field(description="Ссылка на документ")
    snippet: str = Field(description="Короткий сниппет из документа")
    source: str = Field(description="Источник документа (yandex, internal)")

    @field_serializer("url")
    def serialize_url(self, v: HttpUrl) -> str:
        return str(v)


class SearchToolResult(BaseModel):
    """Результат поиска для отображения в UI."""

    tool_name: str = Field(description="Название инструмента поиска")
    query: str = Field(description="Поисковый запрос")
    documents: list[SearchDocument] = Field(description="Найденные документы")
    total_found: int = Field(description="Общее количество найденных документов")
