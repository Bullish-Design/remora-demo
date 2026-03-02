"""T22 — End-to-end golden path smoke test.

Simulates the full demo sequence by:
1. Creating a DB with the configlib demo project state.
2. Running the MockLLM through the golden path beat sequence.
3. Writing events to the DB as the LSP server would.
4. Verifying the bridge detects each change.
5. Verifying the views render correctly at each step.
6. Testing command submission from the browser side.

This test does NOT require the Remora library — it simulates what the LSP
server would write to the DB and verifies the demo-side components handle
it correctly.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
import time
from pathlib import Path

import pytest

from graph.bridge import DBBridge
from graph.layout import ForceLayout
from graph.state import GraphState
from graph.views.event_stream import render_event_list
from graph.views.graph import render_graph
from graph.views.shell import render_shell
from graph.views.sidebar import render_sidebar_content
from remora_demo.mock_llm import MockLLMClient


def _create_demo_db(db_path: str) -> None:
    """Create the full configlib demo database matching T1/T2 project files."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")

    conn.executescript("""
        CREATE TABLE nodes (
            id TEXT PRIMARY KEY,
            node_type TEXT NOT NULL,
            name TEXT NOT NULL,
            file_path TEXT NOT NULL DEFAULT '',
            start_line INTEGER NOT NULL DEFAULT 0,
            end_line INTEGER NOT NULL DEFAULT 0,
            source_code TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'idle'
        );

        CREATE TABLE edges (
            from_id TEXT NOT NULL,
            to_id TEXT NOT NULL,
            edge_type TEXT NOT NULL,
            PRIMARY KEY (from_id, to_id, edge_type)
        );

        CREATE TABLE events (
            event_id TEXT PRIMARY KEY,
            event_type TEXT NOT NULL,
            timestamp REAL NOT NULL,
            correlation_id TEXT,
            agent_id TEXT,
            payload JSON NOT NULL DEFAULT '{}'
        );

        CREATE TABLE cursor_focus (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            agent_id TEXT,
            file_path TEXT,
            line INTEGER,
            timestamp REAL
        );

        CREATE TABLE proposals (
            proposal_id TEXT PRIMARY KEY,
            agent_id TEXT NOT NULL,
            old_source TEXT NOT NULL DEFAULT '',
            new_source TEXT NOT NULL DEFAULT '',
            diff TEXT NOT NULL DEFAULT '',
            status TEXT DEFAULT 'pending',
            created_at REAL NOT NULL,
            file_path TEXT
        );

        CREATE TABLE command_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            command_type TEXT NOT NULL,
            agent_id TEXT,
            payload JSON NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at REAL NOT NULL,
            processed_at REAL
        );
    """)

    now = time.time()

    # Beat 2: Nodes discovered after opening files
    nodes = [
        (
            "loader.py",
            "file",
            "src/configlib/loader.py",
            "loader.py",
            1,
            42,
            "",
            "idle",
        ),
        (
            "load_config",
            "function",
            "src/configlib/loader.py",
            "load_config",
            10,
            25,
            'def load_config(path: str | Path) -> dict[str, Any]:\n    """Load and validate a config file."""\n    ...',
            "idle",
        ),
        (
            "detect_format",
            "function",
            "src/configlib/loader.py",
            "detect_format",
            28,
            35,
            'def detect_format(path: str | Path) -> str:\n    """Detect config file format."""\n    ...',
            "idle",
        ),
        (
            "load_yaml",
            "function",
            "src/configlib/loader.py",
            "load_yaml",
            38,
            42,
            "def load_yaml(path: str | Path) -> dict:\n    ...",
            "idle",
        ),
        (
            "schema.py",
            "file",
            "src/configlib/schema.py",
            "schema.py",
            1,
            24,
            "",
            "idle",
        ),
        (
            "validate",
            "function",
            "src/configlib/schema.py",
            "validate",
            8,
            20,
            "def validate(data: dict, schema: dict) -> dict:\n    ...",
            "idle",
        ),
        ("merge.py", "file", "src/configlib/merge.py", "merge.py", 1, 26, "", "idle"),
        (
            "deep_merge",
            "function",
            "src/configlib/merge.py",
            "deep_merge",
            5,
            18,
            "def deep_merge(base: dict, override: dict) -> dict:\n    ...",
            "idle",
        ),
        (
            "test_loader.py",
            "file",
            "tests/test_loader.py",
            "test_loader.py",
            1,
            35,
            "",
            "idle",
        ),
        (
            "test_load_yaml",
            "function",
            "tests/test_loader.py",
            "test_load_yaml",
            10,
            20,
            "def test_load_yaml(tmp_path: Path) -> None:\n    ...",
            "idle",
        ),
        (
            "test_load_json",
            "function",
            "tests/test_loader.py",
            "test_load_json",
            23,
            33,
            "def test_load_json(tmp_path: Path) -> None:\n    ...",
            "idle",
        ),
        (
            "test_merge.py",
            "file",
            "tests/test_merge.py",
            "test_merge.py",
            1,
            18,
            "",
            "idle",
        ),
        (
            "test_deep_merge",
            "function",
            "tests/test_merge.py",
            "test_deep_merge",
            5,
            12,
            "def test_deep_merge() -> None:\n    ...",
            "idle",
        ),
    ]
    for nid, ntype, fpath, name, sl, el, src, status in nodes:
        conn.execute(
            "INSERT INTO nodes VALUES (?,?,?,?,?,?,?,?)",
            (nid, ntype, name, fpath, sl, el, src, status),
        )

    # Edges: parent_of (file->function) + calls
    edges = [
        ("loader.py", "load_config", "parent_of"),
        ("loader.py", "detect_format", "parent_of"),
        ("loader.py", "load_yaml", "parent_of"),
        ("schema.py", "validate", "parent_of"),
        ("merge.py", "deep_merge", "parent_of"),
        ("test_loader.py", "test_load_yaml", "parent_of"),
        ("test_loader.py", "test_load_json", "parent_of"),
        ("test_merge.py", "test_deep_merge", "parent_of"),
        ("load_config", "detect_format", "calls"),
        ("load_config", "validate", "calls"),
        ("load_config", "load_yaml", "calls"),
        ("test_load_yaml", "load_config", "calls"),
        ("test_load_json", "load_config", "calls"),
        ("test_deep_merge", "deep_merge", "calls"),
    ]
    for fid, tid, etype in edges:
        conn.execute("INSERT INTO edges VALUES (?,?,?)", (fid, tid, etype))

    # Initial events: NodeDiscovered for each node
    for i, (nid, *_rest) in enumerate(nodes):
        conn.execute(
            "INSERT INTO events VALUES (?,?,?,?,?,?)",
            (
                f"discover_{i}",
                "NodeDiscovered",
                now - 60 + i,
                "boot",
                nid,
                json.dumps({"message": f"Discovered {nid}"}),
            ),
        )

    conn.commit()
    conn.close()


