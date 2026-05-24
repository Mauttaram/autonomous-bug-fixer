"""
Seeds the RAG store with realistic past failure events so the demo isn't cold.

Run once before the demo:
    python demo/seed_failures.py

After seeding, run the demo:
    python demo/run_demo.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from feedback.capture import capture_failure

STORE_DIR = "feedback/store"

PAST_FAILURES = [
    # ── Failure 1 ─────────────────────────────────────────────────────────────
    # Same class of bug as BUG-001 (division by zero), but the FIRST attempt
    # at a fix added a guard that still crashed when the list had exactly one item.
    {
        "event_type":   "test_failure",
        "ticket_id":    "BUG-001-attempt-1",
        "ticket_title": "ZeroDivisionError on product detail page (no reviews)",
        "ticket_body":  (
            "Viewing /product/3 (USB-C Hub, 0 reviews) throws ZeroDivisionError.\n"
            "avg_rating = sum(reviews) / len(reviews) crashes when reviews is empty."
        ),
        "repo":         "https://github.com/your-org/test-webapp",
        "diff": """\
--- a/app.py
+++ b/app.py
@@ -52,7 +52,7 @@
-    avg_rating = sum(product["reviews"]) / len(product["reviews"])
+    avg_rating = sum(product["reviews"]) / len(product["reviews"]) if len(product["reviews"]) > 1 else 0
""",
        "error_output": (
            "FAILED tests/test_app.py::test_product_detail_no_reviews\n"
            "AssertionError: Expected 'No reviews yet', got '0'\n"
            "FAILED tests/test_app.py::test_product_detail_single_review\n"
            "AssertionError: avg_rating should be 5.0, got 0"
        ),
        "root_cause": (
            "Guard used `> 1` instead of `> 0`, so a product with exactly one "
            "review showed 0.0 instead of that review's score. The correct check "
            "is `if product['reviews']` (truthy test), which handles both 0 and 1 "
            "elements. Template also needs `{% if avg_rating %}` not `{% if avg_rating > 0 %}`."
        ),
    },

    # ── Failure 2 ─────────────────────────────────────────────────────────────
    # Same class of bug as BUG-001, second attempt: guard was right but the
    # Jinja template was not updated to handle None — crashed at render time.
    {
        "event_type":   "test_failure",
        "ticket_id":    "BUG-001-attempt-2",
        "ticket_title": "ZeroDivisionError on product detail page (no reviews) — retry",
        "ticket_body":  (
            "Second fix attempt for /product/3 crash. Python guard added but "
            "template still tries to display avg_rating without None check."
        ),
        "repo":         "https://github.com/your-org/test-webapp",
        "diff": """\
--- a/app.py
+++ b/app.py
@@ -52,7 +52,7 @@
-    avg_rating = sum(product["reviews"]) / len(product["reviews"])
+    avg_rating = sum(product["reviews"]) / len(product["reviews"]) if product["reviews"] else None
--- a/templates/product.html
+++ b/templates/product.html
# (template NOT updated — avg_rating None check missing)
""",
        "error_output": (
            "FAILED tests/test_app.py::test_product_detail_no_reviews\n"
            "jinja2.exceptions.UndefinedError: 'None' has no attribute 'format'\n"
            "Error in template product.html line 24: {{ '%.1f' % avg_rating }}"
        ),
        "root_cause": (
            "Python fix was correct (avg_rating = None when no reviews) but the "
            "Jinja2 template at product.html:24 still rendered `{{ '%.1f' % avg_rating }}` "
            "without a None guard. Fix MUST update BOTH app.py AND the template: "
            "`{% if avg_rating is not none %}{{ avg_rating }}{% else %}No reviews yet{% endif %}`."
        ),
    },

    # ── Failure 3 ─────────────────────────────────────────────────────────────
    # Same class as BUG-002 (API contract break). First agent attempt only
    # fixed api-service but forgot test-webapp integration tests also run
    # against the live API — they failed because the sandbox wasn't restarted.
    {
        "event_type":   "test_failure",
        "ticket_id":    "BUG-002-attempt-1",
        "ticket_title": "Sale prices show $0.00 — API field renamed (multi-repo)",
        "ticket_body":  (
            "api-service renamed sale_price → final_price without updating test-webapp.\n"
            "Frontend reads .get('sale_price', 0.0) → gets 0.0 silently.\n"
            "Affects api-service + test-webapp repos."
        ),
        "repo":         "https://github.com/your-org/api-service",
        "diff": """\
--- a/api.py
+++ b/api.py
@@ -31,7 +31,7 @@
-    product["final_price"] = compute_sale_price(p["price"], p["discount"])
+    product["sale_price"]  = compute_sale_price(p["price"], p["discount"])
# test-webapp NOT touched — integration tests still fail
""",
        "error_output": (
            "FAILED integration-tests/test_integration.py::test_sale_price_displayed\n"
            "AssertionError: Frontend shows $0.00 for Laptop Pro 15\n"
            "Expected: $1169.99\n"
            "Note: api-service container was not restarted after patch — "
            "old binary still running in sandbox."
        ),
        "root_cause": (
            "Multi-repo fix requires restarting BOTH sandboxes after patching. "
            "api-service was patched but the running container was not rebuilt "
            "`docker-compose build api-sandbox && docker-compose up -d api-sandbox`. "
            "Integration tests hit the old running container. "
            "Always run `docker-compose up --build` after any api-service change."
        ),
    },
]


def seed(store_dir: str = STORE_DIR, force: bool = False) -> int:
    from feedback.rag_store import RAGStore
    store = RAGStore(store_dir=store_dir)
    if store.count() > 0 and not force:
        print(f"[seed] Store already has {store.count()} document(s). "
              f"Pass --force to re-seed.")
        return store.count()

    print(f"[seed] Seeding {len(PAST_FAILURES)} past failures...\n")
    for f in PAST_FAILURES:
        event = capture_failure(store_dir=store_dir, **f)
        print(f"  ✓  {event.event_id}")

    final = RAGStore(store_dir=store_dir).count()
    print(f"\n[seed] Done — {final} failure(s) in store.")
    return final


if __name__ == "__main__":
    force = "--force" in sys.argv
    seed(force=force)
