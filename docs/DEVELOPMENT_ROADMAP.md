# Development Roadmap

Deliverable for step 8 of the development workflow.

---

## Where the project actually is

Honest status, not a plan on paper:

| Workflow step | State |
|---|---|
| 1. Business problem discovery | ✅ Done — captured in PRODUCT_REQUIREMENTS.md |
| 2. Product planning | ✅ Done — PRODUCT_REQUIREMENTS.md *(written after implementation, out of order)* |
| 3. Technical architecture | ✅ Done — TECHNICAL_ARCHITECTURE.md |
| 4. Technology selection | ✅ Done — TECH_STACK.md |
| 5. Database design | ✅ Done — DATABASE_DESIGN.md *(written after implementation)* |
| 6. API design | ✅ Done — API_SPECIFICATION.md *(written after implementation)* |
| 7. UI/UX design | ⏳ **Awaiting approval** — UI_UX_SPECIFICATION.md |
| 8. Development roadmap | ✅ This document |
| 9. Coding standards | ✅ Done — CODING_STANDARDS.md *(written after implementation)* |
| 10. Development environment | ✅ Working — Docker, or manual; `doctor` verifies it |
| 11. Backend development | ✅ Complete for V1 scope |
| 12. Frontend development | ⚠️ **Partial** — 3 of 7 planned screens missing |
| 13. Integration | ✅ End-to-end working |
| 14. Testing | ⚠️ 145 automated tests pass; UAT not started |
| 15. Deployment | ❌ Not started — never run on real infrastructure |
| 16. Version 2 | ❌ Not started |
| 17. Version 3 | ❌ Not started |

**The process was not followed in order.** Steps 11–13 were implemented before
steps 5, 7 and 9 were written. The documents now exist, but they were written to
describe a build rather than to direct one — which is precisely how the frontend
came to diverge from the planned screens.

**From this point the order is honoured:** UI_UX_SPECIFICATION.md is approved
before any screen is built.

---

## Phase 1 — Close the specification gap · ~1 week

**Goal:** the built product matches the specified product.

| # | Task | Depends on | Estimate |
|---|---|---|---|
| 1.1 | Approve UI_UX_SPECIFICATION.md | — | Your review |
| 1.2 | Add `jobs.submitted_by`, adopt Alembic | 1.1 | 0.5 day |
| 1.3 | Dashboard summary endpoint | 1.2 | 0.5 day |
| 1.4 | Build **Dashboard** | 1.3 | 1 day |
| 1.5 | Build **Jobs list** + **Job Details** | 1.2 | 1.5 days |
| 1.6 | Build **Settings** (account, limits, transcription, system check) | 1.2 | 1.5 days |
| 1.7 | Route and naming changes — New Job to `/jobs/new`, Library → History, Team into Settings | 1.1 | 0.5 day |
| 1.8 | Frontend tests for the new screens | 1.4–1.7 | 0.5 day |

**Exit criteria:** all seven specified screens exist and behave as specified;
tests pass; a colleague who has never seen it can complete journey 4.1 from
PRODUCT_REQUIREMENTS.md unaided.

---

## Phase 2 — Prove it on real infrastructure · ~3 days

**Goal:** it works outside a developer's machine. **This is currently the
largest risk in the project**, because two things have never run for real.

| # | Task | Estimate |
|---|---|---|
| 2.1 | Run `doctor --deep` on the target machine — confirms the speech model downloads and transcription speed on that hardware | 1 hour |
| 2.2 | Transcribe one real YouTube video end to end | 1 hour |
| 2.3 | Transcribe one real Instagram Reel, with the cookie file configured | 2 hours |
| 2.4 | Verify the Docker build | 2 hours |
| 2.5 | Batch of 20 real videos — measure wall-clock and tune worker concurrency | 0.5 day |
| 2.6 | Fix whatever 2.1–2.5 uncover | 1 day (reserve) |

**Exit criteria:** a real batch of real videos produces accurate transcripts on
the target machine, with a measured time-per-video figure.

**Note on the reserve:** 2.6 is a deliberate placeholder. The download path and
the speech model have never executed in a real environment, and estimating the
cost of unknown failures at zero would be dishonest.

---

## Phase 3 — Deploy · ~3 days

| # | Task | Estimate |
|---|---|---|
| 3.1 | Provision the VPS; install Docker | 0.5 day |
| 3.2 | Switch to PostgreSQL; add the `tsvector` search backend | 0.5 day |
| 3.3 | Domain, Nginx reverse proxy, SSL via Let's Encrypt | 0.5 day |
| 3.4 | Backups of the database (the only irreplaceable asset) | 0.5 day |
| 3.5 | Add `exports` and `logs` tables | 0.5 day |
| 3.6 | Create real accounts; onboard two pilot users | 0.5 day |

**Exit criteria:** two colleagues using it for real work, on a real domain, over
HTTPS, with backups running.

---

## Phase 4 — Pilot and harden · ~2 weeks, mostly elapsed time

Run with a small group before opening it to everyone.

- Watch which errors actually occur, and improve those messages first
- Tune the model size against the accuracy the team finds acceptable
- Measure the real figure: hours saved per researcher per week
- Fix what the pilot surfaces

**Exit criteria:** the pilot group prefers it to their current process. That is
the gate for wider rollout — not a feature count.

---

## Phase 5 — Version 2, AI analysis · ~3 weeks

Only after V1 is genuinely in daily use. Analysis over research nobody trusts
yet is wasted work.

| # | Task |
|---|---|
| 5.1 | `LLMProvider` interface with an Ollama (free, local) implementation |
| 5.2 | `Analysis` model, FK'd to `Transcript` |
| 5.3 | Analysis stage appended to the pipeline |
| 5.4 | Extraction: topic, hook, opening pattern, framework, CTA, offer, triggers, style, structure, audience, tone, learnings, quotes, viral elements, keywords, category |
| 5.5 | Backfill command for transcripts already collected |
| 5.6 | Analysis surfaced in the Transcript Viewer |
| 5.7 | **Honest quality comparison: free local model vs paid API, on your real transcripts** |

**5.7 is a decision point, not a formality.** Free local models are weaker at
nuanced marketing judgement. The comparison should be run on your own content
and the result shown side by side before anyone commits money.

---

## Phase 6 — Version 3, research system · ~6 weeks

| # | Task |
|---|---|
| 6.1 | Semantic search — embeddings behind the existing search interface |
| 6.2 | Knowledge base across all transcripts |
| 6.3 | Creator and competitor comparison |
| 6.4 | Trend detection |
| 6.5 | Generation: hooks, CTAs, outlines, scripts, strategies |
| 6.6 | AI chat over past research |

---

## Testing strategy

| Type | When | Current |
|---|---|---|
| Unit | Every change | ✅ 145 tests, no network or API keys needed |
| Integration | Every change | ✅ Full pipeline with a fake media backend |
| Real-world | Phase 2 | ❌ **The gap** — never run against a live platform |
| User acceptance | Phase 4 | ❌ Not started |
| Performance | Phase 2.5 | ❌ Not started |

---

## Per-feature loop

Every feature from here follows the same cycle:

```
Requirement → Discussion → Architecture → Documentation → APPROVAL
   → Implementation → Testing → Code review → Refactor → Commit → Next
```

**The approval gate is the one that was skipped, and skipping it is what caused
the frontend divergence.** It is not optional going forward.
