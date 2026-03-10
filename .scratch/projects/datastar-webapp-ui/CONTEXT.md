# CONTEXT — datastar-webapp-ui

## What just happened
Completed a full repository rewrite of `remora-demo` to implement the datastar-webapp-ui
guide as the new primary direction.

## Deliverables
- New root Python package files:
  - `pyproject.toml` (`remora-ui` package + CLI)
  - `src/remora_ui/config.py` (runtime config/env loading)
  - `src/remora_ui/app.py` (Starlette app + `/`, `/config.json`, `/static/*`)
  - `src/remora_ui/static/index.html` (Datastar + Cytoscape + sidebar + replay controls)
  - `src/remora_ui/static/style.css` (graph/event-log/sidebar/replay layout)
  - `src/remora_ui/static/main.js` (graph load, SSE live pings, sidebar, chat, cursor focus,
    replay scrubber)
  - `tests/test_app.py` (server/static smoke tests)
- Removed previous implementation artifacts:
  - Entire `frontend/` tree
  - Legacy architecture docs (`DEMO_ARCHITECTURE*.md`, `SWARM_ARCHITECTURE.md`)
- Updated environment/docs:
  - `README.md`, `devenv.nix`, `devenv.yaml`, `devenv.lock`

## Key technical decisions
1. Keep UI as a thin standalone Starlette host that serves static assets only.
2. Browser talks directly to remora API endpoints over CORS (`/graph/data`, `/events`,
   `/companion/*`, `/replay`).
3. Use Cytoscape compound nodes via `parent` data and call edges from `callee_ids`.
4. Use Datastar signal interop via `window.__datastar_store` with retry fallback.
5. Implement all roadmap phases (P0-P5) in one integrated `main.js` flow.

## Files to modify in remora repo
Not part of this repo rewrite; expected to already be present in the remora library copy under
`.context/remora` and in the actual remora runtime used by the UI.

## Status
Implementation complete in this repository and validated with local tests.

## Next step
Run against a live remora server and verify end-to-end behavior in browser:
graph render, live SSE flashes, sidebar markdown, chat replies, cursor focus highlight, and replay scrubber.
