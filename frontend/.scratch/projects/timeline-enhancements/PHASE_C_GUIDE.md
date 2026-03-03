# Phase C Implementation Guide — Spatial Awareness

> Minimap/Overview Bar, Agent Grouping/Collapsing.
> Estimated ~18 tests. Depends on Phase B (filter controls, data-event-type/data-correlation-id attributes).

## Table of Contents

1. [C1: Minimap / Overview Bar](#c1-minimap--overview-bar) — density histogram SVG, viewport indicator, click-to-jump
2. [C2: Agent Grouping / Collapsing](#c2-agent-grouping--collapsing) — group_agents(), collapsible headers, hide-idle checkbox

---

## C1: Minimap / Overview Bar

### Overview

A thin (~40px tall) SVG density histogram rendered below the main timeline. It shows event density across time buckets, with a semi-transparent viewport indicator rectangle that tracks the current pan/zoom state. Click anywhere on the minimap to jump to that time position.

### Step 1: Tests for `render_minimap()`

Add to `tests/test_timeline_svg.py`:

```python
from timeline.svg import render_minimap

class TestRenderMinimap:
    def _make_data(self, num_events: int = 20) -> TimelineData:
        """Create test data with events spread across a time range."""
        events = [
            {
                "event_id": i + 1,
                "event_type": "AgentStart",
                "timestamp": float(i),
                "from_agent": "agent_a",
                "to_agent": None,
                "correlation_id": None,
                "payload": "{}",
            }
            for i in range(num_events)
        ]
        return TimelineData(
            agents=["agent_a"],
            events=events,
            time_range=(0.0, float(num_events - 1)) if num_events > 1 else (0.0, 0.0),
        )

    def test_returns_string(self) -> None:
        result = render_minimap(self._make_data(), width=800)
        assert isinstance(result, str)

    def test_returns_svg_element(self) -> None:
        result = render_minimap(self._make_data(), width=800)
        assert "<svg" in result
        assert "</svg>" in result

    def test_has_minimap_class(self) -> None:
        result = render_minimap(self._make_data(), width=800)
        assert "minimap-svg" in result

    def test_contains_density_rects(self) -> None:
        result = render_minimap(self._make_data(20), width=800)
        assert "<rect" in result
        assert "minimap-bar" in result

    def test_contains_viewport_rect(self) -> None:
        result = render_minimap(self._make_data(), width=800)
        assert "minimap-viewport" in result

    def test_empty_data(self) -> None:
        result = render_minimap(TimelineData(), width=800)
        assert "<svg" in result
        # Should still render a valid SVG even with no events

    def test_custom_height(self) -> None:
        result = render_minimap(self._make_data(), width=800, height=60)
        assert "60" in result

    def test_width_matches_param(self) -> None:
        result = render_minimap(self._make_data(), width=1000)
        assert "1000" in result

    def test_single_event(self) -> None:
        """No division by zero with single event."""
        result = render_minimap(self._make_data(1), width=800)
        assert "<svg" in result
```

### Step 2: Implement `render_minimap()`

Add to `timeline/svg.py`:

```python
def render_minimap(
    data: TimelineData,
    width: int,
    height: int = 40,
    num_bins: int = 50,
) -> str:
    """Render a minimap density histogram SVG.

    Shows event density across time buckets as vertical bars.
    Includes a viewport indicator rectangle for pan/zoom sync.
    """
    if not data.events:
        return (
            f'<svg class="minimap-svg" viewBox="0 0 {width} {height}" '
            f'xmlns="http://www.w3.org/2000/svg" '
            f'preserveAspectRatio="xMidYMid meet"></svg>'
        )

    t_min, t_max = data.time_range
    duration = t_max - t_min

    # Bin events by time
    bins = [0] * num_bins
    for ev in data.events:
        if duration > 0:
            bin_idx = int((ev["timestamp"] - t_min) / duration * (num_bins - 1))
            bin_idx = max(0, min(num_bins - 1, bin_idx))
        else:
            bin_idx = num_bins // 2
        bins[bin_idx] += 1

    max_count = max(bins) if bins else 1

    parts = [
        f'<svg class="minimap-svg" viewBox="0 0 {width} {height}" '
        f'xmlns="http://www.w3.org/2000/svg" '
        f'preserveAspectRatio="xMidYMid meet">'
    ]

    # Background
    parts.append(
        f'<rect x="0" y="0" width="{width}" height="{height}" '
        f'fill="#181825" class="minimap-bg"/>'
    )

    # Density bars
    bar_width = width / num_bins
    for i, count in enumerate(bins):
        if count == 0:
            continue
        bar_height = (count / max_count) * (height - 4)  # 4px padding
        bar_x = i * bar_width
        bar_y = height - bar_height - 2  # 2px bottom padding
        opacity = 0.3 + 0.7 * (count / max_count)
        parts.append(
            f'<rect x="{bar_x:.1f}" y="{bar_y:.1f}" '
            f'width="{bar_width:.1f}" height="{bar_height:.1f}" '
            f'fill="#89b4fa" opacity="{opacity:.2f}" class="minimap-bar"/>'
        )

    # Viewport indicator (full width initially, JS will resize/position)
    parts.append(
        f'<rect x="0" y="0" width="{width}" height="{height}" '
        f'fill="rgba(137,180,250,0.15)" stroke="#89b4fa" stroke-width="1" '
        f'class="minimap-viewport" rx="2"/>'
    )

    parts.append("</svg>")
    return "".join(parts)
```

### Step 3: Tests for minimap in shell

Add to `tests/test_timeline_views.py` in `TestRenderTimelineShell`:

```python
def test_includes_minimap(self) -> None:
    result = render_timeline_shell(self._make_data())
    assert "minimap" in result

def test_minimap_container(self) -> None:
    result = render_timeline_shell(self._make_data())
    assert "minimap-container" in result or "minimap-svg" in result
```

### Step 4: Integrate minimap into shell

In `timeline/views.py`, import `render_minimap` from `timeline/svg.py`.

In `render_timeline_shell()`, render the minimap below the main SVG, inside the timeline-pane:

```python
from timeline.svg import render_timeline_svg, render_minimap

# In render_timeline_shell():
minimap = render_minimap(data, width=1200)
```

Insert into the HTML template inside `.timeline-pane`, after the main SVG:

```html
<div class="timeline-pane" id="timeline-pane">
  {svg}
  <div class="minimap-container" id="minimap-container">
    {minimap}
  </div>
</div>
```

### Step 5: CSS for minimap

Add to `timeline/css.py`:

```css
/* ---- Minimap ---- */
.minimap-container {
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    height: 40px;
    background: var(--mantle);
    border-top: 1px solid var(--surface2);
    cursor: pointer;
    z-index: 10;
}
.minimap-svg { width: 100%; height: 100%; display: block; }
```

### Step 6: Tests for minimap CSS

Add to `tests/test_timeline_views.py` in `TestTimelineCss`:

```python
def test_contains_minimap_styles(self) -> None:
    result = timeline_css()
    assert ".minimap-container" in result
```

### Step 7: JS for minimap click-to-jump and viewport sync

In `timeline/views.py`, add to the JS block:

```javascript
// Minimap click-to-jump
(function() {
    var minimapContainer = document.getElementById('minimap-container');
    if (!minimapContainer) return;

    minimapContainer.addEventListener('click', function(e) {
        var rect = minimapContainer.getBoundingClientRect();
        var clickFrac = (e.clientX - rect.left) / rect.width;
        var svg = document.getElementById('timeline-svg');
        var pane = document.getElementById('timeline-pane');
        if (!svg || !pane) return;

        // Map click fraction to SVG x coordinate
        var svgWidth = svg.viewBox.baseVal.width || 1200;
        var targetX = clickFrac * svgWidth;

        // Center the clicked position in the pane
        tx = pane.clientWidth / 2 - targetX * scale;
        svg.style.transform = 'translate(' + tx + 'px,' + ty + 'px) scale(' + scale + ')';
        updateMinimapViewport();
    });

    function updateMinimapViewport() {
        var viewport = minimapContainer.querySelector('.minimap-viewport');
        var pane = document.getElementById('timeline-pane');
        var svg = document.getElementById('timeline-svg');
        if (!viewport || !pane || !svg) return;

        var svgWidth = svg.viewBox.baseVal.width || 1200;
        var minimapWidth = minimapContainer.getBoundingClientRect().width;

        // Calculate visible portion
        var visibleLeft = -tx / scale;
        var visibleWidth = pane.clientWidth / scale;
        var fracLeft = Math.max(0, visibleLeft / svgWidth);
        var fracWidth = Math.min(1, visibleWidth / svgWidth);

        viewport.setAttribute('x', (fracLeft * minimapWidth).toFixed(1));
        viewport.setAttribute('width', (fracWidth * minimapWidth).toFixed(1));
    }

    // Update viewport on zoom/pan
    var origWheel = pane.onwheel;
    var paneEl = document.getElementById('timeline-pane');
    if (paneEl) {
        // Hook into existing zoom/pan by polling transform changes
        var lastTx = tx, lastScale = scale;
        setInterval(function() {
            if (tx !== lastTx || scale !== lastScale) {
                lastTx = tx; lastScale = scale;
                updateMinimapViewport();
            }
        }, 100);
    }

    updateMinimapViewport();
})();
```

---

## C2: Agent Grouping / Collapsing

### Overview

Agents are automatically grouped by common prefix (e.g. `module.func_a` and `module.func_b` group under `module`). Groups get collapsible headers. An optional "Hide idle" checkbox removes agents with no events in the current view.

### Step 1: Tests for `group_agents()`

Add to `tests/test_timeline_state.py`:

```python
from timeline.state import group_agents

class TestGroupAgents:
    def test_returns_dict(self) -> None:
        result = group_agents(["a.x", "a.y", "b.z"])
        assert isinstance(result, dict)

    def test_groups_by_common_prefix(self) -> None:
        result = group_agents(["module.func_a", "module.func_b", "other.func_c"])
        assert "module" in result
        assert "other" in result
        assert "module.func_a" in result["module"]
        assert "module.func_b" in result["module"]
        assert "other.func_c" in result["other"]

    def test_no_prefix_groups_individually(self) -> None:
        result = group_agents(["alpha", "beta", "gamma"])
        # Without dots, each agent is its own group
        assert len(result) == 3
        assert "alpha" in result
        assert result["alpha"] == ["alpha"]

    def test_empty_list(self) -> None:
        result = group_agents([])
        assert result == {}

    def test_single_agent(self) -> None:
        result = group_agents(["agent_a"])
        assert "agent_a" in result
        assert result["agent_a"] == ["agent_a"]

    def test_deep_prefix_uses_first_segment(self) -> None:
        result = group_agents(["a.b.c", "a.b.d", "a.e"])
        # Groups by first dot-separated segment
        assert "a" in result
        assert len(result["a"]) == 3

    def test_preserves_order(self) -> None:
        result = group_agents(["b.x", "a.y", "b.z", "a.w"])
        # Within each group, agents should maintain their input order
        assert result["b"] == ["b.x", "b.z"]
        assert result["a"] == ["a.y", "a.w"]
```

### Step 2: Implement `group_agents()`

Add to `timeline/state.py`:

```python
def group_agents(agents: list[str]) -> dict[str, list[str]]:
    """Group agent names by their common prefix.

    Prefix is the first dot-separated segment. Agents without dots
    are placed in their own group.

    Returns:
        Dict mapping group name → list of agent names, preserving input order.
    """
    groups: dict[str, list[str]] = {}
    for agent in agents:
        prefix = agent.split(".")[0] if "." in agent else agent
        groups.setdefault(prefix, []).append(agent)
    return groups
```

### Step 3: Tests for group headers in SVG

Add to `tests/test_timeline_svg.py`:

```python
class TestAgentGrouping:
    def test_group_headers_present(self) -> None:
        data = TimelineData(
            agents=["mod.a", "mod.b", "other.c"],
            events=[
                {
                    "event_id": 1,
                    "event_type": "AgentStart",
                    "timestamp": 1.0,
                    "from_agent": "mod.a",
                    "to_agent": None,
                    "correlation_id": None,
                    "payload": "{}",
                },
            ],
            time_range=(1.0, 1.0),
        )
        result = render_timeline_svg(data)
        # Group headers should appear when agents have prefixes
        assert "agent-group" in result or "data-agent-group" in result

    def test_data_agent_group_attribute_on_lanes(self) -> None:
        data = TimelineData(
            agents=["mod.a", "mod.b"],
            events=[
                {
                    "event_id": 1,
                    "event_type": "Test",
                    "timestamp": 1.0,
                    "from_agent": "mod.a",
                    "to_agent": None,
                    "correlation_id": None,
                    "payload": "{}",
                },
            ],
            time_range=(1.0, 1.0),
        )
        result = render_timeline_svg(data)
        assert 'data-agent-group="mod"' in result
```

### Step 4: Update `render_timeline_svg()` for group headers

In `timeline/svg.py`, import `group_agents`:

```python
from timeline.state import TimelineData, group_agents
```

In `render_timeline_svg()`, after computing `agent_index`, compute groups:

```python
groups = group_agents(data.agents)
```

Update lane backgrounds to include `data-agent-group`:

```python
# Lane backgrounds
for i, agent in enumerate(data.agents):
    lane_y = PADDING_TOP + i * LANE_HEIGHT
    bg = LANE_BG_ODD if i % 2 else LANE_BG_EVEN
    # Determine group for this agent
    prefix = agent.split(".")[0] if "." in agent else agent
    parts.append(
        f'<rect x="0" y="{lane_y}" width="{width}" height="{LANE_HEIGHT}" '
        f'fill="{bg}" class="lane-bg" data-agent-group="{html_mod.escape(prefix)}"/>'
    )
```

Add clickable group header text elements. Insert group header rows above each group's first agent:

```python
# Group headers (optional — only when groups have >1 agent)
rendered_groups: set[str] = set()
for agent in data.agents:
    prefix = agent.split(".")[0] if "." in agent else agent
    if prefix not in rendered_groups and len(groups.get(prefix, [])) > 1:
        rendered_groups.add(prefix)
        idx = agent_index[agent]
        header_y = PADDING_TOP + idx * LANE_HEIGHT - 2
        parts.append(
            f'<text x="4" y="{header_y}" font-size="9px" fill="#a6adc8" '
            f'class="agent-group-header" data-group="{html_mod.escape(prefix)}" '
            f'cursor="pointer">▾ {html_mod.escape(prefix)}</text>'
        )
```

### Step 5: Tests for hide-idle checkbox in views

Add to `tests/test_timeline_views.py` in `TestRenderTimelineShell`:

```python
def test_includes_hide_idle_checkbox(self) -> None:
    result = render_timeline_shell(self._make_data())
    assert "hide-idle" in result

def test_includes_collapse_js(self) -> None:
    result = render_timeline_shell(self._make_data())
    assert "agent-group" in result or "collapseGroup" in result
```

### Step 6: Add hide-idle checkbox to shell

In `timeline/views.py`, add to the controls area (or after the legend):

```html
<label class="control-label">
  <input type="checkbox" id="hide-idle" class="control-checkbox"> Hide idle
</label>
```

### Step 7: CSS for agent grouping

Add to `timeline/css.py`:

```css
/* ---- Agent grouping ---- */
.agent-group-header {
    font-family: 'JetBrains Mono', monospace;
    cursor: pointer;
    user-select: none;
}
.agent-group-header:hover { fill: #cdd6f4; }
.lane-bg.collapsed { display: none; }
.agent-label.collapsed { display: none; }
.event-marker.collapsed { display: none; }
.control-label {
    display: inline-flex; align-items: center; gap: 4px;
    color: var(--subtext); font-size: 11px; cursor: pointer;
}
.control-checkbox { accent-color: var(--blue); }
```

### Step 8: Tests for grouping CSS

Add to `tests/test_timeline_views.py` in `TestTimelineCss`:

```python
def test_contains_agent_group_styles(self) -> None:
    result = timeline_css()
    assert ".agent-group-header" in result

def test_contains_collapsed_styles(self) -> None:
    result = timeline_css()
    assert ".collapsed" in result
```

### Step 9: JS for collapse/expand and hide-idle

In `timeline/views.py`, add to the JS block:

```javascript
// Agent group collapse/expand
(function() {
    document.querySelectorAll('.agent-group-header').forEach(function(header) {
        header.addEventListener('click', function() {
            var group = this.getAttribute('data-group');
            var collapsed = this.textContent.trim().startsWith('▸');
            var svg = document.getElementById('timeline-svg');
            if (!svg) return;

            // Toggle indicator
            var label = this.textContent.trim();
            if (collapsed) {
                this.textContent = '▾ ' + group;
            } else {
                this.textContent = '▸ ' + group;
            }

            // Toggle visibility of lanes, labels, and markers in this group
            svg.querySelectorAll('.lane-bg[data-agent-group="' + group + '"]').forEach(function(el) {
                el.classList.toggle('collapsed', !collapsed);
            });
            // Note: to properly hide agent labels and markers, we'd need
            // data-agent-group on those elements too. For now, use lane-bg visibility.
        });
    });

    // Hide idle
    var hideIdle = document.getElementById('hide-idle');
    if (hideIdle) {
        hideIdle.addEventListener('change', function() {
            var svg = document.getElementById('timeline-svg');
            if (!svg) return;
            var markers = svg.querySelectorAll('.event-marker');
            var activeAgents = new Set();
            markers.forEach(function(m) {
                // Determine agent from cy position
                var cy = parseFloat(m.getAttribute('cy'));
                activeAgents.add(cy);
            });

            svg.querySelectorAll('.lane-bg').forEach(function(lane, idx) {
                var laneCenter = 30 + idx * 50 + 25; // PADDING_TOP + idx * LANE_HEIGHT + LANE_HEIGHT/2
                if (hideIdle.checked && !activeAgents.has(laneCenter)) {
                    lane.classList.add('collapsed');
                } else {
                    lane.classList.remove('collapsed');
                }
            });
        });
    }
})();
```

---

## Phase C Verification

After completing C1 + C2:

```bash
cd /home/andrew/Documents/Projects/remora-demo/frontend && python -m pytest tests/ -q
```

Expected: ~298+ tests passing (253 baseline + ~25 Phase A + ~30 Phase B + ~18 Phase C).

### Checklist

- [ ] `render_minimap()` function exists and has 9 tests
- [ ] Minimap integrated into shell HTML
- [ ] Minimap CSS (.minimap-container) added
- [ ] Click-to-jump JS works
- [ ] Viewport sync JS works
- [ ] `group_agents()` function exists and has 7 tests
- [ ] `data-agent-group` attribute on lane backgrounds
- [ ] Group header text elements in SVG
- [ ] Hide-idle checkbox in controls
- [ ] Collapse/expand JS works
- [ ] All existing tests still pass
