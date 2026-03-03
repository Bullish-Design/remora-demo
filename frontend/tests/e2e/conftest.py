"""E2E test fixtures — server lifecycle, DB seeding, Playwright browser config.

Provides:
- demo_server: Starts the graph viewer as a subprocess with a fresh DB
- db_path: Path to the test DB (from demo_server) for direct mutations
- browser/context/page: Playwright fixtures (via pytest-playwright or manual)

The server is started per-test with a short poll interval (50ms) for fast feedback.
"""

from __future__ import annotations

import json
import os
import socket
import sqlite3
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import pytest


# ── DB creation (reused from test_golden_path.py) ──


def _create_demo_db(db_path: str) -> None:
    """Create the full configlib demo database matching the golden path fixture."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")

    conn.executescript("""
        CREATE TABLE nodes (
            node_id         TEXT PRIMARY KEY,
            node_type       TEXT NOT NULL,
            name            TEXT NOT NULL,
            full_name       TEXT NOT NULL,
            file_path       TEXT NOT NULL,
            start_line      INTEGER NOT NULL,
            end_line        INTEGER NOT NULL,
            start_byte      INTEGER NOT NULL DEFAULT 0,
            end_byte        INTEGER NOT NULL DEFAULT 0,
            source_code     TEXT NOT NULL,
            source_hash     TEXT NOT NULL,
            parent_id       TEXT,
            caller_ids      TEXT NOT NULL DEFAULT '[]',
            callee_ids      TEXT NOT NULL DEFAULT '[]',
            status          TEXT NOT NULL DEFAULT 'idle',
            last_trigger_event TEXT NOT NULL DEFAULT '',
            last_completed_at  REAL,
            extension_name  TEXT,
            custom_system_prompt TEXT NOT NULL DEFAULT '',
            mounted_workspaces TEXT NOT NULL DEFAULT '[]',
            extra_tools     TEXT NOT NULL DEFAULT '[]',
            extra_subscriptions TEXT NOT NULL DEFAULT '[]'
        );

        CREATE TABLE edges (
            from_id TEXT NOT NULL,
            to_id TEXT NOT NULL,
            edge_type TEXT NOT NULL,
            PRIMARY KEY (from_id, to_id, edge_type)
        );

        CREATE TABLE events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            graph_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            payload TEXT NOT NULL,
            timestamp REAL NOT NULL,
            created_at REAL NOT NULL,
            from_agent TEXT,
            to_agent TEXT,
            correlation_id TEXT,
            tags TEXT
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

    nodes = [
        (
            "loader.py",
            "file",
            "loader.py",
            "src/configlib/loader.py",
            "src/configlib/loader.py",
            1,
            42,
            "",
            "hash_loader",
            "idle",
        ),
        (
            "load_config",
            "function",
            "load_config",
            "src.configlib.loader.load_config",
            "src/configlib/loader.py",
            10,
            25,
            "def load_config(path): ...",
            "hash_load_config",
            "idle",
        ),
        (
            "detect_format",
            "function",
            "detect_format",
            "src.configlib.loader.detect_format",
            "src/configlib/loader.py",
            28,
            35,
            "def detect_format(path): ...",
            "hash_detect_format",
            "idle",
        ),
        (
            "load_yaml",
            "function",
            "load_yaml",
            "src.configlib.loader.load_yaml",
            "src/configlib/loader.py",
            38,
            42,
            "def load_yaml(path): ...",
            "hash_load_yaml",
            "idle",
        ),
        (
            "schema.py",
            "file",
            "schema.py",
            "src/configlib/schema.py",
            "src/configlib/schema.py",
            1,
            24,
            "",
            "hash_schema",
            "idle",
        ),
        (
            "validate",
            "function",
            "validate",
            "src.configlib.schema.validate",
            "src/configlib/schema.py",
            8,
            20,
            "def validate(data, schema): ...",
            "hash_validate",
            "idle",
        ),
        (
            "merge.py",
            "file",
            "merge.py",
            "src/configlib/merge.py",
            "src/configlib/merge.py",
            1,
            26,
            "",
            "hash_merge",
            "idle",
        ),
        (
            "deep_merge",
            "function",
            "deep_merge",
            "src.configlib.merge.deep_merge",
            "src/configlib/merge.py",
            5,
            18,
            "def deep_merge(base, override): ...",
            "hash_deep_merge",
            "idle",
        ),
        (
            "test_loader.py",
            "file",
            "test_loader.py",
            "tests/test_loader.py",
            "tests/test_loader.py",
            1,
            35,
            "",
            "hash_test_loader",
            "idle",
        ),
        (
            "test_load_yaml",
            "function",
            "test_load_yaml",
            "tests.test_loader.test_load_yaml",
            "tests/test_loader.py",
            10,
            20,
            "def test_load_yaml(): ...",
            "hash_test_load_yaml",
            "idle",
        ),
        (
            "test_load_json",
            "function",
            "test_load_json",
            "tests.test_loader.test_load_json",
            "tests/test_loader.py",
            23,
            33,
            "def test_load_json(): ...",
            "hash_test_load_json",
            "idle",
        ),
        (
            "test_merge.py",
            "file",
            "test_merge.py",
            "tests/test_merge.py",
            "tests/test_merge.py",
            1,
            18,
            "",
            "hash_test_merge",
            "idle",
        ),
        (
            "test_deep_merge",
            "function",
            "test_deep_merge",
            "tests.test_merge.test_deep_merge",
            "tests/test_merge.py",
            5,
            12,
            "def test_deep_merge(): ...",
            "hash_test_deep_merge",
            "idle",
        ),
    ]
    for nid, ntype, name, full_name, fpath, sl, el, src, shash, status in nodes:
        conn.execute(
            "INSERT INTO nodes (node_id, node_type, name, full_name, file_path, start_line, end_line, source_code, source_hash, status) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (nid, ntype, name, full_name, fpath, sl, el, src, shash, status),
        )

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

    for i, (nid, *_rest) in enumerate(nodes):
        conn.execute(
            "INSERT INTO events (graph_id, event_type, payload, timestamp, created_at, from_agent, correlation_id) VALUES (?,?,?,?,?,?,?)",
            (
                "boot",
                "NodeDiscovered",
                json.dumps({"message": f"Discovered {nid}"}),
                now - 60 + i,
                now - 60 + i,
                nid,
                "boot",
            ),
        )

    conn.commit()
    conn.close()


