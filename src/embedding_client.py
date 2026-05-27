import asyncio
import logging

from langsmith import traceable
from openai import AsyncOpenAI

from src.config import Config

_RETRY_DELAYS = [1.0, 2.0, 4.0]


class EmbeddingClient:
    def __init__(self, config: Config) -> None:
        self._client = AsyncOpenAI(
            api_key=config.open_api_key,
            base_url=config.open_base_url,
        )
        self._model = config.embedding_model

    @traceable(name="embed")
    async def embed(self, text: str) -> list[float]:
        for attempt, delay in enumerate([0.0] + _RETRY_DELAYS):
            if delay:
                await asyncio.sleep(delay)
            try:
                response = await self._client.embeddings.create(
                    model=self._model,
                    input=text,
                    encoding_format="float",
                )
                if response.data and response.data[0].embedding:
                    return response.data[0].embedding
                if attempt < len(_RETRY_DELAYS):
                    logging.warning("Empty embedding response, retrying (attempt %d)", attempt + 1)
                    continue
                raise ValueError("No embedding data received after retries")
            except ValueError as exc:
                if attempt < len(_RETRY_DELAYS):
                    logging.warning("Embedding parse error: %s, retrying (attempt %d)", exc, attempt + 1)
                    continue
                raise
            except Exception as exc:
                if attempt < len(_RETRY_DELAYS):
                    logging.warning("Embedding error: %s, retrying (attempt %d)", exc, attempt + 1)
                    continue
                raise
        raise RuntimeError("unreachable")

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        results = []
        for text in texts:
            embedding = await self.embed(text)
            results.append(embedding)
            await asyncio.sleep(0.3)
        return results
