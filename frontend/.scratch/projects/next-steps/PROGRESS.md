**NEVER use subagents (the Task tool). Do ALL work directly. NO EXCEPTIONS.**

**ALWAYS CONTINUE. NEVER STOP. After every compaction, resume IMMEDIATELY. Do NOT wait for user input. Keep working until the project is FULLY DONE — integrated, tested, everything.**

# Next Steps — Progress

## Agent Infrastructure Setup
- [x] Copy stario-api-notes.md to .scratch/skills/
- [x] Write .scratch/skills/stario-datastar.md
- [x] Write .scratch/skills/remora.md
- [x] Create .scratch/projects/next-steps/ with standard files
- [x] Update .scratch/REPO_RULES.md with skills references
- [x] Full codebase audit (both remora-demo and remora repos)
- [x] Rules files updated (CRITICAL_RULES, REPO_RULES, project files)
- [x] Architecture change: EVENT_BASED_DEMO_PLAN replaces old DESIGN_DOC + backend/
- [x] Updated project files (CONTEXT.md, PROGRESS.md, PLAN.md) for new architecture

## Workstream 1: Demo Project (T1-T2)
- [ ] T1: Create `configlib` demo project files (src/, tests/)
- [ ] T2: Create extension configs (.remora/models/) + remora.yaml

## Workstream 2: Core Migration (T3-T13) — AUDIT COMPLETE
- [x] T3: `get_node_at_position()` — ALREADY EXISTS in EventStore with tests (24 passing)
- [x] T4: `set_node_status()` — ALREADY EXISTS in EventStore with tests
- [x] T5: `remove_nodes_for_file()` — ALREADY EXISTS in EventStore with tests
- [x] T6: Watcher returns dicts — ALREADY DONE (watcher.py returns list[dict])
- [x] T7: documents.py emits NodeDiscoveredEvent — ALREADY DONE (did_open/did_save emit events)
- [x] T8: LSP handlers read AgentNode from EventStore — ALREADY DONE (lens, hover, actions use EventStore)
- [x] T9: commands.py uses EventStore + AgentNode — ALREADY DONE
- [x] T10: runner.py uses EventStore + AgentNode — ALREADY DONE (full tool loop)
- [x] T11: notifications.py uses EventStore — ALREADY DONE (cursor tracking)
- [ ] T12: Wire server.py — PARTIAL. EventStore accepted via __init__ param, but module-level singleton `server = RemoraLanguageServer()` creates with event_store=None. MockLLM selection NOT in library. Demo entry point must handle this.
- [x] T13: LazyGraph reads nodes from EventStore — ALREADY DONE (dual connection)

## Workstream 3: MockLLM (T14)
- [ ] T14: Implement enhanced MockLLMClient with scripted responses + tests

## Workstream 4: Graph Viewer (T15-T20) — ALL VERIFIED COMPLETE
- [x] T15: ForceLayout — EXISTS in graph/layout.py
- [x] T16: SVG element builders — EXISTS in graph/svg.py
- [x] T17: CSS theme + transitions — EXISTS in graph/css.py
- [x] T18: DB→Relay bridge — EXISTS in graph/bridge.py
- [x] T19: Stario app + handlers — EXISTS in graph/app.py
- [x] T20: View functions — EXISTS in graph/views/ (shell, graph, sidebar, event_stream)
- [x] Graph viewer: 132 tests all passing

## Workstream 5: Integration (T21-T22)
- [ ] T21: Demo entry points + launcher
- [ ] T22: End-to-end integration test (golden path smoke test)

## Gap Analysis
- [x] Read all Remora LSP source files (server.py, runner.py, documents.py, handlers, notifications.py, graph.py, db.py, watcher.py, models.py)
- [x] Verified RemoraDB has all required methods (update_edges, proposals, cursor_focus, command_queue, activation_chain)
- [ ] Write gap analysis document for Remora library owner

## Summary of Remaining Work (demo-side only)

| Task | What | Status |
|------|------|--------|
| T1 | Create configlib demo project files | NOT STARTED |
| T2 | Create extension configs + remora.yaml | NOT STARTED |
| T12 | Wire server.py (demo entry point handles EventStore + MockLLM) | PARTIAL — library side done, demo entry point needed |
| T14 | Enhanced MockLLMClient | NOT STARTED |
| T21 | Demo entry points + launcher | NOT STARTED |
| T22 | End-to-end integration test | NOT STARTED |
| Gap analysis | Document for Remora library owner | NOT STARTED |

**ALWAYS CONTINUE. NEVER STOP. After every compaction, resume IMMEDIATELY. Do NOT wait for user input. Keep working until the project is FULLY DONE — integrated, tested, everything.**

**NEVER use subagents (the Task tool). Do ALL work directly. NO EXCEPTIONS.**