# ── DB mutation helpers ──


def add_event(db_path: str, event_type: str, from_agent: str, **kwargs) -> int:
    """Insert an event into the events table. Returns the event ID."""
    conn = sqlite3.connect(db_path)
    now = time.time()
    cursor = conn.execute(
        "INSERT INTO events (graph_id, event_type, payload, timestamp, created_at, from_agent, to_agent, correlation_id) VALUES (?,?,?,?,?,?,?,?)",
        (
            kwargs.get("graph_id", "boot"),
            event_type,
            json.dumps(kwargs.get("payload", {"message": f"{event_type} event"})),
            kwargs.get("timestamp", now),
            kwargs.get("created_at", now),
            from_agent,
            kwargs.get("to_agent"),
            kwargs.get("correlation_id"),
        ),
    )
    event_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return event_id


def change_status(db_path: str, node_id: str, new_status: str) -> None:
    """Update a node's status."""
    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE nodes SET status = ? WHERE node_id = ?", (new_status, node_id))
    conn.commit()
    conn.close()


def set_cursor_focus(db_path: str, agent_id: str, file_path: str, line: int) -> None:
    """Insert or update the cursor_focus table."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT OR REPLACE INTO cursor_focus (id, agent_id, file_path, line, timestamp) VALUES (1, ?, ?, ?, ?)",
        (agent_id, file_path, line, time.time()),
    )
    conn.commit()
    conn.close()


def add_node(db_path: str, node_id: str, **kwargs) -> None:
    """Insert a new node into the DB."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO nodes (node_id, node_type, name, full_name, file_path, start_line, end_line, source_code, source_hash, status) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (
            node_id,
            kwargs.get("node_type", "function"),
            kwargs.get("name", node_id),
            kwargs.get("full_name", node_id),
            kwargs.get("file_path", "src/new.py"),
            kwargs.get("start_line", 1),
            kwargs.get("end_line", 10),
            kwargs.get("source_code", f"def {node_id}(): ..."),
            kwargs.get("source_hash", f"hash_{node_id}"),
            kwargs.get("status", "idle"),
        ),
    )
    conn.commit()
    conn.close()


