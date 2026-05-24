"""
End-to-end demo of the Safe Agentic Deploy RAG feedback loop.

Shows the full cycle in one terminal run:
  1. Seed the RAG store with past failures (skips if already seeded)
  2. Simulate receiving a Jira ticket
  3. Retrieve similar past failures from ChromaDB
  4. Build the enriched OpenHands prompt
  5. Print the docker run command (--dry-run stops here by default)
  6. Optionally fire OpenHands for real (requires Docker + ANTHROPIC_API_KEY)

Usage:
    python demo/run_demo.py               # dry run — shows enriched prompt
    python demo/run_demo.py --fire        # actually runs OpenHands
    python demo/run_demo.py --bug BUG-002 # demo with multi-repo ticket
"""
from __future__ import annotations
import sys
import os
import textwrap
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# ── Ticket definitions ────────────────────────────────────────────────────────

TICKETS = {
    "BUG-001": {
        "ticket_id":    "BUG-003",       # new ticket, similar to past BUG-001 failures
        "ticket_title": "500 crash when product has no reviews — /product/5",
        "ticket_body":  textwrap.dedent("""\
            ## Summary
            Visiting /product/5 (new Webcam HD product, no reviews yet) returns a
            500 Internal Server Error. Same symptom as BUG-001 but on a newly added product.

            ## Steps to Reproduce
            1. Add a new product with an empty reviews list via admin
            2. Visit /product/5
            3. Observe 500 error

            ## Expected
            Page loads. Shows "No reviews yet."

            ## Actual
            ZeroDivisionError: division by zero
              File "app.py", line 55, in product_detail
                avg_rating = sum(product["reviews"]) / len(product["reviews"])

            ## Acceptance Criteria
            - GET /product/5 returns HTTP 200
            - Shows "No reviews yet" when reviews list is empty
            - All tests in tests/test_app.py pass
        """),
        "repo_url": "https://github.com/your-org/test-webapp",
    },
    "BUG-002": {
        "ticket_id":    "BUG-004",
        "ticket_title": "All prices show $0.00 after latest API deployment",
        "ticket_body":  textwrap.dedent("""\
            ## Summary
            After today's api-service deployment, all discounted product prices
            show $0.00 on the TechStore homepage. The API response changed its
            field naming again.

            ## Steps to Reproduce
            1. Open http://localhost:5000
            2. All products with a discount show $0.00

            ## Root Cause (suspected)
            api-service response field was renamed. Frontend reads the wrong key.
            Affects two repos: api-service + test-webapp.

            ## Acceptance Criteria
            - All discounted products show correct prices
            - Integration tests pass
            - Both repos updated and PRs opened
        """),
        "repo_url": "https://github.com/your-org/api-service",
    },
}

# ── Helpers ───────────────────────────────────────────────────────────────────

RESET  = "\033[0m"
BOLD   = "\033[1m"
CYAN   = "\033[36m"
GREEN  = "\033[32m"
YELLOW = "\033[33m"
BLUE   = "\033[34m"
DIM    = "\033[2m"


def banner(text: str, color: str = CYAN) -> None:
    width = 70
    print(f"\n{color}{BOLD}{'─' * width}{RESET}")
    print(f"{color}{BOLD}  {text}{RESET}")
    print(f"{color}{BOLD}{'─' * width}{RESET}")


def step(n: int, text: str) -> None:
    print(f"\n{BOLD}{BLUE}[Step {n}]{RESET} {text}")
    time.sleep(0.3)


def ok(text: str) -> None:
    print(f"  {GREEN}✓{RESET}  {text}")


def info(text: str) -> None:
    print(f"  {DIM}{text}{RESET}")


# ── Main demo ─────────────────────────────────────────────────────────────────

