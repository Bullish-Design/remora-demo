# Next Steps — Decisions

## 1. Skip copying analysis files from remora repo
**Decision:** Do not copy `STRUCTURED_AGENTS_CODEBASE_ANALYSIS.md`, `HOW_TO_USE_GRAIL.md`, or `GRAIL_CODEBASE_ANALYSIS.md` from the remora repo.
**Rationale:** remora-demo already has full snapshots of all five libraries in `.context/`. The skills files provide condensed mental models. Copying redundant analysis files would be noise.

## 2. Skills file scope
**Decision:** Two skills files — `stario-datastar.md` (frontend framework) and `remora.md` (backend framework + data layer). No separate file for structured-agents or Grail.
**Rationale:** An agent working on this demo needs to understand Stario (to build UI) and Remora (to integrate with backend). structured-agents and Grail are Remora internals — an agent only needs to know they exist, not their APIs, until they're working directly on the backend.

## 3. stario-api-notes.md placement
**Decision:** Place in `.scratch/skills/` alongside the other skills files, not in `.context/stario/`.
**Rationale:** It's a condensed reference written for agent consumption, not a library snapshot. Belongs with other agent-facing materials.
