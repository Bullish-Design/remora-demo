# Phase D Implementation Guide — Advanced Features

> Event Replay/Scrub, Performance Flame View, Time Range Brush, Export/Share.
> Estimated ~55 tests. Depends on Phases A–C (data attributes, filter controls, minimap).

## Table of Contents

1. [D1: Event Replay / Scrub](#d1-event-replay--scrub) — play/pause/step/scrub controls, progressive event masking (~18 tests)
2. [D2: Performance Flame View](#d2-performance-flame-view) — extract_spans(), flame bar rendering, Points/Bars toggle (~15 tests)
3. [D3: Time Range Brush](#d3-time-range-brush) — draggable range selector, sync with timeline and server (~12 tests)
4. [D4: Export / Share](#d4-export--share) — SVG/PNG/JSON export, share URL, /timeline/export route (~8 tests)

---

## D1: Event Replay / Scrub

### Overview

Client-side replay that progressively reveals events on the timeline. Controls: Play, Pause, Step Forward, Step Back, Speed selector (0.5x–4x), Scrub slider. Uses `data-event-id` attribute to show/hide markers by index.

### Step 1: Tests for `render_replay_controls()`

Add to `tests/test_timeline_views.py`:

```python
from timeline.views import render_replay_controls

class TestRenderReplayControls:
    def test_returns_string(self) -> None:
        result = render_replay_controls()
        assert isinstance(result, str)

    def test_contains_play_button(self) -> None:
        result = render_replay_controls()
        assert "replay-play" in result

    def test_contains_pause_button(self) -> None:
        result = render_replay_controls()
        assert "replay-pause" in result

    def test_contains_step_forward(self) -> None:
        result = render_replay_controls()
        assert "replay-step-fwd" in result

    def test_contains_step_back(self) -> None:
        result = render_replay_controls()
        assert "replay-step-back" in result

    def test_contains_scrub_slider(self) -> None:
        result = render_replay_controls()
        assert "replay-scrub" in result

    def test_contains_speed_selector(self) -> None:
        result = render_replay_controls()
        assert "replay-speed" in result

    def test_contains_replay_controls_class(self) -> None:
        result = render_replay_controls()
        assert "replay-controls" in result
```

### Step 2: Implement `render_replay_controls()`

Add to `timeline/views.py`:

```python
def render_replay_controls() -> str:
    """Render the event replay control bar.

    Provides play/pause/step controls, a scrub slider, and speed selector
    for client-side progressive event replay.
    """
    return """\
<div class="replay-controls" id="replay-controls">
  <button class="replay-btn" id="replay-step-back" title="Step back">⏮</button>
  <button class="replay-btn" id="replay-play" title="Play">▶</button>
  <button class="replay-btn" id="replay-pause" title="Pause" style="display:none">⏸</button>
  <button class="replay-btn" id="replay-step-fwd" title="Step forward">⏭</button>
  <input type="range" id="replay-scrub" class="replay-slider" min="0" max="0" value="0">
  <span id="replay-position" class="replay-position">0 / 0</span>
  <select id="replay-speed" class="replay-speed">
    <option value="2000">0.5x</option>
    <option value="1000" selected>1x</option>
    <option value="500">2x</option>
    <option value="250">4x</option>
  </select>
</div>"""
```

### Step 3: Tests for replay controls in shell

Add to `tests/test_timeline_views.py` in `TestRenderTimelineShell`:

```python
def test_includes_replay_controls(self) -> None:
    result = render_timeline_shell(self._make_data())
    assert "replay-controls" in result

def test_includes_replay_js(self) -> None:
    result = render_timeline_shell(self._make_data())
    assert "replayTo" in result
```

### Step 4: Integrate replay controls into shell

In `render_timeline_shell()`, call `render_replay_controls()` and insert the result between the controls bar and the timeline pane:

```python
replay = render_replay_controls()
```

Insert `{replay}` in the HTML template after the header/controls and before `.main`.

### Step 5: CSS for replay controls

Add to `timeline/css.py`:

```css
/* ---- Replay controls ---- */
.replay-controls {
    padding: 4px 16px;
    background: var(--surface);
    border-bottom: 1px solid var(--surface2);
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 11px;
}
.replay-btn {
    background: var(--surface2); border: none; color: var(--text);
    font-size: 14px; padding: 2px 8px; border-radius: 3px;
    cursor: pointer; transition: background 0.2s;
    font-family: inherit;
}
.replay-btn:hover { background: var(--overlay); }
.replay-btn.active { background: var(--blue); color: #1e1e2e; }
.replay-slider {
    flex: 1; min-width: 120px; accent-color: var(--blue);
}
.replay-position {
    color: var(--subtext); min-width: 60px; text-align: center;
}
.replay-speed {
    background: var(--surface2); color: var(--text); border: 1px solid var(--overlay);
    border-radius: 3px; font-family: inherit; font-size: 10px; padding: 2px 4px;
}
.event-marker.replay-hidden { display: none; }
```

### Step 6: Tests for replay CSS

Add to `tests/test_timeline_views.py` in `TestTimelineCss`:

```python
def test_contains_replay_styles(self) -> None:
    result = timeline_css()
    assert ".replay-controls" in result
    assert ".replay-btn" in result

def test_contains_replay_hidden_style(self) -> None:
    result = timeline_css()
    assert ".replay-hidden" in result
```

### Step 7: JS for replay state machine

Add to `timeline/views.py` — a new JS constant:

```python
REPLAY_JS = """\
(function() {
    var replayState = 'idle'; // idle, playing, paused
    var replayIndex = 0;
    var replayTimer = null;
    var allMarkers = [];

    function initReplay() {
        allMarkers = Array.from(document.querySelectorAll('.event-marker'));
        var scrub = document.getElementById('replay-scrub');
        var pos = document.getElementById('replay-position');
        if (scrub) {
            scrub.max = Math.max(0, allMarkers.length - 1);
            scrub.value = allMarkers.length - 1;
        }
        if (pos) pos.textContent = allMarkers.length + ' / ' + allMarkers.length;
        replayIndex = allMarkers.length; // show all by default
    }

    function replayTo(index) {
        replayIndex = Math.max(0, Math.min(index, allMarkers.length));
        allMarkers.forEach(function(m, i) {
            if (i < replayIndex) {
                m.classList.remove('replay-hidden');
            } else {
                m.classList.add('replay-hidden');
            }
        });
        var scrub = document.getElementById('replay-scrub');
        var pos = document.getElementById('replay-position');
        if (scrub) scrub.value = replayIndex;
        if (pos) pos.textContent = replayIndex + ' / ' + allMarkers.length;

        // Also hide correlation lines for hidden markers
        document.querySelectorAll('.correlation-line').forEach(function(line) {
            line.style.display = '';
        });
    }

    function getSpeed() {
        var sel = document.getElementById('replay-speed');
        return sel ? parseInt(sel.value) : 1000;
    }

    function play() {
        if (replayState === 'playing') return;
        replayState = 'playing';
        var playBtn = document.getElementById('replay-play');
        var pauseBtn = document.getElementById('replay-pause');
        if (playBtn) playBtn.style.display = 'none';
        if (pauseBtn) pauseBtn.style.display = '';
        if (replayIndex >= allMarkers.length) replayIndex = 0;

        function tick() {
            if (replayState !== 'playing') return;
            replayIndex++;
            replayTo(replayIndex);
            if (replayIndex >= allMarkers.length) {
                pause();
                return;
            }
            replayTimer = setTimeout(tick, getSpeed());
        }
        tick();
    }

    function pause() {
        replayState = 'paused';
        if (replayTimer) { clearTimeout(replayTimer); replayTimer = null; }
        var playBtn = document.getElementById('replay-play');
        var pauseBtn = document.getElementById('replay-pause');
        if (playBtn) playBtn.style.display = '';
        if (pauseBtn) pauseBtn.style.display = 'none';
    }

    var playBtn = document.getElementById('replay-play');
    var pauseBtn = document.getElementById('replay-pause');
    var stepFwd = document.getElementById('replay-step-fwd');
    var stepBack = document.getElementById('replay-step-back');
    var scrub = document.getElementById('replay-scrub');

    if (playBtn) playBtn.addEventListener('click', function() {
        if (allMarkers.length === 0) initReplay();
        play();
    });
    if (pauseBtn) pauseBtn.addEventListener('click', pause);
    if (stepFwd) stepFwd.addEventListener('click', function() {
        if (allMarkers.length === 0) initReplay();
        pause();
        replayTo(Math.min(replayIndex + 1, allMarkers.length));
    });
    if (stepBack) stepBack.addEventListener('click', function() {
        if (allMarkers.length === 0) initReplay();
        pause();
        replayTo(Math.max(replayIndex - 1, 0));
    });
    if (scrub) scrub.addEventListener('input', function() {
        if (allMarkers.length === 0) initReplay();
        pause();
        replayTo(parseInt(this.value));
    });

    // Reinitialize on SSE update
    var obs = new MutationObserver(initReplay);
    var svgParent = document.getElementById('timeline-pane');
    if (svgParent) obs.observe(svgParent, { childList: true, subtree: true });
    initReplay();
})();
"""
```

Include `REPLAY_JS` in the shell page's `<script>` block, after `TIMELINE_ZOOM_PAN_JS`.

### Step 8: Tests for replay JS behavior

Add to `tests/test_timeline_views.py` in `TestRenderTimelineShell`:

```python
def test_replay_state_machine_in_js(self) -> None:
    result = render_timeline_shell(self._make_data())
    assert "replayState" in result

def test_replay_play_pause_logic(self) -> None:
    result = render_timeline_shell(self._make_data())
    assert "play()" in result or "function play" in result
    assert "pause()" in result or "function pause" in result
```

---

## D2: Performance Flame View

### Overview

Pair `AgentStart` → `AgentComplete` events (by agent + correlation_id) into spans. Render spans as horizontal `<rect>` bars instead of point markers. Toggle between "Points" (default) and "Bars" view modes.

### Step 1: Tests for `extract_spans()`

Add to `tests/test_timeline_state.py`:

```python
from timeline.state import extract_spans

class TestExtractSpans:
    def test_returns_list(self) -> None:
        result = extract_spans([])
        assert isinstance(result, list)

    def test_pairs_start_complete(self) -> None:
        events = [
            {"event_id": 1, "event_type": "AgentStart", "timestamp": 1.0,
             "from_agent": "a", "to_agent": None, "correlation_id": "c1", "payload": "{}"},
            {"event_id": 2, "event_type": "AgentComplete", "timestamp": 3.0,
             "from_agent": "a", "to_agent": None, "correlation_id": "c1", "payload": "{}"},
        ]
        result = extract_spans(events)
        assert len(result) == 1
        assert result[0]["agent"] == "a"
        assert result[0]["start"] == 1.0
        assert result[0]["end"] == 3.0
        assert result[0]["correlation_id"] == "c1"

    def test_unpaired_start_ignored(self) -> None:
        events = [
            {"event_id": 1, "event_type": "AgentStart", "timestamp": 1.0,
             "from_agent": "a", "to_agent": None, "correlation_id": "c1", "payload": "{}"},
        ]
        result = extract_spans(events)
        assert len(result) == 0

    def test_unpaired_complete_ignored(self) -> None:
        events = [
            {"event_id": 1, "event_type": "AgentComplete", "timestamp": 2.0,
             "from_agent": "a", "to_agent": None, "correlation_id": "c1", "payload": "{}"},
        ]
        result = extract_spans(events)
        assert len(result) == 0

    def test_multiple_spans(self) -> None:
        events = [
            {"event_id": 1, "event_type": "AgentStart", "timestamp": 1.0,
             "from_agent": "a", "to_agent": None, "correlation_id": "c1", "payload": "{}"},
            {"event_id": 2, "event_type": "AgentStart", "timestamp": 1.5,
             "from_agent": "b", "to_agent": None, "correlation_id": "c2", "payload": "{}"},
            {"event_id": 3, "event_type": "AgentComplete", "timestamp": 2.0,
             "from_agent": "a", "to_agent": None, "correlation_id": "c1", "payload": "{}"},
            {"event_id": 4, "event_type": "AgentComplete", "timestamp": 3.0,
             "from_agent": "b", "to_agent": None, "correlation_id": "c2", "payload": "{}"},
        ]
        result = extract_spans(events)
        assert len(result) == 2
        agents = [s["agent"] for s in result]
        assert "a" in agents
        assert "b" in agents

    def test_null_correlation_uses_agent_only(self) -> None:
        """Without correlation_id, pair by agent name alone (first-in-first-out)."""
        events = [
            {"event_id": 1, "event_type": "AgentStart", "timestamp": 1.0,
             "from_agent": "a", "to_agent": None, "correlation_id": None, "payload": "{}"},
            {"event_id": 2, "event_type": "AgentComplete", "timestamp": 2.0,
             "from_agent": "a", "to_agent": None, "correlation_id": None, "payload": "{}"},
        ]
        result = extract_spans(events)
        assert len(result) == 1

    def test_span_fields(self) -> None:
        events = [
            {"event_id": 1, "event_type": "AgentStart", "timestamp": 10.0,
             "from_agent": "loader", "to_agent": None, "correlation_id": "x", "payload": "{}"},
            {"event_id": 2, "event_type": "AgentComplete", "timestamp": 15.0,
             "from_agent": "loader", "to_agent": None, "correlation_id": "x", "payload": "{}"},
        ]
        result = extract_spans(events)
        span = result[0]
        assert "agent" in span
        assert "start" in span
        assert "end" in span
        assert "correlation_id" in span
```

### Step 2: Implement `extract_spans()`

Add to `timeline/state.py`:

```python
def extract_spans(events: list[dict]) -> list[dict]:
    """Pair AgentStart → AgentComplete events into duration spans.

    Pairs by (agent, correlation_id). If correlation_id is None, pairs
    by agent name alone using first-in-first-out.

    Returns:
        List of span dicts with keys: agent, start, end, correlation_id.
    """
    # Map (agent, correlation_id) → list of start timestamps
    pending: dict[tuple[str, str | None], list[float]] = {}
    spans: list[dict] = []

    for ev in events:
        agent = ev.get("from_agent")
        if agent is None:
            continue
        cid = ev.get("correlation_id")
        key = (agent, cid)

        if ev["event_type"] == "AgentStart":
            pending.setdefault(key, []).append(ev["timestamp"])
        elif ev["event_type"] == "AgentComplete":
            starts = pending.get(key, [])
            if starts:
                start_ts = starts.pop(0)
                spans.append({
                    "agent": agent,
                    "start": start_ts,
                    "end": ev["timestamp"],
                    "correlation_id": cid,
                })

    return spans
```

### Step 3: Tests for `render_flame_bar()`

Add to `tests/test_timeline_svg.py`:

```python
from timeline.svg import render_flame_bar

class TestRenderFlameBar:
    def test_returns_string(self) -> None:
        result = render_flame_bar(x=0, y=0, width=100, height=30, agent="a", color="#89b4fa")
        assert isinstance(result, str)

    def test_returns_rect(self) -> None:
        result = render_flame_bar(x=10, y=20, width=80, height=25, agent="a", color="#89b4fa")
        assert "<rect" in result

    def test_position_and_size(self) -> None:
        result = render_flame_bar(x=50, y=100, width=200, height=30, agent="a", color="#89b4fa")
        assert 'x="50"' in result or "50" in result
        assert "200" in result  # width
        assert "30" in result   # height

    def test_flame_bar_class(self) -> None:
        result = render_flame_bar(x=0, y=0, width=100, height=30, agent="a", color="#89b4fa")
        assert "flame-bar" in result

    def test_color_applied(self) -> None:
        result = render_flame_bar(x=0, y=0, width=100, height=30, agent="a", color="#f38ba8")
        assert "#f38ba8" in result
```

### Step 4: Implement `render_flame_bar()`

Add to `timeline/svg.py`:

```python
def render_flame_bar(
    *,
    x: float,
    y: float,
    width: float,
    height: float,
    agent: str,
    color: str,
) -> str:
    """Render a flame bar as a colored rectangle for a span duration."""
    escaped_agent = html_mod.escape(agent)
    return (
        f'<rect x="{x}" y="{y}" width="{width}" height="{height}" '
        f'fill="{color}" opacity="0.7" rx="3" class="flame-bar" '
        f'data-agent="{escaped_agent}"><title>{escaped_agent}</title></rect>'
    )
```

### Step 5: Tests for `render_flame_view()`

Add to `tests/test_timeline_svg.py`:

```python
from timeline.svg import render_flame_view

class TestRenderFlameView:
    def _make_data(self) -> TimelineData:
        return TimelineData(
            agents=["agent_a", "agent_b"],
            events=[
                {"event_id": 1, "event_type": "AgentStart", "timestamp": 1.0,
                 "from_agent": "agent_a", "to_agent": None, "correlation_id": "c1", "payload": "{}"},
                {"event_id": 2, "event_type": "AgentComplete", "timestamp": 3.0,
                 "from_agent": "agent_a", "to_agent": None, "correlation_id": "c1", "payload": "{}"},
            ],
            correlation_groups={"c1": [1, 2]},
            time_range=(1.0, 3.0),
        )

    def test_returns_string(self) -> None:
        spans = [{"agent": "agent_a", "start": 1.0, "end": 3.0, "correlation_id": "c1"}]
        result = render_flame_view(self._make_data(), spans, width=1200)
        assert isinstance(result, str)

    def test_returns_svg(self) -> None:
        spans = [{"agent": "agent_a", "start": 1.0, "end": 3.0, "correlation_id": "c1"}]
        result = render_flame_view(self._make_data(), spans, width=1200)
        assert "<svg" in result
        assert "</svg>" in result

    def test_contains_flame_bars(self) -> None:
        spans = [{"agent": "agent_a", "start": 1.0, "end": 3.0, "correlation_id": "c1"}]
        result = render_flame_view(self._make_data(), spans, width=1200)
        assert "flame-bar" in result

    def test_empty_spans(self) -> None:
        result = render_flame_view(self._make_data(), [], width=1200)
        assert "<svg" in result

    def test_contains_agent_labels(self) -> None:
        spans = [{"agent": "agent_a", "start": 1.0, "end": 3.0, "correlation_id": "c1"}]
        result = render_flame_view(self._make_data(), spans, width=1200)
        assert "agent_a" in result
```

### Step 6: Implement `render_flame_view()`

Add to `timeline/svg.py`:

```python
def render_flame_view(
    data: TimelineData,
    spans: list[dict],
    width: int = 1200,
) -> str:
    """Render a flame chart SVG showing agent spans as horizontal bars.

    Uses the same layout geometry as render_timeline_svg (same lane heights,
    label width, padding) so the views can toggle seamlessly.
    """
    num_agents = len(data.agents)
    height = PADDING_TOP + num_agents * LANE_HEIGHT + PADDING_BOTTOM

    x_start = LABEL_WIDTH
    x_end = width - PADDING_RIGHT
    t_min, t_max = data.time_range
    duration = t_max - t_min

    def time_to_x(t: float) -> float:
        if duration <= 0:
            return (x_start + x_end) / 2
        frac = (t - t_min) / duration
        return x_start + frac * (x_end - x_start)

    agent_index = {agent: i for i, agent in enumerate(data.agents)}

    parts = [
        f'<svg id="timeline-svg" viewBox="0 0 {width} {height}" '
        f'xmlns="http://www.w3.org/2000/svg" class="timeline-canvas" '
        f'preserveAspectRatio="xMidYMid meet">'
    ]

    # Lane backgrounds
    for i, agent in enumerate(data.agents):
        lane_y = PADDING_TOP + i * LANE_HEIGHT
        bg = LANE_BG_ODD if i % 2 else LANE_BG_EVEN
        parts.append(
            f'<rect x="0" y="{lane_y}" width="{width}" height="{LANE_HEIGHT}" '
            f'fill="{bg}" class="lane-bg"/>'
        )

    # Agent labels
    for agent in data.agents:
        label_y = PADDING_TOP + agent_index[agent] * LANE_HEIGHT + LANE_HEIGHT / 2 + 4
        parts.append(render_agent_label(agent, label_y))

    # Separator line
    parts.append(
        f'<line x1="{LABEL_WIDTH}" y1="{PADDING_TOP}" '
        f'x2="{LABEL_WIDTH}" y2="{PADDING_TOP + num_agents * LANE_HEIGHT}" '
        f'stroke="#585b70" stroke-width="1" opacity="0.3"/>'
    )

    # Flame bars
    bar_height = LANE_HEIGHT * 0.6
    for span in spans:
        agent = span["agent"]
        if agent not in agent_index:
            continue
        idx = agent_index[agent]
        x1 = time_to_x(span["start"])
        x2 = time_to_x(span["end"])
        bar_w = max(2, x2 - x1)  # minimum 2px width
        bar_y = PADDING_TOP + idx * LANE_HEIGHT + (LANE_HEIGHT - bar_height) / 2
        color = EVENT_TYPE_COLORS.get("AgentStart", DEFAULT_COLOR)  # blue for spans
        parts.append(
            render_flame_bar(
                x=x1, y=bar_y, width=bar_w, height=bar_height,
                agent=agent, color=color,
            )
        )

    # Time axis
    axis_y = PADDING_TOP + num_agents * LANE_HEIGHT + 5
    parts.append(
        render_time_axis(
            time_range=data.time_range,
            x_start=float(x_start),
            x_end=float(x_end),
            y=axis_y,
        )
    )

    parts.append("</svg>")
    return "".join(parts)
```

### Step 7: Tests for mode toggle in shell

Add to `tests/test_timeline_views.py` in `TestRenderTimelineShell`:

```python
def test_includes_mode_toggle(self) -> None:
    result = render_timeline_shell(self._make_data())
    assert "mode-toggle" in result or "Points" in result

def test_mode_toggle_has_bars_option(self) -> None:
    result = render_timeline_shell(self._make_data())
    assert "Bars" in result
```

### Step 8: Add mode toggle to shell

In `timeline/views.py`, add mode toggle buttons in the controls area:

```html
<div class="mode-toggle" id="mode-toggle">
  <button class="btn active" id="mode-points" data-mode="points">Points</button>
  <button class="btn" id="mode-bars" data-mode="bars">Bars</button>
</div>
```

JS for mode toggle:

```javascript
// Mode toggle
document.querySelectorAll('#mode-toggle .btn').forEach(function(btn) {
    btn.addEventListener('click', function() {
        document.querySelectorAll('#mode-toggle .btn').forEach(function(b) {
            b.classList.remove('active');
        });
        this.classList.add('active');
        var mode = this.getAttribute('data-mode');
        var params = new URLSearchParams(window.location.search);
        params.set('mode', mode);
        window.location.search = '?' + params.toString();
    });
});
```

### Step 9: CSS for flame view

Add to `timeline/css.py`:

```css
/* ---- Flame view ---- */
.flame-bar {
    cursor: pointer;
    transition: opacity 0.2s;
}
.flame-bar:hover { opacity: 1 !important; }
.mode-toggle {
    display: inline-flex; gap: 0;
    border: 1px solid var(--surface2); border-radius: 3px;
    overflow: hidden;
}
.mode-toggle .btn {
    border-radius: 0; border: none; border-right: 1px solid var(--surface2);
    padding: 3px 10px;
}
.mode-toggle .btn:last-child { border-right: none; }
```

### Step 10: Route changes for mode param

In `graph/app.py`, the `timeline_subscribe` handler should parse a `mode` query param. When mode is `"bars"`:

1. Call `extract_spans()` on the events
2. Call `render_flame_view()` instead of `render_timeline_svg()`

```python
# In timeline_subscribe handler:
mode = query.get("mode", "points")
if mode == "bars":
    from timeline.state import extract_spans
    spans = extract_spans(data.events)
    from timeline.svg import render_flame_view
    svg_html = render_flame_view(data, spans, width=1200)
else:
    svg_html = render_timeline_svg(data)
w.patch(SafeString(svg_html))
```

---

## D3: Time Range Brush

### Overview

An overview SVG (similar to minimap but with draggable range handles) that lets the user select a time range. Dragging the handles updates `since`/`until` filter params and re-subscribes.

### Step 1: Tests for `render_brush()`

Add to `tests/test_timeline_svg.py`:

```python
from timeline.svg import render_brush

class TestRenderBrush:
    def _make_data(self) -> TimelineData:
        events = [
            {"event_id": i + 1, "event_type": "AgentStart", "timestamp": float(i),
             "from_agent": "a", "to_agent": None, "correlation_id": None, "payload": "{}"}
            for i in range(10)
        ]
        return TimelineData(
            agents=["a"], events=events, time_range=(0.0, 9.0),
        )

    def test_returns_string(self) -> None:
        result = render_brush(self._make_data(), width=800)
        assert isinstance(result, str)

    def test_returns_svg(self) -> None:
        result = render_brush(self._make_data(), width=800)
        assert "<svg" in result
        assert "</svg>" in result

    def test_has_brush_class(self) -> None:
        result = render_brush(self._make_data(), width=800)
        assert "brush-svg" in result

    def test_contains_handles(self) -> None:
        result = render_brush(self._make_data(), width=800)
        assert "brush-handle" in result

    def test_contains_range_rect(self) -> None:
        result = render_brush(self._make_data(), width=800)
        assert "brush-range" in result

    def test_contains_context_bars(self) -> None:
        """Should show event density as context."""
        result = render_brush(self._make_data(), width=800)
        assert "<rect" in result

    def test_empty_data(self) -> None:
        result = render_brush(TimelineData(), width=800)
        assert "<svg" in result

    def test_custom_height(self) -> None:
        result = render_brush(self._make_data(), width=800, height=60)
        assert "60" in result
```

### Step 2: Implement `render_brush()`

Add to `timeline/svg.py`:

```python
def render_brush(
    data: TimelineData,
    width: int,
    height: int = 50,
    num_bins: int = 50,
) -> str:
    """Render a time range brush SVG with draggable handles.

    Shows event density as context bars with two draggable handle lines
    and a semi-transparent selected range rectangle.
    """
    if not data.events:
        return (
            f'<svg class="brush-svg" viewBox="0 0 {width} {height}" '
            f'xmlns="http://www.w3.org/2000/svg" '
            f'preserveAspectRatio="xMidYMid meet"></svg>'
        )

    t_min, t_max = data.time_range
    duration = t_max - t_min

    # Bin events
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
        f'<svg class="brush-svg" viewBox="0 0 {width} {height}" '
        f'xmlns="http://www.w3.org/2000/svg" '
        f'preserveAspectRatio="xMidYMid meet">'
    ]

    # Background
    parts.append(
        f'<rect x="0" y="0" width="{width}" height="{height}" '
        f'fill="#181825" class="brush-bg"/>'
    )

    # Context density bars
    bar_width = width / num_bins
    for i, count in enumerate(bins):
        if count == 0:
            continue
        bar_height = (count / max_count) * (height - 8)
        bar_x = i * bar_width
        bar_y = height - bar_height - 4
        parts.append(
            f'<rect x="{bar_x:.1f}" y="{bar_y:.1f}" '
            f'width="{bar_width:.1f}" height="{bar_height:.1f}" '
            f'fill="#6c7086" opacity="0.4"/>'
        )

    # Selected range rect (full width initially)
    parts.append(
        f'<rect x="0" y="0" width="{width}" height="{height}" '
        f'fill="rgba(137,180,250,0.1)" class="brush-range" id="brush-range"/>'
    )

    # Left handle
    parts.append(
        f'<rect x="0" y="0" width="8" height="{height}" '
        f'fill="#89b4fa" rx="2" class="brush-handle" id="brush-handle-left" '
        f'cursor="ew-resize"/>'
    )

    # Right handle
    parts.append(
        f'<rect x="{width - 8}" y="0" width="8" height="{height}" '
        f'fill="#89b4fa" rx="2" class="brush-handle" id="brush-handle-right" '
        f'cursor="ew-resize"/>'
    )

    parts.append("</svg>")
    return "".join(parts)
```

### Step 3: Tests for brush in shell

Add to `tests/test_timeline_views.py` in `TestRenderTimelineShell`:

```python
def test_includes_brush(self) -> None:
    result = render_timeline_shell(self._make_data())
    assert "brush-container" in result or "brush-svg" in result
```

### Step 4: Integrate brush into shell

In `timeline/views.py`, import `render_brush` from `timeline/svg.py`.

In `render_timeline_shell()`, render the brush and insert below the minimap:

```python
from timeline.svg import render_timeline_svg, render_minimap, render_brush

brush = render_brush(data, width=1200)
```

```html
<div class="brush-container" id="brush-container">
  {brush}
</div>
```

### Step 5: CSS for brush

Add to `timeline/css.py`:

```css
/* ---- Time range brush ---- */
.brush-container {
    position: absolute;
    bottom: 42px; /* above minimap */
    left: 0; right: 0;
    height: 50px;
    background: var(--mantle);
    border-top: 1px solid var(--surface2);
    z-index: 10;
}
.brush-svg { width: 100%; height: 100%; display: block; }
.brush-handle {
    cursor: ew-resize;
    transition: fill 0.2s;
}
.brush-handle:hover { fill: #b4befe; }
.brush-range { pointer-events: none; }
```

### Step 6: Tests for brush CSS

Add to `tests/test_timeline_views.py` in `TestTimelineCss`:

```python
def test_contains_brush_styles(self) -> None:
    result = timeline_css()
    assert ".brush-container" in result
    assert ".brush-handle" in result
```

### Step 7: JS for brush drag interaction

In `timeline/views.py`, add to the JS block:

```javascript
// Time range brush
(function() {
    var brushContainer = document.getElementById('brush-container');
    if (!brushContainer) return;

    var handleLeft = document.getElementById('brush-handle-left');
    var handleRight = document.getElementById('brush-handle-right');
    var rangeRect = document.getElementById('brush-range');
    if (!handleLeft || !handleRight || !rangeRect) return;

    var dragging = null; // 'left' or 'right'

    function startDrag(handle) {
        return function(e) {
            dragging = handle;
            e.preventDefault();
        };
    }

    handleLeft.addEventListener('mousedown', startDrag('left'));
    handleRight.addEventListener('mousedown', startDrag('right'));

    document.addEventListener('mousemove', function(e) {
        if (!dragging) return;
        var rect = brushContainer.getBoundingClientRect();
        var x = Math.max(0, Math.min(rect.width, e.clientX - rect.left));

        if (dragging === 'left') {
            handleLeft.setAttribute('x', Math.max(0, x - 4));
            var rightX = parseFloat(handleRight.getAttribute('x'));
            rangeRect.setAttribute('x', x);
            rangeRect.setAttribute('width', Math.max(0, rightX - x));
        } else {
            handleRight.setAttribute('x', Math.min(rect.width - 8, x - 4));
            var leftX = parseFloat(handleLeft.getAttribute('x')) + 4;
            rangeRect.setAttribute('width', Math.max(0, x - leftX));
        }
    });

    document.addEventListener('mouseup', function() {
        if (!dragging) return;
        dragging = null;

        // Calculate time range from handle positions
        var rect = brushContainer.getBoundingClientRect();
        var leftX = parseFloat(handleLeft.getAttribute('x')) + 4;
        var rightX = parseFloat(handleRight.getAttribute('x')) + 4;
        var fracLeft = leftX / rect.width;
        var fracRight = rightX / rect.width;

        // Get the full time range from page metadata
        // (Could embed as data attributes or use a JS variable)
        var params = new URLSearchParams(window.location.search);
        // We store the fraction as since/until fractional — route handler
        // will need access to the full time range to convert these back.
        // Alternative: embed t_min/t_max as data attrs on brush container.
        if (fracLeft > 0.01) params.set('brush_left', fracLeft.toFixed(4));
        else params.delete('brush_left');
        if (fracRight < 0.99) params.set('brush_right', fracRight.toFixed(4));
        else params.delete('brush_right');

        // Re-subscribe with new range
        window.location.search = '?' + params.toString();
    });
})();
```

**NOTE**: The actual `since`/`until` conversion requires knowing the data's `time_range`. A cleaner approach is to embed `data-time-min` and `data-time-max` attributes on the brush container:

```html
<div class="brush-container" id="brush-container"
     data-time-min="{data.time_range[0]}"
     data-time-max="{data.time_range[1]}">
```

Then in the mouseup handler:

```javascript
var tMin = parseFloat(brushContainer.getAttribute('data-time-min'));
var tMax = parseFloat(brushContainer.getAttribute('data-time-max'));
var duration = tMax - tMin;
var since = tMin + fracLeft * duration;
var until = tMin + fracRight * duration;
params.set('since', since.toFixed(6));
params.set('until', until.toFixed(6));
```

---

## D4: Export / Share

### Overview

Export the current timeline view as SVG (serialize DOM), PNG (canvas), or JSON (server route). Also copy a shareable URL with current filter params.

### Step 1: Tests for export route

Add to `tests/test_app.py` in `TestAppModuleStructure`:

```python
def test_app_source_has_timeline_export_route(self) -> None:
    from pathlib import Path
    source = (Path(__file__).parent.parent / "graph" / "app.py").read_text()
    assert 'app.get("/timeline/export"' in source

def test_app_source_has_timeline_export_handler(self) -> None:
    from pathlib import Path
    source = (Path(__file__).parent.parent / "graph" / "app.py").read_text()
    assert "def timeline_export(" in source
```

### Step 2: Implement `/timeline/export` route

Add to `graph/app.py`:

```python
def timeline_export(state: GraphState):
    """GET /timeline/export — return filtered events as JSON."""
    async def handler(c: Context, w: Writer) -> None:
        query = c.req.query
        # Parse same filter params as timeline_subscribe
        kwargs = _parse_timeline_query_params(query)
        conn = state._get_conn()
        data = await asyncio.to_thread(read_timeline_data, conn, **kwargs)
        import json
        w.json(json.dumps({
            "agents": data.agents,
            "events": data.events,
            "time_range": list(data.time_range),
            "correlation_groups": data.correlation_groups,
        }))
    return handler
```

**NOTE**: `_parse_timeline_query_params()` is a helper that encapsulates the query param parsing logic shared between `timeline_subscribe` and `timeline_export`. Extract the parsing code from the subscribe handler (added in B1) into this helper.

Register the route:

```python
app.get("/timeline/export", timeline_export(state))
```

### Step 3: Tests for export UI in shell

Add to `tests/test_timeline_views.py` in `TestRenderTimelineShell`:

```python
def test_includes_export_buttons(self) -> None:
    result = render_timeline_shell(self._make_data())
    assert "export" in result.lower()

def test_export_has_svg_option(self) -> None:
    result = render_timeline_shell(self._make_data())
    assert "SVG" in result

def test_export_has_json_option(self) -> None:
    result = render_timeline_shell(self._make_data())
    assert "JSON" in result

def test_export_has_copy_link(self) -> None:
    result = render_timeline_shell(self._make_data())
    assert "Copy Link" in result or "copy-link" in result
```

### Step 4: Add export UI to shell

In `timeline/views.py`, add export buttons in the controls area:

```html
<div class="export-menu" id="export-menu">
  <button class="btn" id="export-svg">SVG</button>
  <button class="btn" id="export-png">PNG</button>
  <button class="btn" id="export-json">JSON</button>
  <button class="btn" id="export-copy-link">Copy Link</button>
</div>
```

### Step 5: CSS for export

Add to `timeline/css.py`:

```css
/* ---- Export menu ---- */
.export-menu {
    display: inline-flex; gap: 4px; margin-left: auto;
}
```

### Step 6: Tests for export CSS

Add to `tests/test_timeline_views.py` in `TestTimelineCss`:

```python
def test_contains_export_styles(self) -> None:
    result = timeline_css()
    assert ".export-menu" in result
```

### Step 7: JS for export actions

In `timeline/views.py`, add to the JS block:

```javascript
// Export actions
(function() {
    // SVG export
    var svgBtn = document.getElementById('export-svg');
    if (svgBtn) svgBtn.addEventListener('click', function() {
        var svg = document.getElementById('timeline-svg');
        if (!svg) return;
        var serializer = new XMLSerializer();
        var svgStr = serializer.serializeToString(svg);
        var blob = new Blob([svgStr], { type: 'image/svg+xml' });
        var url = URL.createObjectURL(blob);
        var a = document.createElement('a');
        a.href = url; a.download = 'timeline.svg'; a.click();
        URL.revokeObjectURL(url);
    });

    // PNG export
    var pngBtn = document.getElementById('export-png');
    if (pngBtn) pngBtn.addEventListener('click', function() {
        var svg = document.getElementById('timeline-svg');
        if (!svg) return;
        var serializer = new XMLSerializer();
        var svgStr = serializer.serializeToString(svg);
        var canvas = document.createElement('canvas');
        var box = svg.viewBox.baseVal;
        canvas.width = box.width * 2; canvas.height = box.height * 2;
        var ctx = canvas.getContext('2d');
        var img = new Image();
        img.onload = function() {
            ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
            var a = document.createElement('a');
            a.href = canvas.toDataURL('image/png');
            a.download = 'timeline.png'; a.click();
        };
        img.src = 'data:image/svg+xml;base64,' + btoa(unescape(encodeURIComponent(svgStr)));
    });

    // JSON export
    var jsonBtn = document.getElementById('export-json');
    if (jsonBtn) jsonBtn.addEventListener('click', function() {
        var params = new URLSearchParams(window.location.search);
        fetch('/timeline/export?' + params.toString())
            .then(function(r) { return r.blob(); })
            .then(function(blob) {
                var url = URL.createObjectURL(blob);
                var a = document.createElement('a');
                a.href = url; a.download = 'timeline.json'; a.click();
                URL.revokeObjectURL(url);
            });
    });

    // Copy Link
    var linkBtn = document.getElementById('export-copy-link');
    if (linkBtn) linkBtn.addEventListener('click', function() {
        var url = window.location.href;
        navigator.clipboard.writeText(url).then(function() {
            linkBtn.textContent = 'Copied!';
            setTimeout(function() { linkBtn.textContent = 'Copy Link'; }, 2000);
        });
    });
})();
```

---

## Phase D Verification

After completing D1 + D2 + D3 + D4:

```bash
cd /home/andrew/Documents/Projects/remora-demo/frontend && python -m pytest tests/ -q
```

Expected: ~350+ tests passing (253 baseline + ~25 Phase A + ~30 Phase B + ~18 Phase C + ~55 Phase D).

### Checklist

- [ ] `render_replay_controls()` exists with 8 tests
- [ ] Replay controls in shell, replay JS with state machine
- [ ] Replay CSS (.replay-controls, .replay-btn, .replay-hidden)
- [ ] `extract_spans()` exists with 7 tests
- [ ] `render_flame_bar()` exists with 5 tests
- [ ] `render_flame_view()` exists with 5 tests
- [ ] Mode toggle (Points/Bars) in shell
- [ ] Flame CSS (.flame-bar, .mode-toggle)
- [ ] `render_brush()` exists with 8 tests
- [ ] Brush in shell with drag JS
- [ ] Brush CSS (.brush-container, .brush-handle, .brush-range)
- [ ] `/timeline/export` route exists with 2 tests
- [ ] Export buttons (SVG/PNG/JSON/Copy Link) with 4 tests
- [ ] Export CSS (.export-menu)
- [ ] Export JS for all 4 actions
- [ ] All existing tests still pass
