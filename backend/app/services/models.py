import asyncio
import logging
import time
from dataclasses import dataclass

import openai
from openai import AsyncOpenAI, OpenAIError

from app.config import LlmSettings

logger = logging.getLogger(__name__)

# The provider says "this model cannot do that / does not exist / is not allowed": a definite no.
_DEFINITE_NO = (
    openai.BadRequestError,
    openai.NotFoundError,
    openai.UnprocessableEntityError,
    openai.PermissionDeniedError,
)


class ModelProviderError(Exception):
    """The LLM provider could not be reached or refused the request."""


class ModelNotAvailableError(Exception):
    """The requested model is not in the provider's (allowed, chat-capable) list."""


@dataclass(frozen=True)
class ModelInfo:
    id: str
    owned_by: str | None = None


class ModelCatalog:
    """The models the assistant can use: those the OpenAI-compatible provider lists AND that really answer a
    chat completion (embedding, audio, image... models are filtered out by trying them). Cached."""

    def __init__(self, settings: LlmSettings | None = None, client: AsyncOpenAI | None = None) -> None:
        self._settings = settings or LlmSettings()
        self._client = client
        self._cache: tuple[float, list[ModelInfo]] | None = None
        # Single flight: concurrent requests on a cold cache wait for one probe round instead of starting many.
        self._lock = asyncio.Lock()

    async def resolve_default(self) -> str:
        """The model to use when none is chosen: the first chat-capable model the provider offers ("" if none or
        if the provider cannot be asked). There is no configured default to get wrong."""
        try:
            models = await self.list_models()
        except ModelProviderError:
            return ""
        return models[0].id if models else ""

    def _openai(self) -> AsyncOpenAI:
        if self._client is None:
            if not self._settings.OPENAI_API_KEY:
                raise ModelProviderError("OPENAI_API_KEY is not set")
            self._client = AsyncOpenAI(
                api_key=self._settings.OPENAI_API_KEY, base_url=self._settings.OPENAI_BASE_URL, max_retries=0
            )
        return self._client

    def _fresh(self) -> list[ModelInfo] | None:
        return self._cache[1] if self._cache and time.monotonic() < self._cache[0] else None

    async def list_models(self) -> list[ModelInfo]:
        if (cached := self._fresh()) is not None:
            return cached
        async with self._lock:
            if (cached := self._fresh()) is not None:  # filled while we waited for the lock
                return cached
            return await self._refresh()

    async def _refresh(self) -> list[ModelInfo]:
        try:
            page = await self._openai().models.list()
        except OpenAIError as error:
            raise ModelProviderError(f"Model provider error: {error}") from error

        allowed = self._settings.allowed_models
        candidates = sorted(
            (ModelInfo(id=m.id, owned_by=m.owned_by) for m in page.data if not allowed or m.id in allowed),
            key=lambda model: model.id,
        )
        semaphore = asyncio.Semaphore(self._settings.LLM_MODELS_PROBE_CONCURRENCY)

        async def probe(model: ModelInfo) -> bool | None:
            async with semaphore:
                return await self._supports_chat(model.id)

        verdicts = await asyncio.gather(*(probe(m) for m in candidates))
        models = [m for m, ok in zip(candidates, verdicts, strict=True) if ok]
        # Any inconclusive probe (None) makes this result provisional: ask again soon instead of for an hour.
        ttl = (
            self._settings.LLM_MODELS_RETRY_SECONDS
            if any(ok is None for ok in verdicts)
            else self._settings.LLM_MODELS_CACHE_SECONDS
        )
        self._cache = (time.monotonic() + ttl, models)
        logger.info("Model catalog: %d/%d models support chat completions", len(models), len(candidates))
        return models

    async def _supports_chat(self, model_id: str) -> bool | None:
        """True if the model answers a chat completion, False if the provider says it cannot, None if unknown
        (rate limit, timeout, server error: no verdict)."""
        try:
            await asyncio.wait_for(
                self._openai().chat.completions.create(
                    model=model_id,
                    messages=[{"role": "user", "content": "ping"}],
                    # Newer models reject max_tokens in favour of max_completion_tokens.
                    max_completion_tokens=16,
                ),
                timeout=self._settings.LLM_MODELS_PROBE_TIMEOUT_SECONDS,
            )
        except _DEFINITE_NO as error:
            logger.info("Model %s is not usable for chat: %s", model_id, error)
            return False
        except (OpenAIError, TimeoutError) as error:
            logger.warning("Could not test model %s: %s", model_id, error)
            return None
        return True

    async def ensure_available(self, model_id: str) -> None:
        """Raises ModelNotAvailableError unless `model_id` is one of the chat-capable models."""
        if model_id not in {model.id for model in await self.list_models()}:
            raise ModelNotAvailableError(f"Model '{model_id}' is not available")
