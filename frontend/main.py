"""Demo frontend entry point."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from stario import Relay, Stario
from stario.tracing import JsonTracer, RichTracer

from app.client import RemoraClient
from app.handlers import (
    check_backend,
    home,
    send_message,
    set_workspace,
    start_session,
    stop_session,
    subscribe,
)
from app.state import DemoState


async def main() -> None:
    is_dev = "--local" in sys.argv or sys.stdout.isatty()

    if is_dev:
        tracer = RichTracer()
        host, port, workers = "127.0.0.1", 8000, 1
    else:
        tracer = JsonTracer()
        host, port, workers = "0.0.0.0", 8000, 4

    state = DemoState.initial()
    relay = Relay()
    client = RemoraClient(base_url="http://127.0.0.1:8420")

    state.backend_connected = await client.health()
    if state.backend_connected:
        try:
            presets = await client.list_tools()
            state.available_presets = sorted(presets.keys())
        except Exception:
            state.available_presets = ["file_ops", "code_analysis", "all"]

    with tracer:
        app = Stario(tracer)
        app.assets("/static", Path(__file__).parent / "app" / "static")

        app.get("/", home(state))
        app.get("/subscribe", subscribe(state, relay))
        app.post("/check-backend", check_backend(state, client))
        app.post("/set-workspace", set_workspace(state))
        app.post("/start-session", start_session(state, client, relay))
        app.post("/stop-session", stop_session(state, client))
        app.post("/send-message", send_message(state, client))

        print(f"Starting Remora Demo Frontend on http://{host}:{port}")
        print("Backend expected at http://127.0.0.1:8420")
        await app.serve(host=host, port=port, workers=workers)


def cli() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    cli()
