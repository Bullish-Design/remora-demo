# MVP Demo Refactoring Plan

This document provides a detailed analysis of the current state and a step-by-step plan to get the Remora Demo UI working end-to-end.

---

## Executive Summary

**Current State**: The demo has a complete frontend (Stario/Python 3.14) and a thin backend wrapper (Python 3.13), but the system fails because:

1. The backend service is not running or not reachable
2. Python version split (3.13 vs 3.14) requires separate environments that may not be properly activated
3. Missing/incomplete dependency chains in the Remora library for chat functionality
4. Tool registration fails if `structured-agents` is not installed

**Goal**: Get the demo to:
- Start backend on port 8420 (Python 3.13)
- Start frontend on port 8000 (Python 3.14)
- Successfully create sessions, send messages, and see tool events

---

## Part 1: Root Cause Analysis

### 1.1 Architecture Recap

```
┌─────────────────────────────────┐     ┌─────────────────────────────────┐
│  Stario Frontend (Python 3.14)  │     │  Remora Backend (Python 3.13)   │
│  Port 8000                      │────▶│  Port 8420                      │
│                                 │ HTTP│                                 │
│  - Reactive UI (Datastar)       │ SSE │  - ChatSession                  │
│  - RemoraClient (httpx)         │     │  - ToolRegistry                 │
│  - DemoState                    │     │  - EventBus → SSE streaming     │
└─────────────────────────────────┘     └─────────────────────────────────┘
                                                       │
                                                       │ HTTP (OpenAI API)
                                                       ▼
                                        ┌─────────────────────────────────┐
                                        │  vLLM Server                    │
                                        │  Port 8000 (default)            │
                                        │  Model: Qwen/Qwen3-4B           │
                                        └─────────────────────────────────┘
```

### 1.2 Issue: Backend Not Running

**Symptom**: Frontend shows "backend: offline"

**Cause**: The backend is just a thin wrapper (`backend_app/cli.py`) that calls:
```python
uvicorn.run("remora.service.chat_service:app", host="127.0.0.1", port=8420)
```

This requires:
1. Python 3.13 environment activated
2. Remora package installed with all dependencies
3. `structured-agents` available (for tool creation)
4. Cairn workspace service functional

**Current backend code** (10 lines total) has no error handling or validation.

### 1.3 Issue: Remora Module Chain

The chat service imports from multiple Remora modules:

```
chat_service.py
├── remora.core.chat (ChatSession, ChatConfig, Message)
│   ├── remora.core.event_bus (EventBus)
│   ├── remora.core.cairn_bridge (CairnWorkspaceService)
│   ├── remora.core.config (WorkspaceConfig)
│   └── remora.core.tool_registry (ToolRegistry)
│       └── structured_agents (Tool, AgentKernel, ModelAdapter)
├── remora.core.events (ToolCallEvent, ToolResultEvent)
└── remora.core.tool_registry (ToolRegistry)
    └── Calls _register_tools() at import time
```

If ANY of these fail to import, the backend won't start.

### 1.4 Issue: Tool Registration at Import Time

`tool_registry.py` (line 108) calls `_register_tools()` when the module loads:
```python
_register_tools()  # Called at module import!
```

Inside `_register_tools()`:
```python
from structured_agents import Tool  # Fails if not installed
```

**Impact**: The entire module fails if structured-agents isn't available.

### 1.5 Issue: CairnWorkspaceService Initialization

In `chat.py:108-119`, session initialization creates a Cairn workspace:
```python
workspace_config = WorkspaceConfig(
    base_path=str(workspace_path / ".remora" / "workspaces"),
)
self._workspace = CairnWorkspaceService(
    config=workspace_config,
    graph_id=self.session_id,
    project_root=workspace_path,
)
await self._workspace.initialize()
```

This requires:
- `cairn` package installed
- Write permissions to create `.remora/workspaces/` directory
- Proper async initialization

