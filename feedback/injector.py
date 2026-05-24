"""
Injects RAG failure context into the OpenHands agent task prompt.

This is the bridge between the RAG store and the agent.
Instead of modifying the LLM weights, we inject relevant failure history
directly into the prompt — giving the agent everything it needs to avoid
repeating past mistakes.

Flow:
  New Jira ticket
    → retrieve similar past failures (retriever.py)
    → format as structured context block
    → prepend to the agent's task description
    → OpenHands runs with enriched context
"""
from __future__ import annotations
from feedback.retriever import retrieve_similar_failures, format_failures_for_prompt


def build_enriched_task(
    ticket_id:    str,
    ticket_title: str,
    ticket_body:  str,
    repo:         str = "",
    n_failures:   int = 3,
    store_dir:    str = "feedback/store",
) -> str:
    """
    Build the full task string to pass to OpenHands.
    If similar past failures exist, they are prepended as context.

    Returns the enriched task string ready for:
      docker run ... openhands --task "$(python -c 'from feedback.injector import ...')"
    """
    failures = retrieve_similar_failures(
        ticket_title = ticket_title,
        ticket_body  = ticket_body,
        repo         = repo,
        n            = n_failures,
        store_dir    = store_dir,
    )

    failure_block = format_failures_for_prompt(failures)

    task = f"""# Fix Request: {ticket_id}

{failure_block}
## Ticket Description

**Title:** {ticket_title}

{ticket_body}

## Instructions
- Read the ticket and understand the bug.
- If past failure context is shown above, study it carefully before writing any code.
- Make minimal targeted changes. Do not refactor unrelated code.
- Run the test suite before submitting. All tests must pass.
- Open a pull request with a description referencing {ticket_id}.
"""

    if failures:
        print(f"[injector] Enriched prompt with {len(failures)} past failure(s) "
              f"(similarities: {[f['similarity'] for f in failures]})")
    else:
        print("[injector] No similar past failures found — clean prompt.")

    return task


def build_enriched_openhands_command(
    ticket_id:    str,
    ticket_title: str,
    ticket_body:  str,
    repo_url:     str,
    model:        str = "claude-sonnet-4-6",
    config_path:  str = "openhands-config.toml",
    store_dir:    str = "feedback/store",
) -> str:
    """
    Returns the full docker run command to trigger OpenHands
    with the RAG-enriched task prompt.
    """
    task = build_enriched_task(
        ticket_id    = ticket_id,
        ticket_title = ticket_title,
        ticket_body  = ticket_body,
        repo         = repo_url,
        store_dir    = store_dir,
    )

    # Escape single quotes in task for shell safety
    task_escaped = task.replace("'", "'\"'\"'")

    return f"""docker run --rm \\
  -v $(pwd):/app \\
  -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \\
  -e GITHUB_TOKEN=$GITHUB_TOKEN \\
  ghcr.io/all-hands-ai/openhands:latest \\
  --config /app/{config_path} \\
  --task '{task_escaped}'"""
