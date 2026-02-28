"""Remora refactor swarm service entrypoint."""

from __future__ import annotations

import asyncio
import logging
import os
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse

from remora.adapters.starlette import create_app
from remora.core.container import RemoraContainer
from remora.core.context import ContextBuilder
from remora.core.executor import GraphExecutor, ResultSummary, extract_output, AgentState
from remora.core.events import AgentStartEvent, AgentCompleteEvent, AgentErrorEvent
from remora.core.discovery import discover
from remora.core.graph import AgentNode, build_graph
from remora.models import PlanRequest, PlanResponse, RunRequest, RunResponse
from remora.service.api import RemoraService
from remora.service.handlers import _build_bundle_mapping, _normalize_target, _record_target
from remora.core.tools.grail import build_virtual_fs, discover_grail_tools
from remora.core.workspace import CairnDataProvider
from remora.utils import truncate
from structured_agents.agent import load_manifest

logger = logging.getLogger(__name__)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _config_path() -> Path:
    return _repo_root() / "backend" / "remora.yaml"


@dataclass(slots=True)
class AgentInboxEvent:
    agent_id: str
    message: str
    timestamp: float = field(default_factory=time.time)
    graph_id: str = ""


class InboxStore:
    def __init__(self) -> None:
        self._messages: dict[str, list[str]] = {}
        self._broadcast: list[str] = []

    def add(self, agent_id: str, message: str) -> None:
        if agent_id in {"*", "all"}:
            self._broadcast.append(message)
            return
        self._messages.setdefault(agent_id, []).append(message)

    def get(self, agent_id: str) -> list[str]:
        return [*self._broadcast, *self._messages.get(agent_id, [])]


class InboxContextBuilder(ContextBuilder):
    def __init__(self, inbox: InboxStore, max_items: int = 5) -> None:
        super().__init__()
        self._inbox = inbox
        self._max_items = max_items

    def build_context_for(self, node) -> str:
        base = super().build_context_for(node)
        messages = self._inbox.get(getattr(node, "node_id", ""))
        if not messages:
            return base
        lines = ["## Inbox Notes"]
        for message in messages[-self._max_items :]:
            lines.append(f"- {message}")
        inbox_section = "\n".join(lines)
        if not base:
            return inbox_section
        return f"{base}\n\n{inbox_section}"


class RefactorGraphExecutor(GraphExecutor):
    def __init__(
        self,
        *,
        config,
        event_bus,
        context_builder,
        project_root,
        common_tools_dir: Path,
    ):
        super().__init__(
            config=config,
            event_bus=event_bus,
            context_builder=context_builder,
            project_root=project_root,
        )
        self._common_tools_dir = common_tools_dir

    def _discover_tools(self, manifest, externals, files_provider):
        tools = discover_grail_tools(
            manifest.agents_dir,
            externals=externals,
            files_provider=files_provider,
        )
        if self._common_tools_dir.exists():
            tools.extend(
                discover_grail_tools(
                    self._common_tools_dir,
                    externals=externals,
                    files_provider=files_provider,
                )
            )
        deduped = {}
        for tool in tools:
            deduped[tool.schema.name] = tool
        return list(deduped.values())

    async def _execute_agent(
        self,
        node: AgentNode,
        state,
        workspace_service,
        semaphore,
    ) -> ResultSummary:
        async with semaphore:
            state.states[node.id] = AgentState.RUNNING

            await self.event_bus.emit(
                AgentStartEvent(
                    graph_id=state.graph_id,
                    agent_id=node.id,
                    node_name=node.name,
                )
            )

            try:
                workspace = await workspace_service.get_agent_workspace(node.id)
                externals = workspace_service.get_externals(node.id, workspace)
                externals = self._build_externals(externals, graph_id=state.graph_id, agent_id=node.id)

                data_provider = CairnDataProvider(workspace, self._path_resolver)
                files = await data_provider.load_files(node.target)

                manifest = load_manifest(node.bundle_path)
                requires_context = getattr(manifest, "requires_context", True)
                prompt = self._build_prompt(node, files, requires_context=requires_context)

                async def files_provider() -> dict[str, str | bytes]:
                    current_files = await data_provider.load_files(node.target)
                    return build_virtual_fs(current_files)

                tools = self._discover_tools(manifest, externals, files_provider)

                model_name = self._resolve_model_name(node.bundle_path, manifest)
                result = await self._run_agent(manifest, prompt, tools, model_name=model_name)
                output = extract_output(result) or ""

                submission_summary = await self._load_submission_summary(workspace, node.id)
                if submission_summary:
                    output = submission_summary

                summary = ResultSummary(
                    agent_id=node.id,
                    success=True,
                    output=truncate(str(output), max_len=self.config.execution.truncation_limit),
                )

                await self.event_bus.emit(
                    AgentCompleteEvent(
                        graph_id=state.graph_id,
                        agent_id=node.id,
                        result_summary=summary.output[:200],
                    )
                )

                return summary

            except Exception as e:
                logger.error("Agent %s failed: %s", node.id, e)

                summary = ResultSummary(
                    agent_id=node.id,
                    success=False,
                    output="",
                    error=str(e),
                )

                await self.event_bus.emit(
                    AgentErrorEvent(
                        graph_id=state.graph_id,
                        agent_id=node.id,
                        error=str(e),
                    )
                )

                return summary


