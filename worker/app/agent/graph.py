import logging
from typing import TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from app.agent.prompts import ANSWER_SYSTEM, PLAN_SYSTEM, SCOPE_NOTE
from app.backend_client import BackendClient

logger = logging.getLogger(__name__)

# Keeps the prompt bounded on very long conversations; the most recent messages matter most.
MAX_HISTORY_MESSAGES = 40


class AgentState(TypedDict, total=False):
    conversation_id: str  # the only input
    history: list[dict]  # user/assistant messages with text, oldest first
    plan: str
    answer: str


def _text(message: BaseMessage) -> str:
    content = message.content
    if isinstance(content, str):
        return content
    # Content blocks (e.g. Anthropic): keep the text ones.
    return "".join(
        block.get("text", "") for block in content if isinstance(block, dict) and block.get("type") == "text"
    )


def _to_chat(history: list[dict]) -> list[BaseMessage]:
    return [(HumanMessage if m["role"] == "user" else AIMessage)(content=m["content"]) for m in history]


def _scope_note(last: dict) -> list[BaseMessage]:
    collection_ids, file_ids = last.get("collection_ids", []), last.get("file_ids", [])
    if not collection_ids and not file_ids:
        return []
    return [
        SystemMessage(
            SCOPE_NOTE.format(
                collections=len(collection_ids),
                files=len(file_ids),
                collection_ids=", ".join(collection_ids) or "-",
                file_ids=", ".join(file_ids) or "-",
            )
        )
    ]


def build_graph(llm, client: BackendClient):
    """START -> load_history -> plan -> answer -> END.

    Input: {"conversation_id": ...}. The graph reads the conversation itself, drafts a plan for the last
    user message, then answers it following that plan. `llm` only needs `.invoke(list[BaseMessage])`."""

    def load_history(state: AgentState) -> AgentState:
        messages = client.messages(state["conversation_id"])
        history = [m for m in messages if m["role"] in ("user", "assistant") and m["content"]]
        history = history[-MAX_HISTORY_MESSAGES:]
        if not history or history[-1]["role"] != "user":
            raise ValueError("The conversation does not end with a user message: nothing to answer")
        return {"history": history}

    def plan(state: AgentState) -> AgentState:
        history = state["history"]
        response = llm.invoke([SystemMessage(PLAN_SYSTEM), *_to_chat(history), *_scope_note(history[-1])])
        plan_text = _text(response).strip()
        logger.info("Plan for conversation %s:\n%s", state["conversation_id"], plan_text)
        return {"plan": plan_text}

    def answer(state: AgentState) -> AgentState:
        history = state["history"]
        system = SystemMessage(ANSWER_SYSTEM.format(plan=state["plan"] or "(aucun plan)"))
        response = llm.invoke([system, *_to_chat(history), *_scope_note(history[-1])])
        text = _text(response).strip()
        if not text:
            raise ValueError("The model returned an empty answer")
        return {"answer": text}

    graph = StateGraph(AgentState)
    graph.add_node("load_history", load_history)
    graph.add_node("plan", plan)
    graph.add_node("answer", answer)
    graph.add_edge(START, "load_history")
    graph.add_edge("load_history", "plan")
    graph.add_edge("plan", "answer")
    graph.add_edge("answer", END)
    return graph.compile()
