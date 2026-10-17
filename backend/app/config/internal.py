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
    # SQL queries on the analysed files: same worker image as the analysis, own queue and own processes, so that a
    # person waiting for an answer never queues behind the analysis of a large file.
    QUERY_TASK_NAME: str = "analysis.query"
    QUERY_QUEUE: str = "query"
    # Charts are drawn by the same worker (the query worker), from the result of a query.
    CHART_TASK_NAME: str = "analysis.chart"
    # Everything about the saved search indexes (of the collections and of the users) is the index worker's job.
    INDEX_QUEUE: str = "index"
    INDEX_FILE_TASK_NAME: str = "index.file_analysed"
    INDEX_FORGET_TASK_NAME: str = "index.forget_file"
    INDEX_REBUILD_TASK_NAME: str = "index.rebuild_collection"
    INDEX_USER_TASK_NAME: str = "index.rebuild_user"

    model_config = SettingsConfigDict(case_sensitive=True, env_file=(".env", ".env.local"), extra="ignore")
