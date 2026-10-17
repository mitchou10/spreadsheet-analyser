import os

from langchain_openai import ChatOpenAI

DEFAULT_MODEL = "gpt-4o"


def build_llm(model: str | None = None) -> ChatOpenAI:
    """Chat model for a run, through the OpenAI SDK (any OpenAI-compatible endpoint via OPENAI_BASE_URL).

    `model` is the one the user picked (from the backend's GET /models); LLM_DEFAULT_MODEL is the fallback.
    Needs OPENAI_API_KEY."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set: the assistant cannot answer")
    return ChatOpenAI(
        model=model or os.environ.get("LLM_DEFAULT_MODEL", DEFAULT_MODEL),
        api_key=api_key,
        base_url=os.environ.get("OPENAI_BASE_URL") or None,
    )
