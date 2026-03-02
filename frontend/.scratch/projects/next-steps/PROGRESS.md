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

## Workstream 2: Core Migration (T3-T13)
- [ ] T3: Add `get_node_at_position()` to EventStore
- [ ] T4: Add `set_node_status()` to EventStore
- [ ] T5: Add `remove_nodes_for_file()` to EventStore
- [ ] T6: Update watcher to return dicts (not ASTAgentNode)
- [ ] T7: Update documents.py to emit NodeDiscoveredEvent to EventStore
- [ ] T8: Update LSP handlers (lens, hover, actions) to read AgentNode from EventStore
- [ ] T9: Update commands.py to use EventStore + AgentNode
- [ ] T10: Update runner.py to use EventStore + AgentNode
- [ ] T11: Update notifications.py to use EventStore
- [ ] T12: Wire server.py (EventStore + MockLLM selection)
- [ ] T13: Update LazyGraph to read nodes from EventStore

## Workstream 3: MockLLM (T14)
- [ ] T14: Implement enhanced MockLLMClient with scripted responses + tests

## Workstream 4: Graph Viewer (T15-T20)
- [ ] Assess existing graph viewer code vs plan (identify gaps)
- [ ] T15: Server-side ForceLayout (may already exist — verify)
- [ ] T16: SVG element builders (may already exist — verify)
- [ ] T17: CSS theme + transitions (may already exist — verify)
- [ ] T18: DB→Relay bridge (may already exist — verify)
- [ ] T19: Stario app + handlers (may already exist — verify)
- [ ] T20: View functions (shell, graph, sidebar, event_stream — may already exist)

## Workstream 5: Integration (T21-T22)
- [ ] T21: Demo entry points + launcher
- [ ] T22: End-to-end integration test (golden path smoke test)

**ALWAYS CONTINUE. NEVER STOP. After every compaction, resume IMMEDIATELY. Do NOT wait for user input. Keep working until the project is FULLY DONE — integrated, tested, everything.**

**NEVER use subagents (the Task tool). Do ALL work directly. NO EXCEPTIONS.**
