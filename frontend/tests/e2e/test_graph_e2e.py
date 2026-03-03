"""E2E tests for the Graph Viewer page.

Tests the full browser experience: page load, SVG graph rendering,
SSE-driven updates via Datastar, node interactions, and sidebar loading.
"""

from __future__ import annotations

from tests.e2e.conftest import (
    add_event,
    add_node,
    add_proposal,
    change_status,
    set_cursor_focus,
)


class TestGraphPageLoad:
    """Basic page load and structure tests."""

    def test_page_loads_with_correct_title(self, page, demo_server):
        """Server starts, page loads, title is correct."""
        page.goto(demo_server.url)
        assert page.title() == "Remora Graph"

    def test_page_has_header(self, page, demo_server):
        """Page contains the header bar with title."""
        page.goto(demo_server.url)
        header = page.locator(".header-title")
        assert header.text_content() == "Remora Graph"

    def test_page_has_timeline_link(self, page, demo_server):
        """Header contains a link to the timeline page."""
        page.goto(demo_server.url)
        link = page.locator('a[href="/timeline"]')
        assert link.is_visible()

    def test_page_has_sidebar(self, page, demo_server):
        """Page contains the sidebar panel."""
        page.goto(demo_server.url)
        sidebar = page.locator("#sidebar")
        assert sidebar.is_visible()

    def test_page_has_event_stream(self, page, demo_server):
        """Page contains the event stream area."""
        page.goto(demo_server.url)
        stream = page.locator("#event-stream")
        assert stream.is_visible()


class TestGraphRendering:
    """Graph SVG rendering after SSE delivers initial state."""

    def test_graph_svg_appears(self, page, demo_server):
        """The graph SVG element is rendered on the page."""
        page.goto(demo_server.url)
        # Wait for Datastar SSE to deliver the initial graph
        svg = page.locator("#graph-svg")
        svg.wait_for(state="attached", timeout=5000)
        assert svg.is_visible()

    def test_all_13_nodes_rendered(self, page, demo_server):
        """All 13 demo nodes appear as SVG node groups."""
        page.goto(demo_server.url)
        page.locator(".node-group").first.wait_for(state="attached", timeout=5000)
        nodes = page.locator(".node-group")
        assert nodes.count() == 13

    def test_all_14_edges_rendered(self, page, demo_server):
        """All 14 demo edges appear as SVG lines."""
        page.goto(demo_server.url)
        page.locator(".edge-line").first.wait_for(state="attached", timeout=5000)
        edges = page.locator(".edge-line")
        assert edges.count() == 14

    def test_specific_nodes_present(self, page, demo_server):
        """Key nodes are present with correct data-node-id attributes."""
        page.goto(demo_server.url)
        page.locator(".node-group").first.wait_for(state="attached", timeout=5000)

        for node_id in [
            "load_config",
            "detect_format",
            "validate",
            "deep_merge",
            "test_load_yaml",
        ]:
            node = page.locator(f'[data-node-id="{node_id}"]')
            assert node.is_visible(), f"Node {node_id} should be visible"

    def test_node_labels_visible(self, page, demo_server):
        """Node labels (text elements) are rendered."""
        page.goto(demo_server.url)
        page.locator(".node-label").first.wait_for(state="attached", timeout=5000)
        labels = page.locator(".node-label")
        assert labels.count() == 13

    def test_node_colors_match_idle_status(self, page, demo_server):
        """All nodes start as idle (gray fill #6c7086)."""
        page.goto(demo_server.url)
        page.locator(".node-circle").first.wait_for(state="attached", timeout=5000)

        circles = page.locator(".node-circle")
        for i in range(circles.count()):
            fill = circles.nth(i).get_attribute("fill")
            assert fill == "#6c7086", f"Node {i} should have idle fill, got {fill}"

    def test_header_shows_node_count(self, page, demo_server):
        """Header status shows '13 nodes, 14 edges'."""
        page.goto(demo_server.url)
        status = page.locator("#connection-status")
        assert "13 nodes" in status.text_content()
        assert "14 edges" in status.text_content()


