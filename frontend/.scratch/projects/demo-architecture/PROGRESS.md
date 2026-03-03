# PROGRESS: DEMO_ARCHITECTURE.md (Full Rewrite + Audit)

## Study Phase
- [x] Research: Read all Remora core source files (events, event_store, event_bus, subscriptions, agent_node, discovery, reconciler, config, workspace, cairn_bridge, kernel_factory, utils, projections)
- [x] Research: Read all Remora service/API source files (api.py, handlers.py, datastar.py, chat_service.py)
- [x] Research: Read all Remora LSP source files (runner.py, server.py, __main__.py, models.py, watcher.py, handlers/)
- [x] Research: Read UI layer (projector.py, view.py, components/)
- [x] Research: Read extensions.py, cli/main.py, chat.py
- [x] Research: Read Starlette adapter (adapters/starlette.py)
- [x] Research: Read graph viewer (both remora_demo/web/graph/ and frontend/graph/)
- [x] Research: Read mock LLM (frontend mock, test scripts)
- [x] Research: Read all frontend tests

## Writing Phase
- [x] Write TOC skeleton (55 subsections across 9 sections)
- [x] Write Section 1: System Overview
- [x] Write Section 2: Remora Core Architecture (13 subsections: 2.1-2.12 + 2.S)
- [x] Write Section 3: The Data Flow Pipeline (5 subsections)
- [x] Write Section 4: Neovim Demo Architecture (10 subsections)
- [x] Write Section 5: Web Demo Architecture (5 subsections)
- [x] Write Section 6: Graph Viewer Architecture (7 subsections)
- [x] Write Section 7: Crossover Interfaces (12 subsections)
- [x] Write Section 8: Unified SQLite Database (8 subsections)
- [x] Write Section 9: Startup & Lifecycle (5 subsections)

## Round 2: Post-Refactor Audit
- [x] Read entire Remora library source tree (all files)
- [x] Read full DEMO_ARCHITECTURE.md (3158 lines, all 9 sections)
- [x] Identify discrepancies between document and current source
- [x] Fix 1: CSTNode — frozen dataclass → frozen Pydantic BaseModel with custom __hash__ (Section 2.2)
- [x] Fix 2: SubscriptionPattern — @dataclass → Pydantic BaseModel (Section 2.5)
- [x] Fix 3: parse_file() — removed false claim that ASTWatcher uses it (Section 2.2)
- [x] Fix 4: EventBus — added missing clear() method documentation (Section 2.S)
- [x] Fix 5: Section 9.4 routes — /graph, /sidebar, /stream → /subscribe, /agent/*, /events, /command
- [x] Fix 6: Section 9.4 — removed false "never writes" claim, documented push_command() exception
- [x] Fix 7: Section 8.3 — SubscriptionPattern "dataclass" → "Pydantic BaseModel"
- [x] Fix 8: ToolSchema — dataclass → Pydantic BaseModel (Section 2.3)
- [x] Fix 9: to_row() code — asdict()/is_dataclass() → model_dump() (Section 7.4)
- [x] Fix 10: Line number references — to_row 106-116→104-112, from_row 118-129→114-125, to_system_prompt 143-173→139-169 (Section 7.4)
- [x] Fix 11: "List and dataclass fields" → "List and nested Pydantic model fields" (Section 7.4)
- [x] Final review pass — verified all remaining sections match current source

## Project Tracking
- [x] Update PROGRESS.md with final status
- [x] Update CONTEXT.md with final summary

## Final Stats

- **Output file**: `/home/andrew/Documents/Projects/remora-demo/DEMO_ARCHITECTURE.md`
- **Total lines**: ~3168 (grew slightly from fixes adding __hash__ documentation)
- **Sections**: 9 major, ~55 subsections
- **Status**: COMPLETE — document matches current Remora library source
