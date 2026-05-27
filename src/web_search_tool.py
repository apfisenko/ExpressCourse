import logging

from langsmith import traceable
from tavily import AsyncTavilyClient

from src.config import Config


class WebSearchTool:
    def __init__(self, config: Config) -> None:
        self._api_key = config.tavily_api_key
        self._max_results = config.web_search_max_results

    @traceable(name="web_search")
    async def search(self, query: str) -> dict:
        if not self._api_key:
            logging.error("TAVILY_API_KEY is not configured")
            return {"error": "Веб-поиск недоступен: не настроен TAVILY_API_KEY."}

        client = AsyncTavilyClient(api_key=self._api_key)
        try:
            response = await client.search(
                query=query,
                max_results=self._max_results,
                include_answer=True,
            )
        finally:
            await client.close()

        results = [
            {
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "content": item.get("content", ""),
            }
            for item in response.get("results", [])
        ]

        if not results:
            return {"result": "По запросу ничего не найдено.", "query": query}

        return {
            "query": query,
            "answer": response.get("answer"),
            "results": results,
        }
