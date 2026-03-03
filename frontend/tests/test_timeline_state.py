"""Tests for timeline state reader — queries events grouped for swimlane rendering."""

from __future__ import annotations

import sqlite3

from timeline.state import TimelineData, read_timeline_data


def _create_db() -> sqlite3.Connection:
    """Create an in-memory DB with the EventStore schema."""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript("""
        CREATE TABLE events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            graph_id TEXT NOT NULL DEFAULT 'test',
            event_type TEXT NOT NULL,
            payload TEXT NOT NULL DEFAULT '{}',
            timestamp REAL NOT NULL DEFAULT 0,
            created_at REAL NOT NULL DEFAULT 0,
            from_agent TEXT,
            to_agent TEXT,
            correlation_id TEXT,
            tags TEXT
        );
    """)
    conn.commit()
    return conn


def _insert_event(
    conn: sqlite3.Connection,
    *,
    event_type: str = "Test",
    timestamp: float = 1.0,
    from_agent: str | None = None,
    to_agent: str | None = None,
    correlation_id: str | None = None,
    payload: str = "{}",
) -> int:
    """Insert an event and return its id."""
    cursor = conn.execute(
        "INSERT INTO events (graph_id, event_type, payload, timestamp, created_at, from_agent, to_agent, correlation_id) "
        "VALUES ('test', ?, ?, ?, ?, ?, ?, ?)",
        (event_type, payload, timestamp, timestamp, from_agent, to_agent, correlation_id),
    )
    conn.commit()
    return cursor.lastrowid  # type: ignore[return-value]


# ── Empty DB ──


class TestTimelineDataEmpty:
    def test_empty_db_returns_empty_data(self) -> None:
        conn = _create_db()
        result = read_timeline_data(conn)
        assert isinstance(result, TimelineData)
        assert result.agents == []
        assert result.events == []
        assert result.correlation_groups == {}
        assert result.time_range == (0.0, 0.0)

    def test_empty_db_with_filters(self) -> None:
        conn = _create_db()
        result = read_timeline_data(conn, since=1.0, until=5.0, agent_ids=["a"])
        assert result.agents == []
        assert result.events == []


# ── Agent ordering ──


class TestTimelineAgentOrdering:
    def test_agents_ordered_by_first_event_time(self) -> None:
        conn = _create_db()
        _insert_event(conn, from_agent="beta", timestamp=1.0)
        _insert_event(conn, from_agent="alpha", timestamp=2.0)
        _insert_event(conn, from_agent="gamma", timestamp=0.5)
        result = read_timeline_data(conn)
        assert result.agents == ["gamma", "beta", "alpha"]

    def test_agents_include_to_agent(self) -> None:
        """Agents appearing only as to_agent should still show up."""
        conn = _create_db()
        _insert_event(conn, from_agent="sender", to_agent="receiver", timestamp=1.0)
        result = read_timeline_data(conn)
        # sender appears first (from timestamp 1.0), receiver also at 1.0 but as to_agent
        assert "sender" in result.agents
        assert "receiver" in result.agents

    def test_null_agents_excluded(self) -> None:
        """Events with no from_agent and no to_agent should not produce a None agent."""
        conn = _create_db()
        _insert_event(conn, timestamp=1.0)  # no agent
        _insert_event(conn, from_agent="real", timestamp=2.0)
        result = read_timeline_data(conn)
        assert result.agents == ["real"]
        assert None not in result.agents


# ── Flat event list ──


class TestTimelineEventList:
    def test_events_chronological_ascending(self) -> None:
        conn = _create_db()
        _insert_event(conn, from_agent="a", timestamp=3.0, event_type="C")
        _insert_event(conn, from_agent="a", timestamp=1.0, event_type="A")
        _insert_event(conn, from_agent="b", timestamp=2.0, event_type="B")
        result = read_timeline_data(conn)
        types = [e["event_type"] for e in result.events]
        assert types == ["A", "B", "C"]

    def test_event_fields_present(self) -> None:
        conn = _create_db()
        _insert_event(
            conn,
            from_agent="agent_x",
            to_agent="agent_y",
            timestamp=1.5,
            event_type="AgentStart",
            correlation_id="corr-1",
            payload='{"message": "hello"}',
        )
        result = read_timeline_data(conn)
        assert len(result.events) == 1
        ev = result.events[0]
        assert ev["event_id"] == 1
        assert ev["event_type"] == "AgentStart"
        assert ev["from_agent"] == "agent_x"
        assert ev["to_agent"] == "agent_y"
        assert ev["timestamp"] == 1.5
        assert ev["correlation_id"] == "corr-1"
        assert ev["payload"] == '{"message": "hello"}'


# ── Correlation groups ──


