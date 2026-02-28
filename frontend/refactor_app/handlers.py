"""HTTP handlers for the refactor swarm demo UI."""

from __future__ import annotations

import asyncio
import time
from typing import Iterable

from stario import Context, Relay, Writer

from .client import RefactorClient
from .state import BlockedRequest, RefactorState
from .views import (
    blocked_view,
    control_panel_view,
    events_view,
    graph_view,
    home_view,
    results_view,
    status_view,
)


def home(state: RefactorState):
    async def handler(_c: Context, w: Writer) -> None:
        w.html(home_view(state))

    return handler


def check_backend(state: RefactorState, client: RefactorClient, relay: Relay):
    async def handler(_c: Context, w: Writer) -> None:
        state.backend_connected = await client.health()
        if state.backend_connected:
            try:
                config = await client.config()
                mapping = config.get("bundles", {}).get("mapping", {})
                if isinstance(mapping, dict):
                    state.available_bundles = sorted(mapping.keys())
            except Exception:
                state.available_bundles = []
            if not state.event_stream_active and state.event_stream_task is None:
                state.event_stream_task = asyncio.create_task(pump_events(state, client, relay))
        w.patch(status_view(state))
        w.patch(control_panel_view(state))

    return handler


def plan_graph(state: RefactorState, client: RefactorClient):
    async def handler(c: Context, w: Writer) -> None:
        if not state.backend_connected:
            state.error_message = "Backend is not reachable."
            w.patch(status_view(state))
            return

        signals = await c.signals()
        target_path = str(signals.get("target_path", state.target_path)).strip()
        bundle_filter = str(signals.get("bundle_filter", state.bundle_filter)).strip()
        bundle = bundle_filter or None

        if not target_path:
            state.error_message = "Target path is required."
            w.patch(status_view(state))
            return

        state.target_path = target_path
        state.bundle_filter = bundle_filter
        state.error_message = None
        state.planning = True

        w.patch(status_view(state))
        w.patch(control_panel_view(state))

        try:
            plan = await client.plan(target_path, bundle=bundle)
            state.set_plan(plan.get("nodes", []), target=target_path, bundle=bundle)
            _sync_inbox_signals(w, state)
        except Exception as exc:
            state.error_message = f"Plan failed: {exc}"
        finally:
            state.planning = False

        w.patch(status_view(state))
        w.patch(graph_view(state))
        w.patch(control_panel_view(state))

    return handler


def run_graph(state: RefactorState, client: RefactorClient, relay: Relay):
    async def handler(c: Context, w: Writer) -> None:
        if not state.backend_connected:
            state.error_message = "Backend is not reachable."
            w.patch(status_view(state))
            return

        signals = await c.signals()
        target_path = str(signals.get("target_path", state.target_path)).strip()
        bundle_filter = str(signals.get("bundle_filter", state.bundle_filter)).strip()
        bundle = bundle_filter or None

        if not target_path:
            state.error_message = "Target path is required."
            w.patch(status_view(state))
            return

        state.target_path = target_path
        state.bundle_filter = bundle_filter
        state.error_message = None

        if (
            not state.plan_nodes
            or state.plan_target != target_path
            or state.plan_bundle != bundle
        ):
            try:
                plan = await client.plan(target_path, bundle=bundle)
                state.set_plan(plan.get("nodes", []), target=target_path, bundle=bundle)
                _sync_inbox_signals(w, state)
            except Exception as exc:
                state.error_message = f"Plan failed: {exc}"
                w.patch(status_view(state))
                w.patch(graph_view(state))
                return

        state.events.clear()
        state.results.clear()
        state.blocked.clear()
        state.mark_all("queued")
        state.running = True

        w.patch(status_view(state))
        w.patch(graph_view(state))
        w.patch(events_view(state))
        w.patch(results_view(state))
        w.patch(blocked_view(state))

        try:
            response = await client.run(target_path, bundle=bundle)
            state.graph_id = response.get("graph_id")
            relay.publish("status", "run_started")
        except Exception as exc:
            state.error_message = f"Run failed: {exc}"
            state.running = False
            w.patch(status_view(state))

    return handler


def submit_input(state: RefactorState, client: RefactorClient):
    async def handler(c: Context, w: Writer) -> None:
        payload = {}
        try:
            payload = await c.req.json()
        except Exception:
            payload = {}

        request_id = str(payload.get("request_id", "")).strip()
        signals = await c.signals()
        response_key = f"reply_{request_id}"
        response_text = str(signals.get(response_key, "")).strip()

        if not request_id or not response_text:
            w.empty(204)
            return

        try:
            await client.submit_input(request_id, response_text)
            state.clear_blocked(request_id)
            w.sync({response_key: ""})
        except Exception as exc:
            state.error_message = f"Failed to submit input: {exc}"

        w.patch(blocked_view(state))
        w.patch(status_view(state))

    return handler


def send_agent_message(state: RefactorState, client: RefactorClient):
    async def handler(c: Context, w: Writer) -> None:
        try:
            payload = await c.req.json()
        except Exception:
            payload = {}

        agent_id = str(payload.get("agent_id", "")).strip()
        message = str(payload.get("message", "")).strip()
        if not agent_id or not message:
            w.empty(204)
            return

        try:
            await client.send_agent_message(agent_id, message)
        except Exception as exc:
            state.error_message = f"Failed to send message: {exc}"
            w.patch(status_view(state))

    return handler


