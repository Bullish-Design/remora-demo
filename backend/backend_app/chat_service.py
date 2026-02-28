"""Standalone chat service for the demo."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route
from sse_starlette.sse import EventSourceResponse

from remora.core.chat import ChatSession, ChatConfig
from remora.core.config import load_config
from remora.core.event_bus import EventBus
from remora.core.events import ToolCallEvent, ToolResultEvent
from remora.core.tool_registry import ToolRegistry

logger = logging.getLogger(__name__)


class ChatServiceState:
    """Holds service state."""

    def __init__(self) -> None:
        self.sessions: dict[str, ChatSession] = {}
        self.event_buses: dict[str, EventBus] = {}


state = ChatServiceState()

_DEFAULT_MODEL_BASE_URL = ChatConfig.__dataclass_fields__["model_base_url"].default
_DEFAULT_MODEL_API_KEY = ChatConfig.__dataclass_fields__["model_api_key"].default
_DEFAULT_MODEL_NAME = ChatConfig.__dataclass_fields__["model_name"].default
_DEFAULT_MAX_TURNS = ChatConfig.__dataclass_fields__["max_turns"].default


def _find_remora_config_path(workspace: Path) -> Path | None:
    """Search for remora.yaml in the workspace or parent directories."""
    for directory in [workspace] + list(workspace.parents):
        config_path = directory / "remora.yaml"
        if config_path.exists():
            return config_path
        if (directory / "pyproject.toml").exists():
            break
    return None


def _load_workspace_config(workspace: Path):
    config_path = _find_remora_config_path(workspace)
    if not config_path:
        return None
    return load_config(config_path)


async def create_session(request: Request) -> JSONResponse:
    """Create a new chat session."""
    body = await request.json()

    # Validate workspace path
    workspace_path = body.get("workspace_path", "")
    workspace = Path(workspace_path).expanduser().resolve()
    if not workspace.exists() or not workspace.is_dir():
        return JSONResponse(
            {"error": f"Invalid workspace path: {workspace_path}"},
            status_code=400,
        )

    remora_config = _load_workspace_config(workspace)
    if remora_config:
        model_base_url = body.get("model_base_url", remora_config.model.base_url)
        model_api_key = body.get("model_api_key", remora_config.model.api_key)
        model_name = body.get("model_name", remora_config.model.default_model)
        config_source = str(
            _find_remora_config_path(workspace) or "remora.yaml"
        )
    else:
        model_base_url = body.get("model_base_url", _DEFAULT_MODEL_BASE_URL)
        model_api_key = body.get("model_api_key", _DEFAULT_MODEL_API_KEY)
        model_name = body.get("model_name", _DEFAULT_MODEL_NAME)
        config_source = "defaults"

    config = ChatConfig(
        workspace_path=workspace_path,
        system_prompt=body.get("system_prompt", "You are a helpful assistant."),
        tool_presets=body.get("tool_presets", ["file_ops"]),
        model_name=model_name,
        model_base_url=model_base_url,
        model_api_key=model_api_key,
        max_turns=body.get("max_turns", _DEFAULT_MAX_TURNS),
    )

    event_bus = EventBus()
    session = await ChatSession.create(config=config, event_bus=event_bus)

    state.sessions[session.session_id] = session
    state.event_buses[session.session_id] = event_bus

    logger.info(
        "Session created: %s workspace=%s model=%s base_url=%s presets=%s config=%s",
        session.session_id,
        workspace,
        model_name,
        model_base_url,
        config.tool_presets,
        config_source,
    )

    return JSONResponse(
        {
            "session_id": session.session_id,
            "workspace_path": str(workspace),
            "tool_presets": config.tool_presets,
            "model_name": model_name,
            "model_base_url": model_base_url,
        }
    )


async def delete_session(request: Request) -> Response:
    """End a chat session."""
    session_id = request.path_params["session_id"]

    if session_id in state.sessions:
        await state.sessions[session_id].close()
        del state.sessions[session_id]
        del state.event_buses[session_id]
        logger.info("Session deleted: %s", session_id)

    return Response(status_code=204)


async def send_message(request: Request) -> JSONResponse:
    """Send a message and get response."""
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
        logger.exception("Chat message failed for session %s", session_id)
        return JSONResponse(
            {"error": "Chat message failed", "detail": str(exc)}, status_code=500
        )


async def get_history(request: Request) -> JSONResponse:
    """Get conversation history."""
    session_id = request.path_params["session_id"]

    if session_id not in state.sessions:
        return JSONResponse({"error": "Session not found"}, status_code=404)

    session = state.sessions[session_id]

    return JSONResponse(
        {
            "messages": [
                {
                    "id": m.id,
                    "role": m.role,
                    "content": m.content,
                    "timestamp": m.timestamp,
                    "tool_calls": m.tool_calls,
                }
                for m in session.history
            ]
        }
    )


async def stream_events(request: Request) -> EventSourceResponse:
    """Stream tool events via SSE."""
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
                                "timestamp": event.timestamp,
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
                                "timestamp": event.timestamp,
                            }
                        ),
                    }

    return EventSourceResponse(event_generator())


async def list_tools(request: Request) -> JSONResponse:
    """List available tool presets."""
    return JSONResponse(
        {
            "presets": ToolRegistry.list_presets(),
        }
    )


async def health(request: Request) -> JSONResponse:
    """Health check."""
    return JSONResponse(
        {
            "status": "ok",
            "sessions": len(state.sessions),
        }
    )


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


@app.on_event("startup")
async def startup_event() -> None:
    logger.info("Chat service starting...")
    try:
        import structured_agents  # noqa: F401

        logger.info("structured-agents: OK")
    except ImportError as exc:
        logger.error("structured-agents not available: %s", exc)
        logger.error("Install with: pip install structured-agents")

    try:
        import cairn  # noqa: F401

        logger.info("cairn: OK")
    except ImportError as exc:
        logger.error("cairn not available: %s", exc)
