# Testing Guide — Timeline Enhancements

> Comprehensive reference for writing tests for all 13 timeline enhancements.
> Copy these patterns exactly — they are extracted from the existing test suite.

## Table of Contents

1. [Running Tests](#1-running-tests) — Command, baseline, pre-existing failure
2. [Test File Layout](#2-test-file-layout) — Which file tests what
3. [DB Helper: `_create_db()`](#3-db-helper-_create_db) — In-memory SQLite setup
4. [Event Helper: `_insert_event()`](#4-event-helper-_insert_event) — Insert events with keyword args
5. [Data Helper: `_make_data()`](#5-data-helper-_make_data) — Build TimelineData for view tests
6. [Class-Based Test Grouping](#6-class-based-test-grouping) — Convention and naming
7. [String Fragment Assertions](#7-string-fragment-assertions) — SVG/HTML/CSS checking
8. [Source-Code-Reading Pattern](#8-source-code-reading-pattern) — Testing app.py without Stario imports
9. [Testing New Data Layer Functions](#9-testing-new-data-layer-functions) — Pattern for state.py additions
10. [Testing New SVG Functions](#10-testing-new-svg-functions) — Pattern for svg.py additions
11. [Testing New View Elements](#11-testing-new-view-elements) — Pattern for views.py additions
12. [Testing New CSS Classes](#12-testing-new-css-classes) — Pattern for css.py additions
13. [Testing New Routes](#13-testing-new-routes) — Pattern for app.py additions
14. [TDD Workflow](#14-tdd-workflow) — Step-by-step for each enhancement

---

## 1. Running Tests

```bash
cd /home/andrew/Documents/Projects/remora-demo/frontend && python -m pytest tests/ -q
```

**Baseline**: 253 passed, 2 skipped, 1 pre-existing failure.

**Pre-existing failure** (IGNORE):
- `tests/test_cross_process.py::test_nodes_written_by_projection_readable_by_graph_state` — scaffold vs idle mismatch. This is unrelated to timeline work.

**After each enhancement**: Run the full suite and verify:
- All pre-existing 253 tests still pass
- All new tests pass
- Same 2 skipped, same 1 failure

---

## 2. Test File Layout

| Test File | Tests What | Imports From |
|-----------|-----------|--------------|
| `tests/test_timeline_state.py` | Data layer: `read_timeline_data()`, filtering, `TimelineData` | `timeline.state` |
| `tests/test_timeline_svg.py` | SVG renderers: markers, labels, lines, axis, full SVG | `timeline.state`, `timeline.svg` |
| `tests/test_timeline_views.py` | Views: shell page, inspector, CSS | `timeline.state`, `timeline.views`, `timeline.css` |
| `tests/test_app.py` | Route wiring: reads `graph/app.py` source as text | `pathlib.Path` (no Stario import) |

All test files start with:

```python
"""Tests for timeline <description>."""

from __future__ import annotations
```

---

## 3. DB Helper: `_create_db()`

Used in `test_timeline_state.py` to create an in-memory SQLite database with the EventStore schema. Every data layer test starts by calling this.

```python
def _create_db() -> sqlite3.Connection:
    """Create an in-memory DB with the EventStore schema."""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript("""
        CREATE TABLE events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            graph_id TEXT NOT NULL DEFAULT 'test',
            event_type TEXT NOT NULL,
            payload TEXT NOT NULL DEFAULT '{}',
            timestamp REAL NOT NULL DEFAULT 0,
            created_at REAL NOT NULL DEFAULT 0,
            from_agent TEXT,
            to_agent TEXT,
            correlation_id TEXT,
            tags TEXT
        );
    """)
    conn.commit()
    return conn
```

**Key details**:
- `":memory:"` — no disk I/O, fast, isolated per test
- WAL journal mode matches production
- Schema matches the real EventStore `events` table exactly
- `graph_id` defaults to `'test'`
- `from_agent`, `to_agent`, `correlation_id`, `tags` are nullable

---

## 4. Event Helper: `_insert_event()`

Used in `test_timeline_state.py` to insert events into the test database. All params are keyword-only (after `*`).

```python
def _insert_event(
    conn: sqlite3.Connection,
    *,
    event_type: str = "Test",
    timestamp: float = 1.0,
    from_agent: str | None = None,
    to_agent: str | None = None,
    correlation_id: str | None = None,
    payload: str = "{}",
) -> int:
    """Insert an event and return its id."""
    cursor = conn.execute(
        "INSERT INTO events (graph_id, event_type, payload, timestamp, created_at, from_agent, to_agent, correlation_id) "
        "VALUES ('test', ?, ?, ?, ?, ?, ?, ?)",
        (event_type, payload, timestamp, timestamp, from_agent, to_agent, correlation_id),
    )
    conn.commit()
    return cursor.lastrowid  # type: ignore[return-value]
```

**Key details**:
- Returns the auto-incremented `id` (useful for correlation group assertions)
- `created_at` is set equal to `timestamp` for simplicity
- All parameters have sensible defaults — only override what you need
- `graph_id` is always `'test'`

**Usage examples** from the existing tests:

```python
# Minimal — just an agent and timestamp
_insert_event(conn, from_agent="beta", timestamp=1.0)

# With correlation
id1 = _insert_event(conn, from_agent="a", timestamp=1.0, correlation_id="c1")

# With specific event type
_insert_event(conn, from_agent="a", timestamp=1.0, event_type="AgentStart")

# With all fields
_insert_event(
    conn,
    from_agent="agent_x",
    to_agent="agent_y",
    timestamp=1.5,
    event_type="AgentStart",
    correlation_id="corr-1",
    payload='{"message": "hello"}',
)

# Multiple events for limit testing
for i in range(10):
    _insert_event(conn, from_agent="a", timestamp=float(i))
```

---

## 5. Data Helper: `_make_data()`

Used in `test_timeline_views.py` inside `TestRenderTimelineShell` to create a realistic `TimelineData` for view rendering tests. This is a method on the test class.

```python
class TestRenderTimelineShell:
    def _make_data(self) -> TimelineData:
        return TimelineData(
            agents=["agent_a", "agent_b"],
            events=[
                {
                    "event_id": 1,
                    "event_type": "AgentStart",
                    "timestamp": 1000.0,
                    "from_agent": "agent_a",
                    "to_agent": None,
                    "correlation_id": "c1",
                    "payload": "{}",
                },
                {
                    "event_id": 2,
                    "event_type": "AgentComplete",
                    "timestamp": 1001.0,
                    "from_agent": "agent_b",
                    "to_agent": None,
                    "correlation_id": "c1",
                    "payload": "{}",
                },
            ],
            correlation_groups={"c1": [1, 2]},
            time_range=(1000.0, 1001.0),
        )
```

**Key details**:
- 2 agents, 2 events, 1 correlation group — enough to test all structural elements
- Timestamps are realistic Unix-epoch-ish values (1000.0, 1001.0)
- All dict fields present (event_id, event_type, timestamp, from_agent, to_agent, correlation_id, payload)
- `TimelineData()` with no args produces empty data (used for empty-state tests)

**For new enhancements**, extend `_make_data()` or create variation helpers like:

```python
def _make_data_with_search_matches(self) -> TimelineData:
    return TimelineData(
        agents=["agent_a"],
        events=[...],
        search_matches=[1, 3],  # new field added in B3
        time_range=(1000.0, 1002.0),
    )
```

---

## 6. Class-Based Test Grouping

Every group of related tests is a class. Classes use descriptive names with `Test` prefix.

**Naming convention**: `Test` + `FunctionOrFeatureName`

**Existing examples**:

```python
# Data layer tests (test_timeline_state.py)
class TestTimelineDataEmpty:       # Empty DB behavior
class TestTimelineAgentOrdering:   # Agent ordering
class TestTimelineEventList:       # Event list structure
class TestTimelineCorrelationGroups:  # Correlation grouping
class TestTimelineTimeRange:       # Time range calculation
class TestTimelineFiltering:       # All filter params

# SVG tests (test_timeline_svg.py)
class TestRenderTimelineSvg:       # Full SVG output
class TestRenderEventMarker:       # Event marker circles
class TestRenderAgentLabel:        # Agent label text elements
class TestRenderCorrelationLine:   # Correlation connector lines
class TestRenderTimeAxis:          # Time axis with ticks

# View tests (test_timeline_views.py)
class TestTimelineCss:             # CSS output
class TestRenderTimelineShell:     # Full HTML page
class TestRenderEventInspector:    # Inspector panel

# App tests (test_app.py)
class TestAppImport:               # Route wiring checks
```

**For new enhancements**, follow the same pattern:

```python
# Phase A additions
class TestRenderLegend:           # in test_timeline_svg.py
class TestFollowMode:             # in test_timeline_views.py
class TestCorrelationHighlight:   # split across svg + views tests

# Phase B additions
class TestEventTypeFilter:        # in test_timeline_state.py
class TestRenderControlsBar:      # in test_timeline_views.py
class TestKeyboardNavigation:     # in test_timeline_views.py
class TestSearchParam:            # in test_timeline_state.py
class TestSearchUI:               # in test_timeline_views.py

# Phase D additions
class TestExtractSpans:           # in test_timeline_state.py
class TestRenderFlameBar:         # in test_timeline_svg.py
class TestRenderFlameView:        # in test_timeline_svg.py
class TestRenderReplayControls:   # in test_timeline_views.py
```

---

## 7. String Fragment Assertions

All tests for SVG, HTML, and CSS output use string fragment assertions — check that specific substrings are present in the rendered output. **Never parse HTML/SVG as XML.**

### SVG attribute assertions

```python
# Check data attributes
assert 'data-event-id="42"' in result
assert 'data-event-type="AgentStart"' in result

# Check element presence
assert "<circle" in result
assert "<svg" in result
assert "</svg>" in result

# Check CSS class
assert "event-marker" in result
assert "correlation-line" in result
assert "lane-bg" in result

# Check position values
assert 'cx="150.0"' in result
assert 'cy="75.0"' in result
assert f'r="{MARKER_RADIUS}"' in result

# Check color values (Catppuccin Mocha hex)
assert "#f38ba8" in result  # red for AgentError
```

### HTML structure assertions

```python
# Full page structure
assert "<!DOCTYPE html>" in result
assert "<html" in result
assert "</html>" in result

# Specific elements
assert 'id="timeline-svg"' in result
assert 'id="inspector"' in result
assert "<style>" in result

# Content text
assert "No events" in result
assert "2 events" in result
assert "Timeline" in result

# Script/behavior
assert "datastar" in result
assert "data-on-load" in result
assert "/timeline/subscribe" in result
assert "wheel" in result
```

### CSS class assertions

```python
# Check CSS contains selectors
assert ".timeline-canvas" in result
assert ".event-marker" in result
assert ".event-marker:hover" in result
assert ".inspector" in result
```

### XSS escape assertions

```python
# Verify HTML-escaped output
assert "<script>" not in result
assert "&lt;script&gt;" in result
assert "<b>evil</b>" not in result  # if input had this
```

### Negative assertions (absence)

```python
# Verify something is NOT in output
assert "a_very_long_agent_name_indeed" not in result  # truncated
assert None not in result.agents  # null agents excluded
```

---

## 8. Source-Code-Reading Pattern

Used in `test_app.py` for testing route wiring and handler existence **without importing Stario** (which can't be imported in all test environments).

```python
class TestAppImport:
    def test_app_source_has_timeline_routes(self) -> None:
        """Verify timeline routes are wired."""
        from pathlib import Path

        source = (Path(__file__).parent.parent / "graph" / "app.py").read_text()
        assert 'app.get("/timeline"' in source
        assert 'app.get("/timeline/subscribe"' in source
        assert 'app.get("/timeline/event/*"' in source

    def test_app_source_has_timeline_handlers(self) -> None:
        """Verify timeline handler factories exist."""
        from pathlib import Path

        source = (Path(__file__).parent.parent / "graph" / "app.py").read_text()
        assert "def timeline_index(" in source
        assert "def timeline_subscribe(" in source
        assert "def timeline_event_detail(" in source

    def test_app_source_imports_timeline(self) -> None:
        """App should import timeline view functions."""
        from pathlib import Path

        source = (Path(__file__).parent.parent / "graph" / "app.py").read_text()
        assert "from timeline" in source

    def test_app_source_uses_safestring(self) -> None:
        """Views return strings — handlers must wrap in SafeString for w.patch."""
        from pathlib import Path

        source = (Path(__file__).parent.parent / "graph" / "app.py").read_text()
        assert "SafeString" in source

    def test_app_source_uses_asyncio_to_thread(self) -> None:
        """DB reads must be offloaded to avoid blocking the event loop."""
        from pathlib import Path

        source = (Path(__file__).parent.parent / "graph" / "app.py").read_text()
        assert "asyncio.to_thread" in source
```

**Key details**:
- `Path(__file__).parent.parent / "graph" / "app.py"` — navigates from `tests/` up to `frontend/` then into `graph/`
- Reads the file as plain text with `.read_text()`
- Asserts substrings like `'app.get("/timeline"'` or `"def timeline_index("` exist in source
- **Why**: Stario requires Python 3.14 and specific dependencies. Reading source text lets us verify route wiring without importing the framework.

**For new enhancements**, add similar tests:

```python
# Phase D4 — Export route
def test_app_source_has_export_route(self) -> None:
    from pathlib import Path
    source = (Path(__file__).parent.parent / "graph" / "app.py").read_text()
    assert 'app.get("/timeline/export"' in source

# Phase E1 — Compare route
def test_app_source_has_compare_route(self) -> None:
    from pathlib import Path
    source = (Path(__file__).parent.parent / "graph" / "app.py").read_text()
    assert 'app.get("/timeline/compare"' in source
```

---

## 9. Testing New Data Layer Functions

For new functions added to `timeline/state.py`, follow the pattern in `test_timeline_state.py`:

### Adding a new filter parameter (e.g. `event_types`)

```python
class TestEventTypeFilter:
    def test_filter_by_single_event_type(self) -> None:
        conn = _create_db()
        _insert_event(conn, from_agent="a", timestamp=1.0, event_type="AgentStart")
        _insert_event(conn, from_agent="a", timestamp=2.0, event_type="AgentComplete")
        result = read_timeline_data(conn, event_types=["AgentStart"])
        assert len(result.events) == 1
        assert result.events[0]["event_type"] == "AgentStart"

    def test_filter_by_multiple_event_types(self) -> None:
        conn = _create_db()
        _insert_event(conn, from_agent="a", timestamp=1.0, event_type="AgentStart")
        _insert_event(conn, from_agent="a", timestamp=2.0, event_type="AgentComplete")
        _insert_event(conn, from_agent="a", timestamp=3.0, event_type="AgentError")
        result = read_timeline_data(conn, event_types=["AgentStart", "AgentError"])
        assert len(result.events) == 2
        types = [e["event_type"] for e in result.events]
        assert "AgentStart" in types
        assert "AgentError" in types
        assert "AgentComplete" not in types

    def test_filter_event_types_none_returns_all(self) -> None:
        conn = _create_db()
        _insert_event(conn, from_agent="a", timestamp=1.0, event_type="AgentStart")
        _insert_event(conn, from_agent="a", timestamp=2.0, event_type="AgentComplete")
        result = read_timeline_data(conn, event_types=None)
        assert len(result.events) == 2
```

### Adding a new standalone function (e.g. `extract_spans()`)

```python
class TestExtractSpans:
    def test_pairs_start_and_complete(self) -> None:
        events = [
            {"event_id": 1, "event_type": "AgentStart", "timestamp": 1.0, "from_agent": "a", "to_agent": None, "correlation_id": "c1", "payload": "{}"},
            {"event_id": 2, "event_type": "AgentComplete", "timestamp": 2.0, "from_agent": "a", "to_agent": None, "correlation_id": "c1", "payload": "{}"},
        ]
        spans = extract_spans(events)
        assert len(spans) == 1
        assert spans[0]["agent"] == "a"
        assert spans[0]["start"] == 1.0
        assert spans[0]["end"] == 2.0

    def test_unpaired_start_ignored(self) -> None:
        events = [
            {"event_id": 1, "event_type": "AgentStart", "timestamp": 1.0, "from_agent": "a", "to_agent": None, "correlation_id": "c1", "payload": "{}"},
        ]
        spans = extract_spans(events)
        assert len(spans) == 0
```

---

## 10. Testing New SVG Functions

For new functions added to `timeline/svg.py`, follow the pattern in `test_timeline_svg.py`:

```python
class TestRenderLegend:
    def test_returns_string(self) -> None:
        result = render_legend(event_types=["AgentStart", "AgentComplete"])
        assert isinstance(result, str)
        assert len(result) > 0

    def test_contains_all_event_types(self) -> None:
        result = render_legend(event_types=["AgentStart", "AgentComplete", "AgentError"])
        assert "AgentStart" in result
        assert "AgentComplete" in result
        assert "AgentError" in result

    def test_contains_color_dots(self) -> None:
        result = render_legend(event_types=["AgentStart"])
        assert "<circle" in result or "legend-dot" in result

    def test_empty_event_types(self) -> None:
        result = render_legend(event_types=[])
        assert isinstance(result, str)

    def test_legend_class(self) -> None:
        result = render_legend(event_types=["Test"])
        assert "timeline-legend" in result
```

**Import pattern** — add new functions to the existing import block:

```python
from timeline.svg import (
    LANE_HEIGHT,
    LABEL_WIDTH,
    MARKER_RADIUS,
    render_timeline_svg,
    render_event_marker,
    render_agent_label,
    render_correlation_line,
    render_time_axis,
    render_legend,          # new in A1
    render_minimap,         # new in C1
    render_flame_bar,       # new in D2
    render_flame_view,      # new in D2
    render_brush,           # new in D3
    render_comparison_svg,  # new in E1
)
```

---

## 11. Testing New View Elements

For new UI elements in `timeline/views.py`, follow the pattern in `test_timeline_views.py`:

### Testing presence of new HTML elements in the shell

```python
class TestRenderTimelineShell:
    # ... existing tests ...

    # Phase A1 — Legend
    def test_includes_legend(self) -> None:
        result = render_timeline_shell(self._make_data())
        assert "timeline-legend" in result

    # Phase A2 — Follow button
    def test_includes_follow_button(self) -> None:
        result = render_timeline_shell(self._make_data())
        assert 'id="follow-btn"' in result

    # Phase A2 — Follow JS
    def test_includes_follow_js(self) -> None:
        result = render_timeline_shell(self._make_data())
        assert "__timelineFollowMode" in result

    # Phase B1 — Controls bar
    def test_includes_controls_bar(self) -> None:
        result = render_timeline_shell(self._make_data())
        assert "controls-bar" in result
```

### Testing a new standalone view function

```python
class TestRenderControlsBar:
    def test_returns_string(self) -> None:
        data = TimelineData(agents=["a", "b"], events=[], time_range=(0.0, 0.0))
        result = render_controls_bar(data)
        assert isinstance(result, str)

    def test_contains_agent_options(self) -> None:
        data = TimelineData(agents=["agent_a", "agent_b"], events=[], time_range=(0.0, 0.0))
        result = render_controls_bar(data)
        assert "agent_a" in result
        assert "agent_b" in result
```

---

## 12. Testing New CSS Classes

For new CSS added to `timeline/css.py`, follow the pattern in `test_timeline_views.py`:

```python
class TestTimelineCss:
    # ... existing tests ...

    # Phase A1 — Legend styles
    def test_contains_legend_styles(self) -> None:
        result = timeline_css()
        assert ".timeline-legend" in result
        assert ".legend-item" in result

    # Phase A3 — Dim/highlight styles
    def test_contains_dim_highlight_styles(self) -> None:
        result = timeline_css()
        assert ".dim" in result
        assert ".highlight" in result

    # Phase B2 — Keyboard focus styles
    def test_contains_focused_styles(self) -> None:
        result = timeline_css()
        assert ".event-marker.focused" in result
```

---

## 13. Testing New Routes

For new routes added to `graph/app.py`, follow the source-code-reading pattern in `test_app.py`:

```python
class TestAppImport:
    # ... existing tests ...

    # Phase D4 — Export route
    def test_app_source_has_export_route(self) -> None:
        """Verify export endpoint is wired."""
        from pathlib import Path

        source = (Path(__file__).parent.parent / "graph" / "app.py").read_text()
        assert 'app.get("/timeline/export"' in source

    def test_app_source_has_export_handler(self) -> None:
        """Verify export handler function exists."""
        from pathlib import Path

        source = (Path(__file__).parent.parent / "graph" / "app.py").read_text()
        assert "def timeline_export(" in source

    # Phase E1 — Compare route
    def test_app_source_has_compare_route(self) -> None:
        """Verify comparison endpoint is wired."""
        from pathlib import Path

        source = (Path(__file__).parent.parent / "graph" / "app.py").read_text()
        assert 'app.get("/timeline/compare"' in source

    def test_app_source_has_compare_handler(self) -> None:
        """Verify comparison handler function exists."""
        from pathlib import Path

        source = (Path(__file__).parent.parent / "graph" / "app.py").read_text()
        assert "def timeline_compare(" in source
```

---

## 14. TDD Workflow

For every enhancement, follow this exact sequence:

### Step 1: Write failing tests

```bash
# 1. Add test class(es) to the appropriate test file
# 2. Run to confirm they FAIL
cd /home/andrew/Documents/Projects/remora-demo/frontend && python -m pytest tests/ -q
```

Expected: new tests fail with `ImportError` (function doesn't exist yet) or `AssertionError` (output missing expected content).

### Step 2: Implement the minimum code to pass

Edit the source files (`timeline/state.py`, `timeline/svg.py`, `timeline/css.py`, `timeline/views.py`, and/or `graph/app.py`) with just enough code to make the new tests pass.

### Step 3: Verify all tests pass

```bash
cd /home/andrew/Documents/Projects/remora-demo/frontend && python -m pytest tests/ -q
```

Expected: All new tests pass. All pre-existing 253 tests still pass. Same 2 skipped, same 1 pre-existing failure.

### Step 4: Move to next enhancement

Update `PROGRESS.md` to mark the enhancement as done. Check `PLAN.md` for the next item. Repeat from Step 1.

---

## Quick Reference

| Pattern | Where | Example |
|---------|-------|---------|
| DB setup | `test_timeline_state.py` | `conn = _create_db()` |
| Insert event | `test_timeline_state.py` | `_insert_event(conn, from_agent="a", timestamp=1.0)` |
| Build TimelineData | `test_timeline_views.py` | `TimelineData(agents=[...], events=[...], ...)` |
| Assert SVG element | All SVG/view tests | `assert "<circle" in result` |
| Assert data attr | All SVG tests | `assert 'data-event-id="42"' in result` |
| Assert CSS class | CSS/view tests | `assert ".timeline-legend" in result` |
| Assert JS behavior | View tests | `assert "__timelineFollowMode" in result` |
| Assert XSS safe | View/SVG tests | `assert "<script>" not in result` |
| Assert route exists | `test_app.py` | Source text substring check |
| Test empty state | All test files | `TimelineData()` / `_create_db()` with no inserts |
