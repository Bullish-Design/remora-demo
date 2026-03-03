# Progress — Timeline Enhancements

> Task tracker for all 13 enhancements. Update checkboxes as each is completed.

**Baseline**: 253 tests passed, 2 skipped, 1 pre-existing failure

---

## Phase A: Quick Wins (~25 tests)

- [ ] **A1: Event Type Legend** (~8 tests)
  - `data-event-type` attr on markers, `render_legend()`, legend CSS, click-to-filter JS
  - Files: `svg.py`, `css.py`, `views.py` | Tests: `test_timeline_svg.py`, `test_timeline_views.py`

- [ ] **A2: Follow Mode** (~5 tests)
  - Follow button, `__timelineFollowMode` JS, MutationObserver auto-scroll
  - Files: `views.py`, `css.py` | Tests: `test_timeline_views.py`

- [ ] **A3: Correlation Chain Highlighting** (~8 tests)
  - `data-correlation-id` attr, dim/highlight CSS, `highlightCorrelation()`/`clearHighlight()` JS
  - Files: `svg.py`, `css.py`, `views.py` | Tests: `test_timeline_svg.py`, `test_timeline_views.py`

**Phase A test count after completion**: 253 + ~25 = ~278

---

## Phase B: Core Interactivity (~30 tests)

- [ ] **B1: Filter Controls UI** (~12 tests)
  - `event_types` param in `read_timeline_data()`, `render_controls_bar()`, query param parsing
  - Files: `state.py`, `views.py`, `app.py` | Tests: `test_timeline_state.py`, `test_timeline_views.py`, `test_app.py`

- [ ] **B2: Keyboard Navigation** (~10 tests)
  - Vim-style keys, focus tracking, `agentEvents` 2D array, help overlay
  - Files: `views.py`, `css.py` | Tests: `test_timeline_views.py`

- [ ] **B3: Event Search** (~10 tests)
  - `search` param + `search_matches` field, LIKE queries, search input UI
  - Files: `state.py`, `svg.py`, `views.py`, `css.py` | Tests: `test_timeline_state.py`, `test_timeline_svg.py`, `test_timeline_views.py`

**Phase B test count after completion**: ~278 + ~30 = ~308

---

## Phase C: Spatial Awareness (~18 tests)

- [ ] **C1: Minimap / Overview Bar** (~10 tests)
  - `render_minimap()` density histogram SVG, viewport indicator, click-to-jump JS
  - Files: `svg.py`, `views.py`, `css.py` | Tests: `test_timeline_svg.py`, `test_timeline_views.py`

- [ ] **C2: Agent Grouping / Collapsing** (~8 tests)
  - `group_agents()`, `data-agent-group` attr, collapsible headers, hide-idle checkbox
  - Files: `state.py`, `svg.py`, `views.py`, `css.py` | Tests: `test_timeline_state.py`, `test_timeline_svg.py`, `test_timeline_views.py`

**Phase C test count after completion**: ~308 + ~18 = ~326

---

## Phase D: Advanced Features (~55 tests)

- [ ] **D1: Event Replay / Scrub** (~18 tests)
  - `render_replay_controls()`, play/pause/step/scrub/speed, `replayTo(index)`, replay state machine JS
  - Files: `views.py`, `css.py` | Tests: `test_timeline_views.py`

- [ ] **D2: Performance Flame View** (~15 tests)
  - `extract_spans()`, `render_flame_bar()`, `render_flame_view()`, Points/Bars mode toggle
  - Files: `state.py`, `svg.py`, `views.py`, `css.py` | Tests: `test_timeline_state.py`, `test_timeline_svg.py`, `test_timeline_views.py`

- [ ] **D3: Time Range Brush** (~12 tests)
  - `render_brush()` with draggable handles, range rect, drag JS syncing since/until
  - Files: `svg.py`, `views.py`, `css.py` | Tests: `test_timeline_svg.py`, `test_timeline_views.py`

- [ ] **D4: Export / Share** (~8 tests)
  - SVG/PNG/JSON export buttons, `/timeline/export` route, Copy Link, export JS
  - Files: `views.py`, `css.py`, `app.py` | Tests: `test_timeline_views.py`, `test_app.py`

**Phase D test count after completion**: ~326 + ~55 = ~381

---

## Phase E: Polish (~18 tests)

- [ ] **E1: Multi-Timeline Comparison** (~18 tests)
  - `diff_timelines()`, `render_comparison_svg()`, `render_comparison_shell()`, `/timeline/compare` route
  - Files: `state.py`, `svg.py`, `views.py`, `css.py`, `app.py` | Tests: `test_timeline_state.py`, `test_timeline_svg.py`, `test_timeline_views.py`, `test_app.py`

**Phase E test count after completion**: ~381 + ~18 = ~399

---

## Summary

| Phase | Status | Tests Added |
|-------|--------|------------|
| A: Quick Wins | Pending | ~25 |
| B: Core Interactivity | Pending | ~30 |
| C: Spatial Awareness | Pending | ~18 |
| D: Advanced Features | Pending | ~55 |
| E: Polish | Pending | ~18 |
| **Total** | **0/13 done** | **~146** |
