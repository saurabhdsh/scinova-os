"""Facade clients — delegates to real implementations where available."""

from app.services.chromadb_client import chromadb_client as _chroma
from app.services.neo4j_client import neo4j_client as _neo4j
from app.services.llm_service import llm_service as _llm


class Neo4jClient:
    def connect(self):
        ok = _neo4j.connect()
        return {"status": "connected" if ok else "unavailable"}

    def stats(self):
        return _neo4j.stats()


class VectorDBClient:
    def search(self, query: str, top_k: int = 10):
        return _chroma.search(query, top_k=top_k)


class LLMServiceWrapper:
    def __init__(self):
        self._svc = _llm

    async def complete(self, model: str, messages: list, **kwargs):
        if not self._svc.available:
            return {"model": model, "content": "Configure OPENAI_API_KEY for live LLM inference."}
        result = self._svc.chat_json(
            messages[0]["content"] if messages else "",
            messages[1]["content"] if len(messages) > 1 else "",
        )
        return {"model": model, "content": str(result)}


class SLMRuntime:
    async def infer(self, model_name: str, prompt: str, **kwargs):
        from app.services.llm_service import llm_service

        result = llm_service.infer_slm(
            prompt,
            system=kwargs.get("system", ""),
            temperature=float(kwargs.get("temperature", 0.2)),
        )
        result["requested_model"] = model_name
        return result


neo4j_client = Neo4jClient()
vector_db_client = VectorDBClient()
llm_service = LLMServiceWrapper()
slm_runtime = SLMRuntime()
