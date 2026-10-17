from pydantic_settings import BaseSettings, SettingsConfigDict


class LlmSettings(BaseSettings):
    # Any OpenAI-compatible endpoint works (OpenAI, a LiteLLM/vLLM/Ollama gateway...): leave the base URL
    # unset for api.openai.com. The worker reads the same variables to call the model.
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str | None = None
    # Model used when a message does not pick one.
    LLM_DEFAULT_MODEL: str = "gpt-4o"
    # Comma-separated ids to expose (providers also list embedding/audio/... models). Empty = everything listed.
    LLM_ALLOWED_MODELS: str = ""
    # Every listed model is probed with a tiny chat completion, and only the ones that answer are exposed.
    # The result is cached this long (a probe costs a few tokens per model).
    LLM_MODELS_CACHE_SECONDS: int = 3600
    # A probe that failed for a transient reason (rate limit, timeout, 5xx) is retried after this delay.
    LLM_MODELS_RETRY_SECONDS: int = 60
    # Probes run this many at a time, each giving up after LLM_MODELS_PROBE_TIMEOUT_SECONDS.
    LLM_MODELS_PROBE_CONCURRENCY: int = 8
    LLM_MODELS_PROBE_TIMEOUT_SECONDS: float = 20

    model_config = SettingsConfigDict(case_sensitive=True, env_file=(".env", ".env.local"), extra="ignore")

    @property
    def allowed_models(self) -> set[str]:
        return {model.strip() for model in self.LLM_ALLOWED_MODELS.split(",") if model.strip()}