class RefactorService(RemoraService):
    async def plan(self, request: PlanRequest) -> PlanResponse:
        if not request.target_path:
            raise ValueError("target_path is required")

        bundle_mapping = _build_bundle_mapping(self._deps.config)
        target_path = _normalize_target(request.target_path, self._deps.project_root)
        nodes = discover(
            [target_path],
            languages=list(self._deps.config.discovery.languages)
            if self._deps.config.discovery.languages
            else None,
            max_workers=self._deps.config.discovery.max_workers,
        )
        agent_nodes = _build_refactor_graph(nodes, bundle_mapping)

        if request.bundle:
            target_bundle = bundle_mapping.get(request.bundle)
            if target_bundle is None:
                raise ValueError(f"Unknown bundle: {request.bundle}")
            agent_nodes = [node for node in agent_nodes if node.bundle_path == target_bundle]

        return PlanResponse(
            nodes=[_serialize_node(node) for node in agent_nodes],
            bundles={key: str(path) for key, path in bundle_mapping.items()},
        )

    async def run(self, request: RunRequest) -> RunResponse:
        if not request.target_path:
            raise ValueError("target_path is required")

        bundle_mapping = _build_bundle_mapping(self._deps.config)
        target_path = _normalize_target(request.target_path, self._deps.project_root)

        graph_root = target_path if target_path.is_dir() else target_path.parent
        nodes = discover(
            [target_path],
            languages=list(self._deps.config.discovery.languages)
            if self._deps.config.discovery.languages
            else None,
            max_workers=self._deps.config.discovery.max_workers,
        )
        agent_nodes = _build_refactor_graph(nodes, bundle_mapping)

        if request.bundle:
            target_bundle = bundle_mapping.get(request.bundle)
            if target_bundle is None:
                raise ValueError(f"Unknown bundle: {request.bundle}")
            agent_nodes = [node for node in agent_nodes if node.bundle_path == target_bundle]

        graph_id = request.graph_id or uuid.uuid4().hex[:8]
        _record_target(self._deps.projector, target_path, self._deps.project_root)

        task = asyncio.create_task(_execute_graph(graph_id, agent_nodes, graph_root, self._deps))
        self._deps.running_tasks[graph_id] = task

        def _cleanup(_task: asyncio.Task) -> None:
            self._deps.running_tasks.pop(graph_id, None)

        task.add_done_callback(_cleanup)

        return RunResponse(graph_id=graph_id, status="started", node_count=len(agent_nodes))


def build_service() -> tuple[RefactorService, InboxStore]:
    container = RemoraContainer.create(
        config_path=_config_path(),
        project_root=_repo_root(),
    )
    config = container.config
    inbox = InboxStore()

    common_tools_dir = Path(config.bundles.path) / "common_tools"

    def executor_factory(config, event_bus, project_root):
        context_builder = InboxContextBuilder(inbox)
        return RefactorGraphExecutor(
            config=config,
            event_bus=event_bus,
            context_builder=context_builder,
            project_root=project_root,
            common_tools_dir=common_tools_dir,
        )

    service = RefactorService(container=container, executor_factory=executor_factory)
    return service, inbox


service, inbox_store = build_service()
app: Starlette = create_app(service)
_agent_tasks: dict[str, asyncio.Task] = {}


@app.on_event("startup")
async def _log_config() -> None:
    config = service.config_snapshot().to_dict()
    model = config.get("model", {})
    logger.info(
        "Refactor swarm config: base_url=%s default_model=%s",
        model.get("base_url"),
        model.get("default_model"),
    )
    env_overrides = {
        "REMORA_MODEL_BASE_URL": os.environ.get("REMORA_MODEL_BASE_URL"),
        "REMORA_MODEL_DEFAULT": os.environ.get("REMORA_MODEL_DEFAULT"),
        "REMORA_MODEL_API_KEY": os.environ.get("REMORA_MODEL_API_KEY"),
    }
    for key, value in env_overrides.items():
        if value:
            logger.info("Env override %s=%s", key, value)


