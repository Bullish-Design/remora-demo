"""Timeline view functions — shell page and event inspector.

All functions return plain HTML strings. No Stario dependency — testable in Python 3.13.
"""

from __future__ import annotations

import datetime
import html as html_mod
import json

from timeline.css import timeline_css
from timeline.state import TimelineData
from timeline.svg import render_timeline_svg

DATASTAR_CDN = "https://cdn.jsdelivr.net/gh/starfederation/datastar@v1.0.0-RC.7/bundles/datastar.js"

TIMELINE_ZOOM_PAN_JS = """\
(function() {
    let scale = 1, tx = 0, ty = 0;
    const pane = document.getElementById('timeline-pane');
    const svg = document.getElementById('timeline-svg');
    if (!pane || !svg) return;

    pane.addEventListener('wheel', function(e) {
        e.preventDefault();
        const factor = e.deltaY > 0 ? 0.9 : 1.1;
        scale = Math.max(0.2, Math.min(4, scale * factor));
        svg.style.transform = 'translate(' + tx + 'px,' + ty + 'px) scale(' + scale + ')';
    }, { passive: false });

    let dragging = false, startX = 0, startY = 0;
    pane.addEventListener('mousedown', function(e) {
        if (e.target.closest('.event-marker')) return;
        dragging = true; startX = e.clientX - tx; startY = e.clientY - ty;
    });
    pane.addEventListener('mousemove', function(e) {
        if (!dragging) return;
        tx = e.clientX - startX; ty = e.clientY - startY;
        svg.style.transform = 'translate(' + tx + 'px,' + ty + 'px) scale(' + scale + ')';
    });
    window.addEventListener('mouseup', function() { dragging = false; });

    // Tooltip on hover
    const tooltip = document.getElementById('timeline-tooltip');
    if (tooltip) {
        pane.addEventListener('mouseover', function(e) {
            const marker = e.target.closest('.event-marker');
            if (marker) {
                const eid = marker.getAttribute('data-event-id');
                tooltip.textContent = 'Event #' + eid;
                tooltip.style.display = 'block';
                tooltip.style.left = (e.clientX + 10) + 'px';
                tooltip.style.top = (e.clientY - 30) + 'px';
            }
        });
        pane.addEventListener('mouseout', function(e) {
            if (e.target.closest('.event-marker')) {
                tooltip.style.display = 'none';
            }
        });
    }

    // Click to inspect event
    pane.addEventListener('click', function(e) {
        const marker = e.target.closest('.event-marker');
        if (marker) {
            const eid = marker.getAttribute('data-event-id');
            if (eid) {
                // Use Datastar to fetch event details
                const evt = new CustomEvent('timeline-inspect', { detail: { eventId: eid } });
                document.dispatchEvent(evt);
            }
        }
    });
})();
"""


def render_timeline_shell(data: TimelineData) -> str:
    """Render the complete timeline HTML page.

    Layout:
    - Header with title, navigation, event count
    - Timeline pane (left) with SVG swimlane view
    - Inspector panel (right) for event details
    - Tooltip overlay for hover
    """
    css = html_mod.escape(timeline_css(), quote=False)
    svg = render_timeline_svg(data)
    event_count = len(data.events)
    agent_count = len(data.agents)
    inspector = render_event_inspector(None)

    return f"""\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Remora Timeline</title>
<script type="module" src="{DATASTAR_CDN}"></script>
<style>{css}</style>
</head>
<body data-on-load="@get('/timeline/subscribe')">
<div class="app">
  <header class="header">
    <div class="header-title">Remora Timeline</div>
    <nav class="header-nav">
      <a href="/">Graph</a>
      <a href="/timeline" class="active">Timeline</a>
    </nav>
    <div class="header-status">{event_count} events, {agent_count} agents</div>
  </header>
  <div class="main">
    <div class="timeline-pane" id="timeline-pane">
      {svg}
    </div>
    {inspector}
  </div>
</div>
<div class="timeline-tooltip" id="timeline-tooltip"></div>
<script>{TIMELINE_ZOOM_PAN_JS}</script>
</body>
</html>"""


def render_event_inspector(event: dict | None) -> str:
    """Render the event inspector panel.

    Shows full event details when an event is selected, or a placeholder message.
    Target element: #inspector. Updated by w.patch() on event click.
    """
    if event is None:
        return (
            '<div id="inspector" class="inspector">'
            '<div class="inspector-empty">Click an event to view details</div>'
            "</div>"
        )

    event_type = html_mod.escape(str(event.get("event_type", "Unknown")))
    event_id = event.get("event_id", "")
    from_agent = html_mod.escape(str(event.get("from_agent") or ""))
    to_agent = html_mod.escape(str(event.get("to_agent") or ""))
    correlation_id = html_mod.escape(str(event.get("correlation_id") or ""))
    timestamp = event.get("timestamp", 0)
    time_str = _format_timestamp(timestamp)
    payload_raw = event.get("payload", "{}")

    # Try to pretty-print the payload
    try:
        payload_obj = json.loads(payload_raw) if isinstance(payload_raw, str) else payload_raw
        payload_display = html_mod.escape(json.dumps(payload_obj, indent=2))
    except (json.JSONDecodeError, TypeError):
        payload_display = html_mod.escape(str(payload_raw))

    # Color for event type badge
    from timeline.svg import EVENT_TYPE_COLORS, DEFAULT_COLOR

    color = EVENT_TYPE_COLORS.get(event.get("event_type", ""), DEFAULT_COLOR)

    parts = [
        '<div id="inspector" class="inspector">',
        '<div class="inspector-header">',
        f'<span class="inspector-type" style="background:{color};color:#1e1e2e">{event_type}</span>',
        "</div>",
        _inspector_field("Event ID", str(event_id)),
        _inspector_field("Time", time_str),
        _inspector_field("From", from_agent) if from_agent else "",
        _inspector_field("To", to_agent) if to_agent else "",
        _inspector_field("Correlation", correlation_id) if correlation_id else "",
        f'<div class="inspector-payload">{payload_display}</div>',
        "</div>",
    ]
    return "".join(parts)


def _inspector_field(label: str, value: str) -> str:
    return (
        f'<div class="inspector-field">'
        f'<span class="inspector-field-label">{label}</span>'
        f'<span class="inspector-field-value">{value}</span>'
        f"</div>"
    )


def _format_timestamp(ts: float) -> str:
    if not ts:
        return ""
    dt = datetime.datetime.fromtimestamp(ts)
    return dt.strftime("%H:%M:%S.") + f"{int(dt.microsecond / 1000):03d}"
