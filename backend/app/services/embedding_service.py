"""Embedding service — OpenAI-compatible API, Amazon Bedrock (Titan/Cohere), or local fallback."""

import hashlib
import json
import logging
import math
import os
from typing import Literal

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

EmbedProvider = Literal["openai", "bedrock", "local"]
COHERE_BATCH_SIZE = 96


def _is_cohere_bedrock_model(model_id: str) -> bool:
    name = model_id.lower()
    return "cohere" in name and "embed" in name


def _is_titan_bedrock_model(model_id: str) -> bool:
    name = model_id.lower()
    return "titan" in name and "embed" in name


class EmbeddingService:
    def remote_available(self) -> bool:
        return self.resolve_provider() != "local"

    def resolve_provider(self) -> EmbedProvider:
        mode = (settings.embedding_provider or "auto").strip().lower()
        if mode == "openai":
            return "openai" if self._openai_configured() else "local"
        if mode == "bedrock":
            return "bedrock" if self._bedrock_configured() else "local"
        if self._openai_configured():
            return "openai"
        if self._bedrock_configured():
            return "bedrock"
        return "local"

    def provider_label(self) -> str:
        provider = self.resolve_provider()
        if provider == "openai":
            return "openai"
        if provider == "bedrock":
            return "bedrock"
        return "local/chromadb"

    def active_model_id(self) -> str:
        provider = self.resolve_provider()
        if provider == "bedrock":
            return settings.bedrock_embedding_model
        if provider == "openai":
            return settings.embedding_model
        return "local-hash-v1"

    def embed_texts(self, texts: list[str]) -> tuple[list[list[float]], str]:
        if not texts:
            return [], "none"

        provider = self.resolve_provider()
        model_id = self.active_model_id()

        if provider == "openai":
            try:
                return self._openai_embed(texts), model_id
            except Exception as exc:
                logger.warning("OpenAI embedding failed (%s), using local fallback", exc)
        elif provider == "bedrock":
            try:
                return self._bedrock_embed(texts, input_type="search_document"), model_id
            except Exception as exc:
                logger.warning("Bedrock embedding failed (%s), using local fallback", exc)

        return self._local_embed(texts), "local-hash-v1"

    def embed_query(self, query: str) -> tuple[list[float] | None, str]:
        if not query.strip():
            return None, "none"

        provider = self.resolve_provider()
        model_id = self.active_model_id()

        if provider == "openai":
            try:
                embeddings = self._openai_embed([query])
                return embeddings[0] if embeddings else None, model_id
            except Exception as exc:
                logger.warning("OpenAI query embedding failed (%s), using local fallback", exc)
        elif provider == "bedrock":
            try:
                embeddings = self._bedrock_embed([query], input_type="search_query")
                return embeddings[0] if embeddings else None, model_id
            except Exception as exc:
                logger.warning("Bedrock query embedding failed (%s), using local fallback", exc)

        embeddings = self._local_embed([query])
        return embeddings[0] if embeddings else None, "local-hash-v1"

    def _openai_configured(self) -> bool:
        return bool(settings.openai_api_key and settings.embedding_model)

    def _bedrock_configured(self) -> bool:
        if not settings.bedrock_embedding_model:
            return False
        if settings.aws_access_key_id and settings.aws_secret_access_key:
            return True
        if os.environ.get("AWS_ACCESS_KEY_ID") and os.environ.get("AWS_SECRET_ACCESS_KEY"):
            return True
        if os.environ.get("AWS_PROFILE"):
            return True
        if os.environ.get("AWS_CONTAINER_CREDENTIALS_RELATIVE_URI"):
            return True
        # EC2/ECS instance metadata (IMDS) — boto3 resolves at runtime
        try:
            import boto3

            session = boto3.Session(region_name=self._aws_region())
            creds = session.get_credentials()
            return creds is not None
        except Exception:
            return False

    def _aws_region(self) -> str:
        return (
            settings.aws_region
            or os.environ.get("AWS_REGION")
            or os.environ.get("AWS_DEFAULT_REGION")
            or "us-east-1"
        )

    def _bedrock_client(self):
        import boto3

        kwargs: dict = {"region_name": self._aws_region()}
        if settings.aws_access_key_id and settings.aws_secret_access_key:
            kwargs["aws_access_key_id"] = settings.aws_access_key_id
            kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
            if settings.aws_session_token:
                kwargs["aws_session_token"] = settings.aws_session_token
        return boto3.client("bedrock-runtime", **kwargs)

    def _openai_embed(self, texts: list[str]) -> list[list[float]]:
        url = f"{settings.openai_base_url.rstrip('/')}/embeddings"
        headers = {
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
        }
        batch_size = 64
        all_embeddings: list[list[float]] = []

        with httpx.Client(timeout=60.0) as client:
            for i in range(0, len(texts), batch_size):
                batch = texts[i : i + batch_size]
                resp = client.post(
                    url,
                    headers=headers,
                    json={"model": settings.embedding_model, "input": batch},
                )
                resp.raise_for_status()
                data = resp.json()
                sorted_data = sorted(data["data"], key=lambda x: x["index"])
                all_embeddings.extend([item["embedding"] for item in sorted_data])

        return all_embeddings

    def _bedrock_embed(
        self,
        texts: list[str],
        *,
        input_type: Literal["search_document", "search_query"],
    ) -> list[list[float]]:
        model_id = settings.bedrock_embedding_model
        if _is_cohere_bedrock_model(model_id):
            return self._bedrock_cohere_embed(texts, model_id, input_type=input_type)
        if _is_titan_bedrock_model(model_id):
            return self._bedrock_titan_embed(texts, model_id)
        raise ValueError(
            f"Unsupported Bedrock embedding model '{model_id}'. "
            "Use amazon.titan-embed-text-v* or cohere.embed-*"
        )

    def _bedrock_cohere_embed(
        self,
        texts: list[str],
        model_id: str,
        *,
        input_type: Literal["search_document", "search_query"],
    ) -> list[list[float]]:
        client = self._bedrock_client()
        all_embeddings: list[list[float]] = []

        for i in range(0, len(texts), COHERE_BATCH_SIZE):
            batch = texts[i : i + COHERE_BATCH_SIZE]
            body = json.dumps({
                "texts": batch,
                "input_type": input_type,
                "truncate": "END",
            })
            response = client.invoke_model(
                body=body,
                modelId=model_id,
                accept="application/json",
                contentType="application/json",
            )
            payload = json.loads(response["body"].read())
            embeddings = payload.get("embeddings")
            if not embeddings:
                raise ValueError(f"Bedrock Cohere embed returned no embeddings: {payload}")
            all_embeddings.extend(embeddings)

        return all_embeddings

    def _bedrock_titan_embed(self, texts: list[str], model_id: str) -> list[list[float]]:
        client = self._bedrock_client()
        embeddings: list[list[float]] = []

        for text in texts:
            body_dict: dict = {"inputText": text}
            if "v2" in model_id.lower():
                body_dict["normalize"] = True
            body = json.dumps(body_dict)
            response = client.invoke_model(
                body=body,
                modelId=model_id,
                accept="application/json",
                contentType="application/json",
            )
            payload = json.loads(response["body"].read())
            vector = payload.get("embedding")
            if not vector:
                raise ValueError(f"Bedrock Titan embed returned no embedding: {payload}")
            embeddings.append(vector)

        return embeddings

    def _local_embed(self, texts: list[str], dims: int = 384) -> list[list[float]]:
        """Deterministic local embeddings for dev without API keys."""
        return [_hash_embed(t, dims) for t in texts]


def _hash_embed(text: str, dims: int) -> list[float]:
    vec = [0.0] * dims
    tokens = text.lower().split()
    for token in tokens:
        h = int(hashlib.sha256(token.encode()).hexdigest(), 16)
        for d in range(dims):
            vec[d] += math.sin(h * (d + 1) * 0.001)
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


embedding_service = EmbeddingService()
