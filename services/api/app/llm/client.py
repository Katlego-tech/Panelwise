"""Nebius Token Factory chat client, with fast / reasoning / vision tiers.

Built to docs/design/llm.md, against the API behaviour measured in docs/nebius-findings.md.
Ported from FrameFlow's openai_compat.py (retries, the reasoning-but-no-content error); the
provider chain, Gemini and Ollama are gone -- Panelwise runs on Nemotron on Token Factory only.
"""

import asyncio
import logging
import re
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Self, cast

import httpx2

from app.core.config import Settings

logger = logging.getLogger(__name__)

type Message = dict[str, Any]

_RETRYABLE = frozenset({429, 500, 502, 503, 504})
_MAX_RETRY_AFTER_S = 30.0
_THINK_BLOCK = re.compile(r"^\s*<think>.*?</think>", re.DOTALL)


class Tier(StrEnum):
    FAST = "fast"
    REASONING = "reasoning"
    VISION = "vision"


# findings U2: thinking off costs nothing on the fast tier and saves ~68x output tokens there.
# The toggle was only measured on Nemotron, so the vision model gets nothing by default.
_THINKING_DEFAULT: dict[Tier, bool | None] = {
    Tier.FAST: False,
    Tier.REASONING: True,
    Tier.VISION: None,
}


class LLMError(RuntimeError):
    """Base for every failure this module raises."""


class LLMConfigError(LLMError):
    """The client can't make this call as configured."""


class LLMRequestError(LLMError):
    """Token Factory refused the request, or retries ran out."""

    def __init__(self, message: str, status: int | None) -> None:
        super().__init__(message)
        self.status = status


class LLMEmptyResponse(LLMError):
    """A 200 with no usable content."""


@dataclass(frozen=True)
class Usage:
    prompt_tokens: int
    completion_tokens: int
    reasoning_tokens: int


@dataclass(frozen=True)
class ChatResult:
    content: str
    model: str
    tier: Tier
    usage: Usage
    finish_reason: str | None


class NebiusChatModel:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        models: Mapping[Tier, str],
        timeout_s: float = 120.0,
        max_attempts: int = 3,
        transport: httpx2.AsyncBaseTransport | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        on_usage: Callable[[ChatResult], Awaitable[None]] | None = None,
    ) -> None:
        self._models = dict(models)
        # T069 (limits.md §6): awaited after each answer, to count the month's tokens.
        self.on_usage = on_usage
        self._max_attempts = max_attempts
        self._sleep = sleep
        self._client = httpx2.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout_s,
            transport=transport,
        )

    @classmethod
    def from_settings(cls, settings: Settings) -> Self:
        if not settings.nebius_api_key:
            raise LLMConfigError("NEBIUS_API_KEY is not set (see .env.example).")
        return cls(
            api_key=settings.nebius_api_key,
            base_url=settings.nebius_base_url,
            models={
                Tier.FAST: settings.nebius_model_fast,
                Tier.REASONING: settings.nebius_model_reasoning,
                Tier.VISION: settings.nebius_model_vision,
            },
            timeout_s=settings.llm_request_timeout_s,
            max_attempts=settings.llm_max_attempts,
        )

    def model_for(self, tier: Tier) -> str:
        model = self._models.get(tier, "")
        if not model:
            raise LLMConfigError(f"No model configured for the {tier} tier.")
        return model

    async def chat(
        self,
        messages: Sequence[Message],
        tier: Tier = Tier.FAST,
        *,
        thinking: bool | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        response_format: Mapping[str, Any] | None = None,
    ) -> ChatResult:
        model = self.model_for(tier)
        body: dict[str, Any] = {
            "model": model,
            "messages": list(messages),
            "temperature": temperature,
        }
        if max_tokens is not None:
            body["max_tokens"] = max_tokens
        if response_format is not None:
            body["response_format"] = dict(response_format)
        think = _THINKING_DEFAULT[tier] if thinking is None else thinking
        if think is not None:
            body["chat_template_kwargs"] = {"enable_thinking": think}

        data = await self._post(body, model)
        result = _to_result(data, model, tier)
        if self.on_usage is not None:
            await self.on_usage(result)
        return result

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _post(self, body: dict[str, Any], model: str) -> dict[str, Any]:
        backoff = 1.0
        status: int | None = None
        for attempt in range(1, self._max_attempts + 1):
            delay = backoff
            try:
                response = await self._client.post("/chat/completions", json=body)
            except httpx2.TransportError as exc:
                status = None
                logger.warning("%s: %s (attempt %d)", model, type(exc).__name__, attempt)
            else:
                status = response.status_code
                if status == 200:
                    try:
                        data: dict[str, Any] = response.json()
                    except ValueError:
                        # Something in front of Token Factory answered, not the model.
                        raise LLMRequestError(f"{model}: HTTP 200 without JSON", status) from None
                    return data
                if status not in _RETRYABLE:
                    # A bad request fails the same way every time; retrying only spends credit.
                    raise LLMRequestError(f"{model}: HTTP {status}", status)
                delay = _retry_after(response) or backoff
                logger.warning("%s: HTTP %d (attempt %d)", model, status, attempt)

            if attempt < self._max_attempts:
                await self._sleep(delay)
                backoff *= 2
        reason = f"HTTP {status}" if status is not None else "network error"
        raise LLMRequestError(
            f"{model}: gave up after {self._max_attempts} attempts ({reason})", status
        )


def _retry_after(response: httpx2.Response) -> float | None:
    try:
        seconds = float(response.headers.get("retry-after", ""))
    except ValueError:
        return None
    return min(max(seconds, 0.0), _MAX_RETRY_AFTER_S)


def _text_of(content: object) -> str:
    """Message content is a string, or a list of parts of which only text parts carry text."""
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    texts: list[str] = []
    for part in cast(list[object], content):
        if isinstance(part, dict):
            fields = cast(dict[str, object], part)
            if fields.get("type") == "text":
                texts.append(str(fields.get("text", "")))
    return "".join(texts)


def _to_result(data: dict[str, Any], requested: str, tier: Tier) -> ChatResult:
    choices: list[dict[str, Any]] = data.get("choices") or [{}]
    choice = choices[0]
    message: dict[str, Any] = choice.get("message") or {}
    finish_reason: str | None = choice.get("finish_reason")
    content = _THINK_BLOCK.sub("", _text_of(message.get("content"))).strip()
    model: str = data.get("model") or requested

    if not content:
        if message.get("reasoning_content") or message.get("reasoning"):
            raise LLMEmptyResponse(
                f"{model} spent its budget thinking and returned no content "
                f"(finish_reason={finish_reason}). Call with thinking=False or raise max_tokens."
            )
        raise LLMEmptyResponse(f"{model} returned no content (finish_reason={finish_reason}).")

    usage: dict[str, Any] = data.get("usage") or {}
    details: dict[str, Any] = usage.get("completion_tokens_details") or {}
    return ChatResult(
        content=content,
        model=model,
        tier=tier,
        usage=Usage(
            prompt_tokens=usage.get("prompt_tokens") or 0,
            completion_tokens=usage.get("completion_tokens") or 0,
            reasoning_tokens=details.get("reasoning_tokens") or 0,
        ),
        finish_reason=finish_reason,
    )
