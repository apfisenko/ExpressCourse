import asyncio
import logging
import os

from src.agent_service import AgentService
from src.audio_client import AudioClient
from src.bot import Bot
from src.config import Config
from src.dialog_service import DialogService
from src.embedding_client import EmbeddingClient
from src.image_client import ImageClient
from src.lead_store import LeadStore
from src.llm_client import LlmClient
from src.rag_service import RagService
from src.web_search_tool import WebSearchTool


_WEB_SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": (
            "Проверь актуальный факт в интернете только в контексте услуг, "
            "курсов и программ компании «ИИ Агент»: версии технологий из "
            "программ, даты, вендоры, расписание. Не используй для общих "
            "новостей и тем, не связанных с услугами компании."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Поисковый запрос только по теме услуг/курсов компании "
                        "«ИИ Агент»; не используй для посторонних тем"
                    ),
                },
            },
            "required": ["query"],
        },
    },
}

_RAG_SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "rag_search",
        "description": (
            "Найди информацию по корпоративным материалам компании: "
            "услуги, курсы, программы обучения, портфолио. "
            "Используй при вопросах об услугах и продуктах компании."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Поисковый запрос на русском языке",
                },
            },
            "required": ["query"],
        },
    },
}

_CAPTURE_LEAD_TOOL = {
    "type": "function",
    "function": {
        "name": "capture_lead",
        "description": "Сохрани заявку на консультацию: имя и контакт пользователя",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Имя клиента",
                },
                "contact": {
                    "type": "string",
                    "description": "Email, телефон или Telegram-username клиента",
                },
            },
            "required": ["name", "contact"],
        },
    },
}


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
    embedding = EmbeddingClient(config)
    lead_store = LeadStore(config)
    rag = RagService(embedding, config)
    await rag.index_documents()
    web_search = WebSearchTool(config)
    agent = AgentService(llm, config)
    agent.register_tool(_RAG_SEARCH_TOOL, rag.search)
    agent.register_tool(_WEB_SEARCH_TOOL, web_search.search)
    agent.register_tool(_CAPTURE_LEAD_TOOL, lead_store.capture)
    dialog = DialogService(llm, image, audio, config)
    bot = Bot(config.telegram_bot_token, agent, dialog)
    await bot.run()


if __name__ == "__main__":
    asyncio.run(main())