class TestTimelineCorrelationGroups:
    def test_events_grouped_by_correlation_id(self) -> None:
        conn = _create_db()
        id1 = _insert_event(conn, from_agent="a", timestamp=1.0, correlation_id="c1")
        id2 = _insert_event(conn, from_agent="b", timestamp=2.0, correlation_id="c1")
        id3 = _insert_event(conn, from_agent="a", timestamp=3.0, correlation_id="c2")
        result = read_timeline_data(conn)
        assert "c1" in result.correlation_groups
        assert "c2" in result.correlation_groups
        assert result.correlation_groups["c1"] == [id1, id2]
        assert result.correlation_groups["c2"] == [id3]

    def test_null_correlation_excluded(self) -> None:
        conn = _create_db()
        _insert_event(conn, from_agent="a", timestamp=1.0)  # no correlation_id
        _insert_event(conn, from_agent="b", timestamp=2.0, correlation_id="c1")
        result = read_timeline_data(conn)
        assert None not in result.correlation_groups
        assert len(result.correlation_groups) == 1


# ── Time range ──


class TestTimelineTimeRange:
    def test_time_range_min_max(self) -> None:
        conn = _create_db()
        _insert_event(conn, from_agent="a", timestamp=5.0)
        _insert_event(conn, from_agent="b", timestamp=2.0)
        _insert_event(conn, from_agent="c", timestamp=8.0)
        result = read_timeline_data(conn)
        assert result.time_range == (2.0, 8.0)

    def test_single_event_time_range(self) -> None:
        conn = _create_db()
        _insert_event(conn, from_agent="a", timestamp=3.0)
        result = read_timeline_data(conn)
        assert result.time_range == (3.0, 3.0)


# ── Filtering ──


class TestTimelineFiltering:
    def test_filter_since(self) -> None:
        conn = _create_db()
        _insert_event(conn, from_agent="a", timestamp=1.0, event_type="Old")
        _insert_event(conn, from_agent="a", timestamp=5.0, event_type="New")
        result = read_timeline_data(conn, since=3.0)
        assert len(result.events) == 1
        assert result.events[0]["event_type"] == "New"

    def test_filter_until(self) -> None:
        conn = _create_db()
        _insert_event(conn, from_agent="a", timestamp=1.0, event_type="Old")
        _insert_event(conn, from_agent="a", timestamp=5.0, event_type="New")
        result = read_timeline_data(conn, until=3.0)
        assert len(result.events) == 1
        assert result.events[0]["event_type"] == "Old"

    def test_filter_since_and_until(self) -> None:
        conn = _create_db()
        _insert_event(conn, from_agent="a", timestamp=1.0)
        _insert_event(conn, from_agent="a", timestamp=3.0, event_type="Mid")
        _insert_event(conn, from_agent="a", timestamp=5.0)
        result = read_timeline_data(conn, since=2.0, until=4.0)
        assert len(result.events) == 1
        assert result.events[0]["event_type"] == "Mid"

    def test_filter_by_agent_ids(self) -> None:
        conn = _create_db()
        _insert_event(conn, from_agent="a", timestamp=1.0, event_type="A")
        _insert_event(conn, from_agent="b", timestamp=2.0, event_type="B")
        _insert_event(conn, from_agent="c", timestamp=3.0, event_type="C")
        result = read_timeline_data(conn, agent_ids=["a", "c"])
        types = [e["event_type"] for e in result.events]
        assert "A" in types
        assert "C" in types
        assert "B" not in types

    def test_filter_by_agent_ids_includes_to_agent(self) -> None:
        """Filtering by agent_ids should match from_agent OR to_agent."""
        conn = _create_db()
        _insert_event(conn, from_agent="a", to_agent="b", timestamp=1.0, event_type="AB")
        _insert_event(conn, from_agent="c", timestamp=2.0, event_type="C")
        result = read_timeline_data(conn, agent_ids=["b"])
        assert len(result.events) == 1
        assert result.events[0]["event_type"] == "AB"

    def test_filter_by_correlation_id(self) -> None:
        conn = _create_db()
        _insert_event(conn, from_agent="a", timestamp=1.0, correlation_id="c1", event_type="Yes")
        _insert_event(conn, from_agent="a", timestamp=2.0, correlation_id="c2", event_type="No")
        result = read_timeline_data(conn, correlation_id="c1")
        assert len(result.events) == 1
        assert result.events[0]["event_type"] == "Yes"

    def test_limit(self) -> None:
        conn = _create_db()
        for i in range(10):
            _insert_event(conn, from_agent="a", timestamp=float(i))
        result = read_timeline_data(conn, limit=5)
        assert len(result.events) == 5
        # Should be the 5 most recent, returned in ascending order
        timestamps = [e["timestamp"] for e in result.events]
        assert timestamps == [5.0, 6.0, 7.0, 8.0, 9.0]

    def test_combined_filters(self) -> None:
        conn = _create_db()
        _insert_event(conn, from_agent="a", timestamp=1.0, correlation_id="c1", event_type="Match")
        _insert_event(conn, from_agent="b", timestamp=2.0, correlation_id="c1", event_type="WrongAgent")
        _insert_event(conn, from_agent="a", timestamp=3.0, correlation_id="c2", event_type="WrongCorr")
        result = read_timeline_data(conn, agent_ids=["a"], correlation_id="c1")
        assert len(result.events) == 1
        assert result.events[0]["event_type"] == "Match"
