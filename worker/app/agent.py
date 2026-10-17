def generate_reply(context: dict) -> str:
    """Produces the assistant's answer for a run from its context (history + collection/file scope).

    Placeholder until the LLM agent is wired in: it only acknowledges the message, so the whole
    asynchronous pipeline (API -> queue -> worker -> reply) can be exercised end to end."""
    return (
        "L'agent IA n'est pas encore branché. Message bien reçu "
        f"({len(context['messages'])} message(s) dans la conversation, "
        f"{len(context['collection_ids'])} collection(s) et {len(context['file_ids'])} fichier(s) ciblés)."
    )
