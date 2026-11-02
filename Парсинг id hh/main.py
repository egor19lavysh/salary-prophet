import asyncio
import logging
import os
import random
import time
from pathlib import Path

from bs4 import BeautifulSoup
from curl_cffi.requests import AsyncSession
from tqdm import tqdm

from config import (
    HH_BASE_URL,
    ITEMS_ON_PAGE,
    PROFESSIONAL_ROLES,
    CONCURRENCY,
    MAX_RETRIES,
    REQUEST_TIMEOUT,
    REQUEST_DELAY,
    IDS_FILE,
    LOG_FILE,
)


# =========================================================
# LOGGING
# =========================================================

Path(LOG_FILE).parent.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger("hh_parser")
logger.setLevel(logging.INFO)
logger.handlers.clear()

formatter = logging.Formatter(
    fmt="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)

console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)

file_handler = logging.FileHandler(
    LOG_FILE,
    encoding="utf-8",
)
file_handler.setFormatter(formatter)

logger.addHandler(console_handler)
logger.addHandler(file_handler)


# =========================================================
# HEADERS
# =========================================================

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/150.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,image/avif,image/webp,"
        "*/*;q=0.8"
    ),
    "Accept-Language": (
        "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7"
    ),
    "Connection": "keep-alive",
}


# =========================================================
# EXCEPTIONS
# =========================================================

class PageNotFoundError(Exception):
    """HH больше не отдаёт страницы этой выдачи."""


class AccessDeniedError(Exception):
    """HH запретил доступ."""


# =========================================================
# ID PARSER
# =========================================================
import re


VACANCY_URL_PATTERN = re.compile(
    r"/vacancy/(\d+)"
)


def parse_vacancy_ids(html: str) -> set[str]:
    """
    Извлекает ID вакансий из HTML страницы HH.ru.

    Ищет ссылки вида:
        /vacancy/123456789
    """

    soup = BeautifulSoup(html, "lxml")

    vacancy_ids = set()

    # Берём только ссылки на вакансии
    vacancy_links = soup.select(
        'a[href*="/vacancy/"]'
    )

    for link in vacancy_links:

        href = link.get("href")

        if not href:
            continue

        match = VACANCY_URL_PATTERN.search(href)

        if match:
            vacancy_ids.add(match.group(1))

    return vacancy_ids

# =========================================================
# STORAGE
# =========================================================

def load_existing_ids() -> set[str]:
    """
    Загружает уже сохранённые ID.

    Благодаря этому после падения программы
    уже собранные вакансии не теряются.
    """

    path = Path(IDS_FILE)

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.touch(exist_ok=True)

    with path.open(
        "r",
        encoding="utf-8",
    ) as file:

        return {
            line.strip()
            for line in file
            if line.strip()
        }


def append_ids(ids: set[str]) -> None:
    """
    Добавляет новые ID в файл.

    Каждый вызов сразу делает flush + fsync,
    поэтому данные максимально быстро фиксируются
    на диске.
    """

    if not ids:
        return

    with open(
        IDS_FILE,
        "a",
        encoding="utf-8",
    ) as file:

        for vacancy_id in sorted(ids):
            file.write(f"{vacancy_id}\n")

        file.flush()
        os.fsync(file.fileno())


# =========================================================
# URL
# =========================================================

def build_url(
    role_id: int,
    page: int,
) -> str:

    params = [
        ("page", page),

        # Ищем по названию, компании и описанию
        ("search_field", "name"),
        ("search_field", "company_name"),
        ("search_field", "description"),

        ("enable_snippets", "true"),

        # Только вакансии с зарплатой
        ("label", "with_salary"),

        # Главный фильтр
        ("professional_role", role_id),

        # Количество вакансий на странице
        ("items_on_page", ITEMS_ON_PAGE),
    ]

    from urllib.parse import urlencode

    return (
        f"{HH_BASE_URL}?"
        f"{urlencode(params)}"
    )


# =========================================================
# HTTP
# =========================================================

