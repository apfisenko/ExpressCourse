import asyncio
import logging

from src.audio_client import AudioClient
from src.bot import Bot
from src.config import Config
from src.dialog_service import DialogService
from src.image_client import ImageClient
from src.llm_client import LlmClient


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    config = Config()
    llm = LlmClient(config)
    image = ImageClient(config)
    audio = AudioClient(config)
    dialog = DialogService(llm, image, audio, config)
    bot = Bot(config.telegram_bot_token, dialog)
    await bot.run()


if __name__ == "__main__":
    asyncio.run(main())
