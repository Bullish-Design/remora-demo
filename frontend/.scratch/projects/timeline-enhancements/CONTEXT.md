# Context — Timeline Enhancements

> Current state for resumption after compaction. Read this first when starting implementation.

---

## Status: READY FOR IMPLEMENTATION

The implementation guide is **complete**. All 11 project files exist and are ready for an implementing agent to use. No implementation work has been done yet — start at Phase A.

---

## Working Directory

```
/home/andrew/Documents/Projects/remora-demo/frontend
```

---

## What Exists — Base Timeline Debugger (COMPLETE, committed)

The base timeline debugger is a swimlane SVG visualization of agent events, fully working with 67 tests across 3 test files. **253 total tests pass, 2 skipped, 1 pre-existing failure** (scaffold vs idle in `test_cross_process.py` — ignore this).

**Source files** (all in `timeline/`):
- `state.py` — `TimelineData` dataclass + `read_timeline_data()` with filter params
- `svg.py` — `render_timeline_svg()`, `render_event_marker()`, `render_agent_label()`, `render_correlation_line()`, `render_time_axis()`, `EVENT_TYPE_COLORS`
- `css.py` — `timeline_css()` with Catppuccin Mocha theme
- `views.py` — `render_timeline_shell()` (full HTML page), `render_event_inspector()`

**Routes** (in `graph/app.py`): `GET /timeline`, `GET /timeline/subscribe` (SSE), `GET /timeline/event/*`

**Tests**: `tests/test_timeline_state.py` (19), `tests/test_timeline_svg.py` (24), `tests/test_timeline_views.py` (21), plus 3 timeline checks in `tests/test_app.py`

---

## What To Build — 13 Enhancements

No enhancements have been implemented yet. Start at Phase A, Enhancement A1.

| Phase | Enhancements | Est. Tests |
|-------|-------------|-----------|
| A | A1: Event Type Legend, A2: Follow Mode, A3: Correlation Chain Highlighting | ~25 |
| B | B1: Filter Controls UI, B2: Keyboard Navigation, B3: Event Search | ~30 |
| C | C1: Minimap/Overview Bar, C2: Agent Grouping/Collapsing | ~18 |
| D | D1: Event Replay/Scrub, D2: Performance Flame View, D3: Time Range Brush, D4: Export/Share | ~55 |
| E | E1: Multi-Timeline Comparison | ~18 |

---

## How To Use This Project Folder

Read files in this order:

1. **`PLAN.md`** — Master implementation plan. Overview of all 13 enhancements, dependency graph, files to modify, test strategy.
2. **`ARCHITECTURE.md`** — Complete reference to existing code. Package structure, data layer, SVG renderer, CSS theme, views, routes, coding conventions, color palette.
3. **`ASSUMPTIONS.md`** — Constraints and invariants. TDD rules, no-Stario-in-timeline, SafeString conventions, escaping, f-string generation, keyword-only args.
4. **`TESTING_GUIDE.md`** — Test patterns reference. Exact code examples of `_create_db()`, `_insert_event()`, `_make_data()`, assertion patterns, source-code-reading pattern.
5. **`PHASE_A_GUIDE.md`** through **`PHASE_E_GUIDE.md`** — Step-by-step implementation guides for each phase.
6. **`PROGRESS.md`** — Task tracker. Check boxes for all 13 enhancements. Update as you complete each one.

---

## Test Command

```bash
cd /home/andrew/Documents/Projects/remora-demo/frontend && python -m pytest tests/ -q
```

**Baseline**: 253 passed, 2 skipped, 1 pre-existing failure

---

## Next Action

Start Phase A, Enhancement A1 (Event Type Legend). Open `PHASE_A_GUIDE.md` for step-by-step instructions.
