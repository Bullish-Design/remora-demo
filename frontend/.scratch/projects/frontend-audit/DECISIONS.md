**NEVER use subagents (the Task tool). Do ALL work directly. NO EXCEPTIONS.**

# Decisions — Frontend Audit + E2E Testing Research

## D1: Playwright over Cypress/Selenium

**Decision**: Use Playwright (Python) with pytest-playwright for E2E testing.

**Rationale**: Same language as the project, first-class pytest integration, built-in screenshots/video/traces, transparent SSE handling (just test the DOM after Datastar morphs it). Cypress is JavaScript-only. Selenium lacks video recording and trace viewer.

**Assumptions**: Python ecosystem constraint. SSE/Datastar architecture.

## D2: Subprocess server lifecycle over in-process

**Decision**: Start the Stario server as a subprocess in test fixtures rather than running it in-process.

**Rationale**: Simpler, more realistic (tests the actual CLI entry point), avoids asyncio event loop conflicts with Playwright's sync API. The small overhead (server startup ~1-2s) is acceptable for E2E tests.

**Assumptions**: E2E tests are few (~10-15) and expected to be slow (~2-5s each).

## D3: Separate directory for E2E tests

**Decision**: Place E2E tests in `tests/e2e/` rather than mixing with existing tests.

**Rationale**: E2E tests are slower, have different dependencies (Playwright + browsers), and should be runnable independently. Keeping them separate prevents accidentally slowing down the fast unit test run.

## D4: DB writes for state injection (not API calls)

**Decision**: E2E tests inject state changes by writing directly to SQLite, not by calling HTTP endpoints or APIs.

**Rationale**: This is the same approach used by the integration tests (test_golden_path.py). It's the most realistic simulation of the actual system behavior (the LSP server writes to the DB, the graph viewer reads it).

## D5: Frontend audit result — zero discrepancies

**Decision**: No schema changes needed. The frontend is fully aligned with the Remora library.

**Rationale**: Systematic table-by-table comparison of all 6 tables (events, nodes, edges, cursor_focus, proposals, command_queue) showed exact column name matches. All 179 tests pass. The schema-alignment project (completed earlier) already fixed any mismatches.

**NEVER use subagents (the Task tool). Do ALL work directly. NO EXCEPTIONS.**
