# Remora Demo App - Design Document

## Overview

This document describes the architecture and implementation plan for an MVP demo application that showcases Remora's agent capabilities through a Stario-based web UI. The demo allows users to:

1. Select any directory as a workspace
2. Configure an agent with a custom system prompt and tool sets
3. Chat with the agent in an inbox/outbox style interface
4. Observe tool calls and agent state in real-time

---

## Critical Constraint: Python Version Split

**Remora requires Python 3.13** (due to vLLM dependency)
**Stario requires Python 3.14** (language features)

These libraries **cannot coexist in the same Python environment**. This fundamentally shapes the architecture:

```
┌─────────────────────────────┐      ┌─────────────────────────────┐
│   Stario Frontend (3.14)    │ HTTP │  Remora Chat Service (3.13) │
│   - Web UI                  │◄────►│  - Agent execution          │
│   - Browser SSE             │ SSE  │  - Tool calling             │
└─────────────────────────────┘      └─────────────────────────────┘
```

**Two separate processes, two separate virtual environments.**

---

## Goals

### MVP Goals
- **Single agent chat**: User interacts with one agent per session
- **Workspace flexibility**: Any directory can be a workspace
- **Tool selection**: Choose from preset tool sets (file ops, code analysis)
- **Visible state**: Chat history (inbox/outbox) and tool log displayed in UI
- **Session-based**: State lives in memory, lost on restart

### Future Goals (Phase 2+)
- Multi-agent orchestration with dependency graphs
- State persistence (file-based or event-sourced)
- Token streaming for real-time response display
- Full bundle editing (YAML configuration)
- Agent templates

---

## Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           Browser (Datastar)                            │
│   - Reactive signals for UI state                                       │
│   - SSE connection for real-time updates                                │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │ HTTP + SSE (port 8000)
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    Stario Frontend (Python 3.14)                        │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌──────────────┐  │
│   │  Handlers   │  │   Views     │  │   State     │  │ RemoraClient │  │
│   │  (HTTP)     │  │   (HTML)    │  │ (DemoState) │  │ (HTTP+SSE)   │  │
│   └─────────────┘  └─────────────┘  └─────────────┘  └──────────────┘  │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │ HTTP + SSE (port 8420)
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                  Remora Chat Service (Python 3.13)                      │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌──────────────┐  │
│   │ ChatSession │  │ToolRegistry │  │  EventBus   │  │  Workspace   │  │
│   │   (NEW)     │  │   (NEW)     │  │ (existing)  │  │  (existing)  │  │
│   └─────────────┘  └─────────────┘  └─────────────┘  └──────────────┘  │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │ HTTP (OpenAI-compatible)
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                            vLLM Server                                  │
│   - Local model serving                                                 │
│   - OpenAI-compatible API                                               │
└─────────────────────────────────────────────────────────────────────────┘
```

### Directory Structure

```
remora-demo/
├── frontend/                    # Stario app (Python 3.14)
│   ├── pyproject.toml
│   ├── main.py
│   └── app/
│       ├── __init__.py
│       ├── state.py             # DemoState dataclass
│       ├── views.py             # HTML view functions
│       ├── handlers.py          # HTTP handler factories
│       ├── client.py            # RemoraClient (HTTP+SSE to backend)
│       └── static/
│           └── css/
│               └── style.css
│
├── backend/                     # Remora chat service (Python 3.13)
│   ├── pyproject.toml
│   └── ... (or modifications to Remora library)
│
├── scripts/
│   ├── start-backend.sh         # Start Remora service
│   ├── start-frontend.sh        # Start Stario app
│   └── start-all.sh             # Start both
│
├── DESIGN_DOC.md
└── .context/
    └── remora/                  # Remora library source
