"""
Retrieves similar past failures from the RAG store for a new Jira ticket.

Query is built from the ticket title + body. Returns the top-N most
relevant past failures so the injector can include them in the agent prompt.
"""
from __future__ import annotations
from feedback.rag_store import RAGStore


def retrieve_similar_failures(
    ticket_title: str,
    ticket_body:  str,
    repo:         str = "",
    n:            int = 3,
    min_similarity: float = 0.5,
    store_dir:    str = "feedback/store",
) -> list[dict]:
    """
    Query the RAG store for failures similar to the incoming ticket.

    Returns a list of dicts (sorted by similarity desc), each containing:
      ticket_id, ticket_title, root_cause, diff_snippet,
      event_type, repo, similarity
    Only returns results above min_similarity threshold.
    """
    store = RAGStore(store_dir=store_dir)
    if store.count() == 0:
        return []

    query_text = f"{ticket_title}\n{ticket_body[:1000]}"
    if repo:
        query_text = f"Repo: {repo}\n{query_text}"

    results = store.query(query_text, n_results=n)
    return [r for r in results if r["similarity"] >= min_similarity]


def format_failures_for_prompt(failures: list[dict]) -> str:
    """
    Format retrieved failures into a block that can be injected
    directly into the OpenHands system prompt.
    """
    if not failures:
        return ""

    lines = ["## Past Similar Fix Failures — Learn From These\n"]
    for i, f in enumerate(failures, 1):
        lines.append(f"### Failure {i}  (similarity: {f['similarity']:.0%})")
        lines.append(f"- **Ticket:**    {f['ticket_id']} — {f['ticket_title']}")
        lines.append(f"- **Type:**      {f['event_type']}")
        lines.append(f"- **Repo:**      {f['repo']}")
        lines.append(f"- **Root cause:**\n  {f['root_cause']}")
        if f.get("diff_snippet"):
            lines.append(f"- **Failing diff (snippet):**\n```diff\n{f['diff_snippet']}\n```")
        lines.append("")

    lines.append("**Do NOT repeat these patterns. Use the root causes above to avoid the same mistakes.**\n")
    return "\n".join(lines)
