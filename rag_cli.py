"""CLI for RAG index management: index or reindex PDF documents."""
import asyncio
import logging
import sys

from src.config import Config
from src.embedding_client import EmbeddingClient
from src.rag_service import RagService


async def run(force: bool) -> None:
    logging.basicConfig(level=logging.INFO)
    config = Config()
    embedding = EmbeddingClient(config)
    rag = RagService(embedding, config)
    if force:
        await rag.drop_index()
    await rag.index_documents(force=force)


if __name__ == "__main__":
    force = "--reindex" in sys.argv
    asyncio.run(run(force))
