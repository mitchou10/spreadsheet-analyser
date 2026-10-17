import os

from langchain_openai import ChatOpenAI


def build_llm(model: str | None = None) -> ChatOpenAI:
    """Chat model for a run, through the OpenAI SDK (any OpenAI-compatible endpoint via OPENAI_BASE_URL).

    `model` is the one the backend chose for the run (the user's pick, else the provider's first model).
    Needs OPENAI_API_KEY."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set: the assistant cannot answer")
    if not model:
        raise RuntimeError("No model to answer with: pick one, or the provider offers none")
    return ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url=os.environ.get("OPENAI_BASE_URL") or None,
    )
