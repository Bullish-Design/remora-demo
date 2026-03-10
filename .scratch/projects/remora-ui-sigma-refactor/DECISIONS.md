# DECISIONS — remora-ui-sigma-refactor

## D-001 — Use Sigma.js + Graphology as primary graph stack
- Status: accepted
- Rationale:
  - Better fit for high-node-count interactive rendering than current setup.
  - Mature ecosystem for graph data/state and rendering.

## D-002 — Keep existing remora API contract (no backend schema churn for migration)
- Status: accepted
- Rationale:
  - Limits risk and speeds migration.
  - Allows frontend refactor to proceed independently of backend evolution.

## D-003 — Preserve Datastar for sidebar/chat signal wiring
- Status: accepted
- Rationale:
  - Avoid unnecessary refactor of non-graph reactive behavior.
  - Keeps migration focused on graph engine swap.

## D-004 — Disable heavy auto-indexing by default when enabling companion in serve path
- Status: accepted
- Rationale:
  - Reduces startup overhead during UI-focused development.
  - Can be toggled on explicitly when needed.