@pytest.fixture()
def demo_db(tmp_path: Path) -> str:
    db_path = str(tmp_path / "indexer.db")
    _create_demo_db(db_path)
    return db_path


class FakeRelay:
    """Collects published subjects for assertion."""

    def __init__(self) -> None:
        self.published: list[tuple[str, str]] = []

    def publish(self, subject: str, data: str) -> None:
        self.published.append((subject, data))

    @property
    def subjects(self) -> list[str]:
        return [s for s, _ in self.published]

    def clear(self) -> None:
        self.published.clear()


class TestGoldenPathBeat2:
    """Beat 2: Opening files — nodes appear in the graph."""

    def test_initial_graph_has_all_nodes(self, demo_db: str) -> None:
        gs = GraphState(db_path=demo_db)
        snapshot = gs.read_snapshot()
        assert len(snapshot.nodes) == 13
        assert len(snapshot.edges) == 14
        gs.close()

    def test_initial_graph_renders(self, demo_db: str) -> None:
        gs = GraphState(db_path=demo_db)
        snapshot = gs.read_snapshot()
        layout = ForceLayout(width=900, height=600)
        layout.set_graph(
            [
                {"id": n.get("remora_id", n.get("id")), "node_type": n.get("node_type")}
                for n in snapshot.nodes
            ],
            snapshot.edges,
        )
        layout.step(150)
        positions = layout.get_positions()

        html = render_shell(snapshot, positions)
        assert "13 nodes" in html
        assert "14 edges" in html
        assert "load_config" in html
        assert "test_load_yaml" in html
        gs.close()

    def test_bridge_detects_initial_state(self, demo_db: str) -> None:
        gs = GraphState(db_path=demo_db)
        layout = ForceLayout(width=900, height=600)
        relay = FakeRelay()
        bridge = DBBridge(state=gs, layout=layout, relay=relay)

        subjects = asyncio.run(bridge._poll_once())
        assert "graph.topology" in subjects
        assert "graph.events" in subjects
        gs.close()


