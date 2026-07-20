"""Provider-aware LLM wrapper.

Supports Groq (gsk_...), xAI Grok (xai-...), and OpenAI (sk-...) through the
OpenAI-compatible chat API, plus Anthropic (sk-ant-...) natively. The rest of
the codebase only calls complete() / complete_json() and never cares which
provider is behind them.
"""
from __future__ import annotations

import json
import re
from typing import Any

from . import config

_client = None

# OpenAI-compatible base URLs per provider.
_BASE_URLS = {
    "groq": "https://api.groq.com/openai/v1",
    "xai": "https://api.x.ai/v1",
    "openai": None,  # default OpenAI endpoint
}


def _get_client():
    global _client
    if _client is not None:
        return _client
    config.require_llm()
    if config.LLM_PROVIDER == "anthropic":
        import anthropic
        _client = anthropic.Anthropic(api_key=config.LLM_API_KEY)
    else:
        from openai import OpenAI
        _client = OpenAI(api_key=config.LLM_API_KEY,
                         base_url=_BASE_URLS.get(config.LLM_PROVIDER))
    return _client


def complete(system: str, user: str, *, max_tokens: int = 4000, effort: str = "high") -> str:
    client = _get_client()
    if config.LLM_PROVIDER == "anthropic":
        resp = client.messages.create(
            model=config.LLM_MODEL, max_tokens=max_tokens,
            system=system, messages=[{"role": "user", "content": user}],
        )
        return "".join(b.text for b in resp.content if b.type == "text").strip()

    resp = client.chat.completions.create(
        model=config.LLM_MODEL, max_tokens=max_tokens,
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}],
    )
    return (resp.choices[0].message.content or "").strip()


def _extract_json(text: str) -> Any:
    """Parse JSON from a model response, tolerating code fences / stray prose."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # grab the outermost {...} or [...]
        m = re.search(r"[\{\[].*[\}\]]", text, re.DOTALL)
        if m:
            return json.loads(m.group(0))
        raise


def complete_json(system: str, user: str, schema: dict[str, Any], *,
                  max_tokens: int = 4000, effort: str = "high") -> Any:
    client = _get_client()

    if config.LLM_PROVIDER == "anthropic":
        resp = client.messages.create(
            model=config.LLM_MODEL, max_tokens=max_tokens,
            output_config={"format": {"type": "json_schema", "schema": schema}},
            system=system, messages=[{"role": "user", "content": user}],
        )
        text = next((b.text for b in resp.content if b.type == "text"), "{}")
        return json.loads(text)

    # OpenAI-compatible: use JSON mode + schema described in the prompt.
    sys_with_schema = (
        f"{system}\n\nReturn ONLY a JSON object that conforms to this JSON schema "
        f"(no markdown, no commentary):\n{json.dumps(schema)}"
    )
    resp = client.chat.completions.create(
        model=config.LLM_MODEL, max_tokens=max_tokens,
        response_format={"type": "json_object"},
        messages=[{"role": "system", "content": sys_with_schema},
                  {"role": "user", "content": user}],
    )
    return _extract_json(resp.choices[0].message.content or "{}")
