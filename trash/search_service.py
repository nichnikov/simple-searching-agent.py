import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

from pydantic import HttpUrl

from search_config import (
    ACTION_DEFAULT_SCORE,
    ACTION_PAGES,
    ACTION_SEARCH_BASE_PARAMS,
    ACTION_URL_FORMAT,
    YANDEX_DEFAULT_WEIGHT,
    YANDEX_DOMAIN_WEIGHTS,
)

from types import SearchResults, UnifiedDoc
from action_search import ActionSearchClient
from yandex_search import YandexSearchClient

logger = logging.getLogger(__name__)


class JurAgentSearchService:
    """
    Сервис поиска для юридического агента с domain-specific логикой.
    """

    def __init__(self):
        self.action_client = ActionSearchClient()
        self.yandex_client = YandexSearchClient()

    def search_internal(self, query: str, limit: int = 5) -> SearchResults:
        """
        Синхронная обёртка для async поиска во внутренней базе.
        """
        return asyncio.run(self.search_internal_async(query, limit))

    async def search_internal_async(self, query: str, limit: int = 5) -> SearchResults:
        """
        Выполняет поиск во внутренней базе (1gl.ru) с конфигурацией для юр. агента.
        """
        logger.info(f"Internal search: query='{query}', limit={limit}")

        try:
            params = ACTION_SEARCH_BASE_PARAMS.model_copy(update={"fstring": query})

            raw_result = await self.action_client.search_async(search_params=params, pages=ACTION_PAGES)
            raw_docs = raw_result["parsed"][:limit]

            docs = []
            for r in raw_docs:
                url = ACTION_URL_FORMAT.format(moduleId=r["moduleId"], id=r["id"])
                docs.append(
                    UnifiedDoc(
                        title=r.get("title", "Без заголовка"),
                        content=r.get("plain_text"),
                        url=HttpUrl(url),
                        source="internal",
                        score_rank=ACTION_DEFAULT_SCORE,
                    )
                )

            logger.info(f"Internal search completed: {len(docs)} documents found")
            return SearchResults(docs=docs, meta={"provider": "internal", "count": str(len(docs))})

        except Exception as e:
            logger.error(f"Internal search error: {e}")
            logger.exception("Internal search exception details")
            return SearchResults(docs=[], meta={"provider": "internal", "count": "0", "error": str(e)})

    def search_yandex(self, query: str, limit: int = 5) -> SearchResults:
        """
        Синхронная обёртка для async поиска в Yandex.
        """
        return asyncio.run(self.search_yandex_async(query, limit))

    async def search_yandex_async(self, query: str, limit: int = 5) -> SearchResults:
        """
        Выполняет поиск в Yandex с ранжированием по доменам.
        """
        logger.info(f"Yandex search: query='{query}', limit={limit}")

        try:
            raw_results = await self.yandex_client.search(query, num_results=limit)

            docs = []
            for r in raw_results:
                try:
                    docs.append(
                        UnifiedDoc(
                            title=r["title"],
                            content=r.get("content"),
                            url=HttpUrl(r["url"]),
                            source="yandex",
                            published_at=r.get("published_at"),
                            score_rank=0.0,  # Будет установлен в _rank_by_domain
                        )
                    )
                except Exception as e:
                    logger.error(f"Error creating UnifiedDoc for {r.get('url')}: {e}")
                    continue

            docs = self._rank_by_domain(docs)

            logger.info(f"Yandex search completed: {len(docs)} documents found and ranked")
            return SearchResults(docs=docs, meta={"provider": "yandex", "count": str(len(docs))})

        except Exception as e:
            logger.error(f"Yandex search error: {e}")
            logger.exception("Yandex search exception details")
            return SearchResults(docs=[], meta={"provider": "yandex", "count": "0", "error": str(e)})

    def search_everywhere(self, query: str, limit: int = 5) -> SearchResults:
        """
        Выполняет параллельный поиск во внутренней базе и Yandex.
        """
        logger.info(f"Everywhere search: query='{query}', limit={limit}")

        # Параллельный поиск в обоих источниках
        with ThreadPoolExecutor(max_workers=2) as executor:
            future_internal = executor.submit(self.search_internal, query, limit)
            future_yandex = executor.submit(self.search_yandex, query, limit)

            internal_results = future_internal.result()
            yandex_results = future_yandex.result()

        # Объединяем результаты
        all_docs = internal_results.docs + yandex_results.docs

        if not all_docs:
            logger.warning("No documents found in both sources")
            return SearchResults(docs=[], meta={"provider": "everywhere", "count": "0"})

        # Ранжируем по score и берём топ результатов
        ranked = sorted(all_docs, key=lambda d: d.score_rank, reverse=True)[:limit]

        logger.info(
            f"Everywhere search completed: {len(internal_results.docs)} internal + "
            f"{len(yandex_results.docs)} yandex = {len(all_docs)} total, "
            f"returning top {len(ranked)}"
        )

        return SearchResults(
            docs=ranked,
            meta={
                "provider": "everywhere",
                "count": str(len(ranked)),
                "internal_count": str(len(internal_results.docs)),
                "yandex_count": str(len(yandex_results.docs)),
            },
        )

    def _rank_by_domain(self, docs: list[UnifiedDoc]) -> list[UnifiedDoc]:
        """
        Ранжирует документы по весу домена для юридической тематики.
        """
        for doc in docs:
            host = urlparse(str(doc.url)).netloc.lower()
            doc.score_rank = YANDEX_DOMAIN_WEIGHTS.get(host, YANDEX_DEFAULT_WEIGHT)

        return sorted(docs, key=lambda d: d.score_rank, reverse=True)
