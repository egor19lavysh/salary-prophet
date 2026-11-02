import asyncio
import logging
import os
import random
import re
from pathlib import Path

from bs4 import BeautifulSoup
from curl_cffi.requests import AsyncSession

from config import (
    HH_BASE_URL,
    ITEMS_ON_PAGE,
    KEYWORDS,
    CONCURRENCY,
    MAX_RETRIES,
    REQUEST_TIMEOUT,
    REQUEST_DELAY,
    IDS_FILE,
    LOG_FILE,
)


VACANCY_ID_PATTERN = re.compile(r"/vacancy/(\d+)")


# ============================================================
# LOGGING
# ============================================================

Path(LOG_FILE).parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)

logger = logging.getLogger(__name__)


# ============================================================
# LOAD EXISTING IDS
# ============================================================

def load_existing_ids() -> set[str]:
    """
    Загружает уже собранные ID из файла.
    """

    path = Path(IDS_FILE)

    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()

        logger.info("Файл %s не найден — создан новый", IDS_FILE)

        return set()

    with path.open("r", encoding="utf-8") as file:
        ids = {
            line.strip()
            for line in file
            if line.strip()
        }

    logger.info(
        "Загружено существующих ID: %s",
        len(ids),
    )

    return ids


# ============================================================
# SAVE ID
# ============================================================

def append_id(vacancy_id: str) -> None:
    """
    Немедленно записывает новый ID на диск.
    """

    with open(
        IDS_FILE,
        "a",
        encoding="utf-8",
        buffering=1,
    ) as file:

        file.write(vacancy_id + "\n")
        file.flush()

        # Гарантируем запись на диск
        os.fsync(file.fileno())


# ============================================================
# PARSE VACANCY IDS
# ============================================================

def parse_vacancy_ids(html: str) -> set[str]:
    """
    Извлекает ID вакансий из HTML страницы поиска HH.ru.
    """

    soup = BeautifulSoup(html, "lxml")

    vacancy_ids = set()

    vacancy_cards = soup.select(
        '[data-qa="vacancy-serp__vacancy"]'
    )

    for card in vacancy_cards:

        links = card.select(
            'a[href*="/vacancy/"]'
        )

        for link in links:

            href = link.get("href")

            if not href:
                continue

            match = VACANCY_ID_PATTERN.search(href)

            if match:
                vacancy_ids.add(match.group(1))

    return vacancy_ids


# ============================================================
# BUILD URL
# ============================================================

def build_search_url(
    keyword: str,
    page: int,
) -> str:

    return (
        f"{HH_BASE_URL}"
        f"?text={keyword}"
        f"&search_field=name"
        f"&search_field=company_name"
        f"&search_field=description"
        f"&page={page}"
        f"&items_on_page={ITEMS_ON_PAGE}"
        f"&label=with_salary"
        f"&enable_snippets=true"
    )


# ============================================================
# REQUEST
# ============================================================

async def fetch_page(
    session: AsyncSession,
    url: str,
) -> str | None:

    for attempt in range(1, MAX_RETRIES + 1):

        try:

            response = await session.get(
                url,
                timeout=REQUEST_TIMEOUT,
                impersonate="chrome",
            )

            if response.status_code == 200:
                return response.text

            if response.status_code == 404:
                return None

            logger.warning(
                "HTTP %s | попытка %s/%s | %s",
                response.status_code,
                attempt,
                MAX_RETRIES,
                url,
            )

        except Exception as exc:

            logger.warning(
                "Ошибка запроса | попытка %s/%s | %s",
                attempt,
                MAX_RETRIES,
                exc,
            )

        await asyncio.sleep(
            random.uniform(*REQUEST_DELAY)
        )

    return None


# ============================================================
# PARSE ONE KEYWORD
# ============================================================

async def parse_keyword(
    keyword: str,
    session: AsyncSession,
    existing_ids: set[str],
    ids_lock: asyncio.Lock,
):

    page = 0

    keyword_total = 0
    keyword_new = 0

    logger.info(
        "▶ Начинаем поиск: %s",
        keyword,
    )

    while True:

        url = build_search_url(
            keyword=keyword,
            page=page,
        )

        html = await fetch_page(
            session=session,
            url=url,
        )

        if html is None:

            logger.info(
                "■ Поиск завершён: %s | страница %s",
                keyword,
                page,
            )

            break

        vacancy_ids = parse_vacancy_ids(html)

        if not vacancy_ids:

            logger.info(
                "■ Вакансии закончились: %s | страница %s",
                keyword,
                page,
            )

            break

        page_new = 0

        async with ids_lock:

            for vacancy_id in vacancy_ids:

                keyword_total += 1

                if vacancy_id in existing_ids:
                    continue

                existing_ids.add(vacancy_id)

                append_id(vacancy_id)

                page_new += 1
                keyword_new += 1

        logger.info(
            "  %s | page=%s | found=%s | new=%s | total=%s",
            keyword,
            page,
            len(vacancy_ids),
            page_new,
            len(existing_ids),
        )

        page += 1

        await asyncio.sleep(
            random.uniform(*REQUEST_DELAY)
        )

    logger.info(
        "✓ %s | найдено=%s | новых=%s",
        keyword,
        keyword_total,
        keyword_new,
    )


# ============================================================
# WORKER
# ============================================================

async def worker(
    queue: asyncio.Queue,
    session: AsyncSession,
    existing_ids: set[str],
    ids_lock: asyncio.Lock,
):

    while True:

        keyword = await queue.get()

        if keyword is None:

            queue.task_done()
            break

        try:

            await parse_keyword(
                keyword=keyword,
                session=session,
                existing_ids=existing_ids,
                ids_lock=ids_lock,
            )

        except Exception:

            logger.exception(
                "Ошибка при обработке ключевого слова: %s",
                keyword,
            )

        finally:

            queue.task_done()


# ============================================================
# MAIN
# ============================================================

async def main():

    Path(IDS_FILE).parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    existing_ids = load_existing_ids()

    initial_count = len(existing_ids)

    ids_lock = asyncio.Lock()

    queue = asyncio.Queue()

    for keyword in KEYWORDS:
        await queue.put(keyword)

    async with AsyncSession() as session:

        workers = [
            asyncio.create_task(
                worker(
                    queue=queue,
                    session=session,
                    existing_ids=existing_ids,
                    ids_lock=ids_lock,
                )
            )
            for _ in range(CONCURRENCY)
        ]

        await queue.join()

        for _ in workers:
            await queue.put(None)

        await asyncio.gather(*workers)

    logger.info("=" * 70)

    logger.info(
        "СБОР ЗАВЕРШЁН"
    )

    logger.info(
        "Было ID:        %s",
        initial_count,
    )

    logger.info(
        "Стало ID:       %s",
        len(existing_ids),
    )

    logger.info(
        "Добавлено:      %s",
        len(existing_ids) - initial_count,
    )

    logger.info(
        "Файл:           %s",
        IDS_FILE,
    )

    logger.info("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())