### 1.6 Issue: vLLM Server Assumption

`ChatConfig` defaults to:
```python
model_base_url: str = "http://localhost:8000/v1"
model_name: str = "Qwen/Qwen3-4B"
```

**Problem**: Port 8000 conflicts with the frontend! The frontend also listens on 8000.

### 1.7 Issue: SSE Event Streaming

The event streaming in `chat_service.py:130-162` uses:
```python
async with event_bus.stream(ToolCallEvent, ToolResultEvent) as events:
```

This depends on:
- EventBus.stream() working correctly
- ToolCallEvent/ToolResultEvent being emitted by the AgentKernel
- The kernel being configured with `observer=self.event_bus`

---

## Part 2: Required Changes

### Phase 1: Backend Fixes (Remora Library)

#### 1.1 Fix Port Conflict

**File**: `.context/remora_v0.4.8/src/remora/core/chat.py`

**Change**: Update default model URL to avoid frontend port conflict:
```python
# Line 54: Change from
model_base_url: str = "http://localhost:8000/v1"

# To:
model_base_url: str = "http://remora-server:8000/v1"
```

Or better, make it configurable via environment variable.

#### 1.2 Lazy Tool Registration

**File**: `.context/remora_v0.4.8/src/remora/core/tool_registry.py`

**Change**: Remove automatic registration at import time. Instead, register on first use:

```python
# Remove line 108:
# _register_tools()

# Add lazy initialization:
_tools_registered = False

@classmethod
def _ensure_registered(cls):
    global _tools_registered
    if not _tools_registered:
        _register_tools()
        _tools_registered = True

@classmethod
def get_tools(cls, workspace: Any, presets: list[str]) -> list[Any]:
    cls._ensure_registered()  # Add this line
    # ... rest of method
```

This prevents import failures when structured-agents isn't installed yet.

#### 1.3 Add Graceful Error Handling

**File**: `.context/remora_v0.4.8/src/remora/service/chat_service.py`

**Change**: Add startup validation and better error messages:

```python
# Add at top of file:
import logging
logger = logging.getLogger(__name__)

# Add startup event:
@app.on_event("startup")
async def startup_event():
    logger.info("Chat service starting...")
    try:
        from structured_agents import AgentKernel
        logger.info("structured-agents: OK")
    except ImportError as e:
        logger.error(f"structured-agents not available: {e}")
        logger.error("Install with: pip install structured-agents")

    try:
        from cairn import Cairn
        logger.info("cairn: OK")
    except ImportError as e:
        logger.error(f"cairn not available: {e}")
```

#### 1.4 Fix CairnWorkspaceService Interface

**File**: `.context/remora_v0.4.8/src/remora/core/chat.py`

Review and fix the workspace initialization. The current code may have method signature mismatches with the actual CairnWorkspaceService implementation.

**Potential issue** at line 121-122:
```python
agent_workspace = await self._workspace.get_agent_workspace(self.session_id)
externals = self._workspace.get_externals(self.session_id, agent_workspace)
```

These methods need to exist and have compatible signatures.

#### 1.5 Add Mock/Fallback Mode

For demo purposes, add a mock mode that works without vLLM:

**File**: `.context/remora_v0.4.8/src/remora/core/chat.py`

```python
@dataclass
class ChatConfig:
    # ... existing fields
    mock_mode: bool = False  # Add this

async def send(self, content: str) -> AgentResponse:
    if self.config.mock_mode:
        return self._mock_response(content)
    # ... rest of implementation
```

---

### Phase 2: Backend Service Improvements

#### 2.1 Improve CLI Entry Point

**File**: `backend/backend_app/cli.py`

Replace the minimal 10-line implementation with proper startup:

