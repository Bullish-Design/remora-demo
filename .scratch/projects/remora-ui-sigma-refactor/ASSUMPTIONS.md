# ASSUMPTIONS — remora-ui-sigma-refactor

## Scope
- This project is a full frontend graph-engine refactor from Cytoscape.js to Sigma.js.
- The existing remora HTTP API contract remains the source of truth (`/graph/data`, `/events`, `/replay`, `/companion/*`).
- Sidebar/chat/replay features remain in scope and must survive the graph-engine swap.

## Performance assumptions
- Target graph size is currently up to ~9k nodes and can continue to grow.
- Current Cytoscape behavior (compound groups + force layout + labels) is too slow for this scale.
- Sigma.js + Graphology will provide materially better rendering and interaction performance.

## Stack assumptions
- Keep the current no-bundler/static approach (CDN assets + vanilla JS) unless blocked.
- Use Graphology as the data model for Sigma.js.
- Keep Datastar for reactive sidebar/chat signals.

## UX assumptions
- Graph must remain interactive while live events are streaming.
- Node click behavior must still open companion sidebar for that node.
- Event highlights and cursor focus highlights must remain visible and performant.

## Compatibility assumptions
- `GET /graph/data` may continue returning sparse/low-edge graphs; UI must not fail when edge count is low.
- Companion routes can still be unavailable (`503`) if server starts without companion; UI must degrade gracefully.