```

### Communication Protocol

The Stario frontend communicates with the Remora backend via HTTP/SSE:

**Remora Chat Service API (port 8420):**

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `POST /sessions` | Create | Create new chat session |
| `DELETE /sessions/{id}` | Delete | End chat session |
| `POST /sessions/{id}/messages` | Create | Send message, get response |
| `GET /sessions/{id}/events` | SSE | Stream tool events in real-time |
| `GET /tools` | Read | List available tool presets |
| `GET /health` | Read | Health check |

---

## Remora Modifications (Backend - Python 3.13)

### Overview

We extend Remora with:
1. `ChatSession` - Simplified chat-oriented wrapper around AgentKernel
2. `ToolRegistry` - Dynamic tool selection with presets
3. `ChatService` - HTTP service exposing chat sessions

### 1. ChatSession (`remora/core/chat.py`)

```python
"""Chat session wrapper for single-agent interactions."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import time
import uuid

from remora.core.events import RemoraEvent
from remora.core.event_bus import EventBus
from remora.core.workspace import CairnWorkspaceService


@dataclass
class Message:
    """A message in the conversation."""
    id: str
    role: str  # "user" or "assistant"
    content: str
    timestamp: float
    tool_calls: list[dict] = field(default_factory=list)

    @classmethod
    def user(cls, content: str) -> "Message":
        return cls(
            id=str(uuid.uuid4()),
            role="user",
            content=content,
            timestamp=time.time(),
        )

    @classmethod
    def assistant(cls, content: str, tool_calls: list[dict] | None = None) -> "Message":
        return cls(
            id=str(uuid.uuid4()),
            role="assistant",
            content=content,
            timestamp=time.time(),
            tool_calls=tool_calls or [],
        )


@dataclass
class ChatConfig:
    """Configuration for a chat session."""
    workspace_path: str
    system_prompt: str
    tool_presets: list[str] = field(default_factory=lambda: ["file_ops"])
    model_name: str = "Qwen/Qwen3-4B"
    model_base_url: str = "http://localhost:8000/v1"
    model_api_key: str = "EMPTY"
    max_turns: int = 10


@dataclass
class AgentResponse:
    """Response from the agent."""
    message: Message
    turn_count: int


class ChatSession:
    """
    Simplified single-agent chat interface.

    Wraps Remora's AgentKernel to provide a conversation-oriented API
    with automatic history management and event streaming.
    """

    def __init__(
        self,
        session_id: str,
        config: ChatConfig,
        event_bus: EventBus,
    ):
        self.session_id = session_id
        self.config = config
        self.event_bus = event_bus

        self._history: list[Message] = []
        self._workspace: Any = None
        self._tools: list[Any] = []
        self._initialized = False

    @classmethod
    async def create(
        cls,
        config: ChatConfig,
        event_bus: EventBus | None = None,
    ) -> "ChatSession":
        """Factory method to create and initialize a chat session."""
        session_id = str(uuid.uuid4())
        event_bus = event_bus or EventBus()

        session = cls(
            session_id=session_id,
            config=config,
            event_bus=event_bus,
        )
        await session._initialize()
        return session

    async def _initialize(self) -> None:
        """Initialize workspace and tools."""
        from remora.core.tool_registry import ToolRegistry

        # Create workspace
        workspace_path = Path(self.config.workspace_path).expanduser().resolve()
        self._workspace = await CairnWorkspaceService.create(
            base_path=workspace_path,
        )

        # Get tools from registry
        self._tools = ToolRegistry.get_tools(
            workspace=self._workspace,
            presets=self.config.tool_presets,
        )

        self._initialized = True

    async def send(self, content: str) -> AgentResponse:
        """Send a message and get a response."""
        if not self._initialized:
            raise RuntimeError("Session not initialized")

        # Add user message
        user_msg = Message.user(content)
        self._history.append(user_msg)

        # Build messages for kernel
        messages = [{"role": m.role, "content": m.content} for m in self._history]

        # Run agent
        from structured_agents import AgentKernel, ModelAdapter

        kernel = AgentKernel(
            model=ModelAdapter.from_config(
                base_url=self.config.model_base_url,
                api_key=self.config.model_api_key,
                model=self.config.model_name,
            ),
            tools=self._tools,
            system_prompt=self.config.system_prompt,
            observer=self.event_bus,
        )

        result = await kernel.run(
            messages=messages,
            max_turns=self.config.max_turns,
        )

        # Extract response
        tool_calls = [
            {"name": tc.name, "arguments": tc.arguments}
            for tc in result.tool_calls
        ]

        assistant_msg = Message.assistant(
            content=result.final_message.content or "",
            tool_calls=tool_calls,
        )
        self._history.append(assistant_msg)

        return AgentResponse(
            message=assistant_msg,
            turn_count=result.turn_count,
        )

    @property
    def history(self) -> list[Message]:
        """Get conversation history."""
        return self._history.copy()

    def reset(self) -> None:
        """Clear conversation history."""
        self._history.clear()

    async def close(self) -> None:
        """Clean up resources."""
        if self._workspace:
            await self._workspace.cleanup()
```

### 2. ToolRegistry (`remora/core/tool_registry.py`)

```python
"""Tool registry for dynamic tool selection."""

from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class ToolDefinition:
    """Definition of an available tool."""
    name: str
    description: str
    category: str
    factory: Callable[..., Any]


class ToolRegistry:
    """Registry for managing available tools and presets."""

    _TOOLS: dict[str, ToolDefinition] = {}

    PRESETS: dict[str, list[str]] = {
        "file_ops": ["read_file", "write_file", "list_dir", "file_exists", "search_files"],
        "code_analysis": ["discover_symbols"],
        "all": [],
    }

    @classmethod
    def register(cls, name: str, description: str, category: str, factory: Callable) -> None:
        """Register a tool definition."""
        cls._TOOLS[name] = ToolDefinition(name, description, category, factory)
        if name not in cls.PRESETS["all"]:
            cls.PRESETS["all"].append(name)

    @classmethod
    def get_tools(cls, workspace: Any, presets: list[str]) -> list[Any]:
        """Get tool instances for the given workspace."""
        names: set[str] = set()
        for preset in presets:
            if preset in cls.PRESETS:
                names.update(cls.PRESETS[preset])

        return [
            cls._TOOLS[name].factory(workspace)
            for name in names
            if name in cls._TOOLS
        ]

    @classmethod
    def list_presets(cls) -> dict[str, list[str]]:
        """List available presets and their tools."""
        return {k: v for k, v in cls.PRESETS.items() if v}  # Exclude empty


# Tool registration (abbreviated - see full version in previous doc)
def _register_tools():
    from structured_agents import Tool

    def make_read_file(workspace):
        async def read_file(path: str) -> str:
            """Read file contents."""
            return await workspace.read_file(path)
        return Tool.from_function(read_file)

    def make_write_file(workspace):
        async def write_file(path: str, content: str) -> bool:
            """Write content to file."""
            await workspace.write_file(path, content)
            return True
        return Tool.from_function(write_file)

    def make_list_dir(workspace):
        async def list_dir(path: str = ".") -> list[str]:
            """List directory contents."""
            return await workspace.list_dir(path)
        return Tool.from_function(list_dir)

    def make_file_exists(workspace):
        async def file_exists(path: str) -> bool:
            """Check if file exists."""
            return await workspace.file_exists(path)
        return Tool.from_function(file_exists)

    def make_search_files(workspace):
        async def search_files(pattern: str) -> list[str]:
            """Search files by glob pattern."""
            return await workspace.search_files(pattern)
        return Tool.from_function(search_files)

    def make_discover_symbols(workspace):
        from remora.core.discovery import discover

        async def discover_symbols(path: str = ".") -> list[dict]:
            """Discover code symbols (functions, classes)."""
            full_path = workspace.resolve_path(path)
            return [
                {"name": n.name, "type": n.node_type, "file": str(n.file_path), "line": n.start_line}
                for n in discover([full_path])
            ]
        return Tool.from_function(discover_symbols)

    ToolRegistry.register("read_file", "Read file contents", "file_ops", make_read_file)
    ToolRegistry.register("write_file", "Write to file", "file_ops", make_write_file)
    ToolRegistry.register("list_dir", "List directory", "file_ops", make_list_dir)
    ToolRegistry.register("file_exists", "Check file exists", "file_ops", make_file_exists)
    ToolRegistry.register("search_files", "Search by pattern", "file_ops", make_search_files)
    ToolRegistry.register("discover_symbols", "Find code symbols", "code_analysis", make_discover_symbols)

_register_tools()
```

### 3. ChatService (`remora/service/chat_service.py`)

HTTP service exposing chat sessions. This can either:
- **Option A**: Extend the existing RemoraService with new endpoints
- **Option B**: Create a standalone chat-focused service

I recommend **Option B** for cleaner separation:

```python
"""Standalone chat service for the demo."""

import asyncio
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from starlette.applications import Starlette
from starlette.routing import Route
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from sse_starlette.sse import EventSourceResponse

from remora.core.chat import ChatSession, ChatConfig, Message
from remora.core.event_bus import EventBus
from remora.core.events import ToolCallEvent, ToolResultEvent
from remora.core.tool_registry import ToolRegistry


class ChatServiceState:
    """Holds service state."""

    def __init__(self):
        self.sessions: dict[str, ChatSession] = {}
        self.event_buses: dict[str, EventBus] = {}


state = ChatServiceState()


async def create_session(request: Request) -> JSONResponse:
    """Create a new chat session."""
    body = await request.json()

    config = ChatConfig(
        workspace_path=body["workspace_path"],
        system_prompt=body.get("system_prompt", "You are a helpful assistant."),
        tool_presets=body.get("tool_presets", ["file_ops"]),
        model_name=body.get("model_name", "Qwen/Qwen3-4B"),
    )

    # Validate workspace path
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

    return JSONResponse({
        "session_id": session.session_id,
        "workspace_path": str(workspace),
        "tool_presets": config.tool_presets,
    })


async def delete_session(request: Request) -> Response:
    """End a chat session."""
    session_id = request.path_params["session_id"]

    if session_id in state.sessions:
        await state.sessions[session_id].close()
        del state.sessions[session_id]
        del state.event_buses[session_id]

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
        return JSONResponse({
            "message": {
                "id": response.message.id,
                "role": response.message.role,
                "content": response.message.content,
                "timestamp": response.message.timestamp,
                "tool_calls": response.message.tool_calls,
            },
            "turn_count": response.turn_count,
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


async def get_history(request: Request) -> JSONResponse:
    """Get conversation history."""
    session_id = request.path_params["session_id"]

    if session_id not in state.sessions:
        return JSONResponse({"error": "Session not found"}, status_code=404)

    session = state.sessions[session_id]

    return JSONResponse({
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
    })


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
                        "data": json.dumps({
                            "name": event.tool_name,
                            "arguments": event.arguments,
                            "timestamp": event.timestamp,
                        }),
                    }
                elif isinstance(event, ToolResultEvent):
                    yield {
                        "event": "tool_result",
                        "data": json.dumps({
                            "name": event.tool_name,
                            "output": event.output_preview,
                            "is_error": event.is_error,
                            "timestamp": event.timestamp,
                        }),
                    }

    return EventSourceResponse(event_generator())


async def list_tools(request: Request) -> JSONResponse:
    """List available tool presets."""
    return JSONResponse({
        "presets": ToolRegistry.list_presets(),
    })


async def health(request: Request) -> JSONResponse:
    """Health check."""
    return JSONResponse({
        "status": "ok",
        "sessions": len(state.sessions),
    })


# Routes
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
```

---

## Stario Frontend (Python 3.14)

### RemoraClient (`frontend/app/client.py`)

HTTP client for communicating with the Remora backend:

```python
"""HTTP client for Remora Chat Service."""

from dataclasses import dataclass
from typing import Any, AsyncIterator
import httpx


@dataclass
class ToolEvent:
    """A tool execution event."""
    event_type: str  # "tool_call" or "tool_result"
    name: str
    data: dict
    timestamp: float


class RemoraClient:
    """
    Client for the Remora Chat Service.

    Handles HTTP requests and SSE streaming to the backend.
    """

    def __init__(self, base_url: str = "http://127.0.0.1:8420"):
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=120.0)  # Long timeout for LLM

    async def create_session(
        self,
        workspace_path: str,
        system_prompt: str,
        tool_presets: list[str],
    ) -> dict:
        """Create a new chat session."""
        response = await self._client.post(
            f"{self.base_url}/sessions",
            json={
                "workspace_path": workspace_path,
                "system_prompt": system_prompt,
                "tool_presets": tool_presets,
            },
        )
        response.raise_for_status()
        return response.json()

    async def delete_session(self, session_id: str) -> None:
        """End a chat session."""
        response = await self._client.delete(
            f"{self.base_url}/sessions/{session_id}"
        )
        response.raise_for_status()

    async def send_message(self, session_id: str, content: str) -> dict:
        """Send a message and get response."""
        response = await self._client.post(
            f"{self.base_url}/sessions/{session_id}/messages",
            json={"content": content},
        )
        response.raise_for_status()
        return response.json()

    async def get_history(self, session_id: str) -> list[dict]:
        """Get conversation history."""
        response = await self._client.get(
            f"{self.base_url}/sessions/{session_id}/history"
        )
        response.raise_for_status()
        return response.json()["messages"]

    async def stream_events(self, session_id: str) -> AsyncIterator[ToolEvent]:
        """Stream tool events via SSE."""
        import json

        async with self._client.stream(
            "GET",
            f"{self.base_url}/sessions/{session_id}/events",
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("event:"):
                    event_type = line[6:].strip()
                elif line.startswith("data:"):
                    data = json.loads(line[5:].strip())
                    yield ToolEvent(
                        event_type=event_type,
                        name=data["name"],
                        data=data,
                        timestamp=data["timestamp"],
                    )

    async def list_tools(self) -> dict[str, list[str]]:
        """List available tool presets."""
        response = await self._client.get(f"{self.base_url}/tools")
        response.raise_for_status()
        return response.json()["presets"]

    async def health(self) -> bool:
        """Check if backend is healthy."""
        try:
            response = await self._client.get(f"{self.base_url}/health")
            return response.status_code == 200
        except Exception:
            return False

    async def close(self) -> None:
        """Close the client."""
        await self._client.aclose()
```

### State Model (`frontend/app/state.py`)

Same as before, but session management uses the client:

```python
"""Application state model."""

from dataclasses import dataclass, field
from pathlib import Path
import time


@dataclass
class ToolCall:
    """Record of a tool invocation."""
    name: str
    arguments: dict
    result: str | None
    is_error: bool
    timestamp: float


@dataclass
class ChatMessage:
    """A message in the chat."""
    id: str
    role: str
    content: str
    timestamp: float
    tool_calls: list[ToolCall] = field(default_factory=list)


@dataclass
class AgentConfig:
    """Configuration for the agent."""
    system_prompt: str = "You are a helpful assistant with access to file operations."
    enabled_presets: list[str] = field(default_factory=lambda: ["file_ops"])


@dataclass
class DemoState:
    """Complete application state (inbox/outbox pattern)."""

    # Workspace
    workspace_path: str = ""
    workspace_valid: bool = False

    # Agent configuration
    agent_config: AgentConfig = field(default_factory=AgentConfig)

    # Session
    session_id: str | None = None
    session_active: bool = False

    # Chat state (inbox/outbox)
    inbox: list[ChatMessage] = field(default_factory=list)
    outbox: list[ChatMessage] = field(default_factory=list)

    @property
    def messages(self) -> list[ChatMessage]:
        """Interleaved inbox/outbox for display."""
        combined = self.inbox + self.outbox
        return sorted(combined, key=lambda m: m.timestamp)

    # Tool log
    tool_log: list[ToolCall] = field(default_factory=list)

    # UI state
    is_processing: bool = False
    error_message: str | None = None
    backend_connected: bool = False

    @classmethod
    def initial(cls) -> "DemoState":
        return cls()

    def add_user_message(self, id: str, content: str, timestamp: float) -> ChatMessage:
        msg = ChatMessage(id=id, role="user", content=content, timestamp=timestamp)
        self.inbox.append(msg)
        return msg

    def add_agent_message(self, id: str, content: str, timestamp: float, tool_calls: list[ToolCall] | None = None) -> ChatMessage:
        msg = ChatMessage(id=id, role="assistant", content=content, timestamp=timestamp, tool_calls=tool_calls or [])
        self.outbox.append(msg)
        return msg

    def log_tool_call(self, name: str, arguments: dict, result: str | None = None, is_error: bool = False) -> ToolCall:
        call = ToolCall(name=name, arguments=arguments, result=result, is_error=is_error, timestamp=time.time())
        self.tool_log.append(call)
        return call

    def reset_chat(self) -> None:
        self.inbox.clear()
        self.outbox.clear()
        self.tool_log.clear()
```

### Handlers (`frontend/app/handlers.py`)

Updated to use RemoraClient:

```python
"""HTTP request handlers."""

from pathlib import Path
from stario import Context, Writer, Relay
import uuid
import time

from .state import DemoState, ChatMessage, ToolCall
from .views import home_view, chat_view, tool_log_view
from .client import RemoraClient


def home(state: DemoState):
    async def handler(c: Context, w: Writer) -> None:
        w.html(home_view(state))
    return handler


def check_backend(state: DemoState, client: RemoraClient):
    """Check backend connectivity."""
    async def handler(c: Context, w: Writer) -> None:
        state.backend_connected = await client.health()
        w.patch(home_view(state))
    return handler


def set_workspace(state: DemoState):
    async def handler(c: Context, w: Writer) -> None:
        signals = await c.signals()
        path_str = signals.get("workspace_path", "").strip()

        if path_str:
            path = Path(path_str).expanduser().resolve()
            state.workspace_path = str(path)
            state.workspace_valid = path.exists() and path.is_dir()
        else:
            state.workspace_path = ""
            state.workspace_valid = False

        w.patch(home_view(state))
    return handler


def start_session(state: DemoState, client: RemoraClient):
    async def handler(c: Context, w: Writer) -> None:
        signals = await c.signals()

        # Update config
        state.agent_config.system_prompt = signals.get(
            "system_prompt",
            state.agent_config.system_prompt
        )

        try:
            # Create session via backend
            result = await client.create_session(
                workspace_path=state.workspace_path,
                system_prompt=state.agent_config.system_prompt,
                tool_presets=state.agent_config.enabled_presets,
            )

            state.session_id = result["session_id"]
            state.session_active = True
            state.reset_chat()
            state.error_message = None

        except Exception as e:
            state.error_message = f"Failed to start session: {e}"

        w.patch(home_view(state))
    return handler


def stop_session(state: DemoState, client: RemoraClient):
    async def handler(c: Context, w: Writer) -> None:
        if state.session_id:
            try:
                await client.delete_session(state.session_id)
            except Exception:
                pass  # Ignore errors on cleanup

        state.session_id = None
        state.session_active = False
        w.patch(home_view(state))
    return handler


def send_message(state: DemoState, client: RemoraClient, relay: Relay):
    async def handler(c: Context, w: Writer) -> None:
        signals = await c.signals()
        content = signals.get("message_input", "").strip()

        if not content or not state.session_id:
            return w.empty(204)

        # Add user message immediately
        user_msg_id = str(uuid.uuid4())
        state.add_user_message(user_msg_id, content, time.time())
        state.is_processing = True

        w.sync({"message_input": "", "is_processing": True})
        w.patch(chat_view(state))

        try:
            # Send to backend
            result = await client.send_message(state.session_id, content)

            msg = result["message"]
            tool_calls = [
                state.log_tool_call(tc["name"], tc.get("arguments", {}))
                for tc in msg.get("tool_calls", [])
            ]

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
        w.patch(chat_view(state))
        w.patch(tool_log_view(state))

    return handler


def subscribe(state: DemoState, relay: Relay):
    """SSE subscription for real-time updates."""
    async def handler(c: Context, w: Writer) -> None:
        w.patch(home_view(state))

        async for topic, data in w.alive(relay.subscribe("*")):
            if topic == "tool_event":
                state.log_tool_call(
                    name=data["name"],
                    arguments=data.get("arguments", {}),
                    result=data.get("output"),
                    is_error=data.get("is_error", False),
                )
                w.patch(tool_log_view(state))

    return handler
```

### Main Entry Point (`frontend/main.py`)

```python
"""Demo frontend entry point."""

import asyncio
import sys
from pathlib import Path

from stario import Stario, Relay
from stario.tracing import RichTracer, JsonTracer

from app.state import DemoState
from app.handlers import (
    home, check_backend, set_workspace,
    start_session, stop_session, send_message, subscribe,
)
from app.client import RemoraClient


async def main():
    is_dev = "--local" in sys.argv or sys.stdout.isatty()

    if is_dev:
        tracer = RichTracer()
        host, port, workers = "127.0.0.1", 8000, 1
    else:
        tracer = JsonTracer()
        host, port, workers = "0.0.0.0", 8000, 4

    # Shared state
    state = DemoState.initial()
    relay = Relay()
    client = RemoraClient(base_url="http://127.0.0.1:8420")

    # Check backend on startup
    state.backend_connected = await client.health()

    with tracer:
        app = Stario(tracer)

        # Static assets
        app.assets("/static", Path(__file__).parent / "app" / "static")

        # Routes
        app.get("/", home(state))
        app.get("/subscribe", subscribe(state, relay))
        app.post("/check-backend", check_backend(state, client))
        app.post("/set-workspace", set_workspace(state))
        app.post("/start-session", start_session(state, client))
        app.post("/stop-session", stop_session(state, client))
        app.post("/send-message", send_message(state, client, relay))

        print(f"Starting Remora Demo Frontend on http://{host}:{port}")
        print(f"Backend expected at http://127.0.0.1:8420")
        await app.serve(host=host, port=port, workers=workers)


if __name__ == "__main__":
    asyncio.run(main())
```


## Implementation Order

### Phase 1: Remora Backend (Python 3.13)
1. [ ] Create `remora/core/chat.py` (ChatSession)
2. [ ] Create `remora/core/tool_registry.py` (ToolRegistry)
3. [ ] Create `remora/service/chat_service.py` (HTTP endpoints)
4. [ ] Test endpoints with curl/httpie
5. [ ] Test SSE streaming

### Phase 2: Stario Frontend Shell (Python 3.14)
1. [ ] Create frontend directory structure
2. [ ] Implement `client.py` (RemoraClient)
3. [ ] Implement `state.py` (DemoState)
4. [ ] Implement basic `views.py`
5. [ ] Implement `main.py` with routes
6. [ ] Add static CSS

### Phase 3: Integration
1. [ ] Wire up all handlers
2. [ ] Test full flow: create session → send message → see response
3. [ ] Add SSE event streaming from backend to frontend
4. [ ] Tool log real-time updates

### Phase 4: Polish
1. [ ] Error handling and user feedback
2. [ ] Backend health indicator in UI
3. [ ] Startup scripts
4. [ ] Documentation

---

## Open Questions

1. **Backend deployment**: Should chat_service be a separate package or stay in Remora?
2. **Real-time tool events**: Should frontend poll, or establish SSE connection per session?
3. **Model config**: Hardcoded or configurable via UI?

---

*Document version: 2.0*
*Updated to reflect Python version split architecture*
