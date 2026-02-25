# UI Graph Launch Documentation

## Overview

The Remora frontend provides a web UI for interacting with the Remora Hub. It allows users to:
1. Launch new agent graphs from the UI
2. Monitor agent events in real-time
3. Respond to blocked agents requiring user input

## Architecture

```
┌─────────────────┐    proxy     ┌─────────────────┐
│  Frontend       │ ──────────▶ │  Hub            │
│  (Stario)       │ ◀───────── │  (Starlette)    │
│  Port 8001      │   SSE      │  Port 8000      │
└─────────────────┘            └─────────────────┘
```

- **Frontend**: Stario app on port 8001 - serves SPA, proxies requests to hub
- **Hub**: Starlette + datastar-py on port 8000 - runs agents, publishes SSE events

## Launching a Graph

### From the UI

1. Open browser to `http://localhost:8001`
2. Fill in the "Launch Graph" form:
   - **Graph ID** (required): Unique identifier for this graph execution
   - **Bundle** (optional): Agent bundle name, defaults to "default"
   - **Target** (optional): Description or code for the agent to operate on
   - **Target file path** (optional): Path to a file on the system to analyze
3. Click "Start Graph"

### Programmatic (curl)

Launch with just a graph ID:
```bash
curl -X POST http://localhost:8001/graph/execute \
  -H "Content-Type: application/json" \
  -d '{"graph_id": "my-graph-1", "bundle": "default", "target": "Analyze this code"}'
```

Launch with a file path (creates agents based on that file):
```bash
curl -X POST http://localhost:8001/graph/execute \
  -H "Content-Type: application/json" \
  -d '{"graph_id": "my-graph-1", "target_path": "/home/user/myproject/main.py"}'
```

Or directly to hub:

```bash
curl -X POST http://localhost:8000/graph/execute \
  -H "Content-Type: application/json" \
  -d '{"graph_id": "my-graph-1"}'
```

## What Happens When You Launch

1. **Frontend** receives POST to `/graph/execute` with signal payload
2. **Frontend** proxies request to hub: `POST http://localhost:8000/graph/execute`
3. **Hub**:
   - Creates `GraphWorkspace` with the `graph_id`
   - Builds `AgentGraph` with agents based on bundle/target
   - Registers agents with workspace
   - Starts executing graph asynchronously
   - Publishes events to EventBus
4. **Frontend** subscribes to `/subscribe` SSE endpoint
5. **Hub** streams SSE patches with dashboard view updates
6. **Frontend** receives and Datastar applies patches to DOM

## Key Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Serve SPA |
| `/subscribe` | GET | SSE stream (proxied from hub) |
| `/graph/execute` | POST | Launch new graph |
| `/agent/{agent_id}/respond` | POST | Respond to blocked agent |
| `/static/*` | GET | Serve static assets |

## Signal Payloads

### Launch Graph

```json
{
  "graph_id": "unique-graph-id",
  "bundle": "default",
  "target": "optional target description",
  "target_path": "/path/to/file.py"
}
```

All fields except `graph_id` are optional. Use `target_path` to specify a file on your system that the agents should analyze.

### Respond to Agent

```json
{
  "msg_id": "message-id-from-blocked-event",
  "question": "question text",
  "answer": "user's response"
}
```

## Real-time Updates

The UI uses Datastar with SSE to receive real-time updates:

1. Initial page load sets signals via `data-signals__ifmissing`
2. `data-init="@get('/subscribe')"` opens SSE connection
3. Hub publishes events → state updates → new view rendered
4. SSE patches (`datastar-patch-elements`) are streamed to frontend
5. Datastar applies patches to DOM, morphing existing elements

## CSS Classes

- `.graph-launcher-card` - Launch Graph form card
- `.graph-launcher-form` - Form container with inputs
- `.header` - Page header
- `.card` - Content cards (blocked agents, status, results)
- `.events-list` - Event stream container
- `.blocked-agent` - Blocked agent with response form
- `.state-indicator` - Agent state indicator (started/blocked/completed/failed)

## Troubleshooting

### Frontend not loading
- Check hub is running on port 8000
- Check frontend is running on port 8001
- Verify browser console for errors
- Check network tab for `/subscribe` SSE stream

### Graph not starting
- Check hub logs for execution errors
- Verify `graph_id` is provided
- Check bundle name is valid

### Events not updating
- Verify `/subscribe` endpoint is receiving chunks
- Check browser console for Datastar errors
- Ensure hub is publishing events
