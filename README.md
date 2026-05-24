# Safe Agentic Deploy — OSS4AI Hackathon

> **How do you safely let an AI agent fix a bug and ship it to production?**

This project demonstrates an end-to-end pipeline where an AI agent (OpenHands) reads a Jira bug ticket, reproduces the issue in a sandboxed environment, generates a fix, validates it, and promotes it to production — with a human gate at each critical step.

---

## The Problem

AI coding agents (OpenHands, SWE-agent, Devin) can now fix real bugs. But fixing and *safely shipping* are two different things. The missing layer is:

- **Sandbox first** — reproduce the bug in isolation before touching prod
- **Validate the fix** — automated tests + visual diff in sandbox
- **Human gate** — PR review before promotion
- **Safe deploy** — feature-flagged canary, not a full rollout
- **Auditability** — every fix traces back to a Jira ticket

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        TRIGGER                              │
│  Jira Ticket → label: "openhands" → webhook fires          │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                     SANDBOX ENVIRONMENT                     │
│                                                             │
│  OpenHands Agent                                            │
│  ├── Reads Jira ticket (title + description)               │
│  ├── Clones repo into Docker container                     │
│  ├── Browses running app → confirms bug is visible         │
│  ├── Writes fix                                             │
│  ├── Runs test suite → must pass                           │
│  └── Browses app again → confirms bug is gone              │
│                                                             │
│  Sandbox URL: http://sandbox.internal:5000                  │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                      HUMAN GATE                             │
│  Pull Request opened → links back to Jira ticket           │
│  Reviewer sees: bug screenshot | fix diff | test results   │
│  Approve → merge → deploy                                   │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                   PRODUCTION DEPLOY                         │
│  Feature-flagged canary (10% traffic)                       │
│  Auto-rollback if error rate spikes                         │
│  Jira ticket auto-closed on successful deploy               │
└─────────────────────────────────────────────────────────────┘
```

---

## Demo Web App — TechStore

A simple Flask e-commerce product catalog with **two real bugs** planted for the demo.

### Bug 1 — Wrong Sale Price (UI Bug, always visible)
The discount calculation shows the **discount amount** instead of the **sale price**.

```
Product: Laptop Pro 15  |  Price: $1299.99  |  10% off
Expected sale price: $1,169.99
Actual (buggy):       $130.00   ← shows the discount, not the price
```

### Bug 2 — Crash on Product Detail (500 Error)
When a product has no reviews, viewing its detail page throws a `ZeroDivisionError` and returns a 500 error — visible in the browser.

```
GET /product/3  →  ZeroDivisionError: division by zero  →  500 Internal Server Error
```

---

## Project Structure

```
safe-agentic-deploy/
├── README.md                           ← you are here
├── docker-compose.multi-repo.yml       ← multi-repo sandbox + prod
├── test-webapp/                        ← Repo B: Frontend (Flask)
│   ├── app.py                          ← contains Bug 1 + Bug 2 (single-repo)
│   │                                     calls api-service when API_SERVICE_URL set
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── docker-compose.yml              ← single-repo sandbox + prod
│   ├── templates/
│   │   ├── base.html
│   │   ├── index.html                  ← Bug 1 visible here (wrong sale prices)
│   │   ├── product.html                ← Bug 2 crashes here (no reviews)
│   │   └── 404.html
│   └── tests/
│       └── test_app.py                 ← 5 tests fail on buggy code
├── api-service/                        ← Repo A: Backend REST API (Flask)
│   ├── api.py                          ← Bug 3: renamed field breaks frontend
│   ├── requirements.txt
│   ├── Dockerfile
│   └── tests/
│       └── test_api.py                 ← 3 tests fail on buggy code
├── integration-tests/
│   └── test_integration.py             ← cross-service tests (catch contract bugs)
└── bugs/
    ├── BUG-001.md                      ← single-repo: 500 crash on empty reviews
    └── BUG-002.md                      ← multi-repo: API field rename breaks frontend
