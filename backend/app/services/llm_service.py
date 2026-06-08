"""OpenAI-compatible LLM service — frontier (OpenAI) + SLM (Mistral Ministral 8B)."""

import json
import logging
import re

import httpx

from app.config import settings
from app.services.output_style import augment_system_prompt

logger = logging.getLogger(__name__)


def is_slm_model(model: str | None) -> bool:
    if not model:
        return False
    name = model.lower()
    if name.startswith("scinova/"):
        return True
    if name.startswith("ministral"):
        return True
    return name == settings.slm_model.lower()


def resolve_api_model(model: str | None) -> str:
    if not model:
        return settings.llm_model
    if model.startswith("scinova/"):
        return settings.slm_model
    return model


def _provider_for_model(model: str | None) -> tuple[str, str, str]:
    """Return (base_url, api_key, resolved_model)."""
    resolved = resolve_api_model(model)
    if is_slm_model(model):
        return (
            settings.mistral_base_url.rstrip("/"),
            settings.mistral_api_key,
            resolved,
        )
    return (
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
        return bool(settings.openai_api_key)

    @property
    def slm_available(self) -> bool:
        return bool(settings.mistral_api_key)

    def is_configured(self, model: str | None = None) -> bool:
        if is_slm_model(model):
            return self.slm_available
        return self.available

    def chat(
        self,
        system: str,
        user: str,
        model: str | None = None,
        temperature: float = 0.2,
    ) -> str | None:
        use_model = model or self.model
        base_url, api_key, api_model = _provider_for_model(use_model)
        if not api_key:
            provider = "Mistral" if is_slm_model(use_model) else "OpenAI"
            logger.warning("%s API key not configured for model %s", provider, use_model)
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
                            {"role": "system", "content": augment_system_prompt(system)},
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
        base_url, api_key, api_model = _provider_for_model(use_model)
        if not api_key:
            provider = "Mistral" if is_slm_model(use_model) else "OpenAI"
            logger.warning("%s API key not configured for model %s", provider, use_model)
            return None

        payload: dict = {
            "model": api_model,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": augment_system_prompt(system)},
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

    def infer_slm(self, prompt: str, system: str = "", temperature: float = 0.2) -> dict:
        """Direct Ministral 8B inference for SLM runtime."""
        text = self.chat(system or "You are a pharma R&D assistant.", prompt, model=self.slm_model, temperature=temperature)
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