def ask_agent(state: RefactorState, client: RefactorClient):
    async def handler(c: Context, w: Writer) -> None:
        try:
            payload = await c.req.json()
        except Exception:
            payload = {}

        agent_id = str(payload.get("agent_id", "")).strip()
        message = str(payload.get("message", "")).strip()
        target_path = str(payload.get("target_path", "")).strip()
        bundle = str(payload.get("bundle", "")).strip()

        if not agent_id or not message or not target_path:
            w.empty(204)
            return

        try:
            await client.ask_agent(agent_id, message, target_path, bundle or None)
        except Exception as exc:
            state.error_message = f"Failed to ask agent: {exc}"
            w.patch(status_view(state))

    return handler


def subscribe(state: RefactorState, relay: Relay):
    async def handler(_c: Context, w: Writer) -> None:
        w.patch(status_view(state))
        w.patch(graph_view(state))
        w.patch(events_view(state))
        w.patch(results_view(state))
        w.patch(blocked_view(state))

        async for topic, _payload in w.alive(relay.subscribe("*")):
            if topic == "graph":
                w.patch(graph_view(state))
            elif topic == "events":
                w.patch(events_view(state))
            elif topic == "results":
                w.patch(results_view(state))
            elif topic == "blocked":
                w.patch(blocked_view(state))
            elif topic == "status":
                w.patch(status_view(state))

    return handler


def _sync_inbox_signals(w: Writer, state: RefactorState) -> None:
    if not state.plan_nodes:
        return
    payload = {f"inbox_{node.id}": "" for node in state.plan_nodes}
    w.sync(payload)


async def pump_events(state: RefactorState, client: RefactorClient, relay: Relay) -> None:
    state.event_stream_active = True
    relay.publish("status", "stream_open")
    try:
        async for event in client.stream_events():
            updated = _apply_remora_event(state, event.payload)
            _publish_updates(relay, updated)
    except Exception as exc:
        state.error_message = f"Event stream error: {exc}"
    finally:
        state.event_stream_active = False
        relay.publish("status", "stream_closed")


def _publish_updates(relay: Relay, updates: Iterable[str]) -> None:
    for topic in updates:
        relay.publish(topic, "update")


def _apply_remora_event(state: RefactorState, envelope: dict) -> set[str]:
    updates: set[str] = set()
    event_type = str(envelope.get("type", "event"))
    agent_id = str(envelope.get("agent_id", "")).strip() or None
    graph_id = str(envelope.get("graph_id", "")).strip() or None
    payload = envelope.get("payload") or {}
    timestamp = float(envelope.get("timestamp", time.time()))

    message = event_type

    if event_type == "GraphStartEvent":
        node_count = payload.get("node_count", 0)
        state.running = True
        state.graph_id = graph_id or state.graph_id
        state.mark_all("queued")
        message = f"Graph started with {node_count} agents"
        updates.update({"graph", "status"})

    elif event_type == "GraphCompleteEvent":
        completed = payload.get("completed_count", 0)
        failed = payload.get("failed_count", 0)
        state.running = False
        message = f"Graph complete: {completed} done, {failed} failed"
        updates.update({"graph", "status"})

    elif event_type == "GraphErrorEvent":
        state.running = False
        state.error_message = payload.get("error", "Graph error")
        message = "Graph error"
        updates.update({"status"})

    elif event_type == "AgentStartEvent":
        state.update_status(agent_id or "", "running")
        message = f"Agent {payload.get('node_name', agent_id) or agent_id} started"
        updates.update({"graph"})

    elif event_type == "AgentCompleteEvent":
        state.update_status(agent_id or "", "completed")
        summary = str(payload.get("result_summary", "")).strip()
        if summary:
            state.add_result(agent_id or "unknown", summary, timestamp)
            updates.add("results")
        message = f"Agent {agent_id} completed"
        updates.update({"graph"})

    elif event_type == "AgentErrorEvent":
        state.update_status(agent_id or "", "failed")
        message = f"Agent {agent_id} failed"
        updates.update({"graph", "status"})

    elif event_type == "AgentSkippedEvent":
        state.update_status(agent_id or "", "skipped")
        reason = payload.get("reason", "skipped")
        message = f"Agent {agent_id} skipped: {reason}"
        updates.update({"graph"})

    elif event_type == "HumanInputRequestEvent":
        request_id = str(payload.get("request_id", ""))
        question = str(payload.get("question", "")).strip()
        options = list(payload.get("options") or [])
        blocked = BlockedRequest(
            request_id=request_id,
            agent_id=agent_id or "unknown",
            question=question,
            options=options,
            timestamp=timestamp,
        )
        state.add_blocked(blocked)
        message = f"Input requested: {question}"
        updates.update({"blocked", "status"})

    elif event_type == "HumanInputResponseEvent":
        request_id = str(payload.get("request_id", ""))
        state.clear_blocked(request_id)
        message = "Input received"
        updates.update({"blocked"})

    elif event_type == "AgentInboxEvent":
        message_text = str(payload.get("message", "")).strip()
        message = f"Inbox note sent: {message_text}"

    state.add_event(
        event_type,
        message,
        timestamp,
        agent_id=agent_id,
        graph_id=graph_id,
        payload=payload,
    )
    updates.add("events")
    return updates
