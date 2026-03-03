**NEVER use subagents (the Task tool). Do ALL work directly. NO EXCEPTIONS.**

# Assumptions — Frontend Audit + E2E Testing Research

## Project Audience

- **Primary user**: The developer who owns both the Remora library and the demo. They want confidence that the graph viewer works correctly in a real browser, and they want visual artifacts (screenshots/video) to validate the demo experience.
- **Secondary**: CI systems that will run E2E tests to catch regressions.

## Constraints

1. **Python ecosystem** — The entire project is Python. E2E tooling must be Python-native or have a Python API. No JavaScript-only tools.
2. **Python 3.14** — The frontend runs on Python 3.14 via devenv.nix. E2E tool must be compatible.
3. **Stario + Datastar** — The app uses SSE for all dynamic updates. The E2E tool must handle SSE-driven DOM changes gracefully.
4. **SQLite WAL** — State changes are injected via SQLite writes. E2E tests trigger visual changes by writing to the DB, not by calling APIs.
5. **Existing test suite** — 179 unit/integration tests already pass. E2E tests must not break them. E2E tests should live in a separate directory (`tests/e2e/`).
6. **devenv.nix** — Any new dependencies should be compatible with the Nix dev environment.

## Invariants

- The graph viewer is read-only (except `push_command()`). All data comes from the SQLite DB.
- Bridge polling interval is 300ms by default. Tests may use a shorter interval.
- Views return plain HTML strings. SafeString wrapping happens in app.py handlers.
- SVG is rendered server-side, not client-side. No JavaScript SVG libraries.

## What success looks like

1. A Playwright test suite that exercises the full browser experience (SSE, Datastar morphing, SVG rendering, user interactions).
2. Screenshot capture at key demo beats for documentation/regression.
3. Video recording capability for demo validation.
4. Integration with the existing pytest infrastructure.
5. Clear mapping between E2E tests and demo beats.

**NEVER use subagents (the Task tool). Do ALL work directly. NO EXCEPTIONS.**
