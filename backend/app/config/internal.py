from pydantic_settings import BaseSettings, SettingsConfigDict


class InternalSettings(BaseSettings):
    # Shared secret the workers present as `Authorization: Bearer <token>` on /api/internal/*.
    # Empty disables those routes.
    INTERNAL_API_TOKEN: str = ""
    # Celery task the backend enqueues for each run (implemented in the worker service).
    RUN_TASK_NAME: str = "worker.run_agent"
    # Queue consumed by the agent worker (other workers, e.g. spreadsheet analysis, use their own queue).
    RUN_QUEUE: str = "agent"
    # Spreadsheet analysis runs in its own worker (own queue, own memory limit).
    ANALYSIS_TASK_NAME: str = "analysis.run"
    ANALYSIS_QUEUE: str = "analysis"
    # Keeping the collections' saved search index up to date is the analysis worker's job too.
    INDEX_FORGET_TASK_NAME: str = "analysis.forget_file"
    INDEX_REBUILD_TASK_NAME: str = "analysis.rebuild_index"

    model_config = SettingsConfigDict(case_sensitive=True, env_file=(".env", ".env.local"), extra="ignore")
