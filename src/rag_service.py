import asyncio
import logging
from pathlib import Path

import chromadb
import pymupdf4llm
from langsmith import traceable

from src.config import Config
from src.embedding_client import EmbeddingClient

_COLLECTION = "documents"
_CHUNK_SIZE = 1000
_CHUNK_OVERLAP = 100


class RagService:
    def __init__(self, embedding: EmbeddingClient, config: Config) -> None:
        self._embedding = embedding
        self._top_k = config.rag_top_k
        self._pdf_dir = config.pdf_dir
        config.chroma_path.mkdir(parents=True, exist_ok=True)
        self._chroma = chromadb.PersistentClient(path=str(config.chroma_path))
        self._col = self._chroma.get_or_create_collection(_COLLECTION)

    async def index_documents(self, force: bool = False) -> None:
        """Index new or changed PDFs; skip unchanged ones unless force=True."""
        pdf_files = list(self._pdf_dir.glob("*.pdf"))
        if not pdf_files:
            logging.info("RagService: no PDF files found in %s", self._pdf_dir)
            return

        indexed = await asyncio.to_thread(self._get_indexed_files)

        for pdf_path in pdf_files:
            mtime = str(pdf_path.stat().st_mtime)
            key = pdf_path.name

            if not force and indexed.get(key) == mtime:
                logging.info("RagService: skipping unchanged %s", key)
                continue

            logging.info("RagService: indexing %s", key)
            await self._index_file(pdf_path, mtime)

        logging.info("RagService: indexing complete")

    async def drop_index(self) -> None:
        """Delete the entire collection and recreate it."""
        await asyncio.to_thread(self._drop_collection)
        logging.info("RagService: index dropped")

    @traceable(name="rag_search")
    async def search(self, query: str) -> dict:
        embedding = await self._embedding.embed(query)
        results = await asyncio.to_thread(self._query, embedding)

        if not results["documents"] or not results["documents"][0]:
            return {"result": "Информация не найдена в базе знаний."}

        chunks = results["documents"][0]
        sources = [m.get("source", "") for m in results["metadatas"][0]]
        unique_sources = list(dict.fromkeys(sources))

        text = "\n\n---\n\n".join(chunks)
        return {"result": text, "sources": unique_sources}

    async def _index_file(self, pdf_path: Path, mtime: str) -> None:
        md_text = await asyncio.to_thread(pymupdf4llm.to_markdown, str(pdf_path))
        chunks = _split_text(md_text)
        if not chunks:
            return

        embeddings = await self._embedding.embed_batch(chunks)

        ids = [f"{pdf_path.name}::{i}" for i in range(len(chunks))]
        metadatas = [{"source": pdf_path.name, "mtime": mtime} for _ in chunks]

        await asyncio.to_thread(
            self._upsert, ids, embeddings, chunks, metadatas, pdf_path.name
        )
        logging.info("RagService: indexed %d chunks from %s", len(chunks), pdf_path.name)

    def _get_indexed_files(self) -> dict[str, str]:
        """Return {filename: mtime} for all documents already in collection."""
        try:
            result = self._col.get(include=["metadatas"])
            seen: dict[str, str] = {}
            for meta in result["metadatas"]:
                src = meta.get("source", "")
                mt = meta.get("mtime", "")
                if src and src not in seen:
                    seen[src] = mt
            return seen
        except Exception:
            return {}

    def _upsert(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict],
        source: str,
    ) -> None:
        # Remove old chunks for this source before adding new ones
        try:
            existing = self._col.get(where={"source": source})
            if existing["ids"]:
                self._col.delete(ids=existing["ids"])
        except Exception:
            pass
        self._col.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )

    def _query(self, embedding: list[float]) -> dict:
        return self._col.query(
            query_embeddings=[embedding],
            n_results=self._top_k,
            include=["documents", "metadatas"],
        )

    def _drop_collection(self) -> None:
        try:
            self._chroma.delete_collection(_COLLECTION)
        except Exception:
            pass
        self._col = self._chroma.get_or_create_collection(_COLLECTION)


def _split_text(text: str) -> list[str]:
    """Split text into overlapping chunks by character count."""
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + _CHUNK_SIZE, len(text))
        chunks.append(text[start:end])
        if end == len(text):
            break
        start += _CHUNK_SIZE - _CHUNK_OVERLAP
    return [c.strip() for c in chunks if c.strip()]
