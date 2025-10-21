import asyncio
import logging
import os
import re
from datetime import datetime
from typing import Any

import aiohttp
import trafilatura
from bs4 import BeautifulSoup

from search.yandex_search_api import YandexSearchAPIClient
from search.yandex_search_api.client import SearchType

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36 Edg/134.0.0.0"
)
DEFAULT_TIMEOUT = 30  # секунд


def _get_proxy_config() -> str | None:
    """Получает прокси из переменных окружения."""
    for proxy_var in ["HTTP_PROXY", "HTTPS_PROXY"]:
        proxy_url = os.getenv(proxy_var)
        if proxy_url:
            return proxy_url
    return None


def normalize_whitespace(s: str) -> str:
    """Нормализует пробельные символы в тексте."""
    return re.sub(r"\s+", " ", (s or "").strip())


def _parse_yandex_modtime(modtime_str: str) -> datetime | None:
    """
    Парсит дату из формата Yandex modtime (например, 20250307T093511).
    """
    try:
        return datetime.strptime(modtime_str, "%Y%m%dT%H%M%S")
    except (ValueError, AttributeError):
        logger.warning(f"Не удалось распарсить modtime: {modtime_str}")
        return None


def _extract_title_from_html(html: str) -> str:
    """
    Извлекает заголовок из HTML.

    Пытается найти title в следующем порядке:
    1. <title> тег
    2. og:title meta
    3. twitter:title meta
    """
    try:
        soup = BeautifulSoup(html or "", "html.parser")
        if soup.title and soup.title.string:
            t = soup.title.string.strip()
            if t:
                return t
        og = soup.find("meta", property="og:title")
        if og and og.get("content"):
            return og["content"].strip()
        tw = soup.find("meta", attrs={"name": "twitter:title"})
        if tw and tw.get("content"):
            return tw["content"].strip()
    except Exception:
        pass
    return "Без заголовка"


class YandexSearchClient:
    """
    Generic client для поиска через Yandex Search API без domain-specific логики.

    Выполняет:
    1. Поиск через Yandex API -> получение URL
    2. Асинхронный скрапинг каждого URL
    3. Извлечение текста через trafilatura (fallback на BeautifulSoup)
    4. Возврат сырых результатов
    """

    def __init__(self):
        oauth_token = os.getenv("YANDEX_OAUTH_TOKEN")
        folder_id = os.getenv("YANDEX_FOLDER_ID")
        self.client = YandexSearchAPIClient(folder_id=folder_id, oauth_token=oauth_token)

    async def _scrape_page(
        self,
        url: str,
        session: aiohttp.ClientSession | None = None,
        proxy: str | None = None,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> dict[str, str]:
        """
        Скрапит одну страницу и извлекает заголовок и текст.
        """
        headers = {"User-Agent": USER_AGENT}

        own_session = session is None
        if own_session:
            session = aiohttp.ClientSession(headers=headers)
        assert session is not None

        try:
            async with session.get(url, proxy=proxy, timeout=aiohttp.ClientTimeout(total=timeout)) as r:
                if r.status != 200:
                    return {"title": "Ошибка", "content": f"HTTP статус: {r.status}"}
                html = await r.text(errors="ignore")
        except asyncio.TimeoutError:
            logger.warning(f"Тайм-аут при загрузке {url}")
            return {"title": "Ошибка", "content": f"Тайм-аут при загрузке {url}"}
        except aiohttp.ClientError as e:
            logger.error(f"Ошибка aiohttp при загрузке {url}: {e}")
            return {"title": "Ошибка", "content": f"Ошибка aiohttp при загрузке {url}: {e}"}
        except Exception as e:
            logger.exception(f"Неожиданная ошибка при загрузке {url}")
            return {"title": "Ошибка", "content": f"Неожиданная ошибка при загрузке {url}: {e}"}
        finally:
            if own_session:
                await session.close()

        title = _extract_title_from_html(html)

        # Извлекаем текст через trafilatura
        try:
            extracted = trafilatura.extract(html, include_comments=False, include_tables=False) or ""
        except Exception:
            extracted = None

        if extracted:
            return {"title": title, "content": normalize_whitespace(extracted)}

        # Fallback: BeautifulSoup
        try:
            soup = BeautifulSoup(html, "html.parser")

            # Удаляем шум
            for tag in soup(["script", "style", "header", "footer", "nav", "aside"]):
                tag.decompose()

            content = soup.get_text(separator="\n", strip=True)
            content = normalize_whitespace(content)

            # Еще одна попытка извлечь title из soup
            if (not title or title == "Без заголовка") and soup.title and soup.title.string:
                title = soup.title.string.strip() or "Без заголовка"

            return {"title": title, "content": content}
        except Exception as e:
            logger.exception(f"Ошибка при обработке HTML для {url}")
            return {"title": "Ошибка", "content": f"Ошибка при обработке HTML: {e}"}

    async def search(
        self, query: str, num_results: int = 5, search_type: SearchType = SearchType.RUSSIAN
    ) -> list[dict[str, Any]]:
        """
        Выполняет поиск в Yandex и асинхронно скрапит страницы.
        """
        try:
            search_results = self.client.get_links(query_text=query, search_type=search_type, n_links=num_results)

            if not search_results:
                logger.warning(f"Yandex не вернул ссылок для запроса: {query}")
                return []

            logger.info(f"Yandex вернул {len(search_results)} ссылок, начинаю скрапинг...")

            # Параллельный асинхронный скрапинг
            proxy_url = _get_proxy_config()
            headers = {"User-Agent": USER_AGENT}

            async with aiohttp.ClientSession(headers=headers) as session:
                tasks = [self._scrape_page(item["url"], session=session, proxy=proxy_url) for item in search_results]
                pages = await asyncio.gather(*tasks, return_exceptions=True)

            processed_items: list[dict[str, Any]] = []
            errors = 0

            for search_item, page_data in zip(search_results, pages):
                if isinstance(page_data, Exception):
                    logger.error(f"Ошибка при скрапинге {search_item['url']}: {page_data}")
                    errors += 1
                    continue

                item = {
                    "title": page_data.get("title", "Без заголовка"),
                    "url": search_item["url"],
                    "content": page_data.get("content", ""),
                }

                # Добавляем published_at если есть modtime
                if "modtime" in search_item:
                    published_at = _parse_yandex_modtime(search_item["modtime"])
                    if published_at:
                        item["published_at"] = published_at

                processed_items.append(item)

            logger.info(f"Скрапинг завершен: успешно {len(processed_items)}, ошибок {errors}")
            return processed_items

        except Exception:
            logger.exception(f"Произошла общая ошибка при поиске в Yandex для запроса: {query}")
            return []


# ============================== Пример ==============================
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format="%(levelname)s: %(message)s")

    try:
        yandex_client = YandexSearchClient()

        test_query = "когда сдавать баланс за 2024 год в ГИР БО"
        results = asyncio.run(yandex_client.search(query=test_query, num_results=3))

        print(f"\nНайдено документов: {len(results)}")

        for i, doc in enumerate(results, 1):
            print(f"\n--- Документ #{i} ---")
            print(f"Заголовок: {doc['title']}")
            print(f"URL: {doc['url']}")
            if "published_at" in doc:
                print(f"Дата: {doc['published_at']}")
            if doc.get("content"):
                print(f"Содержимое: {doc['content'][:200]}{'...' if len(doc['content']) > 200 else ''}")

    except ValueError as e:
        print(f"\nОшибка при создании экземпляра: {e}")
    except Exception as e:
        print(f"\nПроизошла ошибка во время теста: {e}")
        import traceback

        traceback.print_exc()
