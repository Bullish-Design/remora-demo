**NEVER use subagents (the Task tool). Do ALL work directly. NO EXCEPTIONS.**

**ALWAYS CONTINUE. NEVER STOP. After every compaction, resume IMMEDIATELY. Do NOT wait for user input. Keep working until the project is FULLY DONE — integrated, tested, everything.**

# Next Steps — Implementation Plan

**ABSOLUTE RULE — NO SUBAGENTS: NEVER use the Task tool. Do all work directly. This rule is non-negotiable.**

---

## Quick Orientation

You are working on **remora-demo**, a demo showing Remora's EventBased architecture. The sole design authority is **`EVENT_BASED_DEMO_PLAN.md`** (in the frontend/ directory). The old `DESIGN_DOC.md` and `backend/` directory are OBSOLETE — ignore them.

### Architecture Summary

- **Neovim on the left** with Remora LSP plugin (code lenses, hover, chat panel)
- **Graph viewer in browser on the right** (Stario + Datastar, server-rendered SVG)
- Both read from the same `.remora/indexer.db` SQLite database
- The LSP server (in Neovim) is the "backend" — no separate chat service
- Communication: shared SQLite (WAL mode), DB polling bridge → Relay → SSE → Datastar DOM morphing

### First Steps After Compaction
1. Read `.scratch/CRITICAL_RULES.md`
2. Read `.scratch/REPO_RULES.md`
3. Read this file (PLAN.md) + CONTEXT.md + PROGRESS.md
4. Reference `EVENT_BASED_DEMO_PLAN.md` for detailed specs (4012 lines, 14 sections)
5. Resume the next pending task from PROGRESS.md

### Current State

**What is DONE:**
- Graph viewer frontend: 13 source files in `graph/` and `graph/views/` — 132 tests passing
- Remora core (Phase 1): AgentNode, EventStore, NodeProjection, AgentExtension, events — 120 tests passing
- Agent infrastructure: AGENTS.md, .scratch rules, skills files

**What is NOT done:**
- Demo project (configlib sample files)
- Core migration (EventStore methods, LSP handler migration)
- Enhanced MockLLMClient
- Graph viewer gaps (compare existing code to plan)
- Integration (entry points, launcher, E2E test)

---

## Implementation Order (from EVENT_BASED_DEMO_PLAN Section 14)

22 tasks, 5 workstreams, ~60h total effort, ~26h critical path.

### Phase A: Foundations (parallel-safe)

| Task | Description | Effort | Workstream |
|------|-------------|--------|------------|
| T1 | Create `configlib` demo project files | S | Demo Project |
| T2 | Create extension configs + remora.yaml | S | Demo Project |
| T3 | Add `get_node_at_position()` to EventStore | S | Core Migration |
| T4 | Add `set_node_status()` to EventStore | S | Core Migration |
| T5 | Add `remove_nodes_for_file()` to EventStore | S | Core Migration |
| T6 | Update watcher to return dicts | M | Core Migration |
| T14 | Enhanced MockLLMClient with scripted responses | L | MockLLM |
| T15 | Server-side ForceLayout | M | Graph Viewer |
| T16 | SVG element builders | S | Graph Viewer |
| T17 | CSS theme + transitions | M | Graph Viewer |
| T18 | DB→Relay bridge | M | Graph Viewer |

### Phase B: Wiring

| Task | Description | Depends On | Effort |
|------|-------------|-----------|--------|
| T7 | documents.py emits NodeDiscoveredEvent | T3,T4,T5,T6 | M |
| T8 | LSP handlers read AgentNode from EventStore | T7 | M |
| T9 | commands.py uses EventStore + AgentNode | T7 | M |
| T11 | notifications.py uses EventStore | T3 | S |
| T20 | View functions (shell, graph, sidebar, event_stream) | T15,T16,T17 | L |

### Phase C: Assembly

| Task | Description | Depends On | Effort |
|------|-------------|-----------|--------|
| T10 | runner.py uses EventStore + AgentNode | T8,T9 | L |
| T13 | LazyGraph reads nodes from EventStore | T10 | M |
| T19 | Stario app + handlers | T18,T20 | L |

### Phase D: Integration

| Task | Description | Depends On | Effort |
|------|-------------|-----------|--------|
| T12 | Wire server.py (EventStore + MockLLM selection) | T10,T11,T14 | M |

### Phase E: Launch

| Task | Description | Depends On | Effort |
|------|-------------|-----------|--------|
| T21 | Demo entry points + launcher | T2,T12,T19 | M |
| T22 | End-to-end integration test | T21 | L |

### Recommended Sequential Order (single implementer)

1. T3, T4, T5 — EventStore methods (warm up with TDD)
2. T6 — Watcher returns dicts
3. T7 — documents.py uses EventStore
4. T11 — notifications.py uses EventStore
5. T8 — LSP handlers use AgentNode
6. T9 — commands.py uses AgentNode
7. T10 — runner.py uses AgentNode (largest task)
8. T14 — Enhanced MockLLMClient
9. T1, T2 — Demo project files
10. T12 — Wire server.py
11. T13 — Update LazyGraph
12. Assess graph viewer gaps, then T15-T20 as needed
13. T19 — Stario app + handlers
14. T21 — Entry points + launcher
15. T22 — End-to-end test

---

## Key Architecture Decisions (carry forward)

These are settled — do not revisit without explicit user request:

- **Views return plain strings** — no Stario dependency in views
- **SafeString wrapping** happens only in handlers
- **Server-rendered SVG** with CSS transitions (no d3-force client-side)
- **Go-style DI** — closure-based handler factories
- **Catppuccin Mocha** dark theme
- **DB polling bridge** at 300ms interval → Relay → SSE
- **No separate backend** — LSP server is the backend, shared SQLite is the transport
- **MockLLM default** — real LLM via env var override

---

## Key Files

| File | Purpose |
|------|---------|
| `EVENT_BASED_DEMO_PLAN.md` | **THE** design doc (4012 lines, 14 sections) |
| `graph/*.py` | Existing graph viewer code |
| `graph/views/*.py` | Existing view functions |
| `tests/*.py` | Existing test suite (132 tests) |
| `/home/andrew/Documents/Projects/remora/src/remora/core/` | Remora v0.4.12 core |
| `/home/andrew/Documents/Projects/remora/src/remora/lsp/` | Remora LSP server (migration target) |

---

## REMINDER — NO SUBAGENTS

**NEVER use the Task tool.** Do all work directly. This rule is absolute and non-negotiable.

## REMINDER — ALWAYS CONTINUE

**NEVER stop working after compaction.** Read CONTEXT.md, check PROGRESS.md, resume immediately. Keep going until the project is fully done.

**ALWAYS CONTINUE. NEVER STOP. After every compaction, resume IMMEDIATELY. Do NOT wait for user input. Keep working until the project is FULLY DONE — integrated, tested, everything.**

**NEVER use subagents (the Task tool). Do ALL work directly. NO EXCEPTIONS.**
