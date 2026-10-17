from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    DATABASE_URL: str = (
        "postgresql+asyncpg://spreadsheet_analyser:spreadsheet_analyser@localhost:5432/spreadsheet_analyser"
    )

    model_config = SettingsConfigDict(case_sensitive=True, env_file=(".env", ".env.local"), extra="ignore")
