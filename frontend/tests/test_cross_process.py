"""Cross-process integration test — EventStore writes, GraphState reads.

Verifies the true round-trip: Remora's EventStore (with NodeProjection)
creates the DB and writes events/nodes, and the graph viewer's GraphState
reads them back correctly.

This is the only test that imports from both the Remora library and the
graph viewer, proving the schema alignment is real — not just matching
hand-written CREATE TABLE statements.
"""

from __future__ import annotations

import asyncio
import sqlite3
import time
from pathlib import Path

import pytest

from remora.core.event_store import EventStore
from remora.core.events import (
    AgentCompleteEvent,
    AgentErrorEvent,
    AgentMessageEvent,
    AgentStartEvent,
    NodeDiscoveredEvent,
)
from remora.core.projections import NodeProjection

from graph.bridge import DBBridge
from graph.layout import ForceLayout
from graph.state import GraphState
from graph.views.event_stream import render_event_list
from graph.views.shell import render_shell
from graph.views.sidebar import render_sidebar_content


class FakeRelay:
    """Test double for the Relay — records published subjects."""

    def __init__(self) -> None:
        self.published: list[tuple[str, str]] = []

    def publish(self, subject: str, data: str) -> None:
        self.published.append((subject, data))

    @property
    def subjects(self) -> list[str]:
        return [s for s, _ in self.published]

    def clear(self) -> None:
        self.published.clear()


@pytest.fixture()
def db_path(tmp_path: Path) -> str:
    return str(tmp_path / "indexer.db")


@pytest.fixture()
def projection() -> NodeProjection:
    return NodeProjection()


