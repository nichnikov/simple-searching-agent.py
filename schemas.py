# schemas.py

from pydantic import BaseModel, field_validator
from typing import Any, Dict, List, Optional, Union

class SearchParams(BaseModel):
    pubAlias: Optional[str] = None
    fixedregioncode: Optional[str] = None
    isUseHints: Optional[str] = None
    fstring: Optional[str] = None
    sortby: Optional[str] = None
    status: Optional[str] = None
    dataformat: Optional[str] = None
    pubdivid: Optional[int] = None
    pubId: Optional[int] = None
    page: Optional[int] = None

    class Config:
        extra = "allow"


class SearchItem(BaseModel):
    id: Optional[str] = None
    moduleId: Optional[str] = None
    url: Optional[str] = None
    docName: Optional[str] = None
    snippet: Optional[str] = None
    anchor: Optional[str] = None
    position: Optional[int] = None
    score: Optional[float] = None
    isEtalon: Optional[bool] = None
    isPopular: Optional[bool] = None

    @field_validator("id", "moduleId", mode="before")
    @classmethod
    def convert_to_string(cls, v):
        if v is not None:
            return str(v)
        return v

    class Config:
        extra = "allow"


class SearchResult(BaseModel):
    """
    Модель для ОДНОГО результата поиска.
    Содержит информацию о найденном элементе и сам загруженный документ в виде сырого словаря.
    """
    item: SearchItem
    document: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

# --- НОВЫЙ КЛАСС ---
# Добавлен класс UnifiedDoc для структурирования ответа от API документов

class UnifiedDoc(BaseModel):
    """
    Модель для структурирования данных документа, полученного от DOC_API_URL.
    Она представляет собой "унифицированное" представление документа,
    которое можно использовать для валидации и удобного доступа к полям.
    """
    id: Optional[str] = None
    moduleId: Optional[str] = None
    docName: Optional[str] = None
    
    # Поле 'content' может быть строкой (содержащей JSON) или уже распарсенным словарем.
    # Поэтому допускаем оба типа для гибкости.
    content: Optional[Union[str, Dict[str, Any]]] = None

    class Config:
        # Позволяет модели игнорировать лишние поля, которые приходят от API,
        # но не определены в этой схеме.
        extra = "allow"