# Phase E Implementation Guide — Polish

> Multi-Timeline Comparison.
> Estimated ~18 tests. Depends on all previous phases (filter infra, rendering, export).

## Table of Contents

1. [E1: Multi-Timeline Comparison](#e1-multi-timeline-comparison) — diff_timelines(), comparison SVG, split/overlay view, /timeline/compare route

---

## E1: Multi-Timeline Comparison

### Overview

Compare two time ranges (or two filter configurations) side-by-side or overlaid. The user selects two ranges (A and B) and toggles between split view (stacked vertically) and overlay view (semi-transparent overlapping). Diff markers highlight events unique to each range.

### Step 1: Tests for `diff_timelines()`

Add to `tests/test_timeline_state.py`:

```python
from timeline.state import diff_timelines

class TestDiffTimelines:
    def _make_data(self, agent_names: list[str], event_ids: list[int]) -> TimelineData:
        events = [
            {
                "event_id": eid,
                "event_type": "AgentStart",
                "timestamp": float(eid),
                "from_agent": agent_names[i % len(agent_names)],
                "to_agent": None,
                "correlation_id": None,
                "payload": "{}",
            }
            for i, eid in enumerate(event_ids)
        ]
        return TimelineData(
            agents=agent_names,
            events=events,
            time_range=(float(min(event_ids)), float(max(event_ids))) if event_ids else (0.0, 0.0),
        )

    def test_returns_dict(self) -> None:
        a = self._make_data(["a"], [1, 2, 3])
        b = self._make_data(["a"], [2, 3, 4])
        result = diff_timelines(a, b)
        assert isinstance(result, dict)

    def test_identifies_events_only_in_a(self) -> None:
        a = self._make_data(["a"], [1, 2, 3])
        b = self._make_data(["a"], [2, 3, 4])
        result = diff_timelines(a, b)
        assert 1 in result["only_a"]
        assert 4 not in result["only_a"]

    def test_identifies_events_only_in_b(self) -> None:
        a = self._make_data(["a"], [1, 2, 3])
        b = self._make_data(["a"], [2, 3, 4])
        result = diff_timelines(a, b)
        assert 4 in result["only_b"]
        assert 1 not in result["only_b"]

    def test_identifies_common_events(self) -> None:
        a = self._make_data(["a"], [1, 2, 3])
        b = self._make_data(["a"], [2, 3, 4])
        result = diff_timelines(a, b)
        assert 2 in result["common"]
        assert 3 in result["common"]

    def test_identifies_agents_only_in_a(self) -> None:
        a = self._make_data(["a", "b"], [1, 2])
        b = self._make_data(["b", "c"], [3, 4])
        result = diff_timelines(a, b)
        assert "a" in result["agents_only_a"]
        assert "c" not in result["agents_only_a"]

    def test_identifies_agents_only_in_b(self) -> None:
        a = self._make_data(["a", "b"], [1, 2])
        b = self._make_data(["b", "c"], [3, 4])
        result = diff_timelines(a, b)
        assert "c" in result["agents_only_b"]
        assert "a" not in result["agents_only_b"]

    def test_empty_a(self) -> None:
        a = TimelineData()
        b = self._make_data(["a"], [1, 2])
        result = diff_timelines(a, b)
        assert result["only_a"] == []
        assert len(result["only_b"]) == 2

    def test_empty_b(self) -> None:
        a = self._make_data(["a"], [1, 2])
        b = TimelineData()
        result = diff_timelines(a, b)
        assert len(result["only_a"]) == 2
        assert result["only_b"] == []

    def test_identical_timelines(self) -> None:
        a = self._make_data(["a"], [1, 2, 3])
        b = self._make_data(["a"], [1, 2, 3])
        result = diff_timelines(a, b)
        assert result["only_a"] == []
        assert result["only_b"] == []
        assert len(result["common"]) == 3
```

### Step 2: Implement `diff_timelines()`

Add to `timeline/state.py`:

```python
def diff_timelines(a: TimelineData, b: TimelineData) -> dict:
    """Compare two timeline datasets and identify differences.

    Returns:
        Dict with keys:
        - only_a: event IDs present only in timeline A
        - only_b: event IDs present only in timeline B
        - common: event IDs present in both
        - agents_only_a: agent names only in A
        - agents_only_b: agent names only in B
        - agents_common: agent names in both
    """
    ids_a = {ev["event_id"] for ev in a.events}
    ids_b = {ev["event_id"] for ev in b.events}

    agents_a = set(a.agents)
    agents_b = set(b.agents)

    return {
        "only_a": sorted(ids_a - ids_b),
        "only_b": sorted(ids_b - ids_a),
        "common": sorted(ids_a & ids_b),
        "agents_only_a": sorted(agents_a - agents_b),
        "agents_only_b": sorted(agents_b - agents_a),
        "agents_common": sorted(agents_a & agents_b),
    }
```

### Step 3: Tests for `render_comparison_svg()`

Add to `tests/test_timeline_svg.py`:

```python
from timeline.svg import render_comparison_svg

class TestRenderComparisonSvg:
    def _make_data(self, agent: str = "a", event_ids: list[int] | None = None) -> TimelineData:
        ids = event_ids or [1, 2]
        events = [
            {
                "event_id": eid,
                "event_type": "AgentStart",
                "timestamp": float(eid),
                "from_agent": agent,
                "to_agent": None,
                "correlation_id": None,
                "payload": "{}",
            }
            for eid in ids
        ]
        return TimelineData(
            agents=[agent], events=events,
            time_range=(float(min(ids)), float(max(ids))) if len(ids) > 1 else (float(ids[0]), float(ids[0])),
        )

    def test_returns_string(self) -> None:
        result = render_comparison_svg(self._make_data(), self._make_data(), width=1200)
        assert isinstance(result, str)

    def test_returns_svg(self) -> None:
        result = render_comparison_svg(self._make_data(), self._make_data(), width=1200)
        assert "<svg" in result

    def test_contains_timeline_a_class(self) -> None:
        result = render_comparison_svg(self._make_data(), self._make_data(), width=1200)
        assert "timeline-a" in result

    def test_contains_timeline_b_class(self) -> None:
        result = render_comparison_svg(self._make_data(), self._make_data(), width=1200)
        assert "timeline-b" in result

    def test_contains_diff_markers(self) -> None:
        a = self._make_data(event_ids=[1, 2, 3])
        b = self._make_data(event_ids=[2, 3, 4])
        result = render_comparison_svg(a, b, width=1200)
        assert "diff-marker" in result

    def test_empty_data_a(self) -> None:
        result = render_comparison_svg(TimelineData(), self._make_data(), width=1200)
        assert "<svg" in result
```

### Step 4: Implement `render_comparison_svg()`

Add to `timeline/svg.py`:

```python
def render_comparison_svg(
    data_a: TimelineData,
    data_b: TimelineData,
    width: int = 1200,
) -> str:
    """Render a comparison SVG showing two timelines stacked vertically.

    Timeline A is rendered in the top half, timeline B in the bottom half.
    Events unique to each are marked with diff-marker indicators.
    """
    from timeline.state import diff_timelines

    diff = diff_timelines(data_a, data_b)
    only_a_ids = set(diff["only_a"])
    only_b_ids = set(diff["only_b"])

    # Combined agents for consistent lane ordering
    all_agents = list(dict.fromkeys(data_a.agents + data_b.agents))
    num_agents = len(all_agents)

    # Two stacked sections, each with its own lanes
    section_height = PADDING_TOP + num_agents * LANE_HEIGHT + 10
    total_height = section_height * 2 + PADDING_BOTTOM + 20  # 20px gap label

    # Combined time range
    times = [data_a.time_range[0], data_a.time_range[1],
             data_b.time_range[0], data_b.time_range[1]]
    times = [t for t in times if t > 0]
    if times:
        t_min, t_max = min(times), max(times)
    else:
        t_min, t_max = 0.0, 0.0
    duration = t_max - t_min

    x_start = LABEL_WIDTH
    x_end = width - PADDING_RIGHT

    def time_to_x(t: float) -> float:
        if duration <= 0:
            return (x_start + x_end) / 2
        frac = (t - t_min) / duration
        return x_start + frac * (x_end - x_start)

    agent_index = {agent: i for i, agent in enumerate(all_agents)}

    parts = [
        f'<svg id="comparison-svg" viewBox="0 0 {width} {total_height}" '
        f'xmlns="http://www.w3.org/2000/svg" class="timeline-canvas" '
        f'preserveAspectRatio="xMidYMid meet">'
    ]

    def render_section(data: TimelineData, y_offset: float, css_class: str, unique_ids: set) -> None:
        # Section label
        label = "A" if css_class == "timeline-a" else "B"
        parts.append(
            f'<text x="4" y="{y_offset + 14}" font-size="11px" fill="#89b4fa" '
            f'font-weight="bold" class="{css_class}-label">Timeline {label}</text>'
        )

        # Lane backgrounds
        for i, agent in enumerate(all_agents):
            lane_y = y_offset + PADDING_TOP + i * LANE_HEIGHT
            bg = LANE_BG_ODD if i % 2 else LANE_BG_EVEN
            parts.append(
                f'<rect x="0" y="{lane_y}" width="{width}" height="{LANE_HEIGHT}" '
                f'fill="{bg}" class="lane-bg {css_class}"/>'
            )

        # Agent labels
        for agent in all_agents:
            idx = agent_index[agent]
            label_y = y_offset + PADDING_TOP + idx * LANE_HEIGHT + LANE_HEIGHT / 2 + 4
            parts.append(render_agent_label(agent, label_y))

        # Event markers
        for ev in data.events:
            agent = ev.get("from_agent") or ev.get("to_agent")
            if agent is None or agent not in agent_index:
                continue
            x = time_to_x(ev["timestamp"])
            y = y_offset + PADDING_TOP + agent_index[agent] * LANE_HEIGHT + LANE_HEIGHT / 2
            fill = EVENT_TYPE_COLORS.get(ev["event_type"], DEFAULT_COLOR)
            eid = ev["event_id"]

            # Add diff-marker class if unique to this timeline
            extra_class = " diff-marker" if eid in unique_ids else ""
            parts.append(
                f'<circle cx="{x}" cy="{y}" r="{MARKER_RADIUS}" fill="{fill}" '
                f'class="event-marker {css_class}{extra_class}" data-event-id="{eid}"/>'
            )

    # Render section A
    render_section(data_a, 0, "timeline-a", only_a_ids)

    # Gap label
    gap_y = section_height + 5
    parts.append(
        f'<line x1="0" y1="{gap_y}" x2="{width}" y2="{gap_y}" '
        f'stroke="#585b70" stroke-width="1" stroke-dasharray="4,3"/>'
    )

    # Render section B
    render_section(data_b, section_height + 10, "timeline-b", only_b_ids)

    # Time axis at bottom
    axis_y = total_height - PADDING_BOTTOM + 5
    parts.append(
        render_time_axis(
            time_range=(t_min, t_max),
            x_start=float(x_start),
            x_end=float(x_end),
            y=axis_y,
        )
    )

    parts.append("</svg>")
    return "".join(parts)
```

### Step 5: Tests for `render_comparison_shell()`

Add to `tests/test_timeline_views.py`:

```python
from timeline.views import render_comparison_shell

class TestRenderComparisonShell:
    def _make_data(self) -> TimelineData:
        return TimelineData(
            agents=["a"],
            events=[
                {"event_id": 1, "event_type": "AgentStart", "timestamp": 1.0,
                 "from_agent": "a", "to_agent": None, "correlation_id": None, "payload": "{}"},
            ],
            time_range=(1.0, 1.0),
        )

    def test_returns_full_html(self) -> None:
        result = render_comparison_shell(self._make_data(), self._make_data())
        assert "<!DOCTYPE html>" in result

    def test_contains_comparison_view_class(self) -> None:
        result = render_comparison_shell(self._make_data(), self._make_data())
        assert "comparison-view" in result

    def test_contains_range_selectors(self) -> None:
        result = render_comparison_shell(self._make_data(), self._make_data())
        assert "range-a" in result or "Range A" in result
        assert "range-b" in result or "Range B" in result
```

### Step 6: Implement `render_comparison_shell()`

Add to `timeline/views.py`:

```python
def render_comparison_shell(data_a: TimelineData, data_b: TimelineData) -> str:
    """Render the comparison view HTML page.

    Shows two timelines stacked with range selectors and a split/overlay toggle.
    """
    from timeline.svg import render_comparison_svg

    css = html_mod.escape(timeline_css(), quote=False)
    comparison_svg = render_comparison_svg(data_a, data_b)

    count_a = len(data_a.events)
    count_b = len(data_b.events)

    return f"""\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Remora Timeline — Compare</title>
<script type="module" src="{DATASTAR_CDN}"></script>
<style>{css}</style>
</head>
<body>
<div class="app">
  <header class="header">
    <div class="header-title">Timeline Comparison</div>
    <nav class="header-nav">
      <a href="/">Graph</a>
      <a href="/timeline">Timeline</a>
      <a href="/timeline/compare" class="active">Compare</a>
    </nav>
    <div class="header-status">A: {count_a} events | B: {count_b} events</div>
  </header>
  <div class="comparison-controls">
    <div class="range-selector">
      <label class="range-label">Range A:</label>
      <input type="text" id="range-a-since" class="filter-input" placeholder="since">
      <input type="text" id="range-a-until" class="filter-input" placeholder="until">
    </div>
    <div class="range-selector">
      <label class="range-label">Range B:</label>
      <input type="text" id="range-b-since" class="filter-input" placeholder="since">
      <input type="text" id="range-b-until" class="filter-input" placeholder="until">
    </div>
    <button class="btn" id="compare-btn">Compare</button>
  </div>
  <div class="main">
    <div class="comparison-view" id="comparison-view">
      {comparison_svg}
    </div>
  </div>
</div>
</body>
</html>"""
```

### Step 7: Tests for `/timeline/compare` route

Add to `tests/test_app.py` in `TestAppModuleStructure`:

```python
def test_app_source_has_timeline_compare_route(self) -> None:
    from pathlib import Path
    source = (Path(__file__).parent.parent / "graph" / "app.py").read_text()
    assert 'app.get("/timeline/compare"' in source

def test_app_source_has_timeline_compare_handler(self) -> None:
    from pathlib import Path
    source = (Path(__file__).parent.parent / "graph" / "app.py").read_text()
    assert "def timeline_compare(" in source
```

### Step 8: Implement `/timeline/compare` route

Add to `graph/app.py`:

```python
def timeline_compare(state: GraphState):
    """GET /timeline/compare — render comparison view of two time ranges."""
    async def handler(c: Context, w: Writer) -> None:
        query = c.req.query

        # Parse range A
        since_a = float(query.get("since_a")) if query.get("since_a") else None
        until_a = float(query.get("until_a")) if query.get("until_a") else None

        # Parse range B
        since_b = float(query.get("since_b")) if query.get("since_b") else None
        until_b = float(query.get("until_b")) if query.get("until_b") else None

        conn = state._get_conn()

        kwargs_a = {}
        if since_a is not None: kwargs_a["since"] = since_a
        if until_a is not None: kwargs_a["until"] = until_a

        kwargs_b = {}
        if since_b is not None: kwargs_b["since"] = since_b
        if until_b is not None: kwargs_b["until"] = until_b

        data_a = await asyncio.to_thread(read_timeline_data, conn, **kwargs_a)
        data_b = await asyncio.to_thread(read_timeline_data, conn, **kwargs_b)

        from timeline.views import render_comparison_shell
        w.html(SafeString(render_comparison_shell(data_a, data_b)))
    return handler
```

Register the route:

```python
app.get("/timeline/compare", timeline_compare(state))
```

### Step 9: CSS for comparison view

Add to `timeline/css.py`:

```css
/* ---- Comparison view ---- */
.comparison-view {
    flex: 1; position: relative; overflow: auto;
}
.comparison-controls {
    padding: 8px 16px;
    background: var(--surface);
    border-bottom: 1px solid var(--surface2);
    display: flex;
    align-items: center;
    gap: 16px;
    font-size: 11px;
}
.range-selector {
    display: flex; align-items: center; gap: 6px;
}
.range-label { color: var(--subtext); font-weight: 600; }
.timeline-a .event-marker { opacity: 0.9; }
.timeline-b .event-marker { opacity: 0.9; }
.diff-marker {
    stroke: var(--yellow);
    stroke-width: 2;
    stroke-dasharray: 3,2;
}
```

### Step 10: Tests for comparison CSS

Add to `tests/test_timeline_views.py` in `TestTimelineCss`:

```python
def test_contains_comparison_styles(self) -> None:
    result = timeline_css()
    assert ".comparison-view" in result
    assert ".diff-marker" in result
```

---

## Phase E Verification

After completing E1:

```bash
cd /home/andrew/Documents/Projects/remora-demo/frontend && python -m pytest tests/ -q
```

Expected: ~370+ tests passing (253 baseline + ~25 Phase A + ~30 Phase B + ~18 Phase C + ~55 Phase D + ~18 Phase E).

### Checklist

- [ ] `diff_timelines()` exists with 9 tests
- [ ] `render_comparison_svg()` exists with 6 tests
- [ ] `render_comparison_shell()` exists with 3 tests
- [ ] `/timeline/compare` route exists with 2 tests
- [ ] Comparison CSS (.comparison-view, .diff-marker, .timeline-a, .timeline-b)
- [ ] Range selector UI for A and B
- [ ] Compare button triggers comparison
- [ ] All existing tests still pass

---

## All Phases Complete — Final Verification

After all 13 enhancements across phases A–E:

```bash
cd /home/andrew/Documents/Projects/remora-demo/frontend && python -m pytest tests/ -q
```

Expected final: ~400 passed (253 baseline + ~146 new tests), 2 skipped, 1 pre-existing failure.

Review `PROGRESS.md` — all 13 checkboxes should be marked done.
Update `CONTEXT.md` with completion summary.
