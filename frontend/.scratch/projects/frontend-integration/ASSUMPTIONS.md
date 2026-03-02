# Frontend Integration — Assumptions

## Target Environment
- Python 3.14 via devenv.nix
- Stario framework installed via uv
- SQLite DB as data source (WAL mode)
- pytest + pytest-asyncio for testing

## Constraints
- The graph viewer reads from a SQLite DB but does NOT write to it (except command_queue)
- Views must be testable without Stario
- The frontend is a single-page app with SSE-based live updates via Datastar
- Catppuccin Mocha color theme throughout

## User Scenarios
- Developer runs `python -m graph --db path/to/indexer.db` to start the viewer
- Browser connects and sees the force-directed graph of code nodes
- Graph updates in real-time as the Remora backend processes code
- Clicking a node opens the sidebar with details, events, source, connections
- User can send chat commands and approve/reject proposals
