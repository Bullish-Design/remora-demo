# PLAN — remora-ui-sigma-refactor

## ABSOLUTE RULE
**NO SUBAGENTS.** All work for this project is performed directly in-repo.

## Goal
Completely replace Cytoscape.js graph rendering in `remora-ui` with Sigma.js + Graphology while preserving existing remora-ui features (live events, companion sidebar/chat, replay scrubber, cursor focus).

## Architecture direction
- Graph engine: Sigma.js
- Graph model: Graphology
- Layout: Graphology-compatible layout strategy (initial deterministic layout + optional force refinement)
- Interaction bridge: Existing Datastar store and companion HTTP endpoints

## Phases

### Phase 0 — Baseline + safety rails
- Capture current behavior baseline (graph load success, event log, sidebar open, chat request path, replay controls present).
- Add temporary runtime diagnostics in UI console for node/edge count and frame stutter observations.
- Acceptance:
  - Can compare pre/post migration behavior quickly.

### Phase 1 — Introduce Sigma scaffold
- Add Sigma.js + Graphology assets to `index.html`.
- Create a dedicated graph adapter layer in `main.js` (or split file) abstracting:
  - `loadGraphData()`
  - `renderGraph()`
  - `focusNode(nodeId)`
  - `highlightEventNode(nodeId, eventType)`
  - `applyReplaySnapshot()`
- Acceptance:
  - UI boots with Sigma canvas and no Cytoscape dependency in runtime path.

### Phase 2 — Data model conversion
- Convert `/graph/data` payload into Graphology nodes/edges.
- Handle missing/invalid IDs safely.
- Implement fallback for parent relationships (visual grouping strategy without Cytoscape compounds).
- Acceptance:
  - Graph renders all nodes without stacking collapse.
  - Panning/zooming remains smooth at current large scale.

### Phase 3 — Interaction parity
- Re-implement:
  - Node click -> sidebar open
  - Event-based node flash/highlight
  - CursorFocusEvent highlight behavior
  - Event log click -> graph focus
- Acceptance:
  - Existing workflows functionally match Cytoscape version.

### Phase 4 — Replay parity
- Rewire replay scrubber to update Sigma/Graphology node attributes.
- Ensure live mode <-> replay mode transitions do not leak listeners.
- Acceptance:
  - Replay scrubber updates node visual state reliably.

### Phase 5 — Performance pass
- Apply Sigma performance optimizations:
  - label culling / reduced label density
  - edge reduction strategies for viewport interaction
  - batched updates for SSE events
- Acceptance:
  - Interaction remains responsive for large graphs.
  - No major freeze when events stream continuously.

### Phase 6 — Cleanup and docs
- Remove obsolete Cytoscape code and scripts.
- Update README/run docs to describe Sigma architecture.
- Add or update tests covering:
  - app serving
  - static asset presence
  - minimal graph adapter behaviors (if unit-testable)
- Acceptance:
  - No Cytoscape references remain in `remora-ui`.
  - Tests pass.

## Deliverables
- Updated `remora-ui` frontend using Sigma.js
- Updated docs
- Updated/added tests
- Performance notes and known limitations

## Exit criteria
- Graph view fully migrated to Sigma.js with feature parity for core flows.
- Companion sidebar/chat and replay remain operational.
- UI performance improved for very large node counts.

## ABSOLUTE RULE (REPEATED)
**NO SUBAGENTS.** Do all implementation and debugging directly.