async def fetch_page(
    session: AsyncSession,
    role_id: int,
    page: int,
) -> str | None:

    url = build_url(
        role_id=role_id,
        page=page,
    )

    for attempt in range(
        1,
        MAX_RETRIES + 1,
    ):

        try:

            response = await session.get(
                url,
                headers=HEADERS,
                impersonate="chrome",
                timeout=REQUEST_TIMEOUT,
            )

            status = response.status_code

            # ---------------------------------------------
            # Успех
            # ---------------------------------------------

            if status == 200:
                return response.text

            # ---------------------------------------------
            # Страница закончилась
            # ---------------------------------------------

            if status == 404:

                logger.info(
                    "ROLE %s | page %s | 404 → "
                    "выдача закончилась",
                    role_id,
                    page,
                )

                raise PageNotFoundError()

            # ---------------------------------------------
            # Access denied
            # ---------------------------------------------

            if status == 403:

                logger.error(
                    "ROLE %s | page %s | HTTP 403",
                    role_id,
                    page,
                )

                raise AccessDeniedError(
                    f"HTTP 403 for role {role_id}"
                )

            # ---------------------------------------------
            # Too many requests
            # ---------------------------------------------

            if status == 429:

                logger.warning(
                    "ROLE %s | page %s | HTTP 429 | "
                    "попытка %s/%s",
                    role_id,
                    page,
                    attempt,
                    MAX_RETRIES,
                )

            # ---------------------------------------------
            # Server errors
            # ---------------------------------------------

            elif status in (
                500,
                502,
                503,
                504,
            ):

                logger.warning(
                    "ROLE %s | page %s | HTTP %s | "
                    "попытка %s/%s",
                    role_id,
                    page,
                    status,
                    attempt,
                    MAX_RETRIES,
                )

            else:

                logger.error(
                    "ROLE %s | page %s | "
                    "неожиданный HTTP %s",
                    role_id,
                    page,
                    status,
                )

                return None

        except (
            PageNotFoundError,
            AccessDeniedError,
        ):
            raise

        except Exception:

            logger.exception(
                "ROLE %s | page %s | ошибка запроса | "
                "попытка %s/%s",
                role_id,
                page,
                attempt,
                MAX_RETRIES,
            )

        # ---------------------------------------------
        # Retry delay
        # ---------------------------------------------

        if attempt < MAX_RETRIES:

            delay = min(
                2 ** (attempt - 1),
                30,
            )

            delay += random.uniform(
                0.5,
                1.5,
            )

            await asyncio.sleep(delay)

    logger.error(
        "ROLE %s | page %s | "
        "страница не загружена после %s попыток",
        role_id,
        page,
        MAX_RETRIES,
    )

    return None


# =========================================================
# ONE ROLE
# =========================================================

async def crawl_role(
    session: AsyncSession,
    role_id: int,
    seen_ids: set[str],
    write_lock: asyncio.Lock,
    progress,
) -> dict:

    page = 0

    role_new_ids = 0
    role_pages = 0

    started_at = time.perf_counter()

    logger.info(
        "ROLE %s | старт",
        role_id,
    )

    while True:

        # -------------------------------------------------
        # Небольшая случайная задержка
        # -------------------------------------------------

        await asyncio.sleep(
            random.uniform(*REQUEST_DELAY)
        )

        try:

            html = await fetch_page(
                session=session,
                role_id=role_id,
                page=page,
            )

        except PageNotFoundError:

            break

        except AccessDeniedError:

            logger.error(
                "ROLE %s | доступ запрещён | "
                "роль остановлена",
                role_id,
            )

            break

        if html is None:

            logger.error(
                "ROLE %s | page %s | "
                "страница пропущена",
                role_id,
                page,
            )

            page += 1
            continue

        # -------------------------------------------------
        # Парсим ID
        # -------------------------------------------------

        try:

            page_ids = parse_vacancy_ids(html)

        except Exception:

            logger.exception(
                "ROLE %s | page %s | "
                "ошибка парсинга HTML",
                role_id,
                page,
            )

            page += 1
            continue

        # -------------------------------------------------
        # Если страница реально пустая
        # -------------------------------------------------

        if not page_ids:

            logger.warning(
                "ROLE %s | page %s | "
                "ID не найдены",
                role_id,
                page,
            )

            # Не считаем это концом выдачи.
            # Возможно, изменилась разметка.
            page += 1
            continue

        # -------------------------------------------------
        # Глобальная дедупликация
        # -------------------------------------------------

        async with write_lock:

            new_ids = page_ids - seen_ids

            if new_ids:

                append_ids(new_ids)

                seen_ids.update(new_ids)

                role_new_ids += len(new_ids)

        role_pages += 1

        logger.info(
            "ROLE %s | page %s | "
            "найдено: %s | новых: %s | "
            "всего: %s",
            role_id,
            page,
            len(page_ids),
            len(new_ids),
            len(seen_ids),
        )

        progress.update(1)

        page += 1

    elapsed = time.perf_counter() - started_at

    logger.info(
        "ROLE %s | завершена | "
        "страниц: %s | новых ID: %s | "
        "время: %.1f сек.",
        role_id,
        role_pages,
        role_new_ids,
        elapsed,
    )

    return {
        "role_id": role_id,
        "pages": role_pages,
        "new_ids": role_new_ids,
    }


