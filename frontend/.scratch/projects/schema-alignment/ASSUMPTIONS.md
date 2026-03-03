**NEVER use subagents (the Task tool). Do ALL work directly. NO EXCEPTIONS.**

# Schema Alignment — Assumptions

1. The EventStore schema (from `remora/src/remora/core/event_store.py`) is the source of truth.
2. The graph viewer is read-only against nodes/edges/events tables; only writes to command_queue.
3. The demo DB will be created by EventStore.initialize() at runtime, so we must match its schema.
4. The graph viewer only needs a subset of the 22 node columns (node_id, node_type, name, file_path, start_line, end_line, source_code, status) for rendering.
5. The `SELECT *` in state.py will return ALL columns — extra columns are harmless but will be in the dict.
6. The events table's `from_agent` and `to_agent` replace the single `agent_id` — for display we'll show `from_agent`.
7. Test fixtures create their own in-memory DBs matching the EventStore schema, NOT using EventStore.initialize() directly.
8. The proposals, cursor_focus, command_queue, and edges tables already match between viewer and EventStore.

**NEVER use subagents (the Task tool). Do ALL work directly. NO EXCEPTIONS.**
