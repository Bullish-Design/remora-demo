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

## Workstream 1: Demo Project (T1-T2) — DONE
- [x] T1: Create `configlib` demo project files (src/, tests/) — loader.py, schema.py, merge.py, __init__.py, test_loader.py, test_merge.py
- [x] T2: Create extension configs (.remora/models/test_function.py, package_init.py) + remora.yaml + .nvim.lua

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
- [x] T12: Wire server.py — PARTIAL on library side (module-level singleton issue). Demo entry point (__main__.py) handles wiring. Documented in GAP_ANALYSIS.md for library owner.
- [x] T13: LazyGraph reads nodes from EventStore — ALREADY DONE (dual connection)

## Workstream 3: MockLLM (T14) — DONE
- [x] T14: Enhanced MockLLMClient with scripted responses (~362 lines) + 19 passing tests
  - Fixed TestAgentUpdateScript.matches() to also match tool_followup trigger type

## Workstream 4: Graph Viewer (T15-T20) — ALL VERIFIED COMPLETE
- [x] T15: ForceLayout — EXISTS in graph/layout.py
- [x] T16: SVG element builders — EXISTS in graph/svg.py
- [x] T17: CSS theme + transitions — EXISTS in graph/css.py
- [x] T18: DB→Relay bridge — EXISTS in graph/bridge.py
- [x] T19: Stario app + handlers — EXISTS in graph/app.py
- [x] T20: View functions — EXISTS in graph/views/ (shell, graph, sidebar, event_stream)
- [x] Graph viewer: 132 tests all passing

## Workstream 5: Integration (T21-T22) — DONE
- [x] T21: Demo entry points + launcher
  - T21a: `remora_demo/__main__.py` — LSP server entry point (72 lines)
  - T21b: `launch.sh` — Full demo launcher (57 lines, --port, --no-browser flags)
  - T21c: 10 new tests in test_entry_points.py (8 LSP structure + 2 launch.sh)
- [x] T22: End-to-end golden path smoke test — `tests/test_golden_path.py` (~340 lines, 18 tests across 6 classes)

## Gap Analysis — DONE
- [x] Read all Remora LSP source files
- [x] Verified RemoraDB has all required methods
- [x] Wrote GAP_ANALYSIS.md for Remora library owner (3 small gaps: T12 singleton, MockLLM selection, launch.sh LSP command)

## Final Test Suite: 179 tests, ALL PASSING
- 132 graph viewer tests
- 19 mock_llm tests (T14)
- 10 entry point structure tests (T21)
- 18 golden path tests (T22)

## Summary: ALL DEMO-SIDE TASKS COMPLETE

The only blocking work for the actual demo is the 3 small library-side gaps documented in `GAP_ANALYSIS.md` (~15-30 min for the library owner).

## Final Code Review — DONE
- [x] Read all Remora library source files (~7,500 lines across 40+ files)
- [x] Read all remora_demo/ source files (~2,000 lines across 12+ files)
- [x] Read all frontend source files (~3,500 lines)
- [x] Read both pyproject.toml files for dependency analysis
- [x] Wrote FINAL_CODE_REVIEW.md — 17 sections, ~600 lines
  - 2 Critical findings (module-level singleton, dual event types)
  - 4 High findings (3 SQLite DBs, code duplication, dead executor branch, thread safety)
  - 5 Medium findings (error swallowing, unlocked methods, ConfigError shadow, dependencies, no cross-repo tests)
  - 3 Low findings (commented-out config, UI coupling, unused exports)
  - Prioritized recommendations with effort estimates and implementation order

## PROJECT STATUS: FULLY COMPLETE

All deliverables produced:
1. All 22 demo tasks (T1-T22) — DONE
2. 179 tests — ALL PASSING
3. GAP_ANALYSIS.md for library owner — DONE
4. FINAL_CODE_REVIEW.md — DONE

**ALWAYS CONTINUE. NEVER STOP. After every compaction, resume IMMEDIATELY. Do NOT wait for user input. Keep working until the project is FULLY DONE — integrated, tested, everything.**

**NEVER use subagents (the Task tool). Do ALL work directly. NO EXCEPTIONS.**
