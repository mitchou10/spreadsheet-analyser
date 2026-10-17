import logging
import operator
from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END, START, StateGraph

from app.agent.account import Account
from app.agent.catalog import Catalog
from app.agent.prompts import ANSWER_SYSTEM, FORCE_ANSWER, PLAN_SYSTEM, SCOPE_NOTE
from app.agent.tools import build_tools
from app.backend_client import BackendClient

logger = logging.getLogger(__name__)

# Keeps the prompt bounded on very long conversations; the most recent messages matter most.
MAX_HISTORY_MESSAGES = 40
# Tool calls the agent may chain for one answer before it is told to conclude.
MAX_TOOL_STEPS = 8
# Each tool output kept in the trace shown to the user is cut here (the model itself still sees all of it).
MAX_TRACE_OUTPUT_CHARS = 4000


class AgentState(TypedDict, total=False):
    conversation_id: str  # the only input
    history: list[dict]  # user/assistant messages with text, oldest first
    overview: str  # one line per file in scope
    plan: str
    # The tool-calling exchange (assistant tool calls + tool results) of the answer in progress.
    scratch: Annotated[list[BaseMessage], operator.add]
    steps: int
    answer: str
    # What the user can look at afterwards: the files in scope and every tool call with its (cut) output.
    files: list[dict]
    trace_steps: Annotated[list[dict], operator.add]


def _text(message: BaseMessage) -> str:
    content = message.content
    if isinstance(content, str):
        return content
    # Content blocks (some providers return a list): keep the text ones.
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


def build_graph(llm, client: BackendClient, storage, run_id: str, user_email: str | None = None):
    """START -> load_history -> load_catalog -> plan -> agent <-> tools -> END.

    Input: {"conversation_id": ...}. The graph reads the conversation and the analyses of the files in scope
    itself, drafts a plan for the last user message, then answers it, searching the analyses with tools as
    needed. `llm` needs `.invoke(messages)` and `.bind_tools(tools)`."""
    holder: dict[str, Catalog] = {}

    def get_account() -> Account:
        # Asked to the backend the first time the agent needs it (most questions are about the files' content).
        if "account" not in holder_account:
            holder_account["account"] = Account(client.account(run_id))
        return holder_account["account"]

    holder_account: dict[str, Account] = {}
    tools = build_tools(lambda: holder["catalog"], get_account)
    tools_by_name = {tool.name: tool for tool in tools}
    llm_with_tools = llm.bind_tools(tools)

    def load_history(state: AgentState) -> AgentState:
        messages = client.messages(state["conversation_id"])
        history = [m for m in messages if m["role"] in ("user", "assistant") and m["content"]]
        history = history[-MAX_HISTORY_MESSAGES:]
        if not history or history[-1]["role"] != "user":
            raise ValueError("The conversation does not end with a user message: nothing to answer")
        return {"history": history}

    def load_catalog(state: AgentState) -> AgentState:
        scope = client.run_files(run_id)
        holder["catalog"] = Catalog.load(scope, storage, user_email=user_email)
        logger.info("Catalog: %d files in scope", len(holder["catalog"].entries))
        files = [
            {"file_id": f["file_id"], "file_name": f["file_name"], "collection_name": f.get("collection_name") or ""}
            for f in scope
        ]
        return {"overview": holder["catalog"].overview(), "files": files}

    def plan(state: AgentState) -> AgentState:
        history = state["history"]
        system = SystemMessage(PLAN_SYSTEM.format(overview=state["overview"]))
        response = llm.invoke([system, *_to_chat(history), *_scope_note(history[-1])])
        plan_text = _text(response).strip()
        logger.info("Plan for conversation %s:\n%s", state["conversation_id"], plan_text)
        return {"plan": plan_text}

    def agent(state: AgentState) -> AgentState:
        history, scratch, steps = state["history"], state.get("scratch", []), state.get("steps", 0)
        system = SystemMessage(ANSWER_SYSTEM.format(plan=state["plan"] or "(aucun plan)", overview=state["overview"]))
        messages = [system, *_to_chat(history), *_scope_note(history[-1]), *scratch]
        if steps >= MAX_TOOL_STEPS:
            response = llm.invoke([*messages, SystemMessage(FORCE_ANSWER)])  # no tools: it must conclude
        else:
            response = llm_with_tools.invoke(messages)
            if getattr(response, "tool_calls", None):
                return {"scratch": [response], "steps": steps + 1}
        text = _text(response).strip()
        if not text:
            raise ValueError("The model returned an empty answer")
        return {"answer": text}

    def run_tools(state: AgentState) -> AgentState:
        results, log = [], []
        for call in state["scratch"][-1].tool_calls:
            tool = tools_by_name.get(call["name"])
            if tool is None:
                output = f"Erreur : outil inconnu '{call['name']}'. Outils : {', '.join(tools_by_name)}."
            else:
                try:
                    output = tool.invoke(call["args"])
                except Exception as error:  # bad arguments from the model: let it correct itself
                    output = f"Erreur : arguments invalides ({type(error).__name__}: {error})"
            logger.info("Tool %s(%s) -> %d chars", call["name"], call["args"], len(output))
            results.append(ToolMessage(content=output, tool_call_id=call["id"], name=call["name"]))
            shown = (
                output if len(output) <= MAX_TRACE_OUTPUT_CHARS else output[:MAX_TRACE_OUTPUT_CHARS] + "\n… (tronqué)"
            )
            log.append({"tool": call["name"], "arguments": call["args"], "output": shown})
        return {"scratch": results, "trace_steps": log}

    graph = StateGraph(AgentState)
    graph.add_node("load_history", load_history)
    graph.add_node("load_catalog", load_catalog)
    graph.add_node("plan", plan)
    graph.add_node("agent", agent)
    graph.add_node("tools", run_tools)
    graph.add_edge(START, "load_history")
    graph.add_edge("load_history", "load_catalog")
    graph.add_edge("load_catalog", "plan")
    graph.add_edge("plan", "agent")
    graph.add_conditional_edges("agent", lambda state: END if "answer" in state else "tools", ["tools", END])
    graph.add_edge("tools", "agent")
    return graph.compile()
