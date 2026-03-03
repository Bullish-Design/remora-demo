# Phase B Implementation Guide — Core Interactivity

> Filter Controls UI, Keyboard Navigation, Event Search.
> Estimated ~30 tests. Depends on Phase A (data-event-type, data-correlation-id attributes).

## Table of Contents

1. [B1: Filter Controls UI](#b1-filter-controls-ui) — event_types param, controls bar HTML, query param parsing
2. [B2: Keyboard Navigation](#b2-keyboard-navigation) — vim-style keys, focus tracking, help overlay
3. [B3: Event Search](#b3-event-search) — search param, LIKE queries, search input UI

---

## B1: Filter Controls UI

### Step 1: Tests for `event_types` filter in data layer

Add to `tests/test_timeline_state.py` in `TestTimelineFiltering`:

```python
def test_filter_by_event_types(self) -> None:
    conn = _create_db()
    _insert_event(conn, from_agent="a", timestamp=1.0, event_type="AgentStart")
    _insert_event(conn, from_agent="a", timestamp=2.0, event_type="AgentComplete")
    _insert_event(conn, from_agent="a", timestamp=3.0, event_type="AgentError")
    result = read_timeline_data(conn, event_types=["AgentStart", "AgentError"])
    types = [e["event_type"] for e in result.events]
    assert "AgentStart" in types
    assert "AgentError" in types
    assert "AgentComplete" not in types

def test_filter_by_event_types_single(self) -> None:
    conn = _create_db()
    _insert_event(conn, from_agent="a", timestamp=1.0, event_type="AgentStart")
    _insert_event(conn, from_agent="a", timestamp=2.0, event_type="AgentComplete")
    result = read_timeline_data(conn, event_types=["AgentComplete"])
    assert len(result.events) == 1
    assert result.events[0]["event_type"] == "AgentComplete"

def test_filter_event_types_with_other_filters(self) -> None:
    conn = _create_db()
    _insert_event(conn, from_agent="a", timestamp=1.0, event_type="AgentStart", correlation_id="c1")
    _insert_event(conn, from_agent="b", timestamp=2.0, event_type="AgentStart", correlation_id="c2")
    _insert_event(conn, from_agent="a", timestamp=3.0, event_type="AgentComplete", correlation_id="c1")
    result = read_timeline_data(conn, event_types=["AgentStart"], agent_ids=["a"])
    assert len(result.events) == 1
    assert result.events[0]["event_type"] == "AgentStart"
    assert result.events[0]["from_agent"] == "a"
```

### Step 2: Implement `event_types` filter

In `timeline/state.py`, add `event_types: list[str] | None = None` parameter to `read_timeline_data()`:

```python
def read_timeline_data(
    conn: sqlite3.Connection,
    *,
    since: float | None = None,
    until: float | None = None,
    agent_ids: list[str] | None = None,
    correlation_id: str | None = None,
    event_types: list[str] | None = None,
    limit: int | None = None,
) -> TimelineData:
```

Add to the WHERE clause building section (after the `agent_ids` block):

```python
if event_types is not None:
    placeholders = ",".join("?" for _ in event_types)
    conditions.append(f"event_type IN ({placeholders})")
    params.extend(event_types)
```

### Step 3: Tests for controls bar in shell

Add to `tests/test_timeline_views.py` in `TestRenderTimelineShell`:

```python
def test_includes_controls_bar(self) -> None:
    result = render_timeline_shell(self._make_data())
    assert "timeline-controls" in result

def test_controls_bar_has_event_type_filter(self) -> None:
    result = render_timeline_shell(self._make_data())
    assert "event-type-filter" in result or "eventTypes" in result

def test_controls_bar_has_agent_filter(self) -> None:
    result = render_timeline_shell(self._make_data())
    assert "agent-filter" in result or "agentFilter" in result

def test_controls_bar_has_limit_control(self) -> None:
    result = render_timeline_shell(self._make_data())
    assert "limit" in result.lower()
```

### Step 4: Implement `render_controls_bar()`

Add to `timeline/views.py`:

```python
def render_controls_bar(data: TimelineData) -> str:
    """Render the filter controls bar above the timeline."""
    # Collect observed event types and agents
    event_types = sorted(set(ev["event_type"] for ev in data.events))
    agents = data.agents

    type_options = "".join(
        f'<option value="{html_mod.escape(et)}">{html_mod.escape(et)}</option>'
        for et in event_types
    )
    agent_options = "".join(
        f'<option value="{html_mod.escape(a)}">{html_mod.escape(a)}</option>'
        for a in agents
    )

    return f"""\
<div class="timeline-controls" id="timeline-controls">
  <label>Types:</label>
  <select multiple id="event-type-filter" class="filter-select">{type_options}</select>
  <label>Agents:</label>
  <select multiple id="agent-filter" class="filter-select">{agent_options}</select>
  <label>Correlation:</label>
  <input type="text" id="correlation-filter" class="filter-input" placeholder="correlation id">
  <label>Limit:</label>
  <input type="range" id="limit-slider" min="10" max="1000" value="500" class="filter-slider">
  <span id="limit-value">500</span>
  <button class="btn" id="apply-filters-btn">Apply</button>
</div>"""
```

Integrate into `render_timeline_shell()` — place the controls bar inside the `.app` div, between the header and `.main`.

### Step 5: CSS for controls

Add to `timeline/css.py`:

```css
/* ---- Filter controls ---- */
.filter-select {
    background: var(--surface2); color: var(--text); border: 1px solid var(--overlay);
    border-radius: 3px; font-family: inherit; font-size: 10px; padding: 2px 4px;
    max-width: 150px;
}
.filter-input {
    background: var(--surface2); color: var(--text); border: 1px solid var(--overlay);
    border-radius: 3px; font-family: inherit; font-size: 10px; padding: 3px 6px;
    width: 120px;
}
.filter-slider {
    width: 80px; accent-color: var(--blue);
}
```

### Step 6: JS for filter application

In `timeline/views.py`, add JS:

```javascript
// Filter controls
var applyBtn = document.getElementById('apply-filters-btn');
if (applyBtn) {
    applyBtn.addEventListener('click', function() {
        var params = new URLSearchParams();
        var typeSelect = document.getElementById('event-type-filter');
        if (typeSelect) {
            Array.from(typeSelect.selectedOptions).forEach(function(o) {
                params.append('event_types', o.value);
            });
        }
        var agentSelect = document.getElementById('agent-filter');
        if (agentSelect) {
            Array.from(agentSelect.selectedOptions).forEach(function(o) {
                params.append('agent_ids', o.value);
            });
        }
        var corrInput = document.getElementById('correlation-filter');
        if (corrInput && corrInput.value) params.set('correlation_id', corrInput.value);
        var limitSlider = document.getElementById('limit-slider');
        if (limitSlider) params.set('limit', limitSlider.value);
        // Trigger new SSE subscription with filters
        // Datastar: update the body's data-on-load to include query params
        var url = '/timeline/subscribe?' + params.toString();
        // Use Datastar to re-subscribe
        document.body.setAttribute('data-on-load', "@get('" + url + "')");
        // Force re-connection by dispatching a custom event or page nav
        window.location.search = '?' + params.toString();
    });
    // Limit slider value display
    var limitSlider = document.getElementById('limit-slider');
    var limitValue = document.getElementById('limit-value');
    if (limitSlider && limitValue) {
        limitSlider.addEventListener('input', function() {
            limitValue.textContent = this.value;
        });
    }
}
```

### Step 7: Route changes for query param parsing

Add to `tests/test_app.py` in `TestAppModuleStructure`:

```python
def test_timeline_subscribe_parses_query_params(self) -> None:
    from pathlib import Path
    source = (Path(__file__).parent.parent / "graph" / "app.py").read_text()
    assert "event_types" in source or "c.req.query" in source
```

In `graph/app.py`, update `timeline_subscribe()` to parse query params:

```python
def timeline_subscribe(state: GraphState, relay: Relay):
    async def handler(c: Context, w: Writer) -> None:
        c("timeline.subscribe.connected")

        # Parse filter params from query string
        query = c.req.query
        event_types = query.getlist("event_types") if hasattr(query, "getlist") else query.get("event_types")
        agent_ids = query.getlist("agent_ids") if hasattr(query, "getlist") else query.get("agent_ids")
        correlation_id = query.get("correlation_id")
        limit_str = query.get("limit")
        limit = int(limit_str) if limit_str else None
        since_str = query.get("since")
        since = float(since_str) if since_str else None
        until_str = query.get("until")
        until = float(until_str) if until_str else None

        # Normalize to lists or None
        if isinstance(event_types, str):
            event_types = [event_types]
        if isinstance(agent_ids, str):
            agent_ids = [agent_ids]

        kwargs = {}
        if event_types: kwargs["event_types"] = event_types
        if agent_ids: kwargs["agent_ids"] = agent_ids
        if correlation_id: kwargs["correlation_id"] = correlation_id
        if limit: kwargs["limit"] = limit
        if since is not None: kwargs["since"] = since
        if until is not None: kwargs["until"] = until

        conn = state._get_conn()
        data = await asyncio.to_thread(read_timeline_data, conn, **kwargs)
        w.patch(SafeString(render_timeline_svg(data)))

        async for subject, _change_type in w.alive(relay.subscribe("graph.events")):
            c("timeline.subscribe.event", {"subject": subject})
            conn = state._get_conn()
            data = await asyncio.to_thread(read_timeline_data, conn, **kwargs)
            w.patch(SafeString(render_timeline_svg(data)))

        c("timeline.subscribe.disconnected")
    return handler
```

**NOTE**: The exact query param parsing API depends on Stario's `c.req.query`. Study `c.req.query` behavior in the stario docs. It may return a dict, a MultiDict, or require different access patterns. The key point is that filter params should be extracted from the URL query string and passed through to `read_timeline_data()`.

---

## B2: Keyboard Navigation

### Step 1: Tests for keyboard JS

Add to `tests/test_timeline_views.py` in `TestRenderTimelineShell`:

```python
def test_includes_keyboard_handler(self) -> None:
    result = render_timeline_shell(self._make_data())
    assert "keydown" in result

def test_keyboard_j_k_navigation(self) -> None:
    result = render_timeline_shell(self._make_data())
    assert "focusAgent" in result or "'j'" in result

def test_keyboard_h_l_navigation(self) -> None:
    result = render_timeline_shell(self._make_data())
    assert "'h'" in result or "'l'" in result

def test_keyboard_enter_inspect(self) -> None:
    result = render_timeline_shell(self._make_data())
    assert "'Enter'" in result or "Enter" in result

def test_keyboard_help_overlay(self) -> None:
    result = render_timeline_shell(self._make_data())
    assert "keyboard-help" in result

def test_focused_marker_css(self) -> None:
    result = timeline_css()
    assert ".focused" in result
```

### Step 2: Implement keyboard JS

Add a new JS constant in `timeline/views.py`:

```python
KEYBOARD_NAV_JS = """\
(function() {
    var focusAgent = -1, focusEvent = -1;
    var agentEvents = []; // 2D: agentEvents[agentIdx] = [marker_elements]

    function rebuildEventIndex() {
        var svg = document.getElementById('timeline-svg');
        if (!svg) return;
        var agents = [];
        var agentMap = {};
        svg.querySelectorAll('.agent-label').forEach(function(label, idx) {
            agents.push(label.textContent.trim());
            agentMap[label.textContent.trim()] = idx;
        });
        agentEvents = agents.map(function() { return []; });
        svg.querySelectorAll('.event-marker').forEach(function(m) {
            // Determine which lane by cy
            var cy = parseFloat(m.getAttribute('cy'));
            var laneIdx = Math.round((cy - 55) / 50); // PADDING_TOP + LANE_HEIGHT/2 = 55, LANE_HEIGHT=50
            if (laneIdx >= 0 && laneIdx < agentEvents.length) {
                agentEvents[laneIdx].push(m);
            }
        });
    }

    function updateFocus() {
        document.querySelectorAll('.event-marker.focused').forEach(function(m) {
            m.classList.remove('focused');
        });
        if (focusAgent >= 0 && focusAgent < agentEvents.length &&
            focusEvent >= 0 && focusEvent < agentEvents[focusAgent].length) {
            agentEvents[focusAgent][focusEvent].classList.add('focused');
        }
    }

    document.addEventListener('keydown', function(e) {
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT') return;
        switch(e.key) {
            case 'j':
                if (agentEvents.length === 0) rebuildEventIndex();
                focusAgent = Math.min(focusAgent + 1, agentEvents.length - 1);
                focusEvent = Math.min(focusEvent, (agentEvents[focusAgent] || []).length - 1);
                if (focusEvent < 0) focusEvent = 0;
                updateFocus(); e.preventDefault(); break;
            case 'k':
                focusAgent = Math.max(focusAgent - 1, 0);
                focusEvent = Math.min(focusEvent, (agentEvents[focusAgent] || []).length - 1);
                if (focusEvent < 0) focusEvent = 0;
                updateFocus(); e.preventDefault(); break;
            case 'l':
                if (focusAgent >= 0) {
                    focusEvent = Math.min(focusEvent + 1, (agentEvents[focusAgent] || []).length - 1);
                    updateFocus();
                }
                e.preventDefault(); break;
            case 'h':
                focusEvent = Math.max(focusEvent - 1, 0);
                updateFocus(); e.preventDefault(); break;
            case 'Enter':
                if (focusAgent >= 0 && agentEvents[focusAgent] && agentEvents[focusAgent][focusEvent]) {
                    agentEvents[focusAgent][focusEvent].dispatchEvent(new Event('click', {bubbles: true}));
                }
                e.preventDefault(); break;
            case 'Escape':
                focusAgent = -1; focusEvent = -1; updateFocus();
                clearHighlight();
                var help = document.getElementById('keyboard-help');
                if (help) help.style.display = 'none';
                e.preventDefault(); break;
            case 'f':
                window.__timelineFollowMode = !window.__timelineFollowMode;
                var fb = document.getElementById('follow-btn');
                if (fb) fb.classList.toggle('active', window.__timelineFollowMode);
                e.preventDefault(); break;
            case 'c':
                if (focusAgent >= 0 && agentEvents[focusAgent] && agentEvents[focusAgent][focusEvent]) {
                    var cid = agentEvents[focusAgent][focusEvent].getAttribute('data-correlation-id');
                    highlightCorrelation(cid);
                }
                e.preventDefault(); break;
            case '+': case '=':
                scale = Math.min(4, scale * 1.2);
                document.getElementById('timeline-svg').style.transform = 'translate(' + tx + 'px,' + ty + 'px) scale(' + scale + ')';
                e.preventDefault(); break;
            case '-':
                scale = Math.max(0.2, scale * 0.8);
                document.getElementById('timeline-svg').style.transform = 'translate(' + tx + 'px,' + ty + 'px) scale(' + scale + ')';
                e.preventDefault(); break;
            case '0':
                scale = 1; tx = 0; ty = 0;
                document.getElementById('timeline-svg').style.transform = '';
                e.preventDefault(); break;
            case '/':
                e.preventDefault();
                var si = document.getElementById('search-input');
                if (si) { si.style.display = 'block'; si.focus(); }
                break;
            case '?':
                var help = document.getElementById('keyboard-help');
                if (help) help.style.display = help.style.display === 'none' ? 'flex' : 'none';
                e.preventDefault(); break;
        }
    });

    // Rebuild index on SSE update
    var obs = new MutationObserver(rebuildEventIndex);
    var svgParent = document.getElementById('timeline-pane');
    if (svgParent) obs.observe(svgParent, { childList: true, subtree: true });
    rebuildEventIndex();
})();
"""
```

### Step 3: Help overlay HTML

Add to `render_timeline_shell()`:

```html
<div id="keyboard-help" class="keyboard-help" style="display:none">
  <div class="keyboard-help-content">
    <h3>Keyboard Shortcuts</h3>
    <div><kbd>j</kbd>/<kbd>k</kbd> — Next/prev agent lane</div>
    <div><kbd>h</kbd>/<kbd>l</kbd> — Prev/next event</div>
    <div><kbd>Enter</kbd> — Inspect focused event</div>
    <div><kbd>Escape</kbd> — Close/clear</div>
    <div><kbd>f</kbd> — Toggle follow mode</div>
    <div><kbd>c</kbd> — Highlight correlation chain</div>
    <div><kbd>+</kbd>/<kbd>-</kbd> — Zoom in/out</div>
    <div><kbd>0</kbd> — Reset zoom</div>
    <div><kbd>/</kbd> — Search</div>
    <div><kbd>?</kbd> — This help</div>
  </div>
</div>
```

### Step 4: CSS for keyboard features

Add to `timeline/css.py`:

```css
/* ---- Keyboard focus ---- */
.event-marker.focused { stroke: var(--lavender); stroke-width: 2; }

/* ---- Help overlay ---- */
.keyboard-help {
    position: fixed; top: 0; left: 0; right: 0; bottom: 0;
    background: rgba(0,0,0,0.7);
    display: flex; align-items: center; justify-content: center;
    z-index: 200;
}
.keyboard-help-content {
    background: var(--surface); padding: 24px 32px;
    border-radius: 8px; border: 1px solid var(--surface2);
    font-size: 13px; line-height: 2;
}
.keyboard-help-content h3 { margin-bottom: 12px; color: var(--blue); }
.keyboard-help-content kbd {
    background: var(--surface2); padding: 2px 6px; border-radius: 3px;
    font-family: inherit; font-size: 11px;
}
```

---

## B3: Event Search

### Step 1: Tests for `search` param in data layer

Add to `tests/test_timeline_state.py`:

```python
class TestTimelineSearch:
    def test_search_by_event_type(self) -> None:
        conn = _create_db()
        _insert_event(conn, from_agent="a", timestamp=1.0, event_type="AgentStart")
        _insert_event(conn, from_agent="a", timestamp=2.0, event_type="AgentComplete")
        result = read_timeline_data(conn, search="Start")
        assert len(result.events) == 2  # all events returned
        assert 1 in result.search_matches  # event_id 1 matches

    def test_search_by_agent_name(self) -> None:
        conn = _create_db()
        _insert_event(conn, from_agent="load_config", timestamp=1.0, event_type="AgentStart")
        _insert_event(conn, from_agent="process_yaml", timestamp=2.0, event_type="AgentStart")
        result = read_timeline_data(conn, search="config")
        assert 1 in result.search_matches
        assert 2 not in result.search_matches

    def test_search_by_payload(self) -> None:
        conn = _create_db()
        _insert_event(conn, from_agent="a", timestamp=1.0, payload='{"message": "hello world"}')
        _insert_event(conn, from_agent="a", timestamp=2.0, payload='{"message": "goodbye"}')
        result = read_timeline_data(conn, search="hello")
        assert 1 in result.search_matches
        assert 2 not in result.search_matches

    def test_search_empty_returns_no_matches(self) -> None:
        conn = _create_db()
        _insert_event(conn, from_agent="a", timestamp=1.0)
        result = read_timeline_data(conn, search="nonexistent")
        assert len(result.search_matches) == 0

    def test_search_none_returns_empty_matches(self) -> None:
        conn = _create_db()
        _insert_event(conn, from_agent="a", timestamp=1.0)
        result = read_timeline_data(conn)
        assert result.search_matches == []
```

### Step 2: Add `search` param and `search_matches` field

In `timeline/state.py`, add `search_matches` to TimelineData:

```python
@dataclass
class TimelineData:
    agents: list[str] = field(default_factory=list)
    events: list[dict] = field(default_factory=list)
    correlation_groups: dict[str, list[int]] = field(default_factory=dict)
    time_range: tuple[float, float] = (0.0, 0.0)
    search_matches: list[int] = field(default_factory=list)
```

Add `search: str | None = None` parameter to `read_timeline_data()`.

After fetching rows, if search is provided, run a second query to find matching event IDs:

```python
search_matches: list[int] = []
if search is not None and rows:
    pattern = f"%{search}%"
    match_sql = """
        SELECT id FROM events
        WHERE (event_type LIKE ? OR from_agent LIKE ? OR to_agent LIKE ? OR payload LIKE ?)
    """
    match_params = [pattern, pattern, pattern, pattern]
    # Only match within the already-fetched event IDs
    event_ids = [r["event_id"] for r in rows]
    id_placeholders = ",".join("?" for _ in event_ids)
    match_sql += f" AND id IN ({id_placeholders})"
    match_params.extend(event_ids)
    cursor = conn.execute(match_sql, match_params)
    search_matches = [row[0] for row in cursor.fetchall()]
```

Include in the return:

```python
return TimelineData(
    agents=agents,
    events=rows,
    correlation_groups=correlation_groups,
    time_range=time_range,
    search_matches=search_matches,
)
```

### Step 3: Tests for search UI

Add to `tests/test_timeline_views.py` in `TestRenderTimelineShell`:

```python
def test_includes_search_input(self) -> None:
    result = render_timeline_shell(self._make_data())
    assert "search-input" in result

def test_search_input_hidden_by_default(self) -> None:
    result = render_timeline_shell(self._make_data())
    # Search input should be hidden initially (display:none or hidden attr)
    assert 'display:none' in result or 'display: none' in result or 'hidden' in result
```

Add to `tests/test_timeline_views.py` in `TestTimelineCss`:

```python
def test_contains_search_styles(self) -> None:
    result = timeline_css()
    assert ".search-input" in result

def test_contains_search_match_styles(self) -> None:
    result = timeline_css()
    assert ".search-match" in result
```

### Step 4: Add search input HTML

In `render_timeline_shell()`, add:

```html
<input type="text" id="search-input" class="search-input" placeholder="Search events..." style="display:none">
```

### Step 5: CSS for search

Add to `timeline/css.py`:

```css
/* ---- Search ---- */
.search-input {
    position: fixed; top: 60px; left: 50%; transform: translateX(-50%);
    width: 400px; padding: 8px 12px;
    background: var(--surface); color: var(--text);
    border: 2px solid var(--blue); border-radius: 6px;
    font-family: inherit; font-size: 13px;
    z-index: 150; box-shadow: 0 4px 12px rgba(0,0,0,0.5);
}
.search-input:focus { outline: none; border-color: var(--lavender); }
.event-marker.search-match { stroke: var(--yellow); stroke-width: 2; }
```

### Step 6: JS for search interaction

Add to the JS block:

```javascript
// Search
var searchInput = document.getElementById('search-input');
if (searchInput) {
    searchInput.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            this.style.display = 'none';
            this.value = '';
            document.querySelectorAll('.event-marker.search-match').forEach(function(m) {
                m.classList.remove('search-match');
            });
            e.preventDefault();
            e.stopPropagation();
        } else if (e.key === 'Enter') {
            // Trigger search via server re-subscribe
            var q = this.value.trim();
            if (q) {
                var params = new URLSearchParams(window.location.search);
                params.set('search', q);
                window.location.search = '?' + params.toString();
            }
            e.preventDefault();
        }
    });
}
```

### Step 7: Route updates for search param

In `graph/app.py`, the `timeline_subscribe` handler (updated in B1) should also parse `search`:

```python
search = query.get("search")
if search: kwargs["search"] = search
```

And also in `timeline_index`:

```python
def timeline_index(state: GraphState):
    async def handler(c: Context, w: Writer) -> None:
        query = c.req.query
        search = query.get("search")
        kwargs = {}
        if search: kwargs["search"] = search
        # ... parse other filter params similarly ...
        conn = state._get_conn()
        data = await asyncio.to_thread(read_timeline_data, conn, **kwargs)
        w.html(render_timeline_shell(data))
    return handler
```

---

## Phase B Verification

After completing B1 + B2 + B3:

```bash
cd /home/andrew/Documents/Projects/remora-demo/frontend && python -m pytest tests/ -q
```

Expected: ~280+ tests passing (253 baseline + ~25 Phase A + ~30 Phase B).
