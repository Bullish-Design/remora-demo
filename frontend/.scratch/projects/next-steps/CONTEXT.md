**NEVER use subagents (the Task tool). Do ALL work directly. NO EXCEPTIONS.**

**ALWAYS CONTINUE. NEVER STOP. After every compaction, resume IMMEDIATELY. Do NOT wait for user input. Keep working until the project is FULLY DONE — integrated, tested, everything.**

# Next Steps — Context

## Current State (2026-03-02)

### Architecture — CRITICAL

**The old `DESIGN_DOC.md` and `backend/` directory are OBSOLETE. IGNORE THEM.**

Sole authority: **`EVENT_BASED_DEMO_PLAN.md`** (4012 lines, 14 sections, 22 tasks).

- Neovim on left with Remora LSP plugin
- Graph viewer in browser on right (Stario + Datastar, server-rendered SVG)
- Both read from same `.remora/indexer.db` SQLite database
- LSP server (inside Neovim) IS the backend — no separate process
- MockLLM default, real LLM via env var override

### Audit Results — MAJOR FINDING

**The Remora library owner has ALREADY implemented most of the Option A migration.** T3-T11 and T13 are all done. The only remaining library-side gap is T12 (server.py wiring), and even that is partially done — `RemoraLanguageServer.__init__()` accepts `event_store=None`, but the module-level singleton on line 106 creates it with no EventStore. The demo entry point must handle wiring.

### What Exists

1. **Graph viewer** (`frontend/graph/`): 13 source files, 132 passing tests. Complete.
2. **Remora library** (separate repo, READ ONLY): T3-T11, T13 all done. EventStore has all needed methods. LSP handlers all use EventStore. Runner uses AgentNode. Documents.py emits events.
3. **RemoraDB** (`lsp/db.py`): Still used for edges, proposals, cursor_focus, command_queue, activation_chain. All methods confirmed working. Docstring says "Node state lives in EventStore."

### What's NOT Done (demo-side work)

| Task | What | Effort |
|------|------|--------|
| Gap analysis doc | Document for Remora library owner (minimal — mainly T12 MockLLM) | S |
| T1 | configlib demo project files (src/, tests/) | S |
| T2 | Extension configs (.remora/models/) + remora.yaml | S |
| T14 | Enhanced MockLLMClient with scripted responses | L |
| T21 | Demo entry points + launcher | M |
| T22 | End-to-end integration test | L |

### Resume Point

**Write the gap analysis document**, then start implementing demo-side tasks in order: T1 → T2 → T14 → T21 → T22.

### Key Files

| File | Location | Purpose |
|------|----------|---------|
| `EVENT_BASED_DEMO_PLAN.md` | `frontend/` | THE design doc |
| `graph/**/*.py` | `frontend/` | Graph viewer (complete) |
| `tests/**/*.py` | `frontend/` | Graph viewer tests (132 passing) |
| `.scratch/projects/next-steps/` | `frontend/` | Project tracking |
| Remora LSP source | `/home/andrew/Documents/Projects/remora/src/remora/lsp/` | READ ONLY |

### Key Constraints

- **DO NOT modify Remora library** — read only, produce gap analysis
- **TDD** — write failing test first
- **Views return plain strings** — not Stario Tag objects
- **Python 3.14** for frontend (Stario), **3.13** for Remora — separate processes sharing SQLite

**ALWAYS CONTINUE. NEVER STOP. After every compaction, resume IMMEDIATELY. Do NOT wait for user input. Keep working until the project is FULLY DONE — integrated, tested, everything.**

**NEVER use subagents (the Task tool). Do ALL work directly. NO EXCEPTIONS.**
