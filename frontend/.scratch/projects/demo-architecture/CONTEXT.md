# CONTEXT: DEMO_ARCHITECTURE.md

## Current State

**PROJECT COMPLETE.**

The DEMO_ARCHITECTURE.md document has been written in full at `/home/andrew/Documents/Projects/remora-demo/DEMO_ARCHITECTURE.md`. It is 1715 lines covering 8 major sections and 51 subsections.

## What Was Done

1. Read all Remora source files from `/home/andrew/Documents/Projects/remora/src/remora/`:
   - Core: events, event_bus, event_store, agent_node, discovery, subscriptions, projections, workspace, cairn_bridge, cairn_externals, swarm_executor, swarm_state, agent_state, config, chat, reconciler, errors, tools/grail, tools/swarm
   - Service: api, handlers, datastar, chat_service
   - Adapters: starlette
   - LSP: server, runner, db, graph, watcher, models, notifications, handlers/*, __main__
   - UI: projector, view, components/*
   - Extensions, CLI main

2. Created project tracking at `frontend/.scratch/projects/demo-architecture/`

3. Wrote DEMO_ARCHITECTURE.md using TOC-first approach, section by section:
   - Section 1: System Overview (architecture diagram, three modes of operation)
   - Section 2: Remora Core Architecture (10 subsections covering every core module)
   - Section 3: The Data Flow Pipeline (5 subsections tracing source code → agent turn)
   - Section 4: Neovim Demo Architecture (9 subsections covering entire LSP layer)
   - Section 5: Web Demo Architecture (6 subsections: service, adapter, Datastar, UI, chat, graph viewer)
   - Section 6: Crossover Interfaces (12 subsections — the main focus — all boundaries documented with data shapes and gotchas)
   - Section 7: Shared State & SQLite Databases (5 databases with full schemas)
   - Section 8: Startup & Lifecycle (4 startup modes documented step by step)

## Note

NVIM_DEMO_CONCEPT.md was listed as a reference doc but does not exist in the repo. The Neovim demo section was written from the actual LSP source code instead.
