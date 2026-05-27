import logging
from io import BytesIO

from aiogram import Bot as AiogramBot
from aiogram import Dispatcher, F, types
from aiogram.filters import CommandStart

from src.agent_service import AgentService
from src.audio_converter import AudioConverterError
from src.dialog_service import DialogService
from src.llm_client import LlmAuthError, LlmProviderError, ModalityNotSupportedError

AUTH_ERROR_MESSAGE = (
    "Ошибка авторизации LLM. Проверьте ключ API (OPEN_API_KEY)."
)
PROVIDER_ERROR_MESSAGE = (
    "Сервис модели временно недоступен или отклонил запрос. Попробуйте позже."
)
VOICE_ERROR_MESSAGE = (
    "Не удалось обработать голосовое. Установите ffmpeg или напишите текстом."
)
AUDIO_NOT_SUPPORTED_MESSAGE = (
    "Текущая модель не поддерживает обработку голосовых сообщений. "
    "Напишите текстом или выберите в Ollama модель с поддержкой аудио."
)
IMAGE_NOT_SUPPORTED_MESSAGE = (
    "Текущая модель не поддерживает обработку фото. "
    "Опишите вопрос текстом или выберите vision-модель в Ollama (например, llava)."
)
ERROR_MESSAGE = "Сейчас не могу ответить. Попробуйте позже."
MAX_MESSAGE_LENGTH = 4096


class Bot:
    def __init__(self, token: str, agent: AgentService, dialog: DialogService) -> None:
        self._bot = AiogramBot(token=token)
        self._dp = Dispatcher()
        self._agent = agent
        self._dialog = dialog
        self._register_handlers()

    def _register_handlers(self) -> None:
        @self._dp.errors()
        async def handle_error(event: types.ErrorEvent) -> None:
            logging.exception("Unhandled error", exc_info=event.exception)

        @self._dp.message(CommandStart())
        async def handle_start(message: types.Message) -> None:
            self._agent.reset_session(message.from_user.id)
            try:
                reply = await self._agent.handle_message(message.from_user.id, "/start")
                await self._send_reply(message, reply)
            except LlmAuthError:
                logging.exception("LLM authentication failed")
                await self._send_error_message(message, AUTH_ERROR_MESSAGE)
            except LlmProviderError:
                logging.exception("LLM provider error")
                await self._send_error_message(message, PROVIDER_ERROR_MESSAGE)
            except Exception:
                logging.exception("Failed to process /start")
                await self._send_error_message(message, ERROR_MESSAGE)

        @self._dp.message(F.photo)
        async def handle_photo(message: types.Message) -> None:
            try:
                photo = message.photo[-1]
                file = await self._bot.get_file(photo.file_id)
                buffer = BytesIO()
                await self._bot.download_file(file.file_path, buffer)
                reply = await self._dialog.reply_photo(
                    message.from_user.id,
                    buffer.getvalue(),
                    "image/jpeg",
                    message.caption or "",
                )
                await self._send_reply(message, reply)
            except ModalityNotSupportedError:
                logging.warning("Image modality not supported by current model")
                await self._send_error_message(message, IMAGE_NOT_SUPPORTED_MESSAGE)
            except LlmAuthError:
                logging.exception("LLM authentication failed")
                await self._send_error_message(message, AUTH_ERROR_MESSAGE)
            except LlmProviderError:
                logging.exception("LLM provider error")
                await self._send_error_message(message, PROVIDER_ERROR_MESSAGE)
            except Exception:
                logging.exception("Failed to process photo")
                await self._send_error_message(message, ERROR_MESSAGE)

        @self._dp.message(F.voice)
        async def handle_voice(message: types.Message) -> None:
            try:
                file = await self._bot.get_file(message.voice.file_id)
                buffer = BytesIO()
                await self._bot.download_file(file.file_path, buffer)
                reply = await self._dialog.reply_voice(
                    message.from_user.id,
                    buffer.getvalue(),
                )
                await self._send_reply(message, reply)
            except ModalityNotSupportedError:
                logging.warning("Audio modality not supported by current model")
                await self._send_error_message(message, AUDIO_NOT_SUPPORTED_MESSAGE)
            except AudioConverterError:
                logging.exception("Voice conversion failed")
                await self._send_error_message(message, VOICE_ERROR_MESSAGE)
            except LlmAuthError:
                logging.exception("LLM authentication failed")
                await self._send_error_message(message, AUTH_ERROR_MESSAGE)
            except LlmProviderError:
                logging.exception("LLM provider error")
                await self._send_error_message(message, PROVIDER_ERROR_MESSAGE)
            except Exception:
                logging.exception("Failed to process voice message")
                await self._send_error_message(message, ERROR_MESSAGE)

        @self._dp.message()
        async def handle_message(message: types.Message) -> None:
            if not message.text:
                return
            try:
                reply = await self._agent.handle_message(message.from_user.id, message.text)
                await self._send_reply(message, reply)
            except LlmAuthError:
                logging.exception("LLM authentication failed")
                await self._send_error_message(message, AUTH_ERROR_MESSAGE)
            except LlmProviderError:
                logging.exception("LLM provider error")
                await self._send_error_message(message, PROVIDER_ERROR_MESSAGE)
            except Exception:
                logging.exception("Failed to process message")
                await self._send_error_message(message, ERROR_MESSAGE)

    async def _send_reply(self, message: types.Message, text: str) -> None:
        for chunk in self._split_message(text):
            await message.answer(chunk)

    def _split_message(self, text: str) -> list[str]:
        if len(text) <= MAX_MESSAGE_LENGTH:
            return [text]

        chunks: list[str] = []
        rest = text
        while rest:
            if len(rest) <= MAX_MESSAGE_LENGTH:
                chunks.append(rest)
                break
            split_at = rest.rfind("\n", 0, MAX_MESSAGE_LENGTH)
            if split_at <= 0:
                split_at = MAX_MESSAGE_LENGTH
            chunks.append(rest[:split_at])
            rest = rest[split_at:].lstrip("\n")
        return chunks

    async def _send_error_message(
        self, message: types.Message, text: str
    ) -> None:
        try:
            await message.answer(text)
        except Exception:
            logging.exception("Failed to send error message to user")

    async def run(self) -> None:
        await self._dp.start_polling(self._bot)
