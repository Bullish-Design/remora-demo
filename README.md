# remora-ui (in remora-demo)

This repository now hosts a standalone **Remora Web UI** package that runs on Python 3.14 and connects to a running Remora server over HTTP/SSE.

## Architecture

- Remora server (usually `http://127.0.0.1:8765`) provides:
  - `GET /graph/data`
  - `GET /events` (SSE)
  - `GET /replay`
  - `GET /companion/sidebar/{node_id}`
  - `POST /companion/chat`
  - `GET /companion/workspace/{node_id}`
- This app (`remora-ui`) serves static UI assets on `http://127.0.0.1:8766`.
- Browser loads UI from `:8766` and calls Remora API on `:8765` via CORS.

## Features Implemented

- Full-screen Cytoscape graph view with compound nodes
- Live event log + node flash animations from `/events`
- Node sidebar (markdown) from `/companion/sidebar/{node_id}`
- Node chat from `/companion/chat`
- Cursor-focus graph highlighting from `CursorFocusEvent`
- Replay scrubber using `/replay?graph_id=swarm`

## Quick Start

1. Start Remora server (in the Remora repo):

```bash
devenv shell -- python scripts/start_webserver.py
```

2. Start this UI server (in this repo):

```bash
devenv shell -- uv sync --extra dev
devenv shell -- remora-ui --remora-url http://localhost:8765
```

3. Open:

```text
http://localhost:8766
```

## Environment Variables

- `REMORA_URL` (default `http://localhost:8765`)
- `REMORA_UI_HOST` (default `127.0.0.1`)
- `REMORA_UI_PORT` (default `8766`)

## Local Testing

```bash
devenv shell -- uv sync --extra dev
devenv shell -- pytest -q
```
