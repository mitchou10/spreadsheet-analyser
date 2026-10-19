from pydantic_settings import BaseSettings, SettingsConfigDict


class AnalysisSettings(BaseSettings):
    # A file whose content was already analysed (same sha256 and extension, whoever uploaded it) reuses that result
    # instead of going through the analysis worker again.
    ANALYSIS_REUSE: bool = True
    # Stamped on every analysis, and only analyses with the same stamp are reused. Change it together with any change of
    # what the analysis worker produces (its profiling, its tables, SCHEMA_VERSION): results made by the old code
    # are then no longer reused.
    ANALYSIS_REUSE_VERSION: str = "1"

    model_config = SettingsConfigDict(case_sensitive=True, env_file=(".env", ".env.local"), extra="ignore")
