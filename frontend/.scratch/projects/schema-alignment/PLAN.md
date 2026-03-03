**NEVER use subagents (the Task tool). Do ALL work directly. NO EXCEPTIONS.**

# Schema Alignment — Plan

Align the graph viewer's DB schema expectations with the actual Remora EventStore schema.

## Problem

The graph viewer (state.py, bridge.py, tests) uses a test-only schema with different column names than the real EventStore:

| Table | Viewer uses | EventStore has |
|-------|------------|----------------|
| nodes PK | `id` | `node_id` |
| nodes cols | 8 columns | 22 columns |
| events PK | `event_id TEXT` | `id INTEGER AUTOINCREMENT` |
| events agent | `agent_id` | `from_agent` / `to_agent` |
| events cols | 6 columns | 10 columns |

## Steps

1. **Update `state.py`** — Fix all SQL queries and dict key transformations
   - `read_snapshot()`: `n.pop("node_id")` instead of `n.pop("id")`
   - `read_node()`: `WHERE node_id = ?` instead of `WHERE id = ?`
   - `read_events_for_agent()`: Use `from_agent`/`to_agent` instead of `agent_id`
   - `read_recent_events()`: Use `id` (INTEGER) instead of `event_id` (TEXT)
   - `read_proposals_for_agent()`: Fine as-is (proposals schema matches)

2. **Update `bridge.py`** — Fix fingerprint query: `ORDER BY node_id` instead of `ORDER BY id`

3. **Update `test_golden_path.py`** — Rewrite `_create_demo_db()`:
   - `nodes` table: `node_id TEXT PRIMARY KEY` + full 22-column schema
   - `events` table: `id INTEGER PRIMARY KEY AUTOINCREMENT` + 10 columns
   - All INSERT statements updated for new column order
   - All `WHERE id = ?` references in test SQL updated to `WHERE node_id = ?`

4. **Update `test_integration_graph.py`** — Same schema changes in `demo_db` fixture

5. **Update views** — Fix field name references:
   - `event_stream.py`: `agent_id` -> `from_agent` (for display)
   - `sidebar.py`: Already uses `node.get("remora_id")` — should be fine

6. **Update `__main__.py`** — Add `await event_store.initialize()` call

7. **Run all tests** — All 179 tests passing

8. **Update `skills/remora.md`** — Reflect the actual schema

## Acceptance Criteria

- All tests pass with the aligned schema
- Graph viewer correctly reads from a DB created by the real EventStore
- No references to the old `id`/`event_id`/`agent_id` column names remain

**NEVER use subagents (the Task tool). Do ALL work directly. NO EXCEPTIONS.**
