"""
Failure event capture for the RAG feedback loop.

Called whenever a fix attempt fails — either at the test stage or at
the production deploy stage (rollback). Normalises the event into a
document and stores it in the RAG store so future agents can learn from it.

Two trigger points:
  1. Test failure  — OpenHands opened a PR, but tests failed in CI
  2. Rollback      — PR merged, deploy happened, but error rate spiked → auto-rolled back

Usage:
  from feedback.capture import capture_failure
  capture_failure(event_type="test_failure", ...)
  capture_failure(event_type="rollback", ...)
"""
from __future__ import annotations
import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path

from feedback.rag_store import RAGStore


@dataclass
class FailureEvent:
    event_id:      str          # unique id, e.g. "BUG-001_2026-05-13T10:30Z"
    event_type:    str          # "test_failure" | "rollback"
    ticket_id:     str          # Jira ticket, e.g. "BUG-001"
    ticket_title:  str          # short description of the bug
    ticket_body:   str          # full Jira ticket text
    repo:          str          # which repo was changed
    diff:          str          # the git diff the agent produced
    error_output:  str          # test failure log or rollback error
    root_cause:    str          # human or Claude-inferred explanation of why it failed
    timestamp:     str          # ISO-8601


def capture_failure(
    event_type:   str,
    ticket_id:    str,
    ticket_title: str,
    ticket_body:  str,
    repo:         str,
    diff:         str,
    error_output: str,
    root_cause:   str = "",
    store_dir:    str = "feedback/store",
) -> FailureEvent:
    """
    Capture a failed fix attempt and store it in the RAG vector database.

    If root_cause is not provided, Claude infers it from the diff + error output.
    """
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    event = FailureEvent(
        event_id     = f"{ticket_id}_{ts}",
        event_type   = event_type,
        ticket_id    = ticket_id,
        ticket_title = ticket_title,
        ticket_body  = ticket_body,
        repo         = repo,
        diff         = diff,
        error_output = error_output,
        root_cause   = root_cause or _infer_root_cause(diff, error_output),
        timestamp    = ts,
    )

    # Persist raw JSON for auditability
    raw_dir = Path(store_dir) / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    (raw_dir / f"{event.event_id}.json").write_text(json.dumps(asdict(event), indent=2))

    # Store in vector DB
    store = RAGStore(store_dir=store_dir)
    store.add(event)

    print(f"[feedback] Captured {event_type} for {ticket_id} → stored in RAG.")
    return event


def _infer_root_cause(diff: str, error_output: str) -> str:
    """Ask Claude to infer why the fix failed from the diff + error log."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return "Root cause inference skipped (no ANTHROPIC_API_KEY)."
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=256,
            messages=[{"role": "user", "content": f"""A code fix failed. Explain in 2-3 sentences why it failed and what should be done differently next time.

Git diff of the failed fix:
{diff[:2000]}

Error output:
{error_output[:2000]}

Respond with ONLY the root cause explanation."""}],
        )
        return response.content[0].text.strip()
    except Exception as e:
        return f"Root cause inference failed: {e}"