```python
"""CLI entrypoint for the Remora demo backend."""

from __future__ import annotations

import os
import sys
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def check_dependencies() -> bool:
    """Validate required packages are available."""
    missing = []

    try:
        import remora
        logger.info(f"remora: {remora.__version__ if hasattr(remora, '__version__') else 'OK'}")
    except ImportError:
        missing.append("remora")

    try:
        import structured_agents
        logger.info("structured-agents: OK")
    except ImportError:
        missing.append("structured-agents")

    try:
        import starlette
        logger.info("starlette: OK")
    except ImportError:
        missing.append("starlette")

    if missing:
        logger.error(f"Missing packages: {', '.join(missing)}")
        logger.error("Run: uv sync")
        return False

    return True


def main() -> None:
    """Start the backend service."""
    logger.info("Remora Demo Backend")
    logger.info("=" * 40)

    if not check_dependencies():
        sys.exit(1)

    import uvicorn

    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8420"))

    logger.info(f"Starting on http://{host}:{port}")
    logger.info("Endpoints:")
    logger.info("  POST   /sessions           - Create session")
    logger.info("  DELETE /sessions/{id}      - Delete session")
    logger.info("  POST   /sessions/{id}/messages - Send message")
    logger.info("  GET    /sessions/{id}/events   - SSE stream")
    logger.info("  GET    /tools              - List tool presets")
    logger.info("  GET    /health             - Health check")

    uvicorn.run(
        "remora.service.chat_service:app",
        host=host,
        port=port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
```

#### 2.2 Add Health Check Improvements

**File**: `.context/remora_v0.4.8/src/remora/service/chat_service.py`

Enhance the health endpoint to report more status:

```python
async def health(request: Request) -> JSONResponse:
    """Health check with dependency status."""
    status = {
        "status": "ok",
        "sessions": len(state.sessions),
        "dependencies": {}
    }

    try:
        from structured_agents import AgentKernel
        status["dependencies"]["structured_agents"] = "ok"
    except ImportError:
        status["dependencies"]["structured_agents"] = "missing"
        status["status"] = "degraded"

    try:
        from cairn import Cairn
        status["dependencies"]["cairn"] = "ok"
    except ImportError:
        status["dependencies"]["cairn"] = "missing"
        status["status"] = "degraded"

    return JSONResponse(status)
```

---

### Phase 3: Frontend Improvements

#### 3.1 Better Backend Status Display

**File**: `frontend/app/views.py`

Update status_view to show more details when backend is offline:

```python
def status_view(state: DemoState):
    status_items = [
        pill("backend", state.backend_connected),
        pill("session", state.session_active),
        pill("stream", state.event_stream_active, neutral_if_false=True),
    ]

    error_content = []
    if state.error_message:
        error_content.append(Div({"class": "error-banner"}, state.error_message))

    if not state.backend_connected:
        error_content.append(
            Div({"class": "info-banner"},
                "Backend not reachable. Start it with: ",
                Span({"class": "code"}, "cd backend && devenv shell && start-backend")
            )
        )

    return Div(
        {"id": "status-panel"},
        Div({"class": "status-row"}, *status_items),
        *error_content,
    )
```

#### 3.2 Add Retry Logic for Backend Connection

**File**: `frontend/main.py`

Add retry logic on startup:

```python
async def wait_for_backend(client: RemoraClient, max_attempts: int = 5) -> bool:
    """Wait for backend to become available."""
    for attempt in range(max_attempts):
        if await client.health():
            return True
        print(f"Waiting for backend... ({attempt + 1}/{max_attempts})")
        await asyncio.sleep(2)
    return False
```

#### 3.3 Add Backend URL Configuration

**File**: `frontend/main.py`

Support environment variable for backend URL:

```python
import os

backend_url = os.environ.get("REMORA_BACKEND_URL", "http://127.0.0.1:8420")
client = RemoraClient(base_url=backend_url)
```

---

### Phase 4: Startup Scripts

#### 4.1 Create `scripts/start-backend.sh`

