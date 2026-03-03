# Timeline Architecture Guide

> Complete reference for the existing timeline debugger code. Read this before modifying anything.

## Table of Contents

1. [Package Structure](#1-package-structure)
2. [Data Layer — `timeline/state.py`](#2-data-layer)
3. [SVG Renderer — `timeline/svg.py`](#3-svg-renderer)
4. [CSS Theme — `timeline/css.py`](#4-css-theme)
5. [Views — `timeline/views.py`](#5-views)
6. [Routes — `graph/app.py`](#6-routes)
7. [Coding Conventions](#7-coding-conventions)
8. [Catppuccin Mocha Palette](#8-catppuccin-mocha-palette)
9. [Event Type Colors](#9-event-type-colors)
10. [SVG Layout Constants](#10-svg-layout-constants)

---

## 1. Package Structure

```
frontend/
├── timeline/
│   ├── __init__.py      # Just docstring
│   ├── state.py         # Data queries (TimelineData, read_timeline_data)
│   ├── svg.py           # SVG builders (markers, labels, lines, axis, full SVG)
│   ├── css.py           # Catppuccin Mocha CSS (timeline_css())
│   └── views.py         # HTML page + inspector (render_timeline_shell, render_event_inspector)
├── graph/
│   ├── app.py           # Stario route handlers (timeline routes at bottom)
│   ├── views/shell.py   # Graph shell (has Timeline nav link)
│   └── ...
├── tests/
│   ├── test_timeline_state.py   # 19 tests
│   ├── test_timeline_svg.py     # 24 tests
│   ├── test_timeline_views.py   # 21 tests
│   └── test_app.py              # 11 tests (3 are timeline route checks)
└── pyproject.toml               # "timeline" listed in packages
```

### Import dependency graph

```
timeline/state.py  →  (stdlib only: sqlite3, dataclasses)
timeline/svg.py    →  timeline/state.py (TimelineData)
timeline/css.py    →  (nothing)
timeline/views.py  →  timeline/css.py, timeline/state.py, timeline/svg.py
graph/app.py       →  timeline/state.py, timeline/svg.py, timeline/views.py, stario
```

**Rule**: `timeline/` modules NEVER import from `stario`. Only `graph/app.py` imports Stario. This makes `timeline/` testable under Python 3.13.

---

## 2. Data Layer

### File: `timeline/state.py`

**`TimelineData` dataclass** — immutable result of a timeline query:

```python
@dataclass
class TimelineData:
    agents: list[str] = field(default_factory=list)           # Agent names, ordered by first event time
    events: list[dict] = field(default_factory=list)           # Flat chronological list of event dicts
    correlation_groups: dict[str, list[int]] = field(default_factory=dict)  # correlation_id → [event_ids]
    time_range: tuple[float, float] = (0.0, 0.0)              # (earliest_timestamp, latest_timestamp)
```

Each event dict has keys: `event_id`, `event_type`, `timestamp`, `from_agent`, `to_agent`, `correlation_id`, `payload`.

**`read_timeline_data(conn, *, since, until, agent_ids, correlation_id, limit) -> TimelineData`**

- Takes a raw `sqlite3.Connection` (testable with `:memory:`)
- Builds WHERE clause dynamically from optional filters
- If `limit` is set: subquery to get N most recent, then reorder ascending
- Builds agent list ordered by first event time (both `from_agent` and `to_agent` contribute)
- Builds correlation groups (skips None correlation_id)
- Returns TimelineData

### Events table schema (SQLite)

```sql
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
```

The query aliases `id` → `event_id` to avoid confusion.

---

## 3. SVG Renderer

### File: `timeline/svg.py`

#### Constants

```python
LANE_HEIGHT = 50
LABEL_WIDTH = 140
MARKER_RADIUS = 6
PADDING_TOP = 30
PADDING_BOTTOM = 40
PADDING_RIGHT = 30
MIN_TIMELINE_WIDTH = 600
LANE_BG_EVEN = "#1e1e2e"    # base
LANE_BG_ODD = "#181825"     # mantle
DEFAULT_COLOR = "#6c7086"
```

#### Event Type Colors

```python
EVENT_TYPE_COLORS = {
    "NodeDiscovered": "#a6e3a1",  "NodeRemoved": "#6c7086",
    "AgentStart": "#89b4fa",      "AgentComplete": "#a6e3a1",
    "AgentError": "#f38ba8",      "ContentChanged": "#f9e2af",
    "ModelRequest": "#cba6f7",    "ModelResponse": "#cba6f7",
    "AgentMessage": "#89dceb",    "HumanChat": "#fab387",
    "RewriteProposal": "#f9e2af", "RewriteApplied": "#a6e3a1",
    "RewriteRejected": "#f38ba8",
}
```

#### Primitive builders

All return plain strings. No Stario dependency.

**`render_event_marker(*, event_id, x, y, event_type) -> str`**
- Returns `<circle>` with `cx`, `cy`, `r`, `fill`, `class="event-marker"`, `data-event-id`
- Color looked up from `EVENT_TYPE_COLORS`

**`render_agent_label(name, y) -> str`**
- Returns `<text>` right-aligned at `LABEL_WIDTH - 10`
- Truncates at 20 chars, HTML-escapes

**`render_correlation_line(*, x1, y1, x2, y2) -> str`**
- Returns `<line>` with dashed stroke, 30% opacity, class `correlation-line`

**`render_time_axis(*, time_range, x_start, x_end, y, num_ticks=5) -> str`**
- Returns `<g class="time-axis">` with axis line, tick marks, HH:MM:SS.mmm labels
- Handles single-timestamp (no division by zero)

#### Composite builder

**`render_timeline_svg(data: TimelineData, width: int = 1200) -> str`**
- Returns complete `<svg id="timeline-svg" ...>` element
- Layout: lane backgrounds → agent labels → separator line → event markers → correlation lines → time axis
- Height calculated from number of agents
- X position: `time_to_x(t)` maps timestamp to pixel X
- Y position: `agent_to_y(agent)` maps agent name to lane center Y
- Empty data: returns SVG with "No events to display" text

**Current marker attributes**: `cx`, `cy`, `r`, `fill`, `class="event-marker"`, `data-event-id`
**Missing attributes needed by enhancements**: `data-event-type`, `data-correlation-id`

---

## 4. CSS Theme

### File: `timeline/css.py`

Single function `timeline_css() -> str` returning the full CSS string.

**CSS custom properties** (Catppuccin Mocha):
```css
--bg: #1e1e2e;     --mantle: #181825;   --surface: #313244;
--surface2: #45475a; --overlay: #585b70;  --text: #cdd6f4;
--subtext: #a6adc8;  --green: #a6e3a1;   --blue: #89b4fa;
--yellow: #f9e2af;   --red: #f38ba8;     --gray: #6c7086;
--lavender: #b4befe;
```

**Existing class selectors** (partial list):
- `.app`, `.header`, `.header-title`, `.header-nav`, `.header-status`
- `.main`, `.timeline-pane`, `.timeline-canvas`
- `.event-marker`, `.event-marker:hover`, `.agent-label`, `.lane-bg`, `.correlation-line`
- `.inspector`, `.inspector-empty`, `.inspector-header`, `.inspector-type`, `.inspector-field`, `.inspector-payload`
- `.timeline-tooltip`
- `.timeline-controls`, `.timeline-controls .btn`, `.timeline-controls .btn.active`

---

## 5. Views

### File: `timeline/views.py`

**`TIMELINE_ZOOM_PAN_JS`** — inline JS for zoom (wheel), pan (drag), tooltip (hover), click-to-inspect.

Key JS variables: `scale`, `tx`, `ty`. Transform applied via `svg.style.transform = 'translate(...) scale(...)'`.

**`render_timeline_shell(data: TimelineData) -> str`**
- Returns complete `<!DOCTYPE html>` page
- Includes: Datastar CDN script, CSS in `<style>`, SSE auto-connect via `data-on-load="@get('/timeline/subscribe')"`
- Layout: header (title, nav, status) → main (timeline-pane with SVG + inspector panel) → tooltip div → JS script
- Inspector initialized as empty (click hint)

**`render_event_inspector(event: dict | None) -> str`**
- Returns `<div id="inspector" class="inspector">` content
- None: placeholder "Click an event to view details"
- Event: type badge (colored), fields (Event ID, Time, From, To, Correlation), pretty-printed payload

---

## 6. Routes

### File: `graph/app.py`

Timeline-related handlers (all use closure-based DI):

**`timeline_index(state)`** — `GET /timeline`
- Reads all events via `read_timeline_data(conn)`, renders full shell page

**`timeline_subscribe(state, relay)`** — `GET /timeline/subscribe`
- SSE endpoint. Sends initial SVG, then re-renders on `graph.events` relay messages
- Currently does NOT parse query params (enhancement B1 will add this)

**`timeline_event_detail(state)`** — `GET /timeline/event/*`
- Reads single event by ID from `c.req.tail`, renders inspector panel

### Route registration in `create_app()`:
```python
app.get("/timeline", timeline_index(state))
app.get("/timeline/subscribe", timeline_subscribe(state, relay))
app.get("/timeline/event/*", timeline_event_detail(state))
```

---

## 7. Coding Conventions

1. **All functions return plain strings** — never Stario elements
2. **`html_mod.escape()`** for all user-provided text
3. **f-strings** for SVG/HTML generation
4. **`from __future__ import annotations`** at top of every file
5. **Keyword-only args** (`*`) for SVG builder params
6. **Type hints** on all function signatures
7. **Docstrings** on all public functions
8. **No isinstance** in business logic
9. **SafeString wrapping** only in `graph/app.py`, never in timeline/
10. **Tests use in-memory SQLite** (`sqlite3.connect(":memory:")`) for data layer tests
11. **Tests check for string fragments** (e.g., `assert "data-event-id" in result`)
12. **Class-based test grouping** (e.g., `class TestRenderEventMarker:`)

---

## 8. Catppuccin Mocha Palette

Full reference for consistent theming:

| Name | Hex | Usage |
|------|-----|-------|
| Rosewater | #f5e0dc | |
| Flamingo | #f2cdcd | |
| Pink | #f5c2e7 | |
| Mauve | #cba6f7 | ModelRequest, ModelResponse |
| Red | #f38ba8 | AgentError, RewriteRejected |
| Maroon | #eba0ac | |
| Peach | #fab387 | HumanChat |
| Yellow | #f9e2af | ContentChanged, RewriteProposal |
| Green | #a6e3a1 | NodeDiscovered, AgentComplete, RewriteApplied |
| Teal | #94e2d5 | |
| Sky | #89dceb | AgentMessage |
| Sapphire | #74c7ec | |
| Blue | #89b4fa | AgentStart |
| Lavender | #b4befe | Correlation lines |
| Text | #cdd6f4 | Primary text |
| Subtext1 | #bac2de | |
| Subtext0 | #a6adc8 | Secondary text |
| Overlay2 | #9399b2 | |
| Overlay1 | #7f849c | |
| Overlay0 | #6c7086 | Default/gray |
| Surface2 | #585b70 | Borders, axis |
| Surface1 | #45475a | |
| Surface0 | #313244 | Panel backgrounds |
| Base | #1e1e2e | Main background |
| Mantle | #181825 | Alternate lane bg |
| Crust | #11111b | |

---

## 9. Event Type Colors

Exact mapping used in both `timeline/svg.py` and `graph/views/event_stream.py`:

```python
EVENT_TYPE_COLORS = {
    "NodeDiscovered": "#a6e3a1",   # green
    "NodeRemoved": "#6c7086",      # gray
    "AgentStart": "#89b4fa",       # blue
    "AgentComplete": "#a6e3a1",    # green
    "AgentError": "#f38ba8",       # red
    "ContentChanged": "#f9e2af",   # yellow
    "ModelRequest": "#cba6f7",     # mauve
    "ModelResponse": "#cba6f7",    # mauve
    "AgentMessage": "#89dceb",     # sky
    "HumanChat": "#fab387",        # peach
    "RewriteProposal": "#f9e2af",  # yellow
    "RewriteApplied": "#a6e3a1",   # green
    "RewriteRejected": "#f38ba8",  # red
}
DEFAULT_COLOR = "#6c7086"  # gray
```

---

## 10. SVG Layout Constants

```
┌─────────────────────────────────────────────────────────┐
│                    PADDING_TOP (30px)                     │
│  ┌──────────────┐ ┌──────────────────────────────────┐   │
│  │ Agent Labels  │ │     Swimlane Timeline Area       │   │
│  │ (LABEL_WIDTH │ │                                  │   │
│  │  = 140px)    │ │  ● ── ● ── ●    Event Markers   │   │
│  │              │ │  LANE_HEIGHT = 50px per lane      │   │
│  │              │ │                                  │   │
│  │              │ │  ● ────── ●                      │   │
│  │              │ │                                  │   │
│  └──────────────┘ └──────────────────────────────────┘   │
│                    PADDING_BOTTOM (40px)                  │
│             ┌── Time Axis (HH:MM:SS.mmm) ──┐             │
│             └─────────────────────────────────┘           │
│                                         PADDING_RIGHT    │
│                                           (30px)         │
└─────────────────────────────────────────────────────────┘
```

- SVG width: configurable (default 1200)
- SVG height: `PADDING_TOP + num_agents * LANE_HEIGHT + PADDING_BOTTOM`
- Time area X range: `LABEL_WIDTH` to `width - PADDING_RIGHT`
- Marker Y: `PADDING_TOP + agent_index * LANE_HEIGHT + LANE_HEIGHT / 2`
- Marker X: linear interpolation of timestamp within time range
