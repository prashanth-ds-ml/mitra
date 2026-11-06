from __future__ import annotations

import json
import os
from urllib import error, request

from langchain_ollama import ChatOllama

_LOCAL_BASE_URL = "http://localhost:11434"


def _make_client_kwargs(api_key: str | None = None) -> dict | None:
    api_key = (api_key or os.getenv("OLLAMA_API_KEY", "")).strip()
    if not api_key:
        return None
    return {"headers": {"Authorization": f"Bearer {api_key}"}}


def get_llm(
    model: str,
    temperature: float = 0.2,
    *,
    base_url: str | None = None,
    api_key: str | None = None,
    num_ctx: int | None = None,
    num_gpu: int | None = None,
    num_predict: int | None = None,
    reasoning: bool | None = None,
) -> ChatOllama:
    """Return a ChatOllama instance for the given model name."""
    kwargs = {
        "model": model,
        "temperature": temperature,
    }
    if num_ctx:
        kwargs["num_ctx"] = num_ctx
    if num_gpu is not None:
        kwargs["num_gpu"] = num_gpu
    if num_predict is not None:
        kwargs["num_predict"] = num_predict
    if base_url:
        kwargs["base_url"] = base_url
    if reasoning is not None:
        kwargs["reasoning"] = reasoning
    client_kwargs = _make_client_kwargs(api_key)
    if client_kwargs:
        kwargs["client_kwargs"] = client_kwargs
    return ChatOllama(**kwargs)


def get_local_llm(
    model: str,
    temperature: float = 0.2,
    *,
    base_url: str | None = None,
    num_ctx: int | None = None,
    num_gpu: int | None = None,
    num_predict: int | None = None,
    reasoning: bool | None | str = "auto",
) -> ChatOllama:
    """Return a client for the local Ollama daemon.

    reasoning="auto" turns thinking on for models that report the `thinking` capability, so the model's reasoning
    arrives separately (shown as the thinking line) instead of being dropped by langchain-ollama (E-016).
    """
    if reasoning == "auto":
        reasoning = model_supports_thinking(model)
    return get_llm(
        model,
        temperature,
        base_url=base_url or _LOCAL_BASE_URL,
        num_ctx=num_ctx,
        num_gpu=num_gpu,
        num_predict=num_predict,
        reasoning=reasoning,
    )


def thinking_setting(value) -> bool | str:
    """mitra.toml `thinking`: "on" -> think, "off" -> no thinking (faster), anything else -> auto (on for models
    that support it). D-020."""
    v = str(value or "auto").strip().lower()
    if v in ("on", "true", "yes"):
        return True
    if v in ("off", "false", "no"):
        return False
    return "auto"


def model_supports_thinking(model: str) -> bool | None:
    """True for thinking models, None (model default) when unknown or not a thinking model."""
    try:
        from app import config

        facts = config.get_model_facts(model)
    except Exception:
        return None
    if facts and "thinking" in (facts.get("capabilities") or ()):
        return True
    return None




# Legacy aliases kept for any existing call sites




def probe_ollama(base_url: str | None = None, timeout: float = 2.0) -> tuple[bool, str]:
    """Check whether the Ollama HTTP API is reachable."""
    target = (base_url or _LOCAL_BASE_URL).rstrip("/")
    try:
        with request.urlopen(f"{target}/api/tags", timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8") or "{}")
    except error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        return False, f"Unavailable: {reason}"
    except Exception as exc:
        return False, f"Unavailable: {exc}"

    models = payload.get("models") or []
    count = len(models)
    label = "model" if count == 1 else "models"
    return True, f"Connected: {count} local {label} detected"