```bash
#!/bin/bash
# Start the Remora backend (Python 3.13)

set -e
cd "$(dirname "$0")/../backend"

echo "=== Remora Demo Backend ==="

# Check for devenv
if command -v devenv &> /dev/null; then
    echo "Using devenv..."
    exec devenv shell -- start-backend
else
    echo "devenv not found, trying direct Python..."

    # Try to find Python 3.13
    PYTHON=""
    for py in python3.13 python3; do
        if command -v "$py" &> /dev/null; then
            version=$("$py" --version 2>&1 | grep -oE '[0-9]+\.[0-9]+')
            if [[ "$version" == "3.13" ]]; then
                PYTHON="$py"
                break
            fi
        fi
    done

    if [[ -z "$PYTHON" ]]; then
        echo "ERROR: Python 3.13 required but not found"
        exit 1
    fi

    # Ensure venv exists
    if [[ ! -d ".venv" ]]; then
        echo "Creating virtual environment..."
        "$PYTHON" -m venv .venv
        source .venv/bin/activate
        pip install -e .
    else
        source .venv/bin/activate
    fi

    exec python -m backend_app.cli
fi
```

#### 4.2 Create `scripts/start-frontend.sh`

```bash
#!/bin/bash
# Start the Stario frontend (Python 3.14)

set -e
cd "$(dirname "$0")/../frontend"

echo "=== Remora Demo Frontend ==="

if command -v devenv &> /dev/null; then
    echo "Using devenv..."
    exec devenv shell -- python main.py --local
else
    # Try direct Python 3.14
    PYTHON=""
    for py in python3.14 python3; do
        if command -v "$py" &> /dev/null; then
            version=$("$py" --version 2>&1 | grep -oE '[0-9]+\.[0-9]+')
            if [[ "$version" == "3.14" ]]; then
                PYTHON="$py"
                break
            fi
        fi
    done

    if [[ -z "$PYTHON" ]]; then
        echo "WARNING: Python 3.14 required. Trying system Python..."
        PYTHON="python3"
    fi

    if [[ ! -d ".venv" ]]; then
        echo "Creating virtual environment..."
        "$PYTHON" -m venv .venv
        source .venv/bin/activate
        pip install -e .
    else
        source .venv/bin/activate
    fi

    exec python main.py --local
fi
```

#### 4.3 Create `scripts/start-all.sh`

```bash
#!/bin/bash
# Start both backend and frontend

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== Starting Remora Demo ==="

# Start backend in background
echo "Starting backend..."
"$SCRIPT_DIR/start-backend.sh" &
BACKEND_PID=$!

# Wait for backend
echo "Waiting for backend to be ready..."
for i in {1..30}; do
    if curl -sf http://127.0.0.1:8420/health > /dev/null 2>&1; then
        echo "Backend ready!"
        break
    fi
    if ! kill -0 $BACKEND_PID 2>/dev/null; then
        echo "ERROR: Backend process died"
        exit 1
    fi
    sleep 1
done

# Check if backend is actually ready
if ! curl -sf http://127.0.0.1:8420/health > /dev/null 2>&1; then
    echo "ERROR: Backend failed to start within 30 seconds"
    kill $BACKEND_PID 2>/dev/null
    exit 1
fi

# Trap to cleanup on exit
cleanup() {
    echo "Shutting down..."
    kill $BACKEND_PID 2>/dev/null
}
trap cleanup EXIT

# Start frontend (foreground)
echo "Starting frontend..."
"$SCRIPT_DIR/start-frontend.sh"
```

---

## Part 3: Testing Plan

### 3.1 Test Backend Isolation

```bash
# Terminal 1: Start backend only
cd backend
devenv shell
start-backend

# Terminal 2: Test endpoints
curl http://127.0.0.1:8420/health
curl http://127.0.0.1:8420/tools
curl -X POST http://127.0.0.1:8420/sessions \
  -H "Content-Type: application/json" \
  -d '{"workspace_path": "/tmp/test", "system_prompt": "You are helpful."}'
```

