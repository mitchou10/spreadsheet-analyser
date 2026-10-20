from pydantic_settings import BaseSettings, SettingsConfigDict


class McpSettings(BaseSettings):
    # The MCP server is mounted under /mcp (turn it off with false).
    MCP_ENABLED: bool = True
    # `analyze_files` waits this long for the pre-analysis of the files before starting the question; past that it
    # returns the analysis and the caller asks later with `ask`.
    MCP_PREANALYSIS_WAIT_SECONDS: int = 30
    # Files travel in the call as base64: their total size once decoded (bigger files: use the REST route).
    MCP_MAX_UPLOAD_BYTES: int = 10 * 1024 * 1024
    # A chart is returned in the answer when its image is at most this big (otherwise only its URL).
    MCP_MAX_CHART_BYTES: int = 2 * 1024 * 1024

    # `get_analysis(detail="full")` returns the whole analysis of a file when it is at most this big (otherwise its
    # overview, with a note): the statistics of a wide spreadsheet can be large.
    MCP_MAX_PROFILE_BYTES: int = 1024 * 1024

    model_config = SettingsConfigDict(case_sensitive=True, env_file=(".env", ".env.local"), extra="ignore")