class TestSSEUpdates:
    """SSE-driven DOM updates via Datastar morphing."""

    def test_status_change_updates_node_color(self, page, demo_server):
        """Changing a node's status in the DB updates its SVG fill via SSE."""
        page.goto(demo_server.url)
        page.locator(".node-group").first.wait_for(state="attached", timeout=5000)

        # Change load_config to running (blue #89b4fa)
        change_status(demo_server.db_path, "load_config", "running")

        # Wait for the color to update via SSE
        node_circle = page.locator('[data-node-id="load_config"] .node-circle')
        node_circle.wait_for(state="attached", timeout=5000)

        # Playwright auto-waits, but poll for the color change
        page.wait_for_function(
            """() => {
                const el = document.querySelector('[data-node-id="load_config"] circle');
                return el && el.getAttribute('fill') === '#89b4fa';
            }""",
            timeout=5000,
        )
        assert node_circle.get_attribute("fill") == "#89b4fa"

    def test_new_events_appear_in_stream(self, page, demo_server):
        """Adding an event to the DB makes it appear in the event stream via SSE."""
        page.goto(demo_server.url)
        page.locator("#event-stream").wait_for(state="attached", timeout=5000)

        # Add a ContentChanged event
        add_event(
            demo_server.db_path,
            "ContentChanged",
            "load_config",
            correlation_id="c_test",
        )

        # Wait for event to appear in the event stream
        page.wait_for_function(
            """() => {
                const stream = document.getElementById('event-stream');
                return stream && stream.innerHTML.includes('ContentChanged');
            }""",
            timeout=5000,
        )
        stream = page.locator("#event-stream")
        assert "ContentChanged" in stream.inner_html()

    def test_new_node_appears_in_graph(self, page, demo_server):
        """Adding a node to the DB makes it appear in the graph via SSE."""
        page.goto(demo_server.url)
        page.locator(".node-group").first.wait_for(state="attached", timeout=5000)
        assert page.locator(".node-group").count() == 13

        # Add a new node
        add_node(
            demo_server.db_path,
            "new_function",
            name="new_function",
            file_path="src/new.py",
        )
        # Also add an edge so the bridge detects topology change
        import sqlite3

        conn = sqlite3.connect(demo_server.db_path)
        conn.execute(
            "INSERT INTO edges VALUES (?, ?, ?)",
            ("loader.py", "new_function", "parent_of"),
        )
        conn.commit()
        conn.close()

        # Wait for 14th node to appear
        page.wait_for_function(
            """() => {
                const nodes = document.querySelectorAll('.node-group');
                return nodes.length === 14;
            }""",
            timeout=5000,
        )
        assert page.locator(".node-group").count() == 14

    def test_cursor_focus_highlights_node(self, page, demo_server):
        """Setting cursor_focus in the DB highlights the node with a blue stroke."""
        page.goto(demo_server.url)
        page.locator(".node-group").first.wait_for(state="attached", timeout=5000)

        # Set cursor focus to load_config
        set_cursor_focus(
            demo_server.db_path, "load_config", "src/configlib/loader.py", 15
        )

        # Wait for the focus highlight (stroke="#89b4fa" on the circle)
        page.wait_for_function(
            """() => {
                const el = document.querySelector('[data-node-id="load_config"] circle');
                return el && el.getAttribute('stroke') === '#89b4fa';
            }""",
            timeout=5000,
        )
        circle = page.locator('[data-node-id="load_config"] .node-circle')
        assert circle.get_attribute("stroke") == "#89b4fa"


class TestNodeInteraction:
    """User interaction tests — clicking nodes to load sidebar details."""

    def test_click_node_loads_sidebar(self, page, demo_server):
        """Clicking a node circle loads sidebar details for that node."""
        page.goto(demo_server.url)
        page.locator(".node-group").first.wait_for(state="attached", timeout=5000)

        # Click the load_config node
        node = page.locator('[data-node-id="load_config"]')
        node.click()

        # Wait for sidebar to update with node details
        page.wait_for_function(
            """() => {
                const sidebar = document.getElementById('sidebar-content');
                return sidebar && sidebar.innerHTML.includes('load_config');
            }""",
            timeout=5000,
        )
        sidebar = page.locator("#sidebar-content")
        assert "load_config" in sidebar.inner_html()

    def test_proposal_shows_approve_reject(self, page, demo_server):
        """Adding a proposal makes Approve/Reject buttons appear in sidebar."""
        page.goto(demo_server.url)
        page.locator(".node-group").first.wait_for(state="attached", timeout=5000)

        # Add a proposal for test_load_yaml
        add_proposal(
            demo_server.db_path,
            "test_load_yaml",
            "def test_load_yaml(): ...",
            "def test_load_yaml():\n    # with timeout\n    ...",
        )

        # Click the test_load_yaml node to view its sidebar
        node = page.locator('[data-node-id="test_load_yaml"]')
        node.click()

        # Wait for sidebar to show the proposal buttons
        page.wait_for_function(
            """() => {
                const sidebar = document.getElementById('sidebar-content');
                return sidebar && sidebar.innerHTML.includes('Approve');
            }""",
            timeout=5000,
        )
        sidebar = page.locator("#sidebar-content")
        content = sidebar.inner_html()
        assert "Approve" in content
        assert "Reject" in content
