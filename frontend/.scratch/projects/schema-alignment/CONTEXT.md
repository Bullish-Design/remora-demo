**NEVER use subagents (the Task tool). Do ALL work directly. NO EXCEPTIONS.**

# Schema Alignment — Context

## Status: COMPLETE

All schema alignment work is done. The graph viewer's DB expectations now match the actual Remora EventStore schema.

## What Was Changed

### Production code
- `graph/state.py` — All SQL queries use `node_id` instead of `id`, `from_agent`/`to_agent` instead of `agent_id`, event queries use `id as event_id` alias
- `graph/bridge.py` — Fingerprint query uses `ORDER BY node_id`
- `graph/views/event_stream.py` — Uses `from_agent` with `agent_id` fallback for backward compat
- `remora_demo/__main__.py` — Added `await event_store.initialize()` after creating EventStore

### Test code
- `tests/test_integration_graph.py` — Full schema rewrite (22-col nodes, 10-col events with AUTOINCREMENT)
- `tests/test_golden_path.py` — Full schema rewrite, all INSERTs and WHERE clauses updated
- `tests/test_bridge.py` — Schema already updated, all INSERT/UPDATE statements in test methods updated

### Documentation
- `.scratch/skills/remora.md` — Section 4 updated with actual EventStore schema (22-col nodes, AUTOINCREMENT events, full proposals/command_queue tables)

## Final Test Results

177 passed, 2 skipped (the 2 skips are for Stario import tests, unrelated to schema)

**NEVER use subagents (the Task tool). Do ALL work directly. NO EXCEPTIONS.**
