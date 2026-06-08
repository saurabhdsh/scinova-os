"""ChromaDB vector store client for Scientific Data Fabric."""

import logging
import os
import shutil
from pathlib import Path
from typing import Any

# Disable Chroma telemetry before the library loads (avoids posthog API mismatch noise).
os.environ.setdefault("ANONYMIZED_TELEMETRY", "FALSE")

from app.config import settings

logger = logging.getLogger(__name__)

COLLECTION_NAME = "scinova_documents"


def _disable_chroma_telemetry() -> None:
    try:
        import posthog

        posthog.disabled = True
    except ImportError:
        pass


def _chroma_settings(ChromaSettings):
    return ChromaSettings(
        anonymized_telemetry=False,
        chroma_product_telemetry_impl="app.services.chroma_telemetry.NoOpTelemetry",
    )


class ChromaDBClient:
    def __init__(self):
        self._client = None
        self._collection = None
        self._mode = "uninitialized"

    def _ensure_client(self):
        if self._client is not None and self._collection is not None:
            return

        _disable_chroma_telemetry()
        import chromadb
        from chromadb.config import Settings as ChromaSettings

        chroma_settings = _chroma_settings(ChromaSettings)

        if settings.chroma_use_http:
            try:
                self._client = chromadb.HttpClient(
                    host=settings.chroma_host,
                    port=settings.chroma_port,
                    settings=chroma_settings,
                )
                self._client.heartbeat()
                self._mode = "http"
                logger.info("ChromaDB connected via HTTP at %s:%s", settings.chroma_host, settings.chroma_port)
                self._collection = self._open_collection()
                return
            except Exception as e:
                logger.warning("ChromaDB HTTP unavailable (%s), falling back to persistent local store", e)
                self._client = None
                self._collection = None

        self._client, self._collection = self._init_persistent_client(ChromaSettings, chroma_settings)
        self._mode = "persistent"

    def _init_persistent_client(self, ChromaSettings, chroma_settings):
        import chromadb

        path = Path(settings.chroma_persist_dir)
        path.mkdir(parents=True, exist_ok=True)

        for attempt in range(2):
            try:
                client = chromadb.PersistentClient(
                    path=str(path),
                    settings=chroma_settings,
                )
                collection = self._open_collection(client)
                logger.info("ChromaDB using persistent store at %s", path)
                return client, collection
            except (KeyError, ValueError, Exception) as e:
                if attempt == 0:
                    logger.warning(
                        "ChromaDB store at %s is corrupt or incompatible (%s); resetting store",
                        path,
                        e,
                    )
                    self._reset_persist_dir(path)
                else:
                    raise

        raise RuntimeError("Failed to initialize ChromaDB persistent client")

    def _reset_persist_dir(self, path: Path) -> None:
        self._client = None
        self._collection = None
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)
        path.mkdir(parents=True, exist_ok=True)

    def _open_collection(self, client=None):
        client = client or self._client
        try:
            return client.get_or_create_collection(
                name=COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )
        except (KeyError, ValueError, Exception):
            try:
                client.delete_collection(COLLECTION_NAME)
            except Exception:
                pass
            return client.create_collection(
                name=COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )

    def _recreate_collection(self) -> None:
        client = self._client
        try:
            client.delete_collection(COLLECTION_NAME)
        except Exception:
            pass
        self._collection = client.create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    def index_chunks(
        self,
        document_id: str,
        chunks: list[dict],
        embeddings: list[list[float]] | None = None,
    ) -> dict:
        self._ensure_client()
        if not chunks:
            return {"indexed": 0, "collection": COLLECTION_NAME, "mode": self._mode}

        ids = [c["chroma_id"] for c in chunks]
        documents = [c["content"] for c in chunks]
        metadatas = [
            {
                "document_id": document_id,
                "chunk_index": c["chunk_index"],
                "token_count": c.get("token_count", 0),
                **{k: str(v) for k, v in c.get("metadata", {}).items()},
            }
            for c in chunks
        ]

        def _upsert() -> None:
            if embeddings:
                self._collection.upsert(
                    ids=ids,
                    embeddings=embeddings,
                    documents=documents,
                    metadatas=metadatas,
                )
            else:
                self._collection.upsert(
                    ids=ids,
                    documents=documents,
                    metadatas=metadatas,
                )

        try:
            _upsert()
        except Exception as e:
            err = str(e).lower()
            if "dimension" in err or "_type" in err:
                logger.warning("Chroma collection incompatible (%s); recreating collection", e)
                self._recreate_collection()
                _upsert()
            else:
                raise

        return {"indexed": len(chunks), "collection": COLLECTION_NAME, "mode": self._mode}

    def search(
        self,
        query: str,
        top_k: int = 10,
        document_id: str | None = None,
        document_ids: list[str] | None = None,
        query_embedding: list[float] | None = None,
    ) -> list[dict]:
        try:
            self._ensure_client()
            if self._collection.count() == 0:
                return []

            where = None
            if document_id:
                where = {"document_id": document_id}
            elif document_ids:
                if len(document_ids) == 1:
                    where = {"document_id": document_ids[0]}
                elif document_ids:
                    where = {"document_id": {"$in": document_ids}}

            kwargs: dict[str, Any] = {"n_results": min(top_k, self._collection.count())}
            if where:
                kwargs["where"] = where

            if query_embedding:
                results = self._collection.query(query_embeddings=[query_embedding], **kwargs)
            else:
                results = self._collection.query(query_texts=[query], **kwargs)

            return _format_results(results)
        except Exception as e:
            logger.error("ChromaDB search failed: %s", e)
            return []

    def delete_document(self, document_id: str) -> int:
        self._ensure_client()
        try:
            existing = self._collection.get(where={"document_id": document_id})
            if existing and existing["ids"]:
                self._collection.delete(ids=existing["ids"])
                return len(existing["ids"])
        except Exception as e:
            logger.warning("Failed to delete document %s from ChromaDB: %s", document_id, e)
        return 0

    def stats(self) -> dict:
        try:
            self._ensure_client()
            return {
                "collection": COLLECTION_NAME,
                "mode": self._mode,
                "total_chunks": self._collection.count(),
            }
        except Exception as e:
            logger.error("ChromaDB stats failed: %s", e)
            return {
                "collection": COLLECTION_NAME,
                "mode": "error",
                "total_chunks": 0,
            }


def _format_results(results: dict) -> list[dict]:
    items = []
    if not results or not results.get("ids"):
        return items

    ids = results["ids"][0]
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    for i, chunk_id in enumerate(ids):
        score = 1.0 - distances[i] if i < len(distances) else 0.0
        meta = metadatas[i] if i < len(metadatas) else {}
        items.append({
            "chunk_id": chunk_id,
            "content": documents[i] if i < len(documents) else "",
            "document_id": meta.get("document_id", ""),
            "chunk_index": int(meta.get("chunk_index", 0)),
            "score": round(max(0.0, min(1.0, score)), 4),
            "metadata": meta,
        })
    return items


chromadb_client = ChromaDBClient()