def run_demo(bug_key: str = "BUG-001", fire: bool = False) -> None:
    ticket = TICKETS[bug_key]

    banner("Safe Agentic Deploy — RAG Feedback Loop Demo")
    print(f"  Ticket : {ticket['ticket_id']} — {ticket['ticket_title']}")
    print(f"  Repo   : {ticket['repo_url']}")
    print(f"  Mode   : {'LIVE (will run OpenHands)' if fire else 'DRY RUN (shows enriched prompt)'}")

    # ── Step 1: Seed ──────────────────────────────────────────────────────────
    step(1, "Seeding RAG store with past failure history")
    from demo.seed_failures import seed
    count = seed()
    ok(f"RAG store has {count} failure document(s)")

    # ── Step 2: Simulate Jira trigger ─────────────────────────────────────────
    step(2, f"Jira webhook received — ticket {ticket['ticket_id']} labelled 'openhands'")
    info(f"Title : {ticket['ticket_title']}")
    info(f"Body  : {ticket['ticket_body'].splitlines()[0]}...")

    # ── Step 3: Retrieve similar failures ────────────────────────────────────
    step(3, "Querying RAG store for similar past failures")
    from feedback.retriever import retrieve_similar_failures, format_failures_for_prompt
    failures = retrieve_similar_failures(
        ticket_title = ticket["ticket_title"],
        ticket_body  = ticket["ticket_body"],
        repo         = ticket["repo_url"],
        n            = 3,
        min_similarity = 0.4,   # slightly lower for demo visibility
    )

    if failures:
        ok(f"Found {len(failures)} similar past failure(s):")
        for f in failures:
            print(f"     {YELLOW}•{RESET} [{f['similarity']:.0%} match] "
                  f"{f['ticket_id']} — {f['ticket_title'][:60]}")
            print(f"       {DIM}Root cause: {f['root_cause'][:100]}...{RESET}")
    else:
        print(f"  {YELLOW}⚠{RESET}  No similar failures found (store may need more data)")

    # ── Step 4: Build enriched prompt ────────────────────────────────────────
    step(4, "Building enriched OpenHands task prompt")
    from feedback.injector import build_enriched_task, build_enriched_openhands_command
    enriched_task = build_enriched_task(
        ticket_id    = ticket["ticket_id"],
        ticket_title = ticket["ticket_title"],
        ticket_body  = ticket["ticket_body"],
        repo         = ticket["repo_url"],
    )

    banner("Enriched Task Prompt (injected into OpenHands)", color=YELLOW)
    for line in enriched_task.splitlines():
        print(f"  {line}")

    # ── Step 5: Show docker command ───────────────────────────────────────────
    step(5, "OpenHands docker run command")
    cmd = build_enriched_openhands_command(
        ticket_id    = ticket["ticket_id"],
        ticket_title = ticket["ticket_title"],
        ticket_body  = ticket["ticket_body"],
        repo_url     = ticket["repo_url"],
    )
    banner("Generated docker run command", color=DIM)
    for line in cmd.splitlines():
        print(f"  {line}")

    # ── Step 6: Fire (optional) ───────────────────────────────────────────────
    if not fire:
        banner("DRY RUN COMPLETE — pass --fire to actually run OpenHands", color=GREEN)
        print(f"\n  Next steps:")
        print(f"    1.  docker compose up --build sandbox")
        print(f"    2.  python demo/run_demo.py --fire")
        print(f"    3.  If it fails: the failure is auto-captured → RAG store grows")
        print(f"    4.  Re-run — next attempt will see what went wrong last time\n")
        return

    # ── Live fire ─────────────────────────────────────────────────────────────
    step(6, "Firing OpenHands agent (live)")
    from webhook.runner import run_openhands_task
    result = run_openhands_task(
        ticket_id    = ticket["ticket_id"],
        ticket_title = ticket["ticket_title"],
        ticket_body  = ticket["ticket_body"],
        repo_url     = ticket["repo_url"],
        enriched_task= enriched_task,
    )

    if result["success"]:
        banner("Agent SUCCESS — PR opened, tests passed", color=GREEN)
        ok(f"PR: {result.get('pr_url', '(url in agent logs)')}")
    else:
        banner("Agent FAILED — failure captured to RAG store", color=YELLOW)
        info(f"Event ID : {result.get('event_id', 'n/a')}")
        info(f"Root cause: {result.get('root_cause', 'see feedback/store/raw/')}")
        print(f"\n  {YELLOW}The failure has been added to the RAG store.{RESET}")
        print(f"  Run the demo again — the next attempt will see this failure.\n")


if __name__ == "__main__":
    bug_key = "BUG-001"
    fire    = False

    for arg in sys.argv[1:]:
        if arg == "--fire":
            fire = True
        elif arg.startswith("--bug"):
            parts = arg.split()
            bug_key = parts[1] if len(parts) > 1 else sys.argv[sys.argv.index(arg) + 1]

    # Handle --bug BUG-002 (separate token)
    if "--bug" in sys.argv:
        idx = sys.argv.index("--bug")
        if idx + 1 < len(sys.argv):
            bug_key = sys.argv[idx + 1]

    if bug_key not in TICKETS:
        print(f"Unknown bug key '{bug_key}'. Choose from: {list(TICKETS.keys())}")
        sys.exit(1)

    run_demo(bug_key=bug_key, fire=fire)
