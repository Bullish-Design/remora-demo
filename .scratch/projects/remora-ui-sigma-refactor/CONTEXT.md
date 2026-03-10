# CONTEXT — remora-ui-sigma-refactor

## Trigger
User requested a complete graph-engine migration to Sigma.js after observing:
- visually stacked/grouped nodes
- poor interaction performance in the current Cytoscape-based graph view

## Current repo state
- `remora-ui` is active and reachable.
- remora backend graph endpoints are working after runtime init fix.
- companion can be enabled via `remora serve --with-companion`.
- current frontend still contains Cytoscape implementation and a temporary large-graph mode.

## Immediate next step
Begin Phase 0/P1:
1. lock in baseline behavior
2. introduce Sigma+Graphology scaffold without breaking non-graph UI features

## Constraints
- Keep static/no-bundler architecture unless migration is blocked.
- Preserve existing endpoint contract with remora server.
- Keep sidebar/chat/replay features intact.

## Resume note
When resuming, start from `PLAN.md` Phase 0 and execute tasks in order, updating `PROGRESS.md` continuously.