```

---

## Running the Demo

### 1. Start the sandbox (buggy version)
```bash
cd test-webapp
docker-compose up sandbox
```
Open http://localhost:5000 — you will see wrong sale prices (Bug 1).
Click on **USB-C Hub** — you will see a 500 crash (Bug 2).

### 2. Run the tests (they fail)
```bash
docker-compose run --rm sandbox pytest tests/ -v
```

### 3. Trigger OpenHands agent
Add the `openhands` label to [BUG-001](./bugs/BUG-001.md) in Jira, or run locally:
```bash
docker run --rm \
  -e GITHUB_TOKEN=$GITHUB_TOKEN \
  -e LLM_API_KEY=$ANTHROPIC_API_KEY \
  ghcr.io/all-hands-ai/openhands:latest \
  --config openhands-config.yaml
```

### 4. Verify fix in sandbox
```bash
docker-compose up sandbox   # rebuild with agent's patch
```
- http://localhost:5000 → sale prices now correct
- http://localhost:5000/product/3 → shows "No reviews yet" instead of crashing

### 5. Start production environment
```bash
docker-compose up prod      # runs on port 8080
```
Open http://localhost:8080 — production-equivalent environment, fully fixed.

---

## Tools Used

| Layer | Tool |
|---|---|
| AI Agent | [OpenHands](https://github.com/OpenHands/OpenHands) (open source) |
| Issue Tracking | Jira (via OpenHands native integration) |
| Sandbox | Docker (isolated, ephemeral) |
| Web App | Python / Flask |
| LLM Backend | Claude Sonnet (Anthropic) |
| Safe Deploy | Docker Compose profiles (sandbox → prod promotion) |

---

---

## Multi-Repo Setup

### The Problem

Real production bugs often span two repos. A developer renames an API field without telling the frontend team — unit tests in each repo pass in isolation, but the integration breaks in production.

**BUG-002** demonstrates this:
- `api-service` renamed `sale_price` → `final_price` (API contract break)
- `test-webapp` still reads `sale_price` → gets `None` → shows `$0.00` everywhere
- Neither repo's unit tests catch this — only an integration test does

### Multi-Repo Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Jira BUG-002 — lists BOTH affected repos + fix description │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  OpenHands Agent                                            │
│  ├── clone api-service   → fix: rename final_price back     │
│  ├── clone test-webapp   → verify frontend reads sale_price │
│  └── run integration tests (both services in Docker)        │
└──────────┬────────────────────────┬────────────────────────-┘
           │                        │
           ▼                        ▼
    PR opened in              PR opened in
    api-service               test-webapp
    (links to BUG-002)        (links to BUG-002)
           │                        │
           └──────────┬─────────────┘
                      │ both PRs must be approved
                      ▼
           Ordered deploy:
           api-service first → test-webapp second
           (never deploy frontend before backend)
```

### Running the Multi-Repo Demo

**Sandbox — see the bug ($0.00 sale prices):**
```bash
docker-compose -f docker-compose.multi-repo.yml --profile sandbox up
```
- Frontend: http://localhost:5000 — all sale prices show $0.00 (Bug 3)
- API: http://localhost:8001/api/products — returns `final_price`, not `sale_price`

**Run unit tests in each repo (both fail):**
```bash
cd test-webapp  && .venv/bin/pytest tests/ -v
cd api-service  && .venv/bin/pytest tests/ -v
```

**Run integration tests (catches the contract bug):**
```bash
docker-compose -f docker-compose.multi-repo.yml --profile integration run --rm integration-test
```

**Production — after agent fix and PR merge:**
```bash
docker-compose -f docker-compose.multi-repo.yml --profile prod up
```
- Frontend: http://localhost:8080 — correct prices
- API: http://localhost:8002/api/products — returns `sale_price`

### Key Multi-Repo Safety Rules

| Rule | Why |
|---|---|
| Both PRs must pass tests before either merges | Prevent partial fixes reaching prod |
| Integration tests run in Docker Compose (all services together) | Unit tests miss contract bugs |
| Deploy order: API first, then frontend | Frontend depends on API contract being live |
| Jira ticket must list all affected repos | Agent needs full context to fix everything |

---

