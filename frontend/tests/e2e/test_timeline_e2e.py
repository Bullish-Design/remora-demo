"""E2E tests for the Timeline page.

Tests the timeline page load, navigation between graph and timeline,
event marker rendering, and the event inspector panel.
"""

from __future__ import annotations

from tests.e2e.conftest import add_event


class TestTimelinePageLoad:
    """Timeline page load and structure tests."""

    def test_timeline_page_loads(self, page, demo_server):
        """The /timeline page loads with correct title."""
        page.goto(f"{demo_server.url}/timeline")
        assert page.title() == "Remora Timeline"

    def test_timeline_has_header(self, page, demo_server):
        """Timeline page has header with title."""
        page.goto(f"{demo_server.url}/timeline")
        header = page.locator(".header-title")
        assert header.text_content() == "Remora Timeline"

    def test_timeline_has_graph_link(self, page, demo_server):
        """Timeline page has a navigation link back to the graph."""
        page.goto(f"{demo_server.url}/timeline")
        link = page.locator('a[href="/"]')
        assert link.is_visible()
        assert link.text_content() == "Graph"

    def test_timeline_shows_event_count(self, page, demo_server):
        """Header status shows event and agent counts."""
        page.goto(f"{demo_server.url}/timeline")
        status = page.locator(".header-status")
        text = status.text_content()
        assert "13 events" in text
        assert "agents" in text


class TestTimelineSVG:
    """Timeline SVG rendering — swimlane, event markers, labels."""

    def test_timeline_svg_appears(self, page, demo_server):
        """The timeline SVG element is rendered."""
        page.goto(f"{demo_server.url}/timeline")
        svg = page.locator("#timeline-svg")
        svg.wait_for(state="attached", timeout=5000)
        assert svg.is_visible()

    def test_event_markers_visible(self, page, demo_server):
        """Event markers (circles) are rendered in the timeline."""
        page.goto(f"{demo_server.url}/timeline")
        page.locator(".event-marker").first.wait_for(state="attached", timeout=5000)
        markers = page.locator(".event-marker")
        assert markers.count() == 13  # 13 NodeDiscovered events

    def test_agent_labels_visible(self, page, demo_server):
        """Agent labels are rendered in the left column."""
        page.goto(f"{demo_server.url}/timeline")
        page.locator(".agent-label").first.wait_for(state="attached", timeout=5000)
        labels = page.locator(".agent-label")
        assert labels.count() > 0

    def test_lane_backgrounds_present(self, page, demo_server):
        """Lane backgrounds are rendered for each agent."""
        page.goto(f"{demo_server.url}/timeline")
        page.locator(".lane-bg").first.wait_for(state="attached", timeout=5000)
        lanes = page.locator(".lane-bg")
        assert lanes.count() > 0

    def test_time_axis_present(self, page, demo_server):
        """Time axis is rendered at the bottom of the timeline."""
        page.goto(f"{demo_server.url}/timeline")
        page.locator(".time-axis").first.wait_for(state="attached", timeout=5000)
        axis = page.locator(".time-axis")
        assert axis.is_visible()


class TestTimelineNavigation:
    """Navigation between graph and timeline pages."""

    def test_graph_to_timeline_navigation(self, page, demo_server):
        """Clicking 'Timeline' link on graph page navigates to /timeline."""
        page.goto(demo_server.url)
        link = page.locator('a[href="/timeline"]')
        link.click()
        page.wait_for_url(f"{demo_server.url}/timeline")
        assert page.title() == "Remora Timeline"

    def test_timeline_to_graph_navigation(self, page, demo_server):
        """Clicking 'Graph' link on timeline page navigates to /."""
        page.goto(f"{demo_server.url}/timeline")
        link = page.locator('a[href="/"]')
        link.click()
        page.wait_for_url(f"{demo_server.url}/")
        assert page.title() == "Remora Graph"


class TestTimelineInspector:
    """Event inspector panel tests."""

    def test_inspector_shows_placeholder(self, page, demo_server):
        """Inspector panel shows placeholder text when no event selected."""
        page.goto(f"{demo_server.url}/timeline")
        inspector = page.locator("#inspector")
        inspector.wait_for(state="attached", timeout=5000)
        assert "Click an event" in inspector.text_content()


class TestTimelineSSEUpdates:
    """Timeline live updates via SSE."""

    def test_new_event_appears_in_timeline(self, page, demo_server):
        """Adding an event to the DB makes a new marker appear via SSE."""
        page.goto(f"{demo_server.url}/timeline")
        page.locator(".event-marker").first.wait_for(state="attached", timeout=5000)
        initial_count = page.locator(".event-marker").count()

        # Add a new event
        add_event(
            demo_server.db_path,
            "ContentChanged",
            "load_config",
            correlation_id="c_live",
        )

        # Wait for the new marker to appear
        page.wait_for_function(
            f"""() => {{
                const markers = document.querySelectorAll('.event-marker');
                return markers.length > {initial_count};
            }}""",
            timeout=5000,
        )
        assert page.locator(".event-marker").count() > initial_count