### 3.2 Test Frontend Isolation

```bash
# With backend running
cd frontend
devenv shell
python main.py --local

# Open http://127.0.0.1:8000
# Should show "backend: online"
```

### 3.3 End-to-End Test

1. Start backend
2. Start frontend
3. Open http://127.0.0.1:8000
4. Enter workspace path (e.g., `/tmp/test-workspace`)
5. Click "Check backend" - should show green
6. Click "Start session" - should succeed
7. Type a message and send
8. Verify tool events appear (if tools are called)

---

## Part 4: Implementation Order

### Step 1: Fix Remora Library (1-2 hours)

1. [ ] Fix port conflict in ChatConfig (8000 → 8080)
2. [ ] Make tool registration lazy
3. [ ] Add startup validation to chat_service.py
4. [ ] Verify CairnWorkspaceService interface matches usage

### Step 2: Improve Backend CLI (30 min)

1. [ ] Add dependency checking
2. [ ] Add helpful startup messages
3. [ ] Support environment variables for host/port

### Step 3: Create Startup Scripts (30 min)

1. [ ] Create start-backend.sh
2. [ ] Create start-frontend.sh
3. [ ] Create start-all.sh
4. [ ] Make scripts executable

### Step 4: Frontend Polish (30 min)

1. [ ] Add backend URL env var support
2. [ ] Improve error messages when backend offline
3. [ ] Add startup help text

### Step 5: Testing (1 hour)

1. [ ] Test backend in isolation
2. [ ] Test frontend in isolation
3. [ ] Test full integration
4. [ ] Document any remaining issues

---

## Part 5: Potential Remora Library Modifications

Based on the analysis, here are modifications we may need to make to the Remora library:

### 5.1 CairnWorkspaceService Methods

The `chat.py` calls methods that may not exist:
- `get_agent_workspace(session_id)` - verify this exists
- `get_externals(session_id, workspace)` - verify this exists
- `read_file(path)`, `write_file(path, content)`, etc. - verify workspace interface

**Action**: Compare `chat.py` usage against `cairn_bridge.py` implementation.

### 5.2 Event Bus Integration

The chat service assumes `event_bus.stream()` works with specific event types. Verify:
- `EventBus.stream()` accepts event type filters
- Returns an async context manager
- Yields events correctly

**Action**: Review `event_bus.py` implementation.

### 5.3 Tool Creation

Tools use `Tool.from_function()` from structured-agents. Verify:
- The function signature is correct
- Async functions are supported
- Return values are serializable

---

## Part 6: Quick Start (After Implementation)

Once all changes are made:

```bash
# Clone and setup
git clone <repo>
cd remora-demo

# Start everything
./scripts/start-all.sh

# Or start separately:
# Terminal 1:
./scripts/start-backend.sh

# Terminal 2:
./scripts/start-frontend.sh

# Open browser
open http://127.0.0.1:8000
```

---

## Appendix: File Summary

| File | Purpose | Status |
|------|---------|--------|
| `backend/backend_app/cli.py` | Backend entry point | Needs expansion |
| `frontend/main.py` | Frontend entry point | Minor improvements needed |
| `frontend/app/client.py` | HTTP client to backend | Working |
| `frontend/app/state.py` | UI state management | Working |
| `frontend/app/handlers.py` | Request handlers | Working |
| `frontend/app/views.py` | HTML rendering | Minor improvements |
| `.context/remora_v0.4.8/src/remora/core/chat.py` | ChatSession | Port fix needed |
| `.context/remora_v0.4.8/src/remora/core/tool_registry.py` | Tool management | Lazy init needed |
| `.context/remora_v0.4.8/src/remora/service/chat_service.py` | HTTP API | Startup validation needed |
| `scripts/start-*.sh` | Startup scripts | Need to create |

---

*Document version: 1.0*
*Created: 2026-02-27*
