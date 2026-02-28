"""Standalone chat service for the demo."""

from __future__ import annotations

import json
import time
from pathlib import Path

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route
from sse_starlette.sse import EventSourceResponse

from remora.core.chat import ChatConfig, ChatSession
from remora.core.event_bus import EventBus
from remora.core.events import ToolCallEvent, ToolResultEvent
from remora.core.tool_registry import ToolRegistry


class ChatServiceState:
    """Holds service state."""

    def __init__(self) -> None:
        self.sessions: dict[str, ChatSession] = {}
        self.event_buses: dict[str, EventBus] = {}


state = ChatServiceState()


async def create_session(request: Request) -> JSONResponse:
    body = await request.json()

    workspace_path = body.get("workspace_path")
    if not workspace_path:
        return JSONResponse({"error": "workspace_path is required"}, status_code=400)

    tool_presets = body.get("tool_presets") or ["file_ops"]
    if not isinstance(tool_presets, list):
        return JSONResponse({"error": "tool_presets must be a list"}, status_code=400)

    config = ChatConfig(
        workspace_path=workspace_path,
        system_prompt=body.get("system_prompt", "You are a helpful assistant."),
        tool_presets=tool_presets,
        model_name=body.get("model_name", "Qwen/Qwen3-4B"),
        model_family=body.get("model_family", "qwen"),
    )

    workspace = Path(config.workspace_path).expanduser().resolve()
    if not workspace.exists() or not workspace.is_dir():
        return JSONResponse(
            {"error": f"Invalid workspace path: {config.workspace_path}"},
            status_code=400,
        )

    event_bus = EventBus()
    session = await ChatSession.create(config=config, event_bus=event_bus)

    state.sessions[session.session_id] = session
    state.event_buses[session.session_id] = event_bus

    return JSONResponse(
        {
            "session_id": session.session_id,
            "workspace_path": str(workspace),
            "tool_presets": config.tool_presets,
        }
    )


async def delete_session(request: Request) -> Response:
    session_id = request.path_params["session_id"]

    if session_id in state.sessions:
        await state.sessions[session_id].close()
        del state.sessions[session_id]
        del state.event_buses[session_id]

    return Response(status_code=204)


async def send_message(request: Request) -> JSONResponse:
    session_id = request.path_params["session_id"]

    if session_id not in state.sessions:
        return JSONResponse({"error": "Session not found"}, status_code=404)

    body = await request.json()
    content = body.get("content", "").strip()

    if not content:
        return JSONResponse({"error": "Empty message"}, status_code=400)

    session = state.sessions[session_id]

    try:
        response = await session.send(content)
        return JSONResponse(
            {
                "message": {
                    "id": response.message.id,
                    "role": response.message.role,
                    "content": response.message.content,
                    "timestamp": response.message.timestamp,
                    "tool_calls": response.message.tool_calls,
                },
                "turn_count": response.turn_count,
            }
        )
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


async def get_history(request: Request) -> JSONResponse:
    session_id = request.path_params["session_id"]

    if session_id not in state.sessions:
        return JSONResponse({"error": "Session not found"}, status_code=404)

    session = state.sessions[session_id]

    return JSONResponse(
        {
            "messages": [
                {
                    "id": msg.id,
                    "role": msg.role,
                    "content": msg.content,
                    "timestamp": msg.timestamp,
                    "tool_calls": msg.tool_calls,
                }
                for msg in session.history
            ]
        }
    )


async def stream_events(request: Request) -> EventSourceResponse:
    session_id = request.path_params["session_id"]

    if session_id not in state.event_buses:
        return JSONResponse({"error": "Session not found"}, status_code=404)

    event_bus = state.event_buses[session_id]

    async def event_generator():
        async with event_bus.stream(ToolCallEvent, ToolResultEvent) as events:
            async for event in events:
                if isinstance(event, ToolCallEvent):
                    yield {
                        "event": "tool_call",
                        "data": json.dumps(
                            {
                                "name": event.tool_name,
                                "arguments": event.arguments,
                                "timestamp": time.time(),
                                "call_id": event.call_id,
                            }
                        ),
                    }
                elif isinstance(event, ToolResultEvent):
                    yield {
                        "event": "tool_result",
                        "data": json.dumps(
                            {
                                "name": event.tool_name,
                                "output": event.output_preview,
                                "is_error": event.is_error,
                                "timestamp": time.time(),
                                "call_id": event.call_id,
                            }
                        ),
                    }

    return EventSourceResponse(event_generator())


async def list_tools(request: Request) -> JSONResponse:
    return JSONResponse({"presets": ToolRegistry.list_presets()})


async def health(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "sessions": len(state.sessions)})


routes = [
    Route("/sessions", create_session, methods=["POST"]),
    Route("/sessions/{session_id}", delete_session, methods=["DELETE"]),
    Route("/sessions/{session_id}/messages", send_message, methods=["POST"]),
    Route("/sessions/{session_id}/history", get_history, methods=["GET"]),
    Route("/sessions/{session_id}/events", stream_events, methods=["GET"]),
    Route("/tools", list_tools, methods=["GET"]),
    Route("/health", health, methods=["GET"]),
]

app = Starlette(routes=routes)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8420)
