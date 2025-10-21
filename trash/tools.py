import logging

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from search_service import JurAgentSearchService
from types import UnifiedDoc
from search_data import SearchDocument, SearchToolResult

logger = logging.getLogger(__name__)

_search_service = JurAgentSearchService()


def _format_documents(docs: list[UnifiedDoc], total: int) -> str:
    """
    Форматирует список документов в строку для LLM.
    """
    if not docs:
        return "Документы не найдены."

    lines = [f"Найдено документов: {total}\n"]
    total_content_size = 0

    for i, doc in enumerate(docs, 1):
        lines.append(f"{i}. {doc.title}")
        lines.append(f"   URL: {doc.url}")
        lines.append(f"   Источник: {doc.source}")

        if doc.content:
            content_size = len(doc.content)
            total_content_size += content_size

            # Отправляем первые 10000 символов содержимого
            # TODO: Вместо простого обрезания нужно отправлять частями (?)
            content_preview = doc.content[:10000]
            lines.append(f"   Содержимое: {content_preview}")

            if len(doc.content) > 10000:
                lines.append(f"   [Контент обрезан, полный размер: {len(doc.content)} символов]")

            logger.info(
                f"Document '{doc.title[:50]}...': content_size={content_size}, "
                f"source={doc.source}, score={doc.score_rank:.2f}"
            )

        lines.append("")

    logger.info(f"Total content size sent to LLM: {total_content_size} characters")
    return "\n".join(lines)


def _append_search_ui_marker(text: str, tool_name: str, query: str, docs: list[UnifiedDoc]) -> str:
    """
    Добавляет в конец текстового ответа специальный маркер с JSON-пейлоадом
    для UI. Сервис вытащит этот JSON и положит его в custom_data сообщения инструмента.
    """
    search_result = SearchToolResult(
        tool_name=tool_name,
        query=query,
        documents=[
            SearchDocument(
                title=doc.title,
                url=doc.url,
                snippet=doc.content[:300] if doc.content else "",
                source=doc.source,
            )
            for doc in docs
        ],
        total_found=len(docs),
    )

    return f"{text}\n\n__SEARCH_TOOL_RESULT__:{search_result.model_dump_json()}"


@tool
def search_internal(query: str, limit: int = 5, config: RunnableConfig | None = None) -> str:
    """
    Ищет релевантные документы во внутренней базе Актиона (1gl.ru).

    Используй этот инструмент когда:
    - Пользователь явно попросил искать во внутренней базе или в Актионе
    - Текущее предпочтение поиска установлено на "internal"
    - Нужна информация из проверенной внутренней базы документов

    Примеры запросов:
    - "Как заполнить налоговую декларацию УСН за 2024 год"
    - "Статья НК РФ об НДС для IT компаний"
    - "Правила ведения кассовых операций"

    Args:
        query: Чёткий поисковый запрос по юридической или бухгалтерской тематике
        limit: Максимальное количество результатов от 1 до 10. По умолчанию 5

    Returns:
        Строка с информацией о найденных документах
    """
    logger.info(f"search_internal called: query='{query}', limit={limit}")

    if not query or not query.strip():
        logger.warning("Empty query provided")
        return "Документы не найдены. Запрос пустой."

    limit = max(1, min(limit, 10))

    try:
        results = _search_service.search_internal(query, limit)

        return _append_search_ui_marker(
            _format_documents(results.docs, len(results.docs)),
            "search_internal",
            query,
            results.docs,
        )
    except Exception as e:
        logger.error(f"Internal search error: {e}")
        return f"Ошибка при поиске во внутренней базе: {str(e)}"


@tool
def search_yandex(query: str, limit: int = 5, config: RunnableConfig | None = None) -> str:
    """
    Ищет релевантные документы в Яндексе (интернет).

    Используй этот инструмент когда:
    - Пользователь явно попросил искать в Яндексе или интернете
    - Текущее предпочтение поиска установлено на "yandex"
    - Нужна актуальная информация из открытых источников

    Примеры запросов:
    - "Как заполнить налоговую декларацию УСН за 2024 год"
    - "Статья НК РФ об НДС для IT компаний"
    - "Правила ведения кассовых операций"

    Args:
        query: Чёткий поисковый запрос по юридической или бухгалтерской тематике
        limit: Максимальное количество результатов от 1 до 10. По умолчанию 5

    Returns:
        Строка с информацией о найденных документах
    """
    logger.info(f"search_yandex called: query='{query}', limit={limit}")

    if not query or not query.strip():
        logger.warning("Empty query provided")
        return "Документы не найдены. Запрос пустой."

    limit = max(1, min(limit, 10))

    try:
        results = _search_service.search_yandex(query, limit)

        return _append_search_ui_marker(
            _format_documents(results.docs, len(results.docs)),
            "search_yandex",
            query,
            results.docs,
        )
    except Exception as e:
        logger.error(f"Yandex search error: {e}")
        return f"Ошибка при поиске в Яндексе: {str(e)}"


@tool
def search_everywhere(query: str, limit: int = 5, config: RunnableConfig | None = None) -> str:
    """
    Ищет релевантные документы одновременно в Яндексе и внутренней базе.

    Используй этот инструмент когда:
    - Пользователь явно попросил искать везде или во всех источниках
    - Текущее предпочтение поиска установлено на "everywhere" (по умолчанию)
    - Нужен максимально полный охват информации из всех доступных источников

    Примеры запросов:
    - "Как заполнить налоговую декларацию УСН за 2024 год"
    - "Статья НК РФ об НДС для IT компаний"
    - "Правила ведения кассовых операций"

    Args:
        query: Чёткий поисковый запрос по юридической или бухгалтерской тематике
        limit: Максимальное количество результатов от 1 до 10. По умолчанию 5

    Returns:
        Строка с информацией о найденных документах из обоих источников
    """
    logger.info(f"search_everywhere called: query='{query}', limit={limit}")

    if not query or not query.strip():
        logger.warning("Empty query provided")
        return "Документы не найдены. Запрос пустой."

    limit = max(1, min(limit, 10))

    try:
        results = _search_service.search_everywhere(query, limit)

        return _append_search_ui_marker(
            _format_documents(results.docs, len(results.docs)),
            "search_everywhere",
            query,
            results.docs,
        )
    except Exception as e:
        logger.error(f"Everywhere search error: {e}")
        return f"Ошибка при поиске: {str(e)}"
