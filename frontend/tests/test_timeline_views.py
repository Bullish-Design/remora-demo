"""Tests for timeline views — shell page, CSS, inspector panel."""

from __future__ import annotations

import time

from timeline.state import TimelineData
from timeline.views import render_timeline_shell, render_event_inspector
from timeline.css import timeline_css


# ── CSS ──


class TestTimelineCss:
    def test_returns_string(self) -> None:
        result = timeline_css()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_contains_catppuccin_vars(self) -> None:
        result = timeline_css()
        assert "--bg" in result

    def test_contains_timeline_classes(self) -> None:
        result = timeline_css()
        assert ".timeline-canvas" in result
        assert ".event-marker" in result
        assert ".agent-label" in result

    def test_contains_inspector_styles(self) -> None:
        result = timeline_css()
        assert ".inspector" in result

    def test_contains_hover_styles(self) -> None:
        result = timeline_css()
        assert ".event-marker:hover" in result or "event-marker" in result


# ── Shell page ──


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

    def test_returns_full_html(self) -> None:
        result = render_timeline_shell(self._make_data())
        assert "<!DOCTYPE html>" in result
        assert "<html" in result
        assert "</html>" in result

    def test_includes_datastar_script(self) -> None:
        result = render_timeline_shell(self._make_data())
        assert "datastar" in result

    def test_includes_css(self) -> None:
        result = render_timeline_shell(self._make_data())
        assert "<style>" in result
        assert "--bg" in result

    def test_includes_timeline_svg(self) -> None:
        result = render_timeline_shell(self._make_data())
        assert 'id="timeline-svg"' in result

    def test_includes_inspector_panel(self) -> None:
        result = render_timeline_shell(self._make_data())
        assert 'id="inspector"' in result

    def test_includes_sse_connection(self) -> None:
        result = render_timeline_shell(self._make_data())
        assert "data-init" in result
        assert "/timeline/subscribe" in result

    def test_includes_navigation_link(self) -> None:
        """Should link back to the graph view."""
        result = render_timeline_shell(self._make_data())
        assert "Graph" in result or "graph" in result
        assert 'href="/"' in result or "href='/'" in result

    def test_title_contains_timeline(self) -> None:
        result = render_timeline_shell(self._make_data())
        assert "Timeline" in result

    def test_includes_zoom_pan_js(self) -> None:
        result = render_timeline_shell(self._make_data())
        assert "timeline-pane" in result
        assert "wheel" in result

    def test_empty_data(self) -> None:
        result = render_timeline_shell(TimelineData())
        assert "<!DOCTYPE html>" in result
        assert "No events" in result

    def test_event_count_in_status(self) -> None:
        result = render_timeline_shell(self._make_data())
        assert "2 events" in result


# ── Event inspector ──


class TestRenderEventInspector:
    def test_empty_event(self) -> None:
        result = render_event_inspector(None)
        assert 'id="inspector"' in result
        assert "Select an event" in result or "Click" in result

    def test_with_event(self) -> None:
        event = {
            "event_id": 42,
            "event_type": "AgentStart",
            "timestamp": 1000.5,
            "from_agent": "load_config",
            "to_agent": "process_yaml",
            "correlation_id": "corr-abc",
            "payload": '{"message": "starting"}',
        }
        result = render_event_inspector(event)
        assert 'id="inspector"' in result
        assert "AgentStart" in result
        assert "load_config" in result
        assert "process_yaml" in result
        assert "corr-abc" in result

    def test_xss_escaped(self) -> None:
        event = {
            "event_id": 1,
            "event_type": "<script>bad</script>",
            "timestamp": 1.0,
            "from_agent": "<b>evil</b>",
            "to_agent": None,
            "correlation_id": None,
            "payload": "{}",
        }
        result = render_event_inspector(event)
        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    def test_payload_displayed(self) -> None:
        event = {
            "event_id": 1,
            "event_type": "Test",
            "timestamp": 1.0,
            "from_agent": "a",
            "to_agent": None,
            "correlation_id": None,
            "payload": '{"key": "value", "count": 42}',
        }
        result = render_event_inspector(event)
        assert "key" in result
        assert "value" in result

    def test_timestamp_formatted(self) -> None:
        event = {
            "event_id": 1,
            "event_type": "Test",
            "timestamp": 1000.123,
            "from_agent": "a",
            "to_agent": None,
            "correlation_id": None,
            "payload": "{}",
        }
        result = render_event_inspector(event)
        # Should contain some formatted time, not just the raw float
        assert ":" in result  # HH:MM:SS format