# =========================================================
# CRAWLER
# =========================================================

async def crawl():

    # -----------------------------------------------------
    # Загружаем старые ID
    # -----------------------------------------------------

    existing_ids = load_existing_ids()

    logger.info(
        "Уже сохранено ID: %s",
        len(existing_ids),
    )

    seen_ids = existing_ids.copy()

    write_lock = asyncio.Lock()

    semaphore = asyncio.Semaphore(
        CONCURRENCY
    )

    logger.info("=" * 65)

    logger.info(
        "HH.ru VACANCY PARSER"
    )

    logger.info(
        "Ролей: %s",
        len(PROFESSIONAL_ROLES),
    )

    logger.info(
        "Вакансий на странице: %s",
        ITEMS_ON_PAGE,
    )

    logger.info(
        "Параллельных ролей: %s",
        CONCURRENCY,
    )

    logger.info(
        "Файл ID: %s",
        IDS_FILE,
    )

    logger.info("=" * 65)

    # -----------------------------------------------------
    # Session
    # -----------------------------------------------------

    async with AsyncSession() as session:

        # Мы не знаем заранее,
        # сколько страниц будет у каждой роли.
        #
        # Поэтому tqdm здесь показывает
        # количество успешно обработанных страниц,
        # а не процент выполнения.

        with tqdm(
            desc="HH.ru",
            unit=" стр.",
            dynamic_ncols=True,
        ) as progress:

            async def limited_crawl(
                role_id: int,
            ):

                async with semaphore:

                    return await crawl_role(
                        session=session,
                        role_id=role_id,
                        seen_ids=seen_ids,
                        write_lock=write_lock,
                        progress=progress,
                    )

            tasks = [
                asyncio.create_task(
                    limited_crawl(role_id)
                )
                for role_id in PROFESSIONAL_ROLES
            ]

            results = await asyncio.gather(
                *tasks,
                return_exceptions=True,
            )

    # -----------------------------------------------------
    # Results
    # -----------------------------------------------------

    logger.info("")
    logger.info("=" * 65)
    logger.info("СБОР ЗАВЕРШЁН")
    logger.info("=" * 65)

    total_pages = 0
    total_new_ids = 0

    for result in results:

        if isinstance(
            result,
            Exception,
        ):

            logger.error(
                "Ошибка role worker: %r",
                result,
            )

            continue

        total_pages += result["pages"]
        total_new_ids += result["new_ids"]

    logger.info(
        "Обработано страниц: %s",
        total_pages,
    )

    logger.info(
        "Новых ID за запуск: %s",
        total_new_ids,
    )

    logger.info(
        "Всего уникальных ID: %s",
        len(seen_ids),
    )

    logger.info(
        "ID сохранены в: %s",
        IDS_FILE,
    )

    logger.info("=" * 65)


# =========================================================
# ENTRY POINT
# =========================================================

if __name__ == "__main__":

    try:

        asyncio.run(crawl())

    except KeyboardInterrupt:

        logger.warning(
            "Остановка пользователем."
        )

        logger.warning(
            "Все уже сохранённые ID находятся в %s",
            IDS_FILE,
        )

    except Exception:

        logger.exception(
            "Критическая ошибка парсера."
        )

        raise
