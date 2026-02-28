"""HTTP request handlers."""

from __future__ import annotations

import asyncio
import time
import uuid
from pathlib import Path

from stario import Context, Relay, Writer

from .client import RemoraClient
from .state import DemoState
from .views import (
    chat_header_view,
    chat_view,
    home_view,
    status_view,
    tool_log_view,
)


def home(state: DemoState):
    async def handler(c: Context, w: Writer) -> None:
        w.html(home_view(state))
    return handler


def check_backend(state: DemoState, client: RemoraClient):
    async def handler(c: Context, w: Writer) -> None:
        state.backend_connected = await client.health()
        if state.backend_connected:
            try:
                presets = await client.list_tools()
                state.available_presets = sorted(presets.keys())
            except Exception:
                state.available_presets = ["file_ops", "code_analysis", "all"]
        w.sync({"backend_connected": state.backend_connected})
        w.patch(home_view(state))
    return handler


def set_workspace(state: DemoState):
    async def handler(c: Context, w: Writer) -> None:
        signals = await c.signals()
        path_str = str(signals.get("workspace_path", "")).strip()

        if path_str:
            path = Path(path_str).expanduser().resolve()
            state.workspace_path = str(path)
            state.workspace_valid = path.exists() and path.is_dir()
        else:
            state.workspace_path = ""
            state.workspace_valid = False

        w.sync(
            {
                "workspace_path": state.workspace_path,
                "workspace_valid": state.workspace_valid,
            }
        )
        w.patch(home_view(state))
    return handler


def start_session(state: DemoState, client: RemoraClient, relay: Relay):
    async def handler(c: Context, w: Writer) -> None:
        if not state.workspace_valid:
            state.error_message = "Workspace path is not valid."
            w.patch(status_view(state))
            return
        if not state.backend_connected:
            state.error_message = "Backend is not reachable."
            w.patch(status_view(state))
            return

        signals = await c.signals()
        state.agent_config.system_prompt = signals.get(
            "system_prompt",
            state.agent_config.system_prompt,
        )

        presets = []
        for preset in state.available_presets:
            key = f"preset_{preset}"
            if _truthy(signals.get(key)):
                presets.append(preset)
        if not presets:
            presets = ["file_ops"]

        state.agent_config.enabled_presets = presets

        await _stop_event_stream(state)

        try:
            result = await client.create_session(
                workspace_path=state.workspace_path,
                system_prompt=state.agent_config.system_prompt,
                tool_presets=state.agent_config.enabled_presets,
            )
            state.session_id = result["session_id"]
            state.session_active = True
            state.error_message = None
            state.reset_chat()
            state.event_stream_task = asyncio.create_task(
                _pump_events(state, client, relay, state.session_id)
            )
            w.sync({"session_active": True})
        except Exception as e:
            state.error_message = f"Failed to start session: {e}"
            state.session_id = None
            state.session_active = False
            w.sync({"session_active": False})

        w.patch(home_view(state))
    return handler


def stop_session(state: DemoState, client: RemoraClient):
    async def handler(c: Context, w: Writer) -> None:
        if state.session_id:
            try:
                await client.delete_session(state.session_id)
            except Exception:
                pass

        await _stop_event_stream(state)
        state.session_id = None
        state.session_active = False
        state.error_message = None
        state.reset_chat()
        w.sync({"session_active": False, "is_processing": False})
        w.patch(home_view(state))
    return handler


def send_message(state: DemoState, client: RemoraClient):
    async def handler(c: Context, w: Writer) -> None:
        signals = await c.signals()
        content = str(signals.get("message_input", "")).strip()

        if not content or not state.session_id or not state.session_active or state.is_processing:
            w.empty(204)
            return

        user_msg_id = str(uuid.uuid4())
        state.add_user_message(user_msg_id, content, time.time())
        state.is_processing = True

        w.sync({"message_input": "", "is_processing": True})
        w.patch(chat_header_view(state))
        w.patch(chat_view(state))

        try:
            result = await client.send_message(state.session_id, content)
            msg = result["message"]

            tool_calls = []
            if not state.event_stream_active:
                for tc in msg.get("tool_calls", []):
                    tool_calls.append(
                        state.log_tool_call(
                            tc.get("name", ""),
                            tc.get("arguments", {}),
                            call_id=tc.get("id"),
                        )
                    )

            state.add_agent_message(
                id=msg["id"],
                content=msg["content"],
                timestamp=msg["timestamp"],
                tool_calls=tool_calls,
            )
            state.error_message = None
        except Exception as e:
            state.error_message = f"Error: {e}"

        state.is_processing = False
        w.sync({"is_processing": False})
        w.patch(chat_header_view(state))
        w.patch(chat_view(state))
        w.patch(tool_log_view(state))
        w.patch(status_view(state))

    return handler


def subscribe(state: DemoState, relay: Relay):
    async def handler(c: Context, w: Writer) -> None:
        w.patch(status_view(state))
        w.patch(chat_header_view(state))
        w.patch(chat_view(state))
        w.patch(tool_log_view(state))

        async for topic, payload in w.alive(relay.subscribe("*")):
            if topic == "tool_event":
                _handle_tool_event(state, payload)
                w.patch(tool_log_view(state))
            elif topic == "status":
                w.patch(status_view(state))

    return handler


async def _stop_event_stream(state: DemoState) -> None:
    task = state.event_stream_task
    state.event_stream_task = None
    state.event_stream_active = False
    if task and not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        except Exception:
            pass


async def _pump_events(
    state: DemoState,
    client: RemoraClient,
    relay: Relay,
    session_id: str,
) -> None:
    state.event_stream_active = True
    relay.publish("status", "stream_open")
    try:
        async for event in client.stream_events(session_id):
            if event.event_type == "tool_call":
                relay.publish(
                    "tool_event",
                    {
                        "kind": "tool_call",
                        "name": event.name,
                        "arguments": event.data.get("arguments", {}),
                        "timestamp": event.timestamp,
                        "call_id": event.call_id,
                    },
                )
            elif event.event_type == "tool_result":
                relay.publish(
                    "tool_event",
                    {
                        "kind": "tool_result",
                        "name": event.name,
                        "output": event.data.get("output", ""),
                        "is_error": event.data.get("is_error", False),
                        "timestamp": event.timestamp,
                        "call_id": event.call_id,
                    },
                )
    except Exception as exc:
        state.error_message = f"Tool stream error: {exc}"
    finally:
        state.event_stream_active = False
        relay.publish("status", "stream_closed")


def _handle_tool_event(state: DemoState, payload: dict) -> None:
    kind = payload.get("kind")
    if kind == "tool_call":
        state.log_tool_call(
            name=payload.get("name", ""),
            arguments=payload.get("arguments", {}),
            call_id=payload.get("call_id"),
            timestamp=payload.get("timestamp"),
        )
    elif kind == "tool_result":
        state.update_tool_result(
            name=payload.get("name", ""),
            result=payload.get("output"),
            is_error=payload.get("is_error", False),
            call_id=payload.get("call_id"),
            timestamp=payload.get("timestamp"),
        )


def _truthy(value: object) -> bool:
    return str(value).lower() in {"true", "1", "yes", "on"}
