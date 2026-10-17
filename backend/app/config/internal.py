from pydantic_settings import BaseSettings, SettingsConfigDict


class InternalSettings(BaseSettings):
    # Shared secret the workers present as `Authorization: Bearer <token>` on /api/internal/*.
    # Empty disables those routes.
    INTERNAL_API_TOKEN: str = ""
    # Celery task the backend enqueues for each run (implemented in the worker service).
    RUN_TASK_NAME: str = "worker.run_agent"
    # Queue consumed by the agent worker (other workers, e.g. spreadsheet analysis, use their own queue).
    RUN_QUEUE: str = "agent"

    model_config = SettingsConfigDict(case_sensitive=True, env_file=(".env", ".env.local"), extra="ignore")
