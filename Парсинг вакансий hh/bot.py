import asyncio
import logging
import sys
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, html, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import FSInputFile
from pathlib import Path
import os

load_dotenv()

BOT_TOKEN = os.getenv("TOKEN")
BOT_PASSWORD = os.getenv("BOT_PASSWORD")

LOGIN = os.getenv("LOGIN")
PASSWORD = os.getenv("PASSWORD")
HOST = os.getenv("HOST")
PORT = os.getenv("PORT")


from aiogram.client.session.aiohttp import AiohttpSession

PROXY_URL = f"http://{LOGIN}:{PASSWORD}@{HOST}:{PORT}"

USERS_FILE = Path("users.txt")


logger = logging.getLogger(__name__)

dp = Dispatcher()

class AuthStates(StatesGroup):
    password = State()


@dp.message(Command("start"))
async def start_cmd(message: Message, state: FSMContext):
    await message.answer("Введи пароль")
    await state.set_state(AuthStates.password)

@dp.message(AuthStates.password)
async def password_handler(message: Message):
    if message.text.strip() == PASSWORD:
        with open("users.txt", "a") as file:
            file.write(str(message.from_user.id) + "\n")

        await message.answer("Заходи заебал)")
    else:
        await message.answer("Пошел нахуй)")



def get_user_ids() -> list[int]:
    """Читает ID пользователей из users.txt."""
    user_ids = []

    with open("users.txt", "r", encoding="utf-8") as file:
        users = file.readlines()

    return list(set([int(user_id.strip()) for user_id in users]))


async def send_csv_to_users(
    bot: Bot,
    csv_path: str = "vacancies.csv",
) -> None:
    """Отправляет CSV-файл всем пользователям из users.txt."""
    path = Path(csv_path)

    if not path.is_file():
        logger.error("CSV-файл не найден: %s", path)
        return

    user_ids = get_user_ids()
    if not user_ids:
        logger.warning("Нет пользователей для отправки CSV")
        return

    document = FSInputFile(path)

    for user_id in user_ids:
        try:
            await bot.send_document(
                chat_id=user_id,
                document=document,
                caption="Результаты парсинга вакансий",
            )
            logger.info("CSV отправлен пользователю %s", user_id)

        except Exception:
            logger.exception(
                "Не удалось отправить CSV пользователю %s",
                user_id,
            )


async def send_error_message(bot: Bot, message: str) -> None:
    """Отправляет уведомление об ошибке парсера."""
    user_ids = get_user_ids()

    for user_id in user_ids:
        try:
            await bot.send_message(
                chat_id=user_id,
                text=message,
            )
            logger.info("Уведомление отправлено пользователю %s", user_id)

        except Exception:
            logger.exception(
                "Не удалось отправить уведомление пользователю %s",
                user_id,
            )


async def main() -> None:
    with open("users.txt", "a") as file:
        pass
    session = AiohttpSession(proxy=PROXY_URL)
    bot = Bot(token=BOT_TOKEN, session=session)
    await send_error_message(bot, message="Все, пизда... Парсер запущен!")
    await dp.start_polling(bot)
    await send_error_message(bot, message="Все, пизда... Парсер выключен!")

    

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())