class TestEventStoreToGraphState:
    """Round-trip: EventStore.append() -> GraphState.read_*()."""

    @pytest.mark.asyncio
    async def test_nodes_written_by_projection_readable_by_graph_state(
        self, db_path: str, projection: NodeProjection
    ) -> None:
        """NodeDiscoveredEvent -> projection upserts node -> GraphState reads it."""
        store = EventStore(db_path, projection=projection)
        await store.initialize()

        # Emit a NodeDiscoveredEvent (as the LSP indexer would)
        await store.append(
            "graph1",
            NodeDiscoveredEvent(
                node_id="load_config",
                node_type="function",
                name="load_config",
                full_name="configlib.loader.load_config",
                file_path="configlib/loader.py",
                start_line=10,
                end_line=25,
                source_code="def load_config(path):\n    ...",
                source_hash="abc123",
                parent_id=None,
            ),
        )
        await store.close()

        # Now read through GraphState (as the graph viewer would)
        gs = GraphState(db_path=db_path)
        node = gs.read_node("load_config")
        assert node is not None
        assert node["remora_id"] == "load_config"
        assert node["name"] == "load_config"
        assert node["full_name"] == "configlib.loader.load_config"
        assert node["file_path"] == "configlib/loader.py"
        assert node["start_line"] == 10
        assert node["end_line"] == 25
        assert node["source_code"] == "def load_config(path):\n    ..."
        assert node["status"] == "idle"
        gs.close()

    @pytest.mark.asyncio
    async def test_snapshot_reads_multiple_projected_nodes(self, db_path: str, projection: NodeProjection) -> None:
        """Multiple NodeDiscoveredEvents -> snapshot returns all nodes."""
        store = EventStore(db_path, projection=projection)
        await store.initialize()

        nodes_data = [
            ("loader.py", "file", "loader.py", "configlib/loader.py", "configlib/loader.py", 1, 42),
            ("load_config", "function", "load_config", "configlib.loader.load_config", "configlib/loader.py", 10, 25),
            ("validate", "function", "validate", "configlib.schema.validate", "configlib/schema.py", 5, 20),
        ]
        for nid, ntype, name, full_name, fpath, sl, el in nodes_data:
            await store.append(
                "graph1",
                NodeDiscoveredEvent(
                    node_id=nid,
                    node_type=ntype,
                    name=name,
                    full_name=full_name,
                    file_path=fpath,
                    start_line=sl,
                    end_line=el,
                    source_code="",
                    source_hash=f"hash_{nid}",
                ),
            )
        await store.close()

        gs = GraphState(db_path=db_path)
        snapshot = gs.read_snapshot()
        assert len(snapshot.nodes) == 3
        ids = {n["remora_id"] for n in snapshot.nodes}
        assert ids == {"loader.py", "load_config", "validate"}
        gs.close()

    @pytest.mark.asyncio
    async def test_agent_lifecycle_updates_node_status(self, db_path: str, projection: NodeProjection) -> None:
        """AgentStartEvent/AgentCompleteEvent/AgentErrorEvent update node status."""
        store = EventStore(db_path, projection=projection)
        await store.initialize()

        # Discover node
        await store.append(
            "graph1",
            NodeDiscoveredEvent(
                node_id="load_config",
                node_type="function",
                name="load_config",
                full_name="configlib.loader.load_config",
                file_path="configlib/loader.py",
                start_line=10,
                end_line=25,
                source_code="def load_config(path): ...",
                source_hash="abc",
            ),
        )

        # Start agent -> status becomes "running"
        await store.append(
            "graph1",
            AgentStartEvent(
                graph_id="graph1",
                agent_id="load_config",
                node_name="load_config",
                trigger_event_type="ContentChanged",
            ),
        )
        await store.close()

        gs = GraphState(db_path=db_path)
        node = gs.read_node("load_config")
        assert node is not None
        assert node["status"] == "running"
        gs.close()

        # Complete agent -> status becomes "idle"
        store2 = EventStore(db_path, projection=projection)
        await store2.initialize()
        await store2.append(
            "graph1",
            AgentCompleteEvent(
                graph_id="graph1",
                agent_id="load_config",
                result_summary="Analysis complete",
            ),
        )
        await store2.close()

        gs2 = GraphState(db_path=db_path)
        node2 = gs2.read_node("load_config")
        assert node2 is not None
        assert node2["status"] == "idle"
        gs2.close()

    @pytest.mark.asyncio
    async def test_agent_error_sets_error_status(self, db_path: str, projection: NodeProjection) -> None:
        """AgentErrorEvent sets node status to 'error'."""
        store = EventStore(db_path, projection=projection)
        await store.initialize()

        await store.append(
            "graph1",
            NodeDiscoveredEvent(
                node_id="validate",
                node_type="function",
                name="validate",
                full_name="configlib.schema.validate",
                file_path="configlib/schema.py",
                start_line=5,
                end_line=20,
                source_code="def validate(data): ...",
                source_hash="xyz",
            ),
        )
        await store.append(
            "graph1",
            AgentErrorEvent(
                graph_id="graph1",
                agent_id="validate",
                error="Schema validation failed",
            ),
        )
        await store.close()

        gs = GraphState(db_path=db_path)
        node = gs.read_node("validate")
        assert node is not None
        assert node["status"] == "error"
        gs.close()

    @pytest.mark.asyncio
    async def test_events_readable_by_graph_state(self, db_path: str, projection: NodeProjection) -> None:
        """Events appended via EventStore are readable by GraphState.read_recent_events()."""
        store = EventStore(db_path, projection=projection)
        await store.initialize()

        await store.append(
            "graph1",
            NodeDiscoveredEvent(
                node_id="load_config",
                node_type="function",
                name="load_config",
                full_name="configlib.loader.load_config",
                file_path="configlib/loader.py",
                start_line=10,
                end_line=25,
                source_code="",
                source_hash="abc",
            ),
        )
        await store.append(
            "graph1",
            AgentStartEvent(
                graph_id="graph1",
                agent_id="load_config",
                node_name="load_config",
            ),
        )
        await store.close()

        gs = GraphState(db_path=db_path)
        events = gs.read_recent_events(limit=10)
        assert len(events) == 2
        types = {e["event_type"] for e in events}
        assert "NodeDiscoveredEvent" in types
        assert "AgentStartEvent" in types
        # Verify event_id is present (aliased from id)
        assert all("event_id" in e for e in events)
        gs.close()

    @pytest.mark.asyncio
    async def test_events_for_agent_uses_from_agent(self, db_path: str, projection: NodeProjection) -> None:
        """GraphState.read_events_for_agent() finds events via from_agent field."""
        store = EventStore(db_path, projection=projection)
        await store.initialize()

        # AgentStartEvent has from_agent set via getattr(event, "from_agent")
        # which is None — but agent_id is "load_config". The EventStore sets
        # from_agent from the event attribute. Let's use AgentMessageEvent
        # which explicitly has from_agent.
        await store.append(
            "graph1",
            AgentMessageEvent(
                from_agent="load_config",
                to_agent="test_load_yaml",
                content="Update tests for timeout",
                correlation_id="c1",
            ),
        )
        await store.append(
            "graph1",
            AgentMessageEvent(
                from_agent="test_load_yaml",
                to_agent="load_config",
                content="Tests updated",
                correlation_id="c1",
            ),
        )
        await store.close()

        gs = GraphState(db_path=db_path)
        # load_config should see both: one as from_agent, one as to_agent
        events = gs.read_events_for_agent("load_config")
        assert len(events) == 2

        # test_load_yaml should also see both
        events2 = gs.read_events_for_agent("test_load_yaml")
        assert len(events2) == 2
        gs.close()

    @pytest.mark.asyncio
    async def test_edges_written_directly_readable_by_graph_state(
        self, db_path: str, projection: NodeProjection
    ) -> None:
        """Edges written to the EventStore-created DB are readable by GraphState."""
        store = EventStore(db_path, projection=projection)
        await store.initialize()

        # Discover nodes
        for nid, ntype, name in [
            ("loader.py", "file", "loader.py"),
            ("load_config", "function", "load_config"),
            ("validate", "function", "validate"),
        ]:
            await store.append(
                "graph1",
                NodeDiscoveredEvent(
                    node_id=nid,
                    node_type=ntype,
                    name=name,
                    full_name=name,
                    file_path=f"{name}.py" if ntype == "file" else "loader.py",
                    start_line=1,
                    end_line=10,
                    source_code="",
                    source_hash=f"hash_{nid}",
                ),
            )
        await store.close()

        # Write edges directly (as RemoraDB.update_edges would)
        conn = sqlite3.connect(db_path)
        conn.execute(
            "INSERT INTO edges (from_id, to_id, edge_type) VALUES (?, ?, ?)",
            ("loader.py", "load_config", "parent_of"),
        )
        conn.execute(
            "INSERT INTO edges (from_id, to_id, edge_type) VALUES (?, ?, ?)",
            ("load_config", "validate", "calls"),
        )
        conn.commit()
        conn.close()

        gs = GraphState(db_path=db_path)
        snapshot = gs.read_snapshot()
        assert len(snapshot.edges) == 2

        connections = gs.read_edges_for_node("load_config")
        assert "loader.py" in connections["parents"]
        assert "validate" in connections["callees"]
        gs.close()