async def health(_request) -> JSONResponse:
    config = service.config_snapshot().to_dict()
    model = config.get("model", {})
    return JSONResponse(
        {
            "status": "ok",
            "project_root": str(_repo_root()),
            "config_path": str(_config_path()),
            "model_base_url": model.get("base_url"),
            "model_default": model.get("default_model"),
        }
    )


app.add_route("/health", health)


async def agent_message(request: Request) -> JSONResponse:
    try:
        payload = await request.json()
    except Exception:
        payload = {}

    agent_id = str(payload.get("agent_id", "")).strip()
    message = str(payload.get("message", "")).strip()
    if not agent_id:
        return JSONResponse({"error": "agent_id is required"}, status_code=400)
    if not message:
        return JSONResponse({"error": "message is required"}, status_code=400)

    inbox_store.add(agent_id, message)
    await service.event_bus.emit(
        AgentInboxEvent(agent_id=agent_id, message=message)
    )
    return JSONResponse({"status": "ok", "agent_id": agent_id})


app.add_route("/agent-message", agent_message, methods=["POST"])


async def agent_ask(request: Request) -> JSONResponse:
    try:
        payload = await request.json()
    except Exception:
        payload = {}

    agent_id = str(payload.get("agent_id", "")).strip()
    message = str(payload.get("message", "")).strip()
    target_path = str(payload.get("target_path", "")).strip()
    bundle = str(payload.get("bundle", "")).strip()

    if not agent_id:
        return JSONResponse({"error": "agent_id is required"}, status_code=400)
    if not message:
        return JSONResponse({"error": "message is required"}, status_code=400)
    if not target_path:
        return JSONResponse({"error": "target_path is required"}, status_code=400)

    inbox_store.add(agent_id, message)
    await service.event_bus.emit(AgentInboxEvent(agent_id=agent_id, message=message))

    node = _resolve_agent_node(target_path, bundle or None, agent_id)
    if node is None:
        return JSONResponse({"error": f"Agent {agent_id} not found"}, status_code=404)

    single_node = AgentNode(
        id=node.id,
        name=node.name,
        target=node.target,
        bundle_path=node.bundle_path,
        upstream=frozenset(),
        downstream=frozenset(),
        priority=node.priority,
    )

    graph_id = uuid.uuid4().hex[:8]
    task = asyncio.create_task(_run_single_node(graph_id, single_node))
    _agent_tasks[graph_id] = task

    def _cleanup(_task: asyncio.Task) -> None:
        _agent_tasks.pop(graph_id, None)

    task.add_done_callback(_cleanup)
    return JSONResponse({"status": "started", "graph_id": graph_id, "agent_id": agent_id})


async def _run_single_node(graph_id: str, node: AgentNode) -> None:
    try:
        executor = RefactorGraphExecutor(
            config=service._deps.config,  # type: ignore[attr-defined]
            event_bus=service.event_bus,
            context_builder=InboxContextBuilder(inbox_store),
            project_root=service._deps.project_root,  # type: ignore[attr-defined]
            common_tools_dir=Path(service._deps.config.bundles.path) / "common_tools",  # type: ignore[attr-defined]
        )
        await executor.run([node], graph_id)
    except Exception:
        logger.exception("Agent ask run failed: %s", graph_id)


def _resolve_agent_node(target_path: str, bundle: str | None, agent_id: str) -> AgentNode | None:
    config = service._deps.config  # type: ignore[attr-defined]
    project_root = service._deps.project_root  # type: ignore[attr-defined]

    bundle_root = Path(config.bundles.path)
    bundle_mapping = {
        node_type: bundle_root / bundle_path
        for node_type, bundle_path in config.bundles.mapping.items()
    }

    target = Path(target_path)
    if target.is_absolute():
        resolved = target.resolve()
    else:
        resolved = (project_root / target).resolve()

    if not resolved.exists():
        return None

    nodes = discover(
        [resolved],
        languages=list(config.discovery.languages) if config.discovery.languages else None,
        max_workers=config.discovery.max_workers,
    )
    agent_nodes = build_graph(nodes, bundle_mapping)

    if bundle:
        target_bundle = bundle_mapping.get(bundle)
        if target_bundle:
            agent_nodes = [node for node in agent_nodes if node.bundle_path == target_bundle]

    for node in agent_nodes:
        if node.id == agent_id:
            return node

    return None


app.add_route("/agent-ask", agent_ask, methods=["POST"])


