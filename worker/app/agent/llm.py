import os

from langchain_anthropic import ChatAnthropic

DEFAULT_MODEL = "claude-sonnet-5-5"


def build_llm() -> ChatAnthropic:
    """Chat model used by the agent. Needs ANTHROPIC_API_KEY; LLM_MODEL overrides the default model."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError("ANTHROPIC_API_KEY is not set: the assistant cannot answer")
    return ChatAnthropic(model=os.environ.get("LLM_MODEL", DEFAULT_MODEL), max_tokens=4096)
