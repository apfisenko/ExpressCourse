import asyncio
import logging
import os

from src.agent_service import AgentService
from src.audio_client import AudioClient
from src.bot import Bot
from src.config import Config
from src.dialog_service import DialogService
from src.image_client import ImageClient
from src.llm_client import LlmClient


def _init_langsmith(config: Config) -> None:
    if config.langsmith_enabled:
        os.environ["LANGSMITH_TRACING"] = "true"
        if config.langsmith_api_key:
            os.environ["LANGSMITH_API_KEY"] = config.langsmith_api_key
        if config.langsmith_project:
            os.environ["LANGSMITH_PROJECT"] = config.langsmith_project
        logging.info("LangSmith tracing enabled (project=%s)", config.langsmith_project)
    else:
        os.environ["LANGSMITH_TRACING"] = "false"


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    config = Config()
    _init_langsmith(config)
    llm = LlmClient(config)
    image = ImageClient(config)
    audio = AudioClient(config)
    agent = AgentService(llm, config)
    dialog = DialogService(llm, image, audio, config)
    bot = Bot(config.telegram_bot_token, agent, dialog)
    await bot.run()


if __name__ == "__main__":
    asyncio.run(main())
