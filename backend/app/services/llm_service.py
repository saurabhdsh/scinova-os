"""LLM service — OpenAI (direct API), Anthropic Claude (Bedrock), Mistral SLM."""

from __future__ import annotations

import json
import logging
import re
from typing import Literal

import httpx

from app.config import settings
from app.services.bedrock_client import bedrock_credentials_available, get_bedrock_runtime_client
from app.services.output_style import augment_system_prompt

logger = logging.getLogger(__name__)

LLMProvider = Literal["openai", "bedrock", "mistral"]

_JSON_SYSTEM_SUFFIX = (
    "\n\nRespond with valid JSON only. Do not wrap the JSON in markdown code fences."
)


def is_slm_model(model: str | None) -> bool:
    if not model:
        return False
    name = model.lower()
    if name.startswith("scinova/"):
        return True
    if name.startswith("ministral"):
        return True
    return name == settings.slm_model.lower()


def is_bedrock_llm_model(model: str | None) -> bool:
    if not model:
        return False
    name = model.lower()
    if name.startswith("bedrock:"):
        return True
    # anthropic.* or cross-region profile us.anthropic.*
    return "anthropic." in name


def is_openai_model(model: str | None) -> bool:
    if not model:
        return False
    name = model.lower()
    return name.startswith(("gpt-", "o1", "o3", "chatgpt-"))


def resolve_api_model(model: str | None) -> str:
    if not model:
        return settings.llm_model
    if model.startswith("scinova/"):
        return settings.slm_model
    return model


def resolve_bedrock_model_id(model: str | None) -> str:
    resolved = resolve_api_model(model)
    if resolved.startswith("bedrock:"):
        alias = resolved.split(":", 1)[1].strip().lower()
        if alias in {"", "default", "claude"}:
            return settings.bedrock_llm_model or settings.llm_model
        if "anthropic." in alias:
            return alias
        return resolved.split(":", 1)[1]
    if "anthropic." in resolved:
        return resolved
    return settings.bedrock_llm_model or resolved


def llm_provider_for_model(model: str | None) -> LLMProvider:
    resolved = resolve_api_model(model)
    if is_slm_model(resolved):
        return "mistral"
    if is_bedrock_llm_model(resolved):
        return "bedrock"
    if is_openai_model(resolved):
        return "openai"
    if bedrock_credentials_available() and (
        settings.bedrock_llm_model or is_bedrock_llm_model(settings.llm_model)
    ):
        if is_bedrock_llm_model(settings.llm_model):
            return "bedrock"
    if settings.openai_api_key:
        return "openai"
    if bedrock_credentials_available() and settings.bedrock_llm_model:
        return "bedrock"
    return "openai"


def _provider_for_model(model: str | None) -> tuple[LLMProvider, str, str, str]:
    """Return (provider, base_url, api_key, resolved_model)."""
    resolved = resolve_api_model(model)
    provider = llm_provider_for_model(model)
    if provider == "mistral":
        return (
            provider,
            settings.mistral_base_url.rstrip("/"),
            settings.mistral_api_key,
            resolved,
        )
    if provider == "bedrock":
        return (provider, "", "", resolve_bedrock_model_id(model))
    return (
        provider,
        settings.openai_base_url.rstrip("/"),
        settings.openai_api_key,
        resolved,
    )


