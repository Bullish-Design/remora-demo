# Phase A Implementation Guide — Quick Wins

> Event Type Legend, Follow Mode, Correlation Chain Highlighting.
> Estimated ~25 tests. Do these first — they establish `data-event-type` and `data-correlation-id` attributes that later phases depend on.

## Table of Contents

1. [A1: Event Type Legend](#a1-event-type-legend) — SVG data attr + legend renderer + CSS + JS click-to-filter
2. [A2: Follow Mode](#a2-follow-mode) — Follow button + auto-scroll JS + auto-disable on pan
3. [A3: Correlation Chain Highlighting](#a3-correlation-chain-highlighting) — SVG data attr + dim/highlight CSS + JS handler

---

## A1: Event Type Legend

### Step 1: Tests for SVG `data-event-type` attribute

Add to `tests/test_timeline_svg.py` in the `TestRenderEventMarker` class:

```python
def test_data_event_type_attribute(self) -> None:
    result = render_event_marker(event_id=1, x=0, y=0, event_type="AgentStart")
    assert 'data-event-type="AgentStart"' in result

def test_data_event_type_custom(self) -> None:
    result = render_event_marker(event_id=1, x=0, y=0, event_type="CustomType")
    assert 'data-event-type="CustomType"' in result
```

### Step 2: Implement `data-event-type` on markers

In `timeline/svg.py`, modify `render_event_marker()`. Current line:

```python
return (
    f'<circle cx="{x}" cy="{y}" r="{MARKER_RADIUS}" fill="{fill}" class="event-marker" data-event-id="{event_id}"/>'
)
```

Change to:

```python
return (
    f'<circle cx="{x}" cy="{y}" r="{MARKER_RADIUS}" fill="{fill}" '
    f'class="event-marker" data-event-id="{event_id}" data-event-type="{event_type}"/>'
)
```

### Step 3: Tests for `render_legend()`

Add new test class to `tests/test_timeline_svg.py`:

```python
from timeline.svg import render_legend

class TestRenderLegend:
    def test_returns_string(self) -> None:
        result = render_legend(["AgentStart", "AgentComplete"])
        assert isinstance(result, str)

    def test_contains_legend_class(self) -> None:
        result = render_legend(["AgentStart"])
        assert "timeline-legend" in result

    def test_contains_event_type_names(self) -> None:
        result = render_legend(["AgentStart", "AgentError"])
        assert "AgentStart" in result
        assert "AgentError" in result

    def test_contains_colors(self) -> None:
        result = render_legend(["AgentStart"])
        assert "#89b4fa" in result  # blue for AgentStart

    def test_legend_items_have_data_type(self) -> None:
        result = render_legend(["AgentComplete"])
        assert 'data-type="AgentComplete"' in result

    def test_empty_types(self) -> None:
        result = render_legend([])
        assert "timeline-legend" in result
```

### Step 4: Implement `render_legend()`

Add to `timeline/svg.py`:

```python
def render_legend(event_types: list[str]) -> str:
    """Render a color-coded legend of event types present in the data."""
    parts = ['<div class="timeline-legend">']
    for et in sorted(set(event_types)):
        color = EVENT_TYPE_COLORS.get(et, DEFAULT_COLOR)
        parts.append(
            f'<span class="legend-item" data-type="{et}">'
            f'<span class="legend-dot" style="background:{color}"></span> {html_mod.escape(et)}'
            f'</span>'
        )
    parts.append('</div>')
    return "".join(parts)
```

Note: `render_legend` returns HTML (not SVG), so it goes in the shell page, not inside the SVG.

### Step 5: Tests for legend in shell and CSS

Add to `tests/test_timeline_views.py` in `TestRenderTimelineShell`:

```python
def test_includes_legend(self) -> None:
    result = render_timeline_shell(self._make_data())
    assert "timeline-legend" in result

def test_legend_contains_event_types_from_data(self) -> None:
    result = render_timeline_shell(self._make_data())
    assert "AgentStart" in result
    assert "AgentComplete" in result
```

Add to `tests/test_timeline_views.py` in `TestTimelineCss`:

```python
def test_contains_legend_styles(self) -> None:
    result = timeline_css()
    assert ".timeline-legend" in result
    assert ".legend-item" in result
    assert ".legend-dot" in result
```

### Step 6: Integrate legend into shell

In `timeline/views.py`, import `render_legend` from `timeline/svg.py`.

In `render_timeline_shell()`, compute the event types and add the legend between the controls bar and the SVG:

```python
# Compute observed event types
event_types = sorted(set(ev["event_type"] for ev in data.events))
legend = render_legend(event_types) if event_types else ""
```

Then insert `{legend}` in the HTML template between the header and the main div.

### Step 7: Add legend CSS

Add to `timeline/css.py` in the `timeline_css()` return string:

```css
/* ---- Legend ---- */
.timeline-legend {
    padding: 6px 16px;
    background: var(--surface);
    border-bottom: 1px solid var(--surface2);
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
    font-size: 11px;
}
.legend-item {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    cursor: pointer;
    padding: 2px 6px;
    border-radius: 3px;
    transition: opacity 0.2s;
}
.legend-item:hover { background: var(--surface2); }
.legend-item.legend-disabled { opacity: 0.3; text-decoration: line-through; }
.legend-dot {
    display: inline-block;
    width: 8px; height: 8px;
    border-radius: 50%;
}
.event-marker.hidden { display: none; }
```

### Step 8: Add legend click-to-filter JS

In `timeline/views.py`, add to the JS block (inside `TIMELINE_ZOOM_PAN_JS` or a new JS constant):

```javascript
// Legend click-to-filter
document.querySelectorAll('.legend-item').forEach(function(item) {
    item.addEventListener('click', function() {
        var type = this.getAttribute('data-type');
        this.classList.toggle('legend-disabled');
        var hidden = this.classList.contains('legend-disabled');
        document.querySelectorAll('.event-marker[data-event-type="' + type + '"]')
            .forEach(function(m) {
                if (hidden) m.classList.add('hidden');
                else m.classList.remove('hidden');
            });
    });
});
```

---

## A2: Follow Mode

### Step 1: Tests for follow button in shell

Add to `tests/test_timeline_views.py` in `TestRenderTimelineShell`:

```python
def test_includes_follow_button(self) -> None:
    result = render_timeline_shell(self._make_data())
    assert "follow-btn" in result

def test_follow_js_initialized(self) -> None:
    result = render_timeline_shell(self._make_data())
    assert "__timelineFollowMode" in result

def test_follow_auto_disable_on_pan(self) -> None:
    """Follow mode should disable when user manually pans."""
    result = render_timeline_shell(self._make_data())
    assert "mousedown" in result  # already present
    # The pan handler should set followMode to false
    assert "__timelineFollowMode = false" in result or "followMode = false" in result
```

### Step 2: Add follow button and JS

In `timeline/views.py`, in `render_timeline_shell()`, add a Follow button in the controls area (before or after the legend):

```html
<div class="timeline-controls">
  <button class="btn" id="follow-btn" onclick="window.__timelineFollowMode = !window.__timelineFollowMode; this.classList.toggle('active', window.__timelineFollowMode);">Follow</button>
</div>
```

In the JS block, add follow mode logic:

```javascript
window.__timelineFollowMode = false;

// Auto-scroll on SSE update
var observer = new MutationObserver(function() {
    if (!window.__timelineFollowMode) return;
    var markers = document.querySelectorAll('.event-marker');
    if (markers.length === 0) return;
    var last = markers[markers.length - 1];
    var cx = parseFloat(last.getAttribute('cx'));
    var pane = document.getElementById('timeline-pane');
    if (pane) {
        tx = pane.clientWidth * 0.8 - cx * scale;
        var svg = document.getElementById('timeline-svg');
        if (svg) svg.style.transform = 'translate(' + tx + 'px,' + ty + 'px) scale(' + scale + ')';
    }
});
var svgEl = document.getElementById('timeline-svg');
if (svgEl) observer.observe(svgEl.parentElement, { childList: true, subtree: true });
```

In the existing pan mousedown handler, add:

```javascript
// Inside the mousedown handler, after dragging = true:
window.__timelineFollowMode = false;
var followBtn = document.getElementById('follow-btn');
if (followBtn) followBtn.classList.remove('active');
```

### Step 3: CSS for follow button

The `.btn.active` style already exists in `timeline_css()`:
```css
.timeline-controls .btn.active { background: var(--blue); color: #1e1e2e; }
```

No new CSS needed.

---

## A3: Correlation Chain Highlighting

### Step 1: Tests for `data-correlation-id` on markers

Add to `tests/test_timeline_svg.py` in `TestRenderEventMarker`:

```python
def test_data_correlation_id_attribute(self) -> None:
    result = render_event_marker(
        event_id=1, x=0, y=0, event_type="AgentStart", correlation_id="corr-1"
    )
    assert 'data-correlation-id="corr-1"' in result

def test_no_correlation_id_when_none(self) -> None:
    result = render_event_marker(
        event_id=1, x=0, y=0, event_type="AgentStart", correlation_id=None
    )
    assert "data-correlation-id" not in result
```

### Step 2: Add `correlation_id` param to `render_event_marker()`

In `timeline/svg.py`, update the signature:

```python
def render_event_marker(
    *,
    event_id: int,
    x: float,
    y: float,
    event_type: str,
    correlation_id: str | None = None,
) -> str:
```

Update the return:

```python
corr_attr = f' data-correlation-id="{correlation_id}"' if correlation_id else ""
return (
    f'<circle cx="{x}" cy="{y}" r="{MARKER_RADIUS}" fill="{fill}" '
    f'class="event-marker" data-event-id="{event_id}" data-event-type="{event_type}"{corr_attr}/>'
)
```

### Step 3: Update caller in `render_timeline_svg()`

In the event markers loop, pass `correlation_id`:

```python
parts.append(
    render_event_marker(
        event_id=ev["event_id"],
        x=x,
        y=y,
        event_type=ev["event_type"],
        correlation_id=ev.get("correlation_id"),
    )
)
```

### Step 4: Tests for `data-correlation-id` on correlation lines

Add to `tests/test_timeline_svg.py` in `TestRenderCorrelationLine`:

```python
def test_data_correlation_id_attribute(self) -> None:
    result = render_correlation_line(x1=0, y1=0, x2=100, y2=50, correlation_id="c1")
    assert 'data-correlation-id="c1"' in result
```

### Step 5: Add `correlation_id` param to `render_correlation_line()`

Update signature:

```python
def render_correlation_line(
    *,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    correlation_id: str | None = None,
) -> str:
```

Update return:

```python
corr_attr = f' data-correlation-id="{correlation_id}"' if correlation_id else ""
return (
    f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
    f'stroke="#b4befe" stroke-width="1" opacity="0.3" '
    f'stroke-dasharray="4,3" class="correlation-line"{corr_attr}/>'
)
```

### Step 6: Update caller in `render_timeline_svg()`

In the correlation lines loop, pass the correlation_id:

```python
for cid, event_ids in data.correlation_groups.items():
    positioned = [eid for eid in event_ids if eid in event_positions]
    for i in range(len(positioned) - 1):
        x1, y1 = event_positions[positioned[i]]
        x2, y2 = event_positions[positioned[i + 1]]
        parts.append(render_correlation_line(x1=x1, y1=y1, x2=x2, y2=y2, correlation_id=cid))
```

### Step 7: Tests for highlight/dim CSS

Add to `tests/test_timeline_views.py` in `TestTimelineCss`:

```python
def test_contains_dim_styles(self) -> None:
    result = timeline_css()
    assert ".dim" in result

def test_contains_highlight_styles(self) -> None:
    result = timeline_css()
    assert ".highlight" in result
```

### Step 8: Add CSS

Add to `timeline/css.py`:

```css
/* ---- Correlation highlighting ---- */
.event-marker.dim { opacity: 0.15; transition: opacity 0.3s; }
.event-marker.highlight { filter: drop-shadow(0 0 4px currentColor); transition: filter 0.3s; }
.correlation-line.dim { opacity: 0.05; }
.correlation-line.highlight { opacity: 0.8; stroke-width: 2; }
```

### Step 9: Tests for JS highlighting behavior

Add to `tests/test_timeline_views.py` in `TestRenderTimelineShell`:

```python
def test_includes_correlation_highlight_js(self) -> None:
    result = render_timeline_shell(self._make_data())
    assert "highlightCorrelation" in result or "data-correlation-id" in result
```

### Step 10: Add JS handler

In `timeline/views.py`, add to the JS block:

```javascript
// Correlation chain highlighting
function highlightCorrelation(correlationId) {
    if (!correlationId) { clearHighlight(); return; }
    document.querySelectorAll('.event-marker').forEach(function(m) {
        if (m.getAttribute('data-correlation-id') === correlationId) {
            m.classList.add('highlight'); m.classList.remove('dim');
        } else {
            m.classList.add('dim'); m.classList.remove('highlight');
        }
    });
    document.querySelectorAll('.correlation-line').forEach(function(l) {
        if (l.getAttribute('data-correlation-id') === correlationId) {
            l.classList.add('highlight'); l.classList.remove('dim');
        } else {
            l.classList.add('dim'); l.classList.remove('highlight');
        }
    });
}

function clearHighlight() {
    document.querySelectorAll('.event-marker, .correlation-line').forEach(function(el) {
        el.classList.remove('dim', 'highlight');
    });
}

// Wire up: click marker to highlight chain
pane.addEventListener('click', function(e) {
    var marker = e.target.closest('.event-marker');
    if (marker) {
        var cid = marker.getAttribute('data-correlation-id');
        highlightCorrelation(cid);
    } else if (!e.target.closest('.inspector')) {
        clearHighlight();
    }
});

// Escape to clear
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') clearHighlight();
});
```

**NOTE**: The existing click handler for inspect is already in the JS. The correlation click handler should run in addition to (not instead of) the inspect click. Make sure they're both wired up — correlation highlight runs first, then the inspect fetch can proceed.

---

## Phase A Verification

After completing A1 + A2 + A3:

```bash
cd /home/andrew/Documents/Projects/remora-demo/frontend && python -m pytest tests/ -q
```

Expected: all existing 253 tests still pass, plus ~20-25 new tests.
