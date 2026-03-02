**NEVER use subagents (the Task tool). Do ALL work directly. NO EXCEPTIONS.**

**ALWAYS CONTINUE. NEVER STOP. After every compaction, resume IMMEDIATELY. Do NOT wait for user input. Keep working until the project is FULLY DONE — integrated, tested, everything.**

# Next Steps — Context

## Current State (2026-03-02)

### Architecture Change — CRITICAL

**The old `DESIGN_DOC.md` and `backend/` directory are OBSOLETE. IGNORE THEM.**

The sole authority is **`EVENT_BASED_DEMO_PLAN.md`** (4012 lines, 14 sections, 22 tasks). This describes a fundamentally different architecture:

- **Old**: Separate frontend (Stario) + backend (Starlette chat service). Chat-oriented demo.
- **New**: Graph viewer alongside Neovim, both driven by shared SQLite EventLog. No separate backend process. The LSP server (inside Neovim) is the "backend". Graph viewer reads from the same `.remora/indexer.db`.

### What Exists

1. **Graph viewer frontend** (`frontend/graph/`): 13 source files, 132 passing tests. Implements Stario app, DB bridge, force layout, SVG rendering, views (shell, graph, sidebar, event_stream), CSS theme.

2. **Remora library** (`/home/andrew/Documents/Projects/remora/`): v0.4.12. Has `Config`, `ChatSession`, `EventBus`, `AgentNode`, `EventStore`, `NodeProjection`, `AgentExtension`, full event hierarchy. Phase 1 core is complete (120 tests passing).

3. **backend/ directory** (`/home/andrew/Documents/Projects/remora-demo/backend/`): OLD architecture — user said they'll delete it. DO NOT USE.

### What's Next

Implementation of the EVENT_BASED_DEMO_PLAN, following the 22-task order in Section 14. The work is organized into 5 workstreams:

1. **Demo Project** (T1-T2): Create `configlib` sample project + extension configs
2. **Core Migration** (T3-T13): Add EventStore methods, migrate LSP handlers to AgentNode
3. **MockLLM** (T14): Enhanced MockLLMClient with scripted responses
4. **Graph Viewer** (T15-T20): Reconcile existing code with plan, fill gaps
5. **Integration** (T21-T22): Entry points, launcher, end-to-end test

**Critical path**: T3/T4/T5 → T7 → T8 → T10 → T12 → T21 → T22 (~26h)

### Key Decisions

- The existing graph viewer code substantially implements the plan's Sections 5-8. Gaps need to be identified by comparing existing code vs plan specs.
- The old backend chat_service.py fixes are irrelevant — the new architecture has no standalone chat backend.
- Views return plain strings, SafeString wrapping only in handlers.
- Server-rendered SVG with CSS transitions (no d3-force client-side).
- Catppuccin Mocha dark theme.
- Go-style DI via closure-based handler factories.

### Resume Point

Start with: **Assess existing graph viewer code vs EVENT_BASED_DEMO_PLAN** to identify what's already done vs what needs work. Then begin implementation per Section 14 task order.

**ALWAYS CONTINUE. NEVER STOP. After every compaction, resume IMMEDIATELY. Do NOT wait for user input. Keep working until the project is FULLY DONE — integrated, tested, everything.**

**NEVER use subagents (the Task tool). Do ALL work directly. NO EXCEPTIONS.**
