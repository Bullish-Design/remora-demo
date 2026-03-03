"""Timeline SVG builders — swimlane visualization of agent events.

All functions return plain strings. No Stario dependency — testable in Python 3.13.
Reuses the Catppuccin Mocha palette from graph.views.event_stream for event type colors.
"""

from __future__ import annotations

import datetime
import html as html_mod

from timeline.state import TimelineData

# ── Layout constants ──

LANE_HEIGHT = 50  # Vertical space per agent lane
LABEL_WIDTH = 140  # Width of the agent labels column
MARKER_RADIUS = 6  # Radius of event marker circles
PADDING_TOP = 30  # Space above first lane
PADDING_BOTTOM = 40  # Space below last lane for time axis
PADDING_RIGHT = 30  # Right margin
MIN_TIMELINE_WIDTH = 600  # Minimum width of the time area

# ── Event type colors (same Catppuccin Mocha palette as event_stream) ──

EVENT_TYPE_COLORS: dict[str, str] = {
    "NodeDiscovered": "#a6e3a1",
    "NodeRemoved": "#6c7086",
    "AgentStart": "#89b4fa",
    "AgentComplete": "#a6e3a1",
    "AgentError": "#f38ba8",
    "ContentChanged": "#f9e2af",
    "ModelRequest": "#cba6f7",
    "ModelResponse": "#cba6f7",
    "AgentMessage": "#89dceb",
    "HumanChat": "#fab387",
    "RewriteProposal": "#f9e2af",
    "RewriteApplied": "#a6e3a1",
    "RewriteRejected": "#f38ba8",
}

DEFAULT_COLOR = "#6c7086"

# ── Lane background colors (alternating for readability) ──

LANE_BG_EVEN = "#1e1e2e"  # base
LANE_BG_ODD = "#181825"  # mantle


# ── Primitive builders ──


def render_event_marker(
    *,
    event_id: int,
    x: float,
    y: float,
    event_type: str,
) -> str:
    """Render a single event as a colored circle marker."""
    fill = EVENT_TYPE_COLORS.get(event_type, DEFAULT_COLOR)
    return (
        f'<circle cx="{x}" cy="{y}" r="{MARKER_RADIUS}" fill="{fill}" class="event-marker" data-event-id="{event_id}"/>'
    )


def render_agent_label(name: str, y: float) -> str:
    """Render an agent name label at the given Y position."""
    display = name if len(name) <= 20 else name[:18] + ".."
    escaped = html_mod.escape(display)
    return (
        f'<text x="{LABEL_WIDTH - 10}" y="{y}" '
        f'text-anchor="end" class="agent-label" '
        f'font-size="11px" fill="#cdd6f4">{escaped}</text>'
    )


def render_correlation_line(
    *,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
) -> str:
    """Render a line connecting correlated events across lanes."""
    return (
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
        f'stroke="#b4befe" stroke-width="1" opacity="0.3" '
        f'stroke-dasharray="4,3" class="correlation-line"/>'
    )


def render_time_axis(
    *,
    time_range: tuple[float, float],
    x_start: float,
    x_end: float,
    y: float,
    num_ticks: int = 5,
) -> str:
    """Render the time axis with tick marks and labels."""
    t_min, t_max = time_range
    parts = [f'<g class="time-axis">']

    # Axis line
    parts.append(f'<line x1="{x_start}" y1="{y}" x2="{x_end}" y2="{y}" stroke="#585b70" stroke-width="1"/>')

    # Tick marks and labels
    duration = t_max - t_min
    tick_count = num_ticks if duration > 0 else 1

    for i in range(tick_count):
        if duration > 0:
            t = t_min + (duration * i / (tick_count - 1)) if tick_count > 1 else t_min
            frac = (t - t_min) / duration
        else:
            t = t_min
            frac = 0.5  # center single tick

        x = x_start + frac * (x_end - x_start)
        label = _format_timestamp(t)

        # Tick mark
        parts.append(f'<line x1="{x}" y1="{y}" x2="{x}" y2="{y + 6}" stroke="#585b70" stroke-width="1"/>')
        # Label
        parts.append(f'<text x="{x}" y="{y + 18}" text-anchor="middle" font-size="9px" fill="#6c7086">{label}</text>')

    parts.append("</g>")
    return "".join(parts)


