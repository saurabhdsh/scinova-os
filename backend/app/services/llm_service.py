"""LLM service — OpenAI (direct API), Anthropic Claude (Bedrock), Mistral SLM."""

from __future__ import annotations

import json
import logging
import re
import time
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


def _sampling_locked(model: str | None) -> bool:
    """gpt-5 and o-series deployments reject a custom temperature."""
    name = (model or "").lower()
    return name.startswith(("gpt-5", "o1", "o3", "o4"))


def _message_text(message: dict) -> str:
    content = message.get("content")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                parts.append(str(item.get("text") or ""))
        return "".join(parts).strip()
    return ""


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
        payload = {
            "model": api_model,
            "messages": [
                {"role": "system", "content": system_text},
                {"role": "user", "content": user},
            ],
        }
        if _sampling_locked(api_model):
            payload["max_completion_tokens"] = min(int(settings.llm_max_tokens or 4096), 4096)
        else:
            payload["temperature"] = temperature
        return self._post_chat(base_url, api_key, payload)

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
            "messages": [
                {"role": "system", "content": system_text},
                {"role": "user", "content": user},
            ],
        }
        if _sampling_locked(api_model):
            payload["max_completion_tokens"] = min(int(settings.llm_max_tokens or 4096), 4096)
        else:
            payload["temperature"] = temperature
        if not is_slm_model(use_model) or settings.slm_json_mode:
            payload["response_format"] = {"type": "json_object"}
        content = self._post_chat(base_url, api_key, payload)
        return _parse_json_content(content or "")

    def _post_chat(self, base_url: str, api_key: str, payload: dict) -> str | None:
        url = f"{base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        try:
            with httpx.Client(timeout=120.0) as client:
                resp = client.post(url, headers=headers, json=payload)
                if resp.status_code == 400 and any(key in payload for key in ("temperature", "response_format")):
                    logger.warning("LLM 400 (%s): %s", payload.get("model"), resp.text[:300])
                    slim = {key: value for key, value in payload.items() if key not in {"temperature", "response_format"}}
                    resp = client.post(url, headers=headers, json=slim)
                if resp.status_code >= 400:
                    logger.warning("LLM chat failed (%s) HTTP %s: %s", payload.get("model"), resp.status_code, resp.text[:300])
                    return None
                message = (resp.json().get("choices") or [{}])[0].get("message") or {}
                return _message_text(message) or None
        except Exception as e:
            logger.warning("LLM chat failed (%s): %s", payload.get("model"), e)
            return None

    def _bedrock_max_tokens(self, *, json_mode: bool = False) -> int:
        cap = 2048 if json_mode else 3072
        return max(256, min(int(settings.llm_max_tokens or cap), cap))

    def _bedrock_chat(
        self,
        system: str,
        user: str,
        model_id: str,
        temperature: float,
        *,
        json_mode: bool = False,
    ) -> str | None:
        if not self.bedrock_available:
            logger.warning("Bedrock not configured for model %s", model_id)
            return None
        started = time.monotonic()
        try:
            client = get_bedrock_runtime_client()
            kwargs: dict = {
                "modelId": model_id,
                "messages": [{"role": "user", "content": [{"text": user}]}],
                "inferenceConfig": {
                    "maxTokens": self._bedrock_max_tokens(json_mode=json_mode),
                    "temperature": temperature,
                },
            }
            if system:
                kwargs["system"] = [{"text": system}]
            response = client.converse(**kwargs)
            blocks = response["output"]["message"]["content"]
            texts = [b.get("text", "") for b in blocks if b.get("text")]
            logger.info(
                "Bedrock converse OK (%s) in %.1fs",
                model_id,
                time.monotonic() - started,
            )
            return "".join(texts).strip() or None
        except Exception as e:
            elapsed = time.monotonic() - started
            logger.warning("Bedrock converse failed (%s) after %.1fs: %s", model_id, elapsed, e)
            # Do not double-pay a 3-minute timeout with invoke_model.
            if elapsed >= 50 or "ReadTimeout" in type(e).__name__ or "timeout" in str(e).lower():
                return None
            return self._bedrock_invoke_chat(system, user, model_id, temperature, json_mode=json_mode)

    def _bedrock_invoke_chat(
        self,
        system: str,
        user: str,
        model_id: str,
        temperature: float,
        *,
        json_mode: bool = False,
    ) -> str | None:
        """Fallback for models that do not support the Converse API."""
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": self._bedrock_max_tokens(json_mode=json_mode),
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
            json_mode=True,
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