class TestGoldenPathBeat4:
    """Beat 4: Cursor tracking — cursor focus highlights a node."""

    def test_cursor_focus_renders_highlight(self, demo_db: str) -> None:
        # Simulate cursor moving to load_config
        conn = sqlite3.connect(demo_db)
        conn.execute(
            "INSERT INTO cursor_focus (id, agent_id, file_path, line, timestamp) VALUES (1, 'load_config', 'src/configlib/loader.py', 15, ?)",
            (time.time(),),
        )
        conn.commit()
        conn.close()

        gs = GraphState(db_path=demo_db)
        snapshot = gs.read_snapshot()
        layout = ForceLayout(width=900, height=600)
        layout.set_graph(
            [
                {"id": n.get("remora_id", n.get("id")), "node_type": n.get("node_type")}
                for n in snapshot.nodes
            ],
            snapshot.edges,
        )
        layout.step(150)
        positions = layout.get_positions()

        cf = snapshot.cursor_focus.get("agent_id") if snapshot.cursor_focus else None
        graph_html = render_graph(snapshot, positions, cursor_focus=cf)

        # The focused node should have the focus stroke
        assert "#89b4fa" in graph_html  # focus blue color
        gs.close()

    def test_bridge_detects_cursor_change(self, demo_db: str) -> None:
        gs = GraphState(db_path=demo_db)
        layout = ForceLayout(width=900, height=600)
        relay = FakeRelay()
        bridge = DBBridge(state=gs, layout=layout, relay=relay)

        asyncio.run(bridge._poll_once())
        relay.clear()

        # Insert cursor focus
        conn = sqlite3.connect(demo_db)
        conn.execute(
            "INSERT INTO cursor_focus (id, agent_id, file_path, line, timestamp) VALUES (1, 'load_config', 'src/configlib/loader.py', 15, ?)",
            (time.time(),),
        )
        conn.commit()
        conn.close()

        subjects = asyncio.run(bridge._poll_once())
        assert "graph.cursor" in subjects
        gs.close()


class TestGoldenPathBeat5:
    """Beat 5: Human chat — user talks to an agent."""

    @pytest.mark.asyncio
    async def test_mock_llm_handles_chat(self) -> None:
        mock = MockLLMClient()
        messages = [
            {
                "role": "system",
                "content": "You are the agent for `load_config`. node_type: function",
            },
            {"role": "user", "content": "what do you do?"},
        ]
        resp = await mock.chat(messages)
        assert "load_config" in resp.content
        assert resp.tool_calls == []

    def test_chat_command_queued_from_browser(self, demo_db: str) -> None:
        """Browser sends a chat command via command_queue."""
        gs = GraphState(db_path=demo_db)
        cmd_id = gs.push_command("chat", "load_config", {"message": "what do you do?"})
        assert cmd_id > 0

        # Verify the command is in the queue
        conn = sqlite3.connect(demo_db)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM command_queue WHERE id = ?", (cmd_id,)
        ).fetchone()
        assert row["command_type"] == "chat"
        assert row["agent_id"] == "load_config"
        assert row["status"] == "pending"
        conn.close()
        gs.close()

    def test_chat_events_render_in_stream(self, demo_db: str) -> None:
        """After a chat, events appear in the event stream."""
        now = time.time()
        conn = sqlite3.connect(demo_db)
        conn.execute(
            "INSERT INTO events VALUES (?,?,?,?,?,?)",
            (
                "chat_1",
                "HumanChat",
                now,
                "c_chat",
                "load_config",
                json.dumps({"message": "what do you do?"}),
            ),
        )
        conn.execute(
            "INSERT INTO events VALUES (?,?,?,?,?,?)",
            (
                "chat_2",
                "AgentComplete",
                now + 0.5,
                "c_chat",
                "load_config",
                json.dumps({"message": "Agent responded"}),
            ),
        )
        conn.commit()
        conn.close()

        gs = GraphState(db_path=demo_db)
        events = gs.read_recent_events(limit=30)
        html = render_event_list(events)
        assert "HumanChat" in html
        assert "AgentComplete" in html
        gs.close()