class TestEventStoreToBridge:
    """Round-trip: EventStore writes -> DBBridge detects changes."""

    @pytest.mark.asyncio
    async def test_bridge_detects_projected_nodes(self, db_path: str, projection: NodeProjection) -> None:
        """Bridge detects nodes written by EventStore+NodeProjection."""
        store = EventStore(db_path, projection=projection)
        await store.initialize()

        await store.append(
            "graph1",
            NodeDiscoveredEvent(
                node_id="load_config",
                node_type="function",
                name="load_config",
                full_name="configlib.loader.load_config",
                file_path="configlib/loader.py",
                start_line=10,
                end_line=25,
                source_code="def load_config(path): ...",
                source_hash="abc",
            ),
        )
        await store.close()

        gs = GraphState(db_path=db_path)
        layout = ForceLayout()
        relay = FakeRelay()
        bridge = DBBridge(state=gs, layout=layout, relay=relay)

        subjects = await bridge._poll_once()
        assert "graph.topology" in subjects
        assert "graph.events" in subjects
        assert len(relay.published) > 0
        gs.close()

    @pytest.mark.asyncio
    async def test_bridge_detects_status_change_from_agent_events(
        self, db_path: str, projection: NodeProjection
    ) -> None:
        """Bridge detects status change caused by AgentStartEvent projection."""
        store = EventStore(db_path, projection=projection)
        await store.initialize()

        await store.append(
            "graph1",
            NodeDiscoveredEvent(
                node_id="load_config",
                node_type="function",
                name="load_config",
                full_name="configlib.loader.load_config",
                file_path="configlib/loader.py",
                start_line=10,
                end_line=25,
                source_code="def load_config(path): ...",
                source_hash="abc",
            ),
        )
        await store.close()

        gs = GraphState(db_path=db_path)
        layout = ForceLayout()
        relay = FakeRelay()
        bridge = DBBridge(state=gs, layout=layout, relay=relay)

        # First poll: baseline
        await bridge._poll_once()
        relay.clear()

        # Agent starts -> projection sets status to 'running'
        store2 = EventStore(db_path, projection=projection)
        await store2.initialize()
        await store2.append(
            "graph1",
            AgentStartEvent(
                graph_id="graph1",
                agent_id="load_config",
                node_name="load_config",
            ),
        )
        await store2.close()

        # Second poll: should detect status change + new event
        subjects = await bridge._poll_once()
        assert "graph.status" in subjects
        assert "graph.events" in subjects
        gs.close()


