from pydantic_settings import BaseSettings, SettingsConfigDict


class EphemeralSettings(BaseSettings):
    # How long an ephemeral analysis (its files, results and runs) lives when the caller does not say.
    EPHEMERAL_DEFAULT_TTL_HOURS: int = 24
    EPHEMERAL_MAX_TTL_HOURS: int = 24 * 30
    # Files per ephemeral analysis.
    EPHEMERAL_MAX_FILES: int = 20
    # The backend looks for expired analyses this often (0 = never: call POST /api/internal/ephemeral/purge instead).
    EPHEMERAL_PURGE_INTERVAL_SECONDS: int = 600

    model_config = SettingsConfigDict(case_sensitive=True, env_file=(".env", ".env.local"), extra="ignore")