def add_proposal(db_path: str, agent_id: str, old_source: str, new_source: str) -> str:
    """Insert a pending proposal. Returns the proposal_id."""
    import uuid

    proposal_id = f"p_{uuid.uuid4().hex[:8]}"
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO proposals VALUES (?,?,?,?,?,?,?,?)",
        (
            proposal_id,
            agent_id,
            old_source,
            new_source,
            f"- {old_source}\n+ {new_source}",
            "pending",
            time.time(),
            "src/new.py",
        ),
    )
    conn.commit()
    conn.close()
    return proposal_id


# ── Server lifecycle ──


def _find_free_port() -> int:
    """Find a free TCP port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for_server(url: str, timeout: float = 10) -> None:
    """Poll until the server responds to HTTP requests."""
    import urllib.request

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            urllib.request.urlopen(url, timeout=1)
            return
        except Exception:
            time.sleep(0.1)
    raise TimeoutError(f"Server at {url} did not start within {timeout}s")


@dataclass
class DemoServer:
    process: subprocess.Popen
    url: str
    db_path: str
    port: int


@pytest.fixture()
def demo_server(tmp_path):
    """Start the graph viewer server with a fresh demo DB.

    Uses --poll-interval 0.05 for fast SSE update detection in tests.
    """
    db_path = str(tmp_path / "indexer.db")
    _create_demo_db(db_path)

    port = _find_free_port()
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "graph",
            "--db",
            db_path,
            "--port",
            str(port),
            "--poll-interval",
            "0.05",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        _wait_for_server(f"http://127.0.0.1:{port}", timeout=10)
    except Exception:
        proc.terminate()
        proc.wait(timeout=5)
        raise

    yield DemoServer(
        process=proc, url=f"http://127.0.0.1:{port}", db_path=db_path, port=port
    )

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


# ── Playwright browser fixtures ──


def _find_chromium_executable() -> str | None:
    """Find a usable Chromium executable in the nix store or standard locations."""
    # Check PLAYWRIGHT_BROWSERS_PATH first (set by devenv.nix)
    browsers_path = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "")
    if browsers_path:
        # Look for chromium executable in the browsers path
        bp = Path(browsers_path)
        for chromium_dir in sorted(bp.glob("chromium-*"), reverse=True):
            candidate = chromium_dir / "chrome-linux" / "chrome"
            if candidate.exists():
                return str(candidate)

    # Fallback: search nix store for playwright-browsers
    nix_store = Path("/nix/store")
    if nix_store.exists():
        for d in sorted(nix_store.glob("*-playwright-browsers"), reverse=True):
            for chromium_dir in sorted(d.glob("chromium-*"), reverse=True):
                candidate = chromium_dir / "chrome-linux" / "chrome"
                if candidate.exists():
                    return str(candidate)

    return None


@pytest.fixture(scope="session")
def browser_type_launch_args():
    """Provide launch args for Playwright browser, including executable_path if needed."""
    chromium_path = _find_chromium_executable()
    if chromium_path:
        return {"executable_path": chromium_path}
    return {}


SCREENSHOT_DIR = Path(__file__).parent / "screenshots"


@pytest.fixture()
def page(browser_type_launch_args, request):
    """Create a fresh Playwright browser page for each test.

    This manual fixture replaces pytest-playwright's built-in page fixture
    to handle nix-managed chromium executables.

    On test failure, a screenshot is automatically saved to tests/e2e/screenshots/.
    For video recording, use: pytest --video on
    For built-in screenshots, use: pytest --screenshot only-on-failure
    """
    from playwright.sync_api import sync_playwright

    pw = sync_playwright().start()
    try:
        browser = pw.chromium.launch(headless=True, **browser_type_launch_args)
        context = browser.new_context(viewport={"width": 1280, "height": 720})
        pg = context.new_page()
        yield pg

        # Capture screenshot on failure before closing
        # pytest-playwright's pytest_runtest_makereport hook sets rep_call on the item
        if hasattr(request.node, "rep_call") and request.node.rep_call.failed:
            SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
            test_name = request.node.name.replace("/", "_").replace("::", "__")
            screenshot_path = SCREENSHOT_DIR / f"{test_name}.png"
            try:
                pg.screenshot(path=str(screenshot_path), full_page=True)
            except Exception:
                pass  # Page may already be closed

        context.close()
        browser.close()
    finally:
        pw.stop()
