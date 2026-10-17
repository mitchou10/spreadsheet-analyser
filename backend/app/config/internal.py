from pydantic_settings import BaseSettings, SettingsConfigDict


class InternalSettings(BaseSettings):
    # Shared secret the worker presents (X-Internal-Token) on /api/internal/*. Empty disables those routes.
    INTERNAL_API_TOKEN: str = ""
    # Celery task the backend enqueues for each run (implemented in the worker service).
    RUN_TASK_NAME: str = "worker.run_agent"

    model_config = SettingsConfigDict(case_sensitive=True, env_file=(".env", ".env.local"), extra="ignore")
