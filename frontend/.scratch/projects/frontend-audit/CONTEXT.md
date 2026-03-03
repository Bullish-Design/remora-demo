**NEVER use subagents (the Task tool). Do ALL work directly. NO EXCEPTIONS.**

# Context — Frontend Audit + E2E Testing Research

## What This Project Is

Two-phase project: (1) audit the frontend against the Remora library's current schema, (2) research and propose an E2E testing strategy for the graph viewer.

## Current State: COMPLETE

Both phases are done. All deliverables written.

### Phase 1 Result
The frontend is **fully aligned** with the Remora library schema. Zero discrepancies across all 6 tables. All 179 tests pass.

### Phase 2 Result
A comprehensive E2E testing proposal in `PLAN.md` (510 lines, 13 sections) recommending **Playwright (Python)** with pytest-playwright. Key points:
- Playwright doesn't need to parse SSE — it just sees DOM after Datastar morphs it
- Subprocess server fixture, DB writes for state injection (same pattern as test_golden_path.py)
- 10 core E2E tests mapped to demo beats + 3 visual artifact tests
- Screenshots per beat, video recording, trace viewer
- Estimated 4-6 hours to implement

## Deliverables

| File | Status | Description |
|------|--------|-------------|
| `PLAN.md` | Done | 510-line E2E testing proposal — main deliverable |
| `ASSUMPTIONS.md` | Done | Project constraints and success criteria |
| `DECISIONS.md` | Done | 5 key decisions with rationale |
| `PROGRESS.md` | Done | Task tracker |
| `CONTEXT.md` | Done | This file |

## What Happens Next

Awaiting user decision:
1. **Proceed** — Implement E2E tests per PLAN.md Phases 1-4
2. **Modify** — Adjust the proposal
3. **Move on** — Different task entirely

## Key References

- E2E proposal: `.scratch/projects/frontend-audit/PLAN.md`
- Golden path tests (fixture pattern to reuse): `tests/test_golden_path.py`
- App factory with SSE endpoint: `graph/app.py`
- SVG builders (would need data-testid attrs): `graph/svg.py`
- Run tests: `devenv shell -- python -m pytest tests/ -v --ignore=tests/test_cross_process.py`

**NEVER use subagents (the Task tool). Do ALL work directly. NO EXCEPTIONS.**
