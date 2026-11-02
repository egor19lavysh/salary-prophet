import os
from dotenv import load_dotenv
from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.types import FSInputFile

from bot import get_user_ids, send_csv_to_users

from bs4 import BeautifulSoup
from curl_cffi import AsyncSession
from config import generate_headers, BASE_URL
import asyncio
import logging
import random
import csv
import os

load_dotenv()

BOT_TOKEN = os.getenv("TOKEN")
BOT_PASSWORD = os.getenv("BOT_PASSWORD")

LOGIN = os.getenv("LOGIN")
PASSWORD = os.getenv("PASSWORD")
HOST = os.getenv("HOST")
PORT = os.getenv("PORT")

PROXY_URL = f"http://{LOGIN}:{PASSWORD}@{HOST}:{PORT}"

logger = logging.getLogger(__name__)

logger.setLevel(logging.INFO)

formatter = logging.Formatter(
    fmt="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)

console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)

file_handler = logging.FileHandler(
    "logs/parser.log",
    encoding="utf-8",
)
file_handler.setFormatter(formatter)



class TelegramWarningHandler(logging.Handler):
    def __init__(self, bot):
        super().__init__(level=logging.WARNING)
        self.bot: Bot = bot

    def emit(self, record):
        try:
            message = self.format(record)
            loop = asyncio.get_running_loop()
            loop.create_task(self.send_warning(message))
        except Exception:
            self.handleError(record)

    async def send_warning(self, message: str):
        for user_id in get_user_ids():
            try:
                await self.bot.send_message(
                    chat_id=user_id,
                    text=f"⚠️ WARNING парсера:\n{message[:4000]}",
                )
            except Exception:
                pass

logger.addHandler(console_handler)
logger.addHandler(file_handler)


headers_generator = generate_headers()

async def append_error_id(vac_id: int):
    with open("error_ids.txt", "a") as file:
        file.write(str(vac_id) + "\n")

async def append_to_csv(row: dict, filename: str = "vacancies.csv"):
    file_exists = os.path.exists(filename)
    file_is_empty = not file_exists or os.path.getsize(filename) == 0

    with open(filename, "a", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=row.keys())

        if file_is_empty:
            writer.writeheader()

        writer.writerow(row)

        file.flush()
        os.fsync(file.fileno())

def get_text(soup, selector, default=None):
    """Безопасно получает текст по CSS-селектору."""

    element = soup.select_one(selector)

    if element is None:
        return default

    text = element.get_text(" ", strip=True)
    return text.replace("\xa0", " ") or default

async def scrap(html: str, id: int, link: str) -> dict:
    
    soup = BeautifulSoup(html, "lxml")

    title = get_text(soup, "h1")

    # Без заголовка, скорее всего, получена не страница вакансии
    if not title:
        raise ValueError("Не найден заголовок вакансии")

    company_element = soup.select_one(
        '[data-qa="vacancy-company"] '
        '[data-qa="vacancy-company__details"]'
    )

    company = (
        company_element.get_text(" ", strip=True).replace("\xa0", " ")
        if company_element
        else None
    )

    skills_list = soup.select(
        'ul[class*="vacancy-skill-list"] li'
    )

    skills = ", ".join(
        item.get_text(" ", strip=True)
        for item in skills_list
        if item.get_text(" ", strip=True)
    )

    # Класс даты публикации часто меняется, поэтому ищем по data-qa
    created_at = get_text(
        soup,
        '[data-qa="vacancy-creation-time"]',
    )

    # Резервный вариант для HTML, где дата размечена иначе
    if not created_at:
        created_at = get_text(
            soup,
            '[data-qa="vacancy-view-creation-time"]',
        )

    data = {
        "id": int(id),
        "link": link or BASE_URL.format(id),
        "title": title,
        "salary": get_text(soup, '[data-qa="vacancy-salary"]'),
        "compensation-frequency": get_text(
            soup, '[data-qa="compensation-frequency-text"]'
        ),
        "experience": get_text(
            soup, '[data-qa="work-experience-text"]'
        ),
        "employment": get_text(
            soup, '[data-qa="common-employment-text"]'
        ),
        "hiring-formats": get_text(
            soup, '[data-qa="vacancy-hiring-formats"]'
        ),
        "schedule": get_text(
            soup, '[data-qa="work-schedule-by-days-text"]'
        ),
        "hours": get_text(
            soup, '[data-qa="working-hours-text"]'
        ),
        "formats": get_text(
            soup, '[data-qa="work-formats-text"]'
        ),
        "company": company,
        "description": get_text(
            soup, '[data-qa="vacancy-description"]', default=""
        ),
        "address": get_text(
            soup, '[data-qa="vacancy-address-with-map"]'
        ),
        "created_at": created_at,
        "skills": skills,
    }

    return data



async def fetch(url: str, headers: dict, timeout: tuple[float, float] = (15, 30), retries: int = 3):
    async with AsyncSession() as session:

        logger.info(f"Делаем запрос на {url}")

        for i in range(1, retries + 1):
            response = await session.get(url,
                                        headers=headers,
                                        impersonate="chrome")
            
            if response.status_code == 200:
                return response.text

            if response.status_code == 404:
                logger.warning(f"Страница {url} не найдена")
                return None

            if response.status_code in (403, 429):
                time_sleep = random.randint(timeout[0], timeout[1])
                logger.warning(f"Страница {url} запрещена. Делаем повторный запрос через {time_sleep}.")
                await asyncio.sleep(time_sleep)
                continue
        else:
            logger.warning(f"Не смогли получить {url}...")
            return None

async def parser():
    session = AiohttpSession(proxy=PROXY_URL)
    bot = Bot(token=BOT_TOKEN, session=session)

    telegram_handler = TelegramWarningHandler(bot)
    telegram_handler.setFormatter(formatter)
    logger.addHandler(telegram_handler)

    with open("all_ids.txt", "r") as file:
        ids = file.readlines()

    ids = ids[1000:]

    processed = 0
    for vacancy_id in ids:
        url = f"{BASE_URL}{int(vacancy_id)}"
        logger.info(f"Начинаем обработку вакансии {vacancy_id}")

        try:
            if result := await fetch(url=url, headers=next(headers_generator)):
                if row := await scrap(html=result, id=int(vacancy_id), link=url):
                    await append_to_csv(row)
                    logger.info(f"Вакансия {vacancy_id} успешно обработана")
                else:
                    await append_error_id(int(vacancy_id))
                    logger.warning(f"Во время обработки вакансии {vacancy_id} произошла ошибка... Возможно капча")
            else:
                await append_error_id(int(vacancy_id))
                logger.warning(f"Во время получения страницы {vacancy_id} произошла ошибка...")
        except Exception as e:
            await append_error_id(int(vacancy_id))
            logger.error(f"Во время обработки вакансии {vacancy_id} произошла ошибка: {e}")
            continue

        await asyncio.sleep(random.randint(5, 10))

        processed += 1

        if processed % 1000 == 0:
                logger.info(
                    "Обработано %s вакансий. Отправляем CSV.",
                    processed,
                )

                try:
                    await send_csv_to_users(bot, "vacancies.csv")
                except Exception:
                    logger.exception("Не удалось отправить CSV")

                logger.info("Пауза на 15 минут.")
                await asyncio.sleep(15 * 60)

if __name__ == "__main__":
    asyncio.run(parser())
            


