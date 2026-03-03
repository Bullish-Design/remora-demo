"""Timeline state reader — queries events grouped for swimlane rendering.

Takes a raw SQLite connection, making it testable with in-memory SQLite.
Returns a TimelineData dataclass with agents, events, correlation groups, and time range.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field


@dataclass
class TimelineData:
    """Immutable result of a timeline query."""

    agents: list[str] = field(default_factory=list)
    events: list[dict] = field(default_factory=list)
    correlation_groups: dict[str, list[int]] = field(default_factory=dict)
    time_range: tuple[float, float] = (0.0, 0.0)


def read_timeline_data(
    conn: sqlite3.Connection,
    *,
    since: float | None = None,
    until: float | None = None,
    agent_ids: list[str] | None = None,
    correlation_id: str | None = None,
    limit: int | None = None,
) -> TimelineData:
    """Read events from SQLite grouped for swimlane rendering.

    Args:
        conn: SQLite connection (can be in-memory for testing).
        since: Only events with timestamp >= since.
        until: Only events with timestamp <= until.
        agent_ids: Only events involving these agents (from_agent or to_agent).
        correlation_id: Only events with this correlation_id.
        limit: Maximum number of events (most recent N, returned in ascending order).

    Returns:
        TimelineData with agents ordered by first event time, flat chronological
        event list, correlation groups, and time range.
    """
    # Build the WHERE clause dynamically
    conditions: list[str] = []
    params: list[object] = []

    if since is not None:
        conditions.append("timestamp >= ?")
        params.append(since)

    if until is not None:
        conditions.append("timestamp <= ?")
        params.append(until)

    if correlation_id is not None:
        conditions.append("correlation_id = ?")
        params.append(correlation_id)

    if agent_ids is not None:
        placeholders = ",".join("?" for _ in agent_ids)
        conditions.append(f"(from_agent IN ({placeholders}) OR to_agent IN ({placeholders}))")
        params.extend(agent_ids)
        params.extend(agent_ids)

    where = ""
    if conditions:
        where = "WHERE " + " AND ".join(conditions)

    # If limit is set, we want the N most recent events but returned in ascending order.
    # Use a subquery to get the most recent N, then order ascending.
    if limit is not None:
        sql = f"""
            SELECT * FROM (
                SELECT id as event_id, event_type, timestamp, from_agent, to_agent,
                       correlation_id, payload
                FROM events
                {where}
                ORDER BY timestamp DESC
                LIMIT ?
            ) sub
            ORDER BY timestamp ASC
        """
        params.append(limit)
    else:
        sql = f"""
            SELECT id as event_id, event_type, timestamp, from_agent, to_agent,
                   correlation_id, payload
            FROM events
            {where}
            ORDER BY timestamp ASC
        """

    old_row_factory = conn.row_factory
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.execute(sql, params)
        rows = [dict(row) for row in cursor.fetchall()]
    finally:
        conn.row_factory = old_row_factory

    if not rows:
        return TimelineData()

    # Build agent list ordered by first event time
    agent_first_time: dict[str, float] = {}
    for ev in rows:
        ts = ev["timestamp"]
        for agent in (ev["from_agent"], ev["to_agent"]):
            if agent is not None and agent not in agent_first_time:
                agent_first_time[agent] = ts
    agents = sorted(agent_first_time.keys(), key=lambda a: agent_first_time[a])

    # Build correlation groups
    correlation_groups: dict[str, list[int]] = {}
    for ev in rows:
        cid = ev["correlation_id"]
        if cid is not None:
            correlation_groups.setdefault(cid, []).append(ev["event_id"])

    # Time range
    time_range = (rows[0]["timestamp"], rows[-1]["timestamp"])

    return TimelineData(
        agents=agents,
        events=rows,
        correlation_groups=correlation_groups,
        time_range=time_range,
    )
