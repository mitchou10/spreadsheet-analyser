from pydantic_settings import BaseSettings, SettingsConfigDict


class S3Settings(BaseSettings):
    # AWS_* naming so the settings are portable to real S3; locally they point at RustFS.
    AWS_ACCESS_KEY_ID: str = "rustfsadmin"
    AWS_SECRET_ACCESS_KEY: str = "rustfsadmin"
    AWS_REGION: str = "us-east-1"
    # Leave unset for real AWS S3; set to the RustFS URL (e.g. http://rustfs:9000) otherwise.
    AWS_ENDPOINT_URL_S3: str | None = "http://localhost:9000"
    AWS_S3_BUCKET: str = "spreadsheet-analyser"

    model_config = SettingsConfigDict(case_sensitive=True, env_file=(".env", ".env.local"), extra="ignore")