class TestEventStoreToViews:
    """Round-trip: EventStore writes -> Views render correctly."""

    @pytest.mark.asyncio
    async def test_full_pipeline_eventstore_to_rendered_html(self, db_path: str, projection: NodeProjection) -> None:
        """Complete pipeline: EventStore -> GraphState -> Layout -> Views."""
        store = EventStore(db_path, projection=projection)
        await store.initialize()

        # Discover nodes
        nodes = [
            ("loader.py", "file", "loader.py", "configlib/loader.py", 1, 42),
            ("load_config", "function", "load_config", "configlib/loader.py", 10, 25),
            ("validate", "function", "validate", "configlib/schema.py", 5, 20),
        ]
        for nid, ntype, name, fpath, sl, el in nodes:
            await store.append(
                "graph1",
                NodeDiscoveredEvent(
                    node_id=nid,
                    node_type=ntype,
                    name=name,
                    full_name=f"configlib.{name}",
                    file_path=fpath,
                    start_line=sl,
                    end_line=el,
                    source_code=f"def {name}(): ...",
                    source_hash=f"hash_{nid}",
                ),
            )

        # Add edges
        conn = sqlite3.connect(db_path)
        conn.execute("INSERT INTO edges VALUES (?, ?, ?)", ("loader.py", "load_config", "parent_of"))
        conn.execute("INSERT INTO edges VALUES (?, ?, ?)", ("load_config", "validate", "calls"))
        conn.commit()
        conn.close()

        # Start an agent
        await store.append(
            "graph1",
            AgentStartEvent(
                graph_id="graph1",
                agent_id="load_config",
                node_name="load_config",
                trigger_event_type="ContentChanged",
            ),
        )

        # Agent sends message
        await store.append(
            "graph1",
            AgentMessageEvent(
                from_agent="load_config",
                to_agent="validate",
                content="Check schema after timeout change",
                correlation_id="c1",
            ),
        )
        await store.close()

        # Read through GraphState
        gs = GraphState(db_path=db_path)
        snapshot = gs.read_snapshot()
        assert len(snapshot.nodes) == 3
        assert len(snapshot.edges) == 2

        # Verify status was projected
        lc_node = next(n for n in snapshot.nodes if n["remora_id"] == "load_config")
        assert lc_node["status"] == "running"

        # Layout
        layout = ForceLayout(width=900, height=600)
        layout.set_graph(
            [{"id": n["remora_id"], "node_type": n.get("node_type", "function")} for n in snapshot.nodes],
            snapshot.edges,
        )
        layout.step(100)
        positions = layout.get_positions()

        # Render shell
        html = render_shell(snapshot, positions)
        assert "<!DOCTYPE html>" in html
        assert "3 nodes" in html
        assert "2 edges" in html
        assert "load_config" in html

        # Render event stream
        events = gs.read_recent_events(limit=30)
        event_html = render_event_list(events)
        assert "AgentStartEvent" in event_html
        assert "AgentMessageEvent" in event_html

        # Render sidebar
        node = gs.read_node("load_config")
        node_events = gs.read_events_for_agent("load_config")
        connections = gs.read_edges_for_node("load_config")
        sidebar_html = render_sidebar_content(node, node_events, [], connections)
        assert "load_config" in sidebar_html
        assert "running" in sidebar_html
        assert "validate" in sidebar_html  # callee connection

        gs.close()
