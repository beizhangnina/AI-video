"""Singleton OpenAI client pointed at Token360 + a thin httpx client for native endpoints."""

from __future__ import annotations

from functools import lru_cache

import httpx
from openai import OpenAI

from .config import settings


@lru_cache(maxsize=1)
def openai_client() -> OpenAI:
    """Standard OpenAI SDK with base_url swapped to Token360.

    Used by all generate/* modules for normalized (OpenAI-style) requests.
    """
    return OpenAI(api_key=settings.api_key, base_url=settings.base_url)


@lru_cache(maxsize=1)
def http_client() -> httpx.Client:
    """Thin httpx client for endpoints not covered by OpenAI SDK.

    Used for Token360 Assets API (/v1/asset-groups, /v1/assets) and
    native passthrough mode (Token360-Native-Params header).
    """
    return httpx.Client(
        base_url=settings.base_url,
        headers={"Authorization": f"Bearer {settings.api_key}"},
        timeout=httpx.Timeout(60.0, read=300.0),
    )