async def _execute_graph(
    graph_id: str,
    agent_nodes: list[AgentNode],
    project_root: Path,
    deps,
) -> None:
    try:
        event_bus = deps.event_bus
        if deps.event_store is not None:
            from remora.core.event_store import EventSourcedBus

            event_bus = EventSourcedBus(deps.event_bus, deps.event_store, graph_id)
        executor = deps.executor_factory(deps.config, event_bus, project_root)
        await executor.run(agent_nodes, graph_id)
    except Exception:
        logger.exception("Graph execution failed: %s", graph_id)


def _serialize_node(node: AgentNode) -> dict[str, object]:
    return {
        "id": node.id,
        "name": node.name,
        "node_type": node.target.node_type,
        "file_path": node.target.file_path,
        "bundle_path": str(node.bundle_path),
        "upstream": list(node.upstream),
        "downstream": list(node.downstream),
        "priority": node.priority,
    }


def _build_refactor_graph(
    nodes: list,
    bundle_mapping: dict[str, Path],
) -> list[AgentNode]:
    base_nodes = build_graph(nodes, bundle_mapping)
    return _add_class_method_edges(base_nodes)


def _add_class_method_edges(nodes: list[AgentNode]) -> list[AgentNode]:
    file_node_ids_by_path: dict[str, str] = {}
    class_nodes_by_file: dict[str, list[AgentNode]] = defaultdict(list)
    method_nodes_by_file: dict[str, list[AgentNode]] = defaultdict(list)

    for node in nodes:
        node_type = node.target.node_type
        if node_type == "file":
            file_node_ids_by_path[node.target.file_path] = node.id
        elif node_type == "class":
            class_nodes_by_file[node.target.file_path].append(node)
        elif node_type == "method":
            method_nodes_by_file[node.target.file_path].append(node)

    updated_upstream: dict[str, set[str]] = {}
    for file_path, methods in method_nodes_by_file.items():
        classes = class_nodes_by_file.get(file_path, [])
        if not classes:
            continue
        for method in methods:
            parent = _find_parent_class(method, classes)
            if parent is None:
                continue
            upstream = set(method.upstream)
            upstream.add(parent.id)
            file_node_id = file_node_ids_by_path.get(method.target.file_path)
            if file_node_id:
                upstream.discard(file_node_id)
            updated_upstream[method.id] = upstream

    if not updated_upstream:
        return nodes

    updated_nodes: list[AgentNode] = []
    for node in nodes:
        upstream = updated_upstream.get(node.id, set(node.upstream))
        updated_nodes.append(
            AgentNode(
                id=node.id,
                name=node.name,
                target=node.target,
                bundle_path=node.bundle_path,
                upstream=frozenset(upstream),
                downstream=frozenset(),
                priority=node.priority,
            )
        )

    downstream_map: dict[str, set[str]] = defaultdict(set)
    for node in updated_nodes:
        for upstream_id in node.upstream:
            downstream_map[upstream_id].add(node.id)

    final_nodes: list[AgentNode] = []
    for node in updated_nodes:
        final_nodes.append(
            AgentNode(
                id=node.id,
                name=node.name,
                target=node.target,
                bundle_path=node.bundle_path,
                upstream=node.upstream,
                downstream=frozenset(downstream_map[node.id]),
                priority=node.priority,
            )
        )

    return _topological_sort(final_nodes)


def _find_parent_class(method: AgentNode, classes: list[AgentNode]) -> AgentNode | None:
    candidates = []
    start_line = method.target.start_line
    end_line = method.target.end_line
    for cls in classes:
        if cls.target.start_line <= start_line <= cls.target.end_line:
            if cls.target.start_line <= end_line <= cls.target.end_line:
                candidates.append(cls)
    if not candidates:
        return None
    return min(candidates, key=lambda c: (c.target.end_line - c.target.start_line))


def _topological_sort(nodes: list[AgentNode]) -> list[AgentNode]:
    node_by_id = {n.id: n for n in nodes}
    adjacency: dict[str, list[str]] = defaultdict(list)
    in_degree: dict[str, int] = {n.id: 0 for n in nodes}

    for node in nodes:
        for upstream_id in node.upstream:
            if upstream_id in node_by_id:
                adjacency[upstream_id].append(node.id)
                in_degree[node.id] += 1

    queue: deque[AgentNode] = deque(
        sorted(
            [n for n in nodes if in_degree[n.id] == 0],
            key=lambda n: -n.priority,
        )
    )

    result: list[AgentNode] = []
    while queue:
        node = queue.popleft()
        result.append(node)

        newly_ready: list[AgentNode] = []
        for downstream_id in adjacency[node.id]:
            in_degree[downstream_id] -= 1
            if in_degree[downstream_id] == 0:
                newly_ready.append(node_by_id[downstream_id])

        if newly_ready:
            newly_ready.sort(key=lambda n: -n.priority)
            queue.extend(newly_ready)

    return result