class LLMService:
    def __init__(self):
        self.model = settings.llm_model
        self.slm_model = settings.slm_model

    @property
    def available(self) -> bool:
        return bool(settings.openai_api_key) or self.bedrock_available

    @property
    def bedrock_available(self) -> bool:
        if not bedrock_credentials_available():
            return False
        if settings.bedrock_llm_model:
            return True
        return is_bedrock_llm_model(settings.llm_model)

    @property
    def openai_available(self) -> bool:
        return bool(settings.openai_api_key)

    @property
    def slm_available(self) -> bool:
        return bool(settings.mistral_api_key)

    def is_configured(self, model: str | None = None) -> bool:
        provider = llm_provider_for_model(model)
        if provider == "mistral":
            return self.slm_available
        if provider == "bedrock":
            return self.bedrock_available
        return self.openai_available

    def chat(
        self,
        system: str,
        user: str,
        model: str | None = None,
        temperature: float = 0.2,
    ) -> str | None:
        use_model = model or self.model
        provider, base_url, api_key, api_model = _provider_for_model(use_model)
        system_text = augment_system_prompt(system)

        if provider == "bedrock":
            return self._bedrock_chat(system_text, user, api_model, temperature)

        if not api_key:
            provider_name = "Mistral" if provider == "mistral" else "OpenAI"
            logger.warning("%s API key not configured for model %s", provider_name, use_model)
            return None
        try:
            with httpx.Client(timeout=90.0) as client:
                resp = client.post(
                    f"{base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": api_model,
                        "temperature": temperature,
                        "messages": [
                            {"role": "system", "content": system_text},
                            {"role": "user", "content": user},
                        ],
                    },
                )
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"]
        except Exception as e:
            logger.warning("LLM chat failed (%s): %s", api_model, e)
            return None

    def chat_json(
        self,
        system: str,
        user: str,
        model: str | None = None,
        temperature: float = 0.1,
    ) -> dict | list | None:
        use_model = model or self.model
        provider, base_url, api_key, api_model = _provider_for_model(use_model)
        system_text = augment_system_prompt(system)

        if provider == "bedrock":
            return self._bedrock_chat_json(system_text, user, api_model, temperature)

        if not api_key:
            provider_name = "Mistral" if provider == "mistral" else "OpenAI"
            logger.warning("%s API key not configured for model %s", provider_name, use_model)
            return None

        payload: dict = {
            "model": api_model,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system_text},
                {"role": "user", "content": user},
            ],
        }
        if not is_slm_model(use_model) or settings.slm_json_mode:
            payload["response_format"] = {"type": "json_object"}

        try:
            with httpx.Client(timeout=90.0) as client:
                resp = client.post(
                    f"{base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                resp.raise_for_status()
                content = resp.json()["choices"][0]["message"]["content"]
                return _parse_json_content(content)
        except Exception as e:
            logger.warning("LLM JSON call failed (%s): %s", api_model, e)
            return None

    def _bedrock_chat(
        self,
        system: str,
        user: str,
        model_id: str,
        temperature: float,
    ) -> str | None:
        if not self.bedrock_available:
            logger.warning("Bedrock not configured for model %s", model_id)
            return None
        try:
            client = get_bedrock_runtime_client()
            kwargs: dict = {
                "modelId": model_id,
                "messages": [{"role": "user", "content": [{"text": user}]}],
                "inferenceConfig": {
                    "maxTokens": settings.llm_max_tokens,
                    "temperature": temperature,
                },
            }
            if system:
                kwargs["system"] = [{"text": system}]
            response = client.converse(**kwargs)
            blocks = response["output"]["message"]["content"]
            texts = [b.get("text", "") for b in blocks if b.get("text")]
            return "".join(texts).strip() or None
        except Exception as e:
            logger.warning("Bedrock converse failed (%s): %s", model_id, e)
            return self._bedrock_invoke_chat(system, user, model_id, temperature)

    def _bedrock_invoke_chat(
        self,
        system: str,
        user: str,
        model_id: str,
        temperature: float,
    ) -> str | None:
        """Fallback for models that do not support the Converse API."""
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": settings.llm_max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
            "temperature": temperature,
        }
        try:
            client = get_bedrock_runtime_client()
            response = client.invoke_model(
                modelId=model_id,
                body=json.dumps(body),
                contentType="application/json",
                accept="application/json",
            )
            payload = json.loads(response["body"].read())
            blocks = payload.get("content") or []
            texts = [b.get("text", "") for b in blocks if b.get("type") == "text"]
            return "".join(texts).strip() or None
        except Exception as e:
            logger.warning("Bedrock invoke_model failed (%s): %s", model_id, e)
            return None

    def _bedrock_chat_json(
        self,
        system: str,
        user: str,
        model_id: str,
        temperature: float,
    ) -> dict | list | None:
        content = self._bedrock_chat(
            system + _JSON_SYSTEM_SUFFIX,
            user,
            model_id,
            temperature,
        )
        return _parse_json_content(content or "")

    def infer_slm(self, prompt: str, system: str = "", temperature: float = 0.2) -> dict:
        """Direct Ministral 8B inference for SLM runtime."""
        text = self.chat(
            system or "You are a pharma R&D assistant.",
            prompt,
            model=self.slm_model,
            temperature=temperature,
        )
        return {
            "model": self.slm_model,
            "output": text or "",
            "latency_ms": 0,
            "provider": "mistral",
        }


def _parse_json_content(content: str) -> dict | list | None:
    if not content:
        return None
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", content)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    return None


llm_service = LLMService()