def _format_timestamp(ts: float) -> str:
    """Format a UNIX timestamp as HH:MM:SS.mmm."""
    if not ts:
        return ""
    dt = datetime.datetime.fromtimestamp(ts)
    return dt.strftime("%H:%M:%S.") + f"{int(dt.microsecond / 1000):03d}"


# ── Composite: full timeline SVG ──


def render_timeline_svg(data: TimelineData, width: int = 1200) -> str:
    """Render the complete timeline SVG element.

    Layout:
    - Left column: agent labels (LABEL_WIDTH wide)
    - Right area: time-based swimlane with event markers
    - Bottom: time axis
    - Correlation lines connect events sharing a correlation_id
    """
    if not data.events:
        return (
            f'<svg id="timeline-svg" viewBox="0 0 {width} 200" '
            f'xmlns="http://www.w3.org/2000/svg" class="timeline-canvas" '
            f'preserveAspectRatio="xMidYMid meet">'
            f'<text x="{width // 2}" y="100" text-anchor="middle" '
            f'font-size="14px" fill="#6c7086">No events to display</text>'
            f"</svg>"
        )

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

    def agent_to_y(agent: str) -> float:
        idx = agent_index.get(agent, 0)
        return PADDING_TOP + idx * LANE_HEIGHT + LANE_HEIGHT / 2

    parts = [
        f'<svg id="timeline-svg" viewBox="0 0 {width} {height}" '
        f'xmlns="http://www.w3.org/2000/svg" class="timeline-canvas" '
        f'preserveAspectRatio="xMidYMid meet">'
    ]

    # Lane backgrounds
    for i, agent in enumerate(data.agents):
        lane_y = PADDING_TOP + i * LANE_HEIGHT
        bg = LANE_BG_ODD if i % 2 else LANE_BG_EVEN
        parts.append(f'<rect x="0" y="{lane_y}" width="{width}" height="{LANE_HEIGHT}" fill="{bg}" class="lane-bg"/>')

    # Agent labels
    for agent in data.agents:
        label_y = agent_to_y(agent) + 4  # +4 for text baseline
        parts.append(render_agent_label(agent, label_y))

    # Separator line between labels and timeline area
    parts.append(
        f'<line x1="{LABEL_WIDTH}" y1="{PADDING_TOP}" '
        f'x2="{LABEL_WIDTH}" y2="{PADDING_TOP + num_agents * LANE_HEIGHT}" '
        f'stroke="#585b70" stroke-width="1" opacity="0.3"/>'
    )

    # Build event position map for correlation lines
    event_positions: dict[int, tuple[float, float]] = {}

    # Event markers
    for ev in data.events:
        x = time_to_x(ev["timestamp"])
        # Place in the lane of from_agent (prefer from_agent over to_agent)
        agent = ev.get("from_agent") or ev.get("to_agent")
        if agent is None:
            continue
        y = agent_to_y(agent)
        event_positions[ev["event_id"]] = (x, y)
        parts.append(
            render_event_marker(
                event_id=ev["event_id"],
                x=x,
                y=y,
                event_type=ev["event_type"],
            )
        )

    # Correlation lines
    for cid, event_ids in data.correlation_groups.items():
        # Draw lines between consecutive events in the group
        positioned = [eid for eid in event_ids if eid in event_positions]
        for i in range(len(positioned) - 1):
            x1, y1 = event_positions[positioned[i]]
            x2, y2 = event_positions[positioned[i + 1]]
            parts.append(render_correlation_line(x1=x1, y1=y1, x2=x2, y2=y2))

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
