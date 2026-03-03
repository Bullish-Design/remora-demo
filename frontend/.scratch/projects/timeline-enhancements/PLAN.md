# Timeline Enhancements — Implementation Plan

**NEVER use subagents (the Task tool). Do ALL work directly. NO EXCEPTIONS.**

> 13 enhancements to the Agent Timeline Debugger swimlane UI, implemented via TDD.

## Table of Contents

1. [Overview](#1-overview) — What we're building, why, and the phased approach
2. [Phase A: Quick Wins](#2-phase-a-quick-wins) — Event Type Legend, Follow Mode, Correlation Chain Highlighting
3. [Phase B: Core Interactivity](#3-phase-b-core-interactivity) — Filter Controls UI, Keyboard Navigation, Event Search
4. [Phase C: Spatial Awareness](#4-phase-c-spatial-awareness) — Minimap/Overview Bar, Agent Grouping/Collapsing
5. [Phase D: Advanced Features](#5-phase-d-advanced-features) — Event Replay/Scrub, Performance Flame View, Time Range Brush, Export/Share
6. [Phase E: Polish](#6-phase-e-polish) — Multi-Timeline Comparison
7. [Dependency Graph](#7-dependency-graph) — What depends on what
8. [Files to Modify](#8-files-to-modify) — Every file that gets touched
9. [Test Strategy](#9-test-strategy) — TDD cadence and test count estimates
10. [Verification](#10-verification) — How to confirm everything works

---

## 1. Overview

The base timeline debugger is complete and committed. It displays agent events as a swimlane SVG with zoom/pan, hover tooltips, click-to-inspect, and SSE live updates. The 13 enhancements add filtering, navigation, search, replay, export, and comparison capabilities.

### Implementation order

Phases are ordered by value-to-effort ratio and dependency:

| Phase | Items | Est. Tests | Rationale |
|-------|-------|-----------|-----------|
| A | Legend, Follow, Correlation Highlight | ~25 | Quick wins, establish data attributes other phases need |
| B | Filter Controls, Keyboard Nav, Search | ~30 | Core interactivity, server-side filter plumbing |
| C | Minimap, Agent Grouping | ~18 | Spatial awareness for large timelines |
| D | Replay, Flame View, Time Brush, Export | ~55 | Advanced features, highest complexity |
| E | Multi-Timeline Comparison | ~18 | Polish, requires all other features stable |

### TDD cadence for every enhancement

1. Write failing tests for data layer changes (if any) → implement → verify
2. Write failing tests for SVG rendering changes → implement → verify
3. Write failing tests for view/CSS additions → implement → verify
4. Run full suite: `python -m pytest tests/ -q`

---

## 2. Phase A: Quick Wins

### A1. Event Type Legend (~8 tests)

**What**: Color-coded legend from `EVENT_TYPE_COLORS`, click-to-filter via CSS classes.

**Data layer**: None.

**SVG changes** (`timeline/svg.py`):
- Add `data-event-type="{event_type}"` attribute to event markers in `render_event_marker()`
- New function `render_legend(event_types: list[str]) -> str` — horizontal strip of color dots with labels
- `render_timeline_svg()` calls `render_legend()` with the set of event types present in data

**View changes** (`timeline/views.py`):
- Add legend HTML in the shell (either above SVG or in controls bar)
- JS: click legend item → toggle `.hidden` on all markers of that `data-event-type`

**CSS changes** (`timeline/css.py`):
- `.timeline-legend`, `.legend-item`, `.legend-dot`, `.legend-item.legend-disabled`
- `.event-marker.hidden { display: none; }`

**Tests**: data-event-type attr on markers, legend contains all present types, legend omits absent types, legend items have correct colors, hidden class behavior

### A2. Follow Mode (~5 tests)

**What**: Toggle button, auto-scroll to latest events on SSE update, auto-disable on manual pan.

**Data layer**: None.

**View changes** (`timeline/views.py`):
- Add "Follow" button in controls bar: `<button class="btn" id="follow-btn">Follow</button>`
- JS: `window.__timelineFollowMode` flag. On SSE update (MutationObserver on `#timeline-svg`), if follow mode active, calculate rightmost marker cx and set pan transform. On mousedown in pane, disable follow mode.

**CSS changes** (`timeline/css.py`):
- `.btn.active { background: var(--blue); color: #1e1e2e; }` (already exists)

**Tests**: Follow button present in shell, follow JS variable initialized, auto-disable on pan logic present, SSE update handler references follow mode

### A3. Correlation Chain Highlighting (~8 tests)

**What**: Click event → highlight its correlation chain, dim everything else.

**Data layer**: None.

**SVG changes** (`timeline/svg.py`):
- Add `data-correlation-id="{correlation_id}"` attribute to markers in `render_event_marker()` (when correlation_id is not None)
- Add `data-correlation-id="{cid}"` to correlation lines in `render_correlation_line()` — needs new param

**View changes** (`timeline/views.py`):
- JS: on marker click, read `data-correlation-id`, add `.highlight` to matching markers/lines, add `.dim` to non-matching. Click empty space or Escape → clear.

**CSS changes** (`timeline/css.py`):
- `.event-marker.dim { opacity: 0.2; }`
- `.event-marker.highlight { filter: drop-shadow(0 0 3px currentColor); }`
- `.correlation-line.highlight { opacity: 0.8; stroke-width: 2; }`
- `.correlation-line.dim { opacity: 0.05; }`

**Tests**: data-correlation-id on markers, data-correlation-id on correlation lines, CSS contains dim/highlight classes, JS handler references correlation highlighting

---

## 3. Phase B: Core Interactivity

### B1. Filter Controls UI (~12 tests)

**What**: Event type filter, agent multi-select, time range, correlation ID, limit slider. Server-side filtering.

**Data layer** (`timeline/state.py`):
- Add `event_types: list[str] | None = None` parameter to `read_timeline_data()`
- Add `WHERE event_type IN (...)` clause when event_types is provided

**View changes** (`timeline/views.py`):
- Controls bar HTML above the SVG: event type multi-select, agent multi-select, since/until inputs, correlation ID text input, limit slider
- New function `render_controls_bar(data: TimelineData) -> str` — populates dropdowns from data.agents and observed event types
- Datastar signals for filter state, `data-on-change` triggers re-subscribe

**Route changes** (`graph/app.py`):
- `timeline_subscribe` handler: parse query params (`c.req.query`) for `event_types`, `agent_ids`, `since`, `until`, `correlation_id`, `limit` and pass to `read_timeline_data()`

**Tests**: event_types filter in data layer, controls bar HTML present in shell, dropdowns populated from data, query param parsing in subscribe handler source

### B2. Keyboard Navigation (~10 tests)

**What**: j/k (lanes), h/l (events), Enter (inspect), Escape (close), f (follow), c (correlation), +/- (zoom), 0 (reset), / (search), ? (help)

**Data layer**: None.

**View changes** (`timeline/views.py`):
- JS: keydown handler with all key bindings
- Focus tracking: `focusAgent`, `focusEvent` indices, visual ring on focused marker (`.focused` CSS class)
- Event index rebuild on SSE update: 2D array `agentEvents[agentIdx][eventIdx]` from SVG markers
- Help overlay HTML (hidden by default, shown on `?`)

**CSS changes** (`timeline/css.py`):
- `.event-marker.focused { stroke: var(--lavender); stroke-width: 2; }`
- `.keyboard-help` overlay styles

**Tests**: keydown handler present, all key bindings referenced, focused class in CSS, help overlay in shell HTML, event index rebuild logic

### B3. Event Search (~10 tests)

**What**: Search box (`/` to activate), LIKE queries across event fields, highlight matches.

**Data layer** (`timeline/state.py`):
- Add `search: str | None = None` parameter to `read_timeline_data()`
- When provided, add `WHERE (event_type LIKE ? OR from_agent LIKE ? OR to_agent LIKE ? OR payload LIKE ?)` with `%search%` wildcards
- Return matching event IDs in a new `search_matches: list[int]` field on `TimelineData`

**SVG changes** (`timeline/svg.py`):
- If search_matches provided, add `.search-match` class to matching markers

**View changes** (`timeline/views.py`):
- Search input (hidden by default, shown on `/` key): `<input id="search-input" class="search-input" placeholder="Search events...">`
- JS: on input, re-subscribe with `search` query param. Up/Down arrows navigate between matches.

**CSS changes** (`timeline/css.py`):
- `.search-input` styles
- `.event-marker.search-match { stroke: var(--yellow); stroke-width: 2; }`

**Tests**: search param in data layer, LIKE query behavior, search_matches field, search input in shell, search CSS classes

---

## 4. Phase C: Spatial Awareness

### C1. Minimap / Overview Bar (~10 tests)

**What**: Thin density histogram SVG, viewport indicator rectangle, click-to-jump.

**Data layer**: None (uses existing TimelineData).

**SVG changes** (`timeline/svg.py`):
- New function `render_minimap(data: TimelineData, width: int, height: int = 40) -> str`
- Bins events into N time buckets, renders as rects with opacity proportional to count
- Viewport indicator rectangle (semi-transparent overlay)

**View changes** (`timeline/views.py`):
- Minimap div below main SVG: `<div id="minimap" class="minimap">...</div>`
- JS: click-to-jump (map click x to time position, set pan transform), viewport sync on zoom/pan

**CSS changes** (`timeline/css.py`):
- `.minimap` container styles

**Tests**: minimap function returns SVG, density bins calculated correctly, viewport rect present, click handler in JS, minimap container in shell

### C2. Agent Grouping / Collapsing (~8 tests)

**What**: Auto-hide idle agents, collapsible group headers.

**Data layer** (`timeline/state.py`):
- Extract agent metadata: parse agent names for grouping (by prefix convention, e.g. `module.function`)
- New helper `group_agents(agents: list[str]) -> dict[str, list[str]]` — groups by common prefix

**SVG changes** (`timeline/svg.py`):
- Group headers as clickable text elements with collapse/expand indicator
- `data-agent-group` attribute on lane backgrounds

**View changes** (`timeline/views.py`):
- "Hide idle" checkbox in controls bar
- JS: toggle group visibility, collapse/expand click handlers

**CSS changes** (`timeline/css.py`):
- `.agent-group-header` styles, `.lane-bg.collapsed { display: none; }`

**Tests**: group_agents function, group headers in SVG, hide-idle checkbox, collapsed class

---

## 5. Phase D: Advanced Features

### D1. Event Replay / Scrub (~18 tests)

**What**: Play/Pause/Step/Scrub controls, client-side progressive event masking.

**Data layer**: None (uses existing events list).

**View changes** (`timeline/views.py`):
- Replay controls bar: Play, Pause, Step Forward, Step Back, Speed selector, Scrub slider
- New function `render_replay_controls() -> str`
- JS: replay state machine (idle/playing/paused), `replayTo(index)` function that shows/hides markers by `data-event-id`, auto-play with configurable speed, scrub slider input handler

**CSS changes** (`timeline/css.py`):
- `.replay-controls` bar styles, `.replay-btn`, `.replay-slider`, `.replay-speed`

**Tests**: replay controls HTML present, play/pause/step buttons, scrub slider, speed selector, replayTo function in JS, event masking logic, replay state machine

### D2. Performance Flame View (~15 tests)

**What**: Pair AgentStart→AgentComplete as spans, render as `<rect>` bars, toggle Points/Bars mode.

**Data layer** (`timeline/state.py`):
- New function `extract_spans(events: list[dict]) -> list[dict]` — pairs start/end events by agent+correlation_id
- Each span: `{"agent": str, "start": float, "end": float, "correlation_id": str | None, "event_type": "span"}`

**SVG changes** (`timeline/svg.py`):
- New function `render_flame_bar(*, x: float, y: float, width: float, height: float, agent: str, color: str) -> str` — `<rect>` element
- New function `render_flame_view(data: TimelineData, spans: list[dict], width: int) -> str` — flame chart SVG
- `render_timeline_svg()` accepts optional `mode: str = "points"` parameter; when `"bars"`, calls flame view

**View changes** (`timeline/views.py`):
- Mode toggle in controls bar: "Points" | "Bars"
- JS: toggle sends mode param to subscribe endpoint

**CSS changes** (`timeline/css.py`):
- `.flame-bar` styles (with hover effects)

**Tests**: extract_spans pairing logic, unpaired events handled, flame bar rendering, flame view SVG, mode toggle in shell, bars mode SVG output

### D3. Time Range Brush (~12 tests)

**What**: Overview SVG with draggable range selector, syncs with main timeline and server filters.

**Data layer**: None (reuses minimap data).

**SVG changes** (`timeline/svg.py`):
- New function `render_brush(data: TimelineData, width: int, height: int = 50) -> str`
- Draggable range indicator (two handles + fill rect)

**View changes** (`timeline/views.py`):
- Brush container below minimap
- JS: drag interaction for handles, syncs `since`/`until` on drag end, re-subscribes

**CSS changes** (`timeline/css.py`):
- `.brush-container`, `.brush-handle`, `.brush-range` styles

**Tests**: brush SVG renders, handles present, range rect present, drag handler JS, sync logic

### D4. Export / Share (~8 tests)

**What**: SVG/PNG export (client-side), JSON export (new route), share URL with filter params.

**Data layer**: None.

**Route changes** (`graph/app.py`):
- New handler `timeline_export(state)` for `GET /timeline/export` — returns JSON event data
- Parse query params for filters, return filtered events as JSON

**View changes** (`timeline/views.py`):
- Export dropdown/buttons in controls bar: "SVG", "PNG", "JSON", "Copy Link"
- JS: SVG export (serialize `#timeline-svg`), PNG export (canvas + drawImage), JSON (fetch `/timeline/export`), Copy Link (build URL with current filter params)

**CSS changes** (`timeline/css.py`):
- `.export-menu` styles

**Tests**: export buttons in shell, export route in app.py source, SVG serialization logic in JS, JSON route handler, share URL builder

---

## 6. Phase E: Polish

### E1. Multi-Timeline Comparison (~18 tests)

**What**: Split/overlay view of two time ranges, diff markers.

**Data layer** (`timeline/state.py`):
- New function `diff_timelines(a: TimelineData, b: TimelineData) -> dict` — identifies events/agents unique to each

**SVG changes** (`timeline/svg.py`):
- New function `render_comparison_svg(data_a: TimelineData, data_b: TimelineData, width: int) -> str`
- Stacked or overlaid SVGs with distinct color schemes per range

**View changes** (`timeline/views.py`):
- Comparison mode UI: time range selectors for A and B, split/overlay toggle
- New function `render_comparison_shell(data_a: TimelineData, data_b: TimelineData) -> str`

**Route changes** (`graph/app.py`):
- New handler `timeline_compare(state)` for `GET /timeline/compare` — renders comparison view

**CSS changes** (`timeline/css.py`):
- `.comparison-view`, `.timeline-a`, `.timeline-b`, `.diff-marker` styles

**Tests**: diff_timelines function, comparison SVG rendering, split layout, overlay mode, diff markers, comparison route, comparison shell HTML

---

## 7. Dependency Graph

```
A1 (Legend) ─────────┐
A2 (Follow) ──────┐  │
A3 (Correlation) ──┤  │
                   │  │
B1 (Filter UI) ←───┘──┘  (uses data-event-type from A1)
B2 (Keyboard) ←── A2 (f key toggles follow), A3 (c key triggers correlation)
B3 (Search) ←──── B1 (search is another filter param)
                   │
C1 (Minimap) ←────┘  (minimap shows filtered view)
C2 (Grouping)
                   │
D1 (Replay) ←─────┘  (replay respects current filters)
D2 (Flame) ←────── B1 (mode toggle is a filter-like control)
D3 (Brush) ←────── C1 (brush builds on minimap)
D4 (Export) ←────── B1 (exports respect current filters)
                   │
E1 (Compare) ←────┘  (comparison uses filter + rendering infrastructure)
```

Phase A MUST be done first because later phases depend on `data-event-type` and `data-correlation-id` attributes that A1 and A3 add.

---

## 8. Files to Modify

### Source files

| File | Changes |
|------|---------|
| `timeline/state.py` | Add `event_types`, `search` params. Add `search_matches` field to TimelineData. Add `extract_spans()`, `group_agents()`, `diff_timelines()` functions. |
| `timeline/svg.py` | Add `data-event-type`, `data-correlation-id` attrs. Add `render_legend()`, `render_minimap()`, `render_flame_bar()`, `render_flame_view()`, `render_brush()`, `render_comparison_svg()`. Update `render_event_marker()` and `render_correlation_line()` signatures. |
| `timeline/css.py` | Add styles for legend, highlight/dim, follow, search, minimap, replay, flame, brush, export, comparison, keyboard help, focused marker. |
| `timeline/views.py` | Add `render_controls_bar()`, `render_replay_controls()`, `render_comparison_shell()`. Extend shell with legend, controls, minimap, brush, search, keyboard JS, replay JS, export JS, comparison UI. |
| `graph/app.py` | Add `/timeline/export` and `/timeline/compare` routes. Update `timeline_subscribe` to parse filter query params. |

### Test files

| File | Changes |
|------|---------|
| `tests/test_timeline_state.py` | Tests for `event_types` filter, `search` param, `extract_spans()`, `group_agents()`, `diff_timelines()` |
| `tests/test_timeline_svg.py` | Tests for new attributes, `render_legend()`, `render_minimap()`, `render_flame_bar()`, `render_flame_view()`, `render_brush()`, `render_comparison_svg()` |
| `tests/test_timeline_views.py` | Tests for all new UI elements, controls bar, keyboard, replay, export, comparison shell |
| `tests/test_app.py` | Tests for new routes (`/timeline/export`, `/timeline/compare`) |

---

## 9. Test Strategy

- **TDD mandatory**: Write failing test first, implement, verify.
- **Test command**: `cd /home/andrew/Documents/Projects/remora-demo/frontend && python -m pytest tests/ -q`
- **Pre-existing failure**: `test_cross_process.py::test_nodes_written_by_projection_readable_by_graph_state` (scaffold vs idle) — IGNORE this.
- **Baseline**: 253 passed, 2 skipped, 1 pre-existing failure.
- **Expected final**: ~400 passed (roughly 146 new tests across all phases).
- **Run full suite after each enhancement** to verify no regressions.

---

## 10. Verification

After all 13 enhancements are complete:

1. Full test suite passes: `python -m pytest tests/ -q` shows all new tests passing
2. No regressions: same 253 pre-existing tests still pass
3. All new functions have tests
4. All new CSS classes have corresponding test assertions
5. All new JS behaviors have test assertions checking their presence in rendered HTML
6. Update PROGRESS.md with final task status
7. Update CONTEXT.md with completion summary

---

**NEVER use subagents (the Task tool). Do ALL work directly. NO EXCEPTIONS.**
