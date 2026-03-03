"""Tests for timeline SVG renderer — swimlane visualization of agent events."""

from __future__ import annotations

from timeline.state import TimelineData
from timeline.svg import (
    LANE_HEIGHT,
    LABEL_WIDTH,
    MARKER_RADIUS,
    render_timeline_svg,
    render_event_marker,
    render_agent_label,
    render_correlation_line,
    render_time_axis,
)


# ── Full timeline SVG ──


class TestRenderTimelineSvg:
    def test_empty_data(self) -> None:
        data = TimelineData()
        result = render_timeline_svg(data)
        assert "<svg" in result
        assert "</svg>" in result
        assert 'id="timeline-svg"' in result

    def test_empty_shows_message(self) -> None:
        data = TimelineData()
        result = render_timeline_svg(data)
        assert "No events" in result

    def test_with_events(self) -> None:
        data = TimelineData(
            agents=["agent_a", "agent_b"],
            events=[
                {
                    "event_id": 1,
                    "event_type": "AgentStart",
                    "timestamp": 1.0,
                    "from_agent": "agent_a",
                    "to_agent": None,
                    "correlation_id": None,
                    "payload": "{}",
                },
                {
                    "event_id": 2,
                    "event_type": "AgentComplete",
                    "timestamp": 2.0,
                    "from_agent": "agent_b",
                    "to_agent": None,
                    "correlation_id": None,
                    "payload": "{}",
                },
            ],
            correlation_groups={},
            time_range=(1.0, 2.0),
        )
        result = render_timeline_svg(data)
        assert "<svg" in result
        assert "agent_a" in result
        assert "agent_b" in result

    def test_contains_lane_backgrounds(self) -> None:
        data = TimelineData(
            agents=["a"],
            events=[
                {
                    "event_id": 1,
                    "event_type": "Test",
                    "timestamp": 1.0,
                    "from_agent": "a",
                    "to_agent": None,
                    "correlation_id": None,
                    "payload": "{}",
                },
            ],
            time_range=(1.0, 1.0),
        )
        result = render_timeline_svg(data)
        assert "lane-bg" in result

    def test_contains_correlation_lines(self) -> None:
        data = TimelineData(
            agents=["a", "b"],
            events=[
                {
                    "event_id": 1,
                    "event_type": "AgentStart",
                    "timestamp": 1.0,
                    "from_agent": "a",
                    "to_agent": None,
                    "correlation_id": "c1",
                    "payload": "{}",
                },
                {
                    "event_id": 2,
                    "event_type": "AgentComplete",
                    "timestamp": 2.0,
                    "from_agent": "b",
                    "to_agent": None,
                    "correlation_id": "c1",
                    "payload": "{}",
                },
            ],
            correlation_groups={"c1": [1, 2]},
            time_range=(1.0, 2.0),
        )
        result = render_timeline_svg(data)
        assert "correlation-line" in result

    def test_contains_time_axis(self) -> None:
        data = TimelineData(
            agents=["a"],
            events=[
                {
                    "event_id": 1,
                    "event_type": "Test",
                    "timestamp": 1000.0,
                    "from_agent": "a",
                    "to_agent": None,
                    "correlation_id": None,
                    "payload": "{}",
                },
            ],
            time_range=(1000.0, 1000.0),
        )
        result = render_timeline_svg(data)
        assert "time-axis" in result


# ── Event marker ──


class TestRenderEventMarker:
    def test_returns_circle(self) -> None:
        result = render_event_marker(
            event_id=1,
            x=100.0,
            y=50.0,
            event_type="AgentStart",
        )
        assert "<circle" in result
        assert "/>" in result

    def test_position(self) -> None:
        result = render_event_marker(event_id=1, x=150.0, y=75.0, event_type="Test")
        assert 'cx="150.0"' in result
        assert 'cy="75.0"' in result

    def test_radius(self) -> None:
        result = render_event_marker(event_id=1, x=0, y=0, event_type="Test")
        assert f'r="{MARKER_RADIUS}"' in result

    def test_color_by_event_type(self) -> None:
        result = render_event_marker(event_id=1, x=0, y=0, event_type="AgentError")
        assert "#f38ba8" in result  # red

    def test_data_event_id(self) -> None:
        result = render_event_marker(event_id=42, x=0, y=0, event_type="Test")
        assert 'data-event-id="42"' in result

    def test_class_name(self) -> None:
        result = render_event_marker(event_id=1, x=0, y=0, event_type="Test")
        assert "event-marker" in result


# ── Agent label ──


class TestRenderAgentLabel:
    def test_returns_text_element(self) -> None:
        result = render_agent_label("my_agent", y=50.0)
        assert "<text" in result
        assert "my_agent" in result

    def test_y_position(self) -> None:
        result = render_agent_label("agent_a", y=100.0)
        assert 'y="100.0"' in result

    def test_class_name(self) -> None:
        result = render_agent_label("agent_a", y=0)
        assert "agent-label" in result

    def test_long_name_truncated(self) -> None:
        result = render_agent_label("a_very_long_agent_name_indeed", y=0)
        assert ".." in result
        assert "a_very_long_agent_name_indeed" not in result

    def test_xss_escaped(self) -> None:
        result = render_agent_label("<script>bad</script>", y=0)
        assert "<script>" not in result
        assert "&lt;script&gt;" in result


# ── Correlation line ──


class TestRenderCorrelationLine:
    def test_returns_line_or_path(self) -> None:
        result = render_correlation_line(x1=100, y1=50, x2=200, y2=100)
        # Either a <line> or <path> element
        assert "<line" in result or "<path" in result

    def test_class_name(self) -> None:
        result = render_correlation_line(x1=0, y1=0, x2=100, y2=50)
        assert "correlation-line" in result

    def test_coordinates(self) -> None:
        result = render_correlation_line(x1=10, y1=20, x2=30, y2=40)
        assert "10" in result
        assert "20" in result
        assert "30" in result
        assert "40" in result


# ── Time axis ──


class TestRenderTimeAxis:
    def test_returns_group(self) -> None:
        result = render_time_axis(
            time_range=(1000.0, 2000.0),
            x_start=100.0,
            x_end=800.0,
            y=300.0,
        )
        assert "<g" in result
        assert "time-axis" in result

    def test_contains_line(self) -> None:
        result = render_time_axis(
            time_range=(1000.0, 2000.0),
            x_start=100.0,
            x_end=800.0,
            y=300.0,
        )
        assert "<line" in result

    def test_contains_tick_labels(self) -> None:
        result = render_time_axis(
            time_range=(1000.0, 2000.0),
            x_start=100.0,
            x_end=800.0,
            y=300.0,
        )
        assert "<text" in result

    def test_single_timestamp(self) -> None:
        """Single event: axis should still render without division by zero."""
        result = render_time_axis(
            time_range=(1000.0, 1000.0),
            x_start=100.0,
            x_end=800.0,
            y=300.0,
        )
        assert "<g" in result
        assert "<text" in result
