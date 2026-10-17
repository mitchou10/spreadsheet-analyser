import asyncio
from types import SimpleNamespace

import httpx
import openai
import pytest

from app.config import LlmSettings
from app.services.models import ModelCatalog, ModelNotAvailableError, ModelProviderError

REQUEST = httpx.Request("POST", "http://provider/v1/chat/completions")


def api_error(cls, status: int):
    return cls("nope", response=httpx.Response(status, request=REQUEST), body=None)


class FakeOpenAI:
    """The two calls the catalog makes: models.list() and chat.completions.create().

    `verdicts` maps a model id to None (works) or the exception its chat call raises."""

    def __init__(self, verdicts: dict[str, Exception | None], list_error: Exception | None = None) -> None:
        self.verdicts, self.list_error = verdicts, list_error
        self.list_calls = 0
        self.probes: list[dict] = []
        self.models = SimpleNamespace(list=self._list)
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    async def _list(self):
        self.list_calls += 1
        if self.list_error:
            raise self.list_error
        return SimpleNamespace(data=[SimpleNamespace(id=i, owned_by="acme") for i in self.verdicts])

    async def _create(self, **kwargs):
        self.probes.append(kwargs)
        await asyncio.sleep(0)
        if (error := self.verdicts[kwargs["model"]]) is not None:
            raise error
        return SimpleNamespace()


def settings(**overrides) -> LlmSettings:
    return LlmSettings(_env_file=None, **overrides)


async def test_only_models_that_complete_a_chat_are_returned_sorted() -> None:
    client = FakeOpenAI(
        {
            "gpt-b": None,
            "embed-x": api_error(openai.BadRequestError, 400),  # "not a chat model"
            "gpt-a": None,
            "whisper": api_error(openai.NotFoundError, 404),
            "private": api_error(openai.PermissionDeniedError, 403),
        }
    )

    models = await ModelCatalog(settings(), client).list_models()

    assert [(m.id, m.owned_by) for m in models] == [("gpt-a", "acme"), ("gpt-b", "acme")]
    assert len(client.probes) == 5  # every listed model was really tried
    assert client.probes[0]["messages"] == [{"role": "user", "content": "ping"}]
    assert client.probes[0]["max_completion_tokens"] == 16


async def test_allowlist_limits_what_is_probed() -> None:
    client = FakeOpenAI({"gpt-a": None, "gpt-b": None, "gpt-c": None})

    models = await ModelCatalog(settings(LLM_ALLOWED_MODELS=" gpt-a , gpt-c "), client).list_models()

    assert [m.id for m in models] == ["gpt-a", "gpt-c"]
    assert sorted(p["model"] for p in client.probes) == ["gpt-a", "gpt-c"]


async def test_result_is_cached_so_models_are_not_probed_again() -> None:
    client = FakeOpenAI({"gpt-a": None, "embed": api_error(openai.BadRequestError, 400)})
    catalog = ModelCatalog(settings(), client)

    await catalog.list_models()
    await catalog.list_models()
    await catalog.ensure_available("gpt-a")

    assert client.list_calls == 1 and len(client.probes) == 2


async def test_cache_expires() -> None:
    client = FakeOpenAI({"gpt-a": None})
    catalog = ModelCatalog(settings(LLM_MODELS_CACHE_SECONDS=0), client)

    await catalog.list_models()
    await catalog.list_models()

    assert client.list_calls == 2


async def test_concurrent_requests_share_a_single_probe_round() -> None:
    client = FakeOpenAI({"gpt-a": None, "gpt-b": None})
    catalog = ModelCatalog(settings(), client)

    results = await asyncio.gather(*(catalog.list_models() for _ in range(5)))

    assert all(len(r) == 2 for r in results)
    assert client.list_calls == 1 and len(client.probes) == 2


async def test_transient_failures_are_excluded_but_retried_soon_not_cached_for_an_hour() -> None:
    client = FakeOpenAI({"gpt-a": None, "busy": api_error(openai.RateLimitError, 429)})
    catalog = ModelCatalog(settings(LLM_MODELS_RETRY_SECONDS=0), client)

    assert [m.id for m in await catalog.list_models()] == ["gpt-a"]

    client.verdicts["busy"] = None  # the rate limit is over
    assert [m.id for m in await catalog.list_models()] == ["busy", "gpt-a"]


async def test_probe_timeout_is_inconclusive_not_a_no() -> None:
    client = FakeOpenAI({"slow": None, "gpt-a": None})
    original = client._create

    async def slow_for_one(**kwargs):
        if kwargs["model"] == "slow":
            await asyncio.sleep(1)
        return await original(**kwargs)

    client.chat.completions.create = slow_for_one
    catalog = ModelCatalog(settings(LLM_MODELS_PROBE_TIMEOUT_SECONDS=0.05, LLM_MODELS_RETRY_SECONDS=0), client)

    assert [m.id for m in await catalog.list_models()] == ["gpt-a"]
    assert catalog._cache is not None and catalog._cache[0] <= asyncio.get_running_loop().time() + 1  # short TTL


async def test_provider_errors_on_listing_become_model_provider_error() -> None:
    catalog = ModelCatalog(settings(), FakeOpenAI({}, list_error=openai.APIConnectionError(request=REQUEST)))

    with pytest.raises(ModelProviderError):
        await catalog.list_models()


async def test_missing_api_key_is_reported_without_calling_the_provider() -> None:
    with pytest.raises(ModelProviderError, match="OPENAI_API_KEY"):
        await ModelCatalog(settings()).list_models()


async def test_ensure_available_only_accepts_chat_capable_models() -> None:
    client = FakeOpenAI({"gpt-a": None, "embed": api_error(openai.BadRequestError, 400)})
    catalog = ModelCatalog(settings(), client)

    await catalog.ensure_available("gpt-a")
    for unknown in ("embed", "gpt-z"):
        with pytest.raises(ModelNotAvailableError):
            await catalog.ensure_available(unknown)


def test_default_model_comes_from_settings() -> None:
    assert ModelCatalog(settings(LLM_DEFAULT_MODEL="my-model")).default == "my-model"
