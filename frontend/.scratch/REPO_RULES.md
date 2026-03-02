**NEVER use subagents (the Task tool). Do ALL work directly. NO EXCEPTIONS.**

**ALWAYS CONTINUE. NEVER STOP. After every compaction, resume IMMEDIATELY. Do NOT wait for user input. Keep working until the project is FULLY DONE — integrated, tested, everything.**

# REPO RULES — remora-demo

Repo-specific standards and conventions. Loaded after `CRITICAL_RULES.md`.
These are **in addition to** the universal coding standards in CRITICAL_RULES.

---

## Repository Structure

```
remora-demo/
├── frontend/          # Graph viewer webapp (Python 3.14 + Stario)
│   ├── graph/         # Main package
│   │   ├── views/     # View functions (shell, graph, sidebar, event_stream)
│   │   ├── app.py     # Stario app factory and route handlers
│   │   ├── bridge.py  # DB->Relay polling bridge
│   │   ├── layout.py  # Force-directed layout engine
│   │   ├── svg.py     # SVG element builders
│   │   ├── css.py     # CSS theme
│   │   ├── state.py   # GraphState (SQLite reader) and GraphSnapshot
│   │   └── __main__.py # CLI entry point
│   ├── tests/         # Test suite (132 tests)
│   ├── launch.sh      # Shell launcher
│   ├── pyproject.toml  # Package config
│   └── devenv.nix     # Nix dev environment (Python 3.14)
├── backend/           # Backend services
├── .context/          # Reference docs
├── DESIGN_DOC.md      # Overall design document
└── AGENTS.md          # Agent instruction file
```

---

## Coding Standards (repo-specific)

- **Views return plain strings** — no Stario dependency in view functions, SVG builders, or CSS.
- **SafeString wrapping** happens only in app.py handlers, not in views.
- **SVG as f-strings** — Stario has no SVG elements; we use f-string builders wrapped in SafeString.
- **RelayProtocol** — Protocol class for testability without Stario.
- **Deferred Stario import** — `__main__.py` imports Stario inside `_serve()`, not at module top level.
- **DB reads offloaded** — Use `asyncio.to_thread` for all SQLite reads in async handlers.

---

## Test Suite

```
cd frontend && devenv shell -- python -m pytest tests/ -q
```

All 132 tests pass, 0 skipped. The 2 Stario-dependent tests (`TestAppImport`) pass because Stario is available in the Python 3.14 devenv.

---

## Skills Files

Read these before starting work. They provide condensed mental models for the frameworks used in this project.

| Skill | Path | Covers |
|-------|------|--------|
| Stario + Datastar | `.scratch/skills/stario-datastar.md` | Handlers, routing, Writer, SSE, Relay, HTML builders, SafeString, Datastar |
| Remora | `.scratch/skills/remora.md` | Events, DB schema, graph viewer data layer, architecture |
| Stario API quick-ref | `.scratch/skills/stario-api-notes.md` | Imports, methods, patterns at a glance |

---

## Key Reference Files

| Document | Path |
|----------|------|
| Design doc | `DESIGN_DOC.md` |
| Agent startup plan | `.scratch/projects/next-steps/PLAN.md` |
| Stario docs | `.context/stario/` |
| Nvim demo concept | `NVIM_DEMO_CONCEPT.md` |

---

## Dev Environment

- Python 3.14 via devenv.nix
- Stario installed via uv in the venv
- pytest + pytest-asyncio for testing
- Scripts: `start-graph` (run server), `test-graph` (run tests)

**ALWAYS CONTINUE. NEVER STOP. After every compaction, resume IMMEDIATELY. Do NOT wait for user input. Keep working until the project is FULLY DONE — integrated, tested, everything.**

**NEVER use subagents (the Task tool). Do ALL work directly. NO EXCEPTIONS.**
