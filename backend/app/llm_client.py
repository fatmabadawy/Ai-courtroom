"""
backend/app/llm_client.py
─────────────────────────
Thin shim that returns a callable `get_llm_response(system_prompt, user_prompt) -> str`.

When USE_MOCK_LLM=true (the default) every call returns the value of
`mock_response` injected at call time — no network, no API key required.
This makes every agent unit-testable without external services.

When USE_MOCK_LLM=false the shim delegates to the provider selected by
LLM_PROVIDER / LLM_MODEL env vars.  Only "openai" is implemented today;
other providers are wired in here, never in agent code.

DEVIATION NOTE (flagged in implementation_plan.md):
  Nothing in INTERFACES.md specifies the LLM provider.  This module is the
  single place that changes when the provider changes — agent code never
  touches it directly.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from backend.app.config import (
    LLM_MODEL,
    LLM_PROVIDER,
    OPENAI_API_KEY,
    USE_MOCK_LLM,
)

logger = logging.getLogger(__name__)


def get_llm_response(
    system_prompt: str,
    user_prompt: str,
    *,
    mock_response: str = "{}",
    temperature: float = 0.0,
    max_tokens: int = 4096,
) -> str:
    """
    Return the raw string response from the configured LLM.

    Parameters
    ----------
    system_prompt:  Content of the system message.
    user_prompt:    Content of the user message.
    mock_response:  String returned verbatim when USE_MOCK_LLM=true.
                    Each agent supplies a schema-valid JSON string as default.
    temperature:    Sampling temperature (0 = deterministic).
    max_tokens:     Max tokens in the completion.

    Returns
    -------
    str — the raw LLM text (usually JSON, parsed by the caller).
    """
    if USE_MOCK_LLM:
        logger.debug("USE_MOCK_LLM=true — returning mock response.")
        return mock_response

    if LLM_PROVIDER == "openai":
        return _call_openai(system_prompt, user_prompt, temperature, max_tokens)

    raise NotImplementedError(
        f"LLM_PROVIDER={LLM_PROVIDER!r} is not yet implemented in llm_client.py. "
        "Supported values: 'openai'.  Add a new branch here for other providers."
    )


# ── Provider implementations ──────────────────────────────────────────────────


def _call_openai(
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    max_tokens: int,
) -> str:
    """Calls OpenAI chat completions.  Import is deferred so the module loads
    successfully even when the openai package is not installed (mock mode)."""
    try:
        import openai  # type: ignore[import]
    except ImportError as exc:
        raise ImportError(
            "openai package is required when USE_MOCK_LLM=false and LLM_PROVIDER=openai. "
            "Install it with:  pip install openai"
        ) from exc

    client = openai.OpenAI(api_key=OPENAI_API_KEY)
    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content or ""
