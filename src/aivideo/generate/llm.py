"""LLM wrapper — chat completions via Token360.

Supports both plain text and JSON-mode responses. Caches by prompt+model.
"""

from __future__ import annotations

import json
from typing import Any

from ..cache import cache_path, hit
from ..client import openai_client
from ..config import settings


def script(
    prompt: str,
    *,
    system: str | None = None,
    model: str | None = None,
    json_mode: bool = False,
    temperature: float = 0.8,
    use_cache: bool = True,
) -> Any:
    """Generate text or JSON from the LLM.

    Returns:
        - str when json_mode=False
        - dict when json_mode=True (the response is parsed)
    """
    model = model or settings.llm_model
    params = {
        "prompt": prompt,
        "system": system,
        "json_mode": json_mode,
        "temperature": temperature,
    }
    path = cache_path("llm", model, params, "json")
    if use_cache and hit(path):
        cached = json.loads(path.read_text())
        return cached["value"]

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    resp = openai_client().chat.completions.create(**kwargs)
    text = resp.choices[0].message.content or ""
    value = json.loads(text) if json_mode else text

    path.write_text(json.dumps({"value": value}, ensure_ascii=False))
    return value
