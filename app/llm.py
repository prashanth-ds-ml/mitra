from __future__ import annotations

import json
import os
from urllib import error, request

from langchain_ollama import ChatOllama

_LOCAL_BASE_URL = "http://localhost:11434"
_CLOUD_BASE_URL = "https://ollama.com"


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
) -> ChatOllama:
    """Return a client for the local Ollama daemon."""
    return get_llm(
        model,
        temperature,
        base_url=base_url or _LOCAL_BASE_URL,
        num_ctx=num_ctx,
        num_gpu=num_gpu,
        num_predict=num_predict,
    )


def get_cloud_llm(
    model: str,
    temperature: float = 0.2,
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    num_ctx: int | None = None,
    num_gpu: int | None = None,
    num_predict: int | None = None,
) -> ChatOllama:
    """Return a client for Ollama's hosted cloud API."""
    return get_llm(
        model,
        temperature,
        base_url=base_url or _CLOUD_BASE_URL,
        api_key=api_key,
        num_ctx=num_ctx,
        num_gpu=num_gpu,
        num_predict=num_predict,
    )


# Legacy aliases kept for any existing call sites
def get_chat_llm(model: str = "qwen2.5-coder:7b", temperature: float = 0.2) -> ChatOllama:
    return get_local_llm(model, temperature)


def get_agent_llm(model: str = "qwen2.5-coder:7b") -> ChatOllama:
    return get_local_llm(model, temperature=0)


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
