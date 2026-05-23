import logging

from aiogram import Bot as AiogramBot
from aiogram import Dispatcher, types
from aiogram.filters import CommandStart

from src.dialog_service import DialogService
from src.llm_client import LlmAuthError, LlmProviderError

AUTH_ERROR_MESSAGE = (
    "Ошибка авторизации LLM. Проверьте ключ API (OPEN_API_KEY)."
)
PROVIDER_ERROR_MESSAGE = (
    "Сервис модели временно недоступен или отклонил запрос. Попробуйте позже."
)
ERROR_MESSAGE = "Сейчас не могу ответить. Попробуйте позже."


class Bot:
    def __init__(self, token: str, dialog: DialogService) -> None:
        self._bot = AiogramBot(token=token)
        self._dp = Dispatcher()
        self._dialog = dialog
        self._register_handlers()

    def _register_handlers(self) -> None:
        @self._dp.errors()
        async def handle_error(event: types.ErrorEvent) -> None:
            logging.exception("Unhandled error", exc_info=event.exception)

        @self._dp.message(CommandStart())
        async def handle_start(message: types.Message) -> None:
            await message.answer(
                "Привет! Я консультант по Python. Задайте вопрос по языку — помогу с кодом и разбором ошибок."
            )

        @self._dp.message()
        async def handle_message(message: types.Message) -> None:
            if not message.text:
                return
            try:
                reply = await self._dialog.reply(message.from_user.id, message.text)
                await message.answer(reply)
            except LlmAuthError:
                logging.exception("LLM authentication failed")
                await self._send_error_message(message, AUTH_ERROR_MESSAGE)
            except LlmProviderError:
                logging.exception("LLM provider error")
                await self._send_error_message(message, PROVIDER_ERROR_MESSAGE)
            except Exception:
                logging.exception("Failed to process message")
                await self._send_error_message(message, ERROR_MESSAGE)

    async def _send_error_message(
        self, message: types.Message, text: str
    ) -> None:
        try:
            await message.answer(text)
        except Exception:
            logging.exception("Failed to send error message to user")

    async def run(self) -> None:
        await self._dp.start_polling(self._bot)