class TestGoldenPathBeat6to8:
    """Beats 6-8: Edit triggers cascade — the core demo sequence.

    Beat 6: User edits load_config (adds timeout param).
    Beat 7: load_config agent detects change, messages test agent.
    Beat 8: test agent reads source, proposes rewrite.
    """

    @pytest.mark.asyncio
    async def test_full_cascade_with_mock_llm(self) -> None:
        """Verify MockLLM produces the complete golden path cascade."""
        mock = MockLLMClient()

        # Beat 6-7: Source agent detects parameter change
        r1 = await mock.chat(
            [
                {
                    "role": "system",
                    "content": "You are the agent for `load_config`. node_type: function",
                },
                {
                    "role": "user",
                    "content": "The parameter `timeout` was added to load_config.",
                },
            ]
        )
        assert r1.tool_calls[0].name == "message_node"
        assert "test_load_yaml" in r1.tool_calls[0].arguments["target_id"]

        # Beat 8 round 0: Test agent receives message, reads source
        r2 = await mock.chat(
            [
                {
                    "role": "system",
                    "content": "You are the agent for `test_load_yaml`. node_type: function\nYou are a test function agent.",
                },
                {
                    "role": "user",
                    "content": "[From load_config]: timeout param was added",
                },
            ]
        )
        assert r2.tool_calls[0].name == "read_node"

        # Beat 8 round 1: Test agent proposes rewrite
        r3 = await mock.chat(
            [
                {
                    "role": "system",
                    "content": "You are the agent for `test_load_yaml`. node_type: function\nYou are a test function agent.",
                },
                {
                    "role": "user",
                    "content": "[From load_config]: timeout param was added",
                },
                {"role": "assistant", "content": r2.content or ""},
                {
                    "role": "user",
                    "content": "[Tool result for read_node]: def load_config(path, timeout=30): ...",
                },
            ]
        )
        assert r3.tool_calls[0].name == "rewrite_self"
        assert "timeout" in r3.tool_calls[0].arguments["new_source"]

    def test_cascade_events_in_db_and_views(self, demo_db: str) -> None:
        """Simulate the cascade events being written to DB, verify rendering."""
        now = time.time()
        conn = sqlite3.connect(demo_db)

        # Beat 6: Content changed
        conn.execute("UPDATE nodes SET status = 'running' WHERE id = 'load_config'")
        conn.execute(
            "INSERT INTO events VALUES (?,?,?,?,?,?)",
            (
                "cascade_1",
                "ContentChanged",
                now,
                "c_edit",
                "load_config",
                json.dumps({"message": "timeout parameter added"}),
            ),
        )
        conn.execute(
            "INSERT INTO events VALUES (?,?,?,?,?,?)",
            (
                "cascade_2",
                "AgentStart",
                now + 0.1,
                "c_edit",
                "load_config",
                json.dumps({"message": "Analyzing change"}),
            ),
        )

        # Beat 7: Agent thinks, sends message
        conn.execute(
            "INSERT INTO events VALUES (?,?,?,?,?,?)",
            (
                "cascade_3",
                "ModelRequest",
                now + 0.2,
                "c_edit",
                "load_config",
                json.dumps({"message": "Requesting analysis"}),
            ),
        )
        conn.execute(
            "INSERT INTO events VALUES (?,?,?,?,?,?)",
            (
                "cascade_4",
                "ModelResponse",
                now + 0.3,
                "c_edit",
                "load_config",
                json.dumps({"content": "Detected timeout parameter change"}),
            ),
        )
        conn.execute(
            "INSERT INTO events VALUES (?,?,?,?,?,?)",
            (
                "cascade_5",
                "AgentMessage",
                now + 0.4,
                "c_edit",
                "test_load_yaml",
                json.dumps({"message": "Update tests for timeout"}),
            ),
        )
        conn.execute("UPDATE nodes SET status = 'idle' WHERE id = 'load_config'")

        # Beat 8: Test agent runs
        conn.execute("UPDATE nodes SET status = 'running' WHERE id = 'test_load_yaml'")
        conn.execute(
            "INSERT INTO events VALUES (?,?,?,?,?,?)",
            (
                "cascade_6",
                "AgentStart",
                now + 0.5,
                "c_cascade",
                "test_load_yaml",
                json.dumps({"message": "Test agent started"}),
            ),
        )

        # Proposal created
        conn.execute(
            "INSERT INTO proposals VALUES (?,?,?,?,?,?,?,?)",
            (
                "p_cascade",
                "test_load_yaml",
                "def test_load_yaml(): ...",
                "def test_load_yaml():\n    # with timeout\n    ...",
                "- old\n+ new with timeout",
                "pending",
                now + 1.0,
                "tests/test_loader.py",
            ),
        )
        conn.execute(
            "INSERT INTO events VALUES (?,?,?,?,?,?)",
            (
                "cascade_7",
                "RewriteProposal",
                now + 1.0,
                "c_cascade",
                "test_load_yaml",
                json.dumps({"message": "Proposed test update"}),
            ),
        )

        conn.commit()
        conn.close()

        gs = GraphState(db_path=demo_db)

        # Verify snapshot reflects cascade state
        snapshot = gs.read_snapshot()
        test_node = next(
            n for n in snapshot.nodes if n.get("remora_id") == "test_load_yaml"
        )
        assert test_node["status"] == "running"

        # Verify event stream shows cascade
        events = gs.read_recent_events(limit=30)
        html = render_event_list(events)
        assert "ContentChanged" in html
        assert "AgentStart" in html
        assert "ModelRequest" in html
        assert "ModelResponse" in html
        assert "AgentMessage" in html
        assert "RewriteProposal" in html

        # Verify sidebar shows proposal
        proposals = gs.read_proposals_for_agent("test_load_yaml")
        assert len(proposals) == 1
        assert "timeout" in proposals[0]["new_source"]

        sidebar_html = render_sidebar_content(
            gs.read_node("test_load_yaml"),
            gs.read_events_for_agent("test_load_yaml"),
            proposals,
            gs.read_edges_for_node("test_load_yaml"),
        )
        assert "Approve" in sidebar_html
        assert "Reject" in sidebar_html
        assert "timeout" in sidebar_html

        gs.close()

    def test_bridge_detects_cascade_events(self, demo_db: str) -> None:
        """Bridge detects status changes and new events during cascade."""
        gs = GraphState(db_path=demo_db)
        layout = ForceLayout(width=900, height=600)
        relay = FakeRelay()
        bridge = DBBridge(state=gs, layout=layout, relay=relay)

        asyncio.run(bridge._poll_once())
        relay.clear()

        # Simulate beat 6: status change + new event
        conn = sqlite3.connect(demo_db)
        conn.execute("UPDATE nodes SET status = 'running' WHERE id = 'load_config'")
        conn.execute(
            "INSERT INTO events VALUES (?,?,?,?,?,?)",
            (
                "cascade_b_1",
                "ContentChanged",
                time.time(),
                "c_b",
                "load_config",
                json.dumps({"message": "change"}),
            ),
        )
        conn.commit()
        conn.close()

        subjects = asyncio.run(bridge._poll_once())
        assert "graph.status" in subjects
        assert "graph.events" in subjects
        gs.close()