## RAG Feedback Loop — Learning From Failures

Every failed fix (test failure or production rollback) is automatically captured, embedded, and stored in a local vector database. The **next time a similar ticket arrives**, the agent's prompt is enriched with the relevant failure history — so the agent doesn't repeat the same mistake.

### How It Works

```
┌─────────────────────────────────────────────────────────────┐
│  New Jira Ticket                                            │
│  e.g. "ZeroDivisionError in product detail"                 │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  feedback/retriever.py                                      │
│  Embed ticket title + body → query ChromaDB                 │
│  Return top-3 similar past failures (similarity ≥ 0.5)     │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  feedback/injector.py                                       │
│  Prepend failure context block to the OpenHands task prompt │
│                                                             │
│  ## Past Similar Fix Failures — Learn From These           │
│  ### Failure 1 (similarity: 87%)                           │
│  - Ticket: BUG-001                                          │
│  - Root cause: forgot to guard against empty list before   │
│    division — fix added check but broke avg when len == 1  │
│  - Failing diff: ...                                        │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  OpenHands Agent runs with enriched context                 │
│  Studies past failures BEFORE writing any code              │
└──────────────────────────┬──────────────────────────────────┘
                           │
              ┌────────────┴────────────┐
              │                         │
              ▼                         ▼
     Fix passes tests           Fix fails / rollback
     → deploy succeeds          → feedback/capture.py
                                  ├── Claude Haiku infers
                                  │   root cause from diff+log
                                  ├── Saved to ChromaDB
                                  │   (semantic search index)
                                  └── Raw JSON audit trail
                                      feedback/store/raw/
```

### Files

| File | Purpose |
|---|---|
| `feedback/capture.py` | `capture_failure()` — normalise + store a failed fix event |
| `feedback/rag_store.py` | `RAGStore` — ChromaDB wrapper with sentence-transformer embeddings |
| `feedback/retriever.py` | `retrieve_similar_failures()` — semantic search over past failures |
| `feedback/injector.py` | `build_enriched_task()` — builds the enriched prompt string |

### Triggering the Enriched Agent

```bash
# Install feedback loop dependencies (ChromaDB + sentence-transformers)
pip install -r requirements.txt

# Run agent with RAG-enriched prompt
python -c "
from feedback.injector import build_enriched_openhands_command
print(build_enriched_openhands_command(
    ticket_id    = 'BUG-001',
    ticket_title = 'ZeroDivisionError on product detail page',
    ticket_body  = open('bugs/BUG-001.md').read(),
    repo_url     = 'https://github.com/your-org/test-webapp',
))" | bash
```

### Capturing a Failure (after CI or rollback)

```bash
python -c "
from feedback.capture import capture_failure
capture_failure(
    event_type   = 'test_failure',
    ticket_id    = 'BUG-001',
    ticket_title = 'ZeroDivisionError on product detail page',
    ticket_body  = open('bugs/BUG-001.md').read(),
    repo         = 'https://github.com/your-org/test-webapp',
    diff         = open('/tmp/agent.diff').read(),
    error_output = open('/tmp/pytest.log').read(),
    # root_cause auto-inferred by Claude Haiku if omitted
)"
```

### Why RAG, Not Fine-Tuning?

| | RAG (this approach) | Fine-tuning |
|---|---|---|
| Setup time | Minutes | Days + GPU budget |
| Update latency | Instant (add to store) | Retrain cycle |
| Traceability | Every injection is visible in the prompt | Black box in weights |
| Cost | Free (local ChromaDB + offline embeddings) | $100s per run |
| Works with closed models | Yes | No |

---

## Key Safety Properties

| Property | How |
|---|---|
| Isolation | Agent runs inside Docker, never touches prod directly |
| Reversibility | Every change is a git commit; one `git revert` undoes it |
| Validation | Tests must pass before PR is opened |
| Human gate | PR review required before merge |
| Auditability | PR links back to Jira ticket; full agent action log available |
| Blast radius | Prod deploy is canary (10% traffic) with auto-rollback |
| Self-improvement | Failed fixes fed back into RAG store; agent learns from history |
