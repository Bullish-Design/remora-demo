"""State model for the refactor swarm demo UI."""

from __future__ import annotations

import time
from collections import deque
import asyncio
import json
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class GraphNode:
    id: str
    name: str
    node_type: str
    file_path: str
    upstream: list[str]
    downstream: list[str]
    priority: int
    lane: int = 0


@dataclass
class EventItem:
    event_type: str
    message: str
    payload: str
    timestamp: float
    agent_id: str | None = None
    graph_id: str | None = None


@dataclass
class ResultItem:
    agent_id: str
    agent_name: str
    summary: str
    timestamp: float


@dataclass
class BlockedRequest:
    request_id: str
    agent_id: str
    question: str
    options: list[str]
    timestamp: float


@dataclass
class RefactorState:
    target_path: str = "backend"
    bundle_filter: str = ""
    backend_connected: bool = False
    event_stream_active: bool = False
    planning: bool = False
    running: bool = False
    error_message: str | None = None

    plan_target: str | None = None
    plan_bundle: str | None = None
    graph_id: str | None = None
    plan_nodes: list[GraphNode] = field(default_factory=list)
    node_status: dict[str, str] = field(default_factory=dict)
    events: deque[EventItem] = field(default_factory=lambda: deque(maxlen=120))
    results: deque[ResultItem] = field(default_factory=lambda: deque(maxlen=60))
    blocked: dict[str, BlockedRequest] = field(default_factory=dict)
    available_bundles: list[str] = field(default_factory=list)
    event_stream_task: asyncio.Task | None = field(default=None, repr=False)
    node_labels: dict[str, str] = field(default_factory=dict)

    def reset_graph(self) -> None:
        self.plan_nodes.clear()
        self.node_status.clear()
        self.events.clear()
        self.results.clear()
        self.blocked.clear()
        self.graph_id = None
        self.running = False
        self.planning = False

    def set_plan(self, nodes: list[dict], *, target: str, bundle: str | None) -> None:
        parsed: list[GraphNode] = []
        labels: dict[str, str] = {}
        for node in nodes:
            raw_path = node.get("file_path", "")
            file_path = _normalize_path(raw_path)
            name = str(node.get("name", ""))
            node_type = str(node.get("node_type", ""))
            label = _format_node_label(name, node_type, file_path, node.get("id", ""))
            parsed.append(
                GraphNode(
                    id=str(node["id"]),
                    name=name,
                    node_type=node_type,
                    file_path=file_path,
                    upstream=[str(item) for item in (node.get("upstream") or [])],
                    downstream=[str(item) for item in (node.get("downstream") or [])],
                    priority=int(node.get("priority") or 0),
                )
            )
            labels[str(node["id"])] = label
        self.plan_nodes = _assign_lanes(parsed)
        self.node_status = {node.id: "idle" for node in self.plan_nodes}
        self.plan_target = target
        self.plan_bundle = bundle
        self.node_labels = labels

    def mark_all(self, status: str) -> None:
        for node_id in self.node_status:
            self.node_status[node_id] = status

    def update_status(self, agent_id: str, status: str) -> None:
        if agent_id in self.node_status:
            self.node_status[agent_id] = status

    def add_event(
        self,
        event_type: str,
        message: str,
        timestamp: float | None = None,
        *,
        agent_id: str | None = None,
        graph_id: str | None = None,
        payload: object | None = None,
    ) -> None:
        self.events.appendleft(
            EventItem(
                event_type=event_type,
                message=message,
                payload=_format_payload(payload),
                timestamp=timestamp or time.time(),
                agent_id=agent_id,
                graph_id=graph_id,
            )
        )

    def add_result(self, agent_id: str, summary: str, timestamp: float | None = None) -> None:
        label = self.node_labels.get(agent_id, agent_id)
        self.results.appendleft(
            ResultItem(
                agent_id=agent_id,
                agent_name=label,
                summary=summary,
                timestamp=timestamp or time.time(),
            )
        )

    def add_blocked(self, blocked: BlockedRequest) -> None:
        self.blocked[blocked.request_id] = blocked

    def clear_blocked(self, request_id: str) -> None:
        self.blocked.pop(request_id, None)

    @property
    def progress(self) -> dict[str, int]:
        total = len(self.node_status)
        completed = sum(1 for status in self.node_status.values() if status == "completed")
        failed = sum(1 for status in self.node_status.values() if status == "failed")
        running = sum(1 for status in self.node_status.values() if status == "running")
        skipped = sum(1 for status in self.node_status.values() if status == "skipped")
        return {
            "total": total,
            "completed": completed,
            "failed": failed,
            "running": running,
            "skipped": skipped,
        }


def _assign_lanes(nodes: list[GraphNode]) -> list[GraphNode]:
    node_by_id = {node.id: node for node in nodes}
    in_degree: dict[str, int] = {}
    upstream_map: dict[str, list[str]] = {}
    for node in nodes:
        upstream = [u for u in node.upstream if u in node_by_id]
        in_degree[node.id] = len(upstream)
        upstream_map[node.id] = upstream

    queue = [node_id for node_id, count in in_degree.items() if count == 0]
    queue.sort()
    lane_map: dict[str, int] = {}

    while queue:
        current = queue.pop(0)
        upstream = upstream_map.get(current, [])
        lane_map[current] = 0
        if upstream:
            lane_map[current] = max(lane_map.get(u, 0) for u in upstream) + 1

        for node in nodes:
            if current in node.upstream:
                in_degree[node.id] -= 1
                if in_degree[node.id] == 0:
                    queue.append(node.id)
                    queue.sort()

    for node in nodes:
        node.lane = lane_map.get(node.id, 0)

    return sorted(nodes, key=lambda n: (n.lane, -n.priority, n.name))


def _normalize_path(value: object) -> str:
    if isinstance(value, (list, tuple)):
        parts = [str(part).strip("/") for part in value if part]
        return "/".join(parts)
    if value is None:
        return ""
    return str(value)


def _format_node_label(name: str, node_type: str, file_path: str, fallback: object) -> str:
    if file_path and (node_type == "file" or name.strip() == "unknown"):
        return Path(file_path).name or name or str(fallback)
    if name:
        return name
    return str(fallback)


def _format_payload(payload: object | None) -> str:
    if payload is None:
        return ""
    try:
        text = json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2)
    except Exception:
        text = str(payload)
    return _truncate_text(text, 1200)


def _truncate_text(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."