class TestGoldenPathBeat9:
    """Beat 9: Approve/Reject from browser."""

    def test_approve_command(self, demo_db: str) -> None:
        gs = GraphState(db_path=demo_db)
        cmd_id = gs.push_command("approve", "test_load_yaml", {"proposal_id": "p1"})
        assert cmd_id > 0
        gs.close()

    def test_reject_command(self, demo_db: str) -> None:
        gs = GraphState(db_path=demo_db)
        cmd_id = gs.push_command(
            "reject", "test_load_yaml", {"proposal_id": "p1", "feedback": "needs more"}
        )
        assert cmd_id > 0
        gs.close()


class TestDemoProjectFiles:
    """Verify all T1/T2 demo project files exist."""

    def test_configlib_source_files(self) -> None:
        base = (
            Path(__file__).parent.parent
            / "remora_demo"
            / "project"
            / "src"
            / "configlib"
        )
        assert (base / "__init__.py").exists()
        assert (base / "loader.py").exists()
        assert (base / "schema.py").exists()
        assert (base / "merge.py").exists()

    def test_configlib_test_files(self) -> None:
        base = Path(__file__).parent.parent / "remora_demo" / "project" / "tests"
        assert (base / "test_loader.py").exists()
        assert (base / "test_merge.py").exists()

    def test_remora_config(self) -> None:
        p = Path(__file__).parent.parent / "remora_demo" / "project" / "remora.yaml"
        assert p.exists()
        content = p.read_text()
        assert "mock" in content

    def test_extension_models(self) -> None:
        base = (
            Path(__file__).parent.parent
            / "remora_demo"
            / "project"
            / ".remora"
            / "models"
        )
        assert (base / "test_function.py").exists()
        assert (base / "package_init.py").exists()

    def test_nvim_config(self) -> None:
        p = Path(__file__).parent.parent / "remora_demo" / "project" / ".nvim.lua"
        assert p.exists()
        content = p.read_text()
        assert "remora" in content.lower()
