"""Refactor swarm demo frontend entry point."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from stario import JsonTracer, Relay, RichTracer, Stario

from refactor_app.client import RefactorClient
from refactor_app.handlers import (
    check_backend,
    home,
    plan_graph,
    run_graph,
    subscribe,
)
from refactor_app.handlers import ask_agent, pump_events, send_agent_message, submit_input
from refactor_app.state import RefactorState


async def main() -> None:
    is_dev = "--local" in sys.argv or sys.stdout.isatty()

    if is_dev:
        tracer = RichTracer()
        host, port, workers = "127.0.0.1", 8001, 1
    else:
        tracer = JsonTracer()
        host, port, workers = "0.0.0.0", 8001, 4

    state = RefactorState()
    relay = Relay()

    base_url = os.environ.get("REFACTOR_BACKEND_URL", "http://127.0.0.1:8421")
    client = RefactorClient(base_url=base_url)

    state.backend_connected = await client.health()
    if state.backend_connected:
        try:
            config = await client.config()
            mapping = config.get("bundles", {}).get("mapping", {})
            if isinstance(mapping, dict):
                state.available_bundles = sorted(mapping.keys())
        except Exception:
            state.available_bundles = []
        state.event_stream_task = asyncio.create_task(pump_events(state, client, relay))

    with tracer:
        app = Stario(tracer)
        app.assets("/static", Path(__file__).parent / "app" / "static")

        app.get("/", home(state))
        app.get("/subscribe", subscribe(state, relay))
        app.post("/check-backend", check_backend(state, client, relay))
        app.post("/plan-graph", plan_graph(state, client))
        app.post("/run-graph", run_graph(state, client, relay))
        app.post("/submit-input", submit_input(state, client))
        app.post("/agent-message", send_agent_message(state, client))
        app.post("/agent-ask", ask_agent(state, client))

        print(f"Starting Refactor Swarm Frontend on http://{host}:{port}")
        print(f"Backend expected at {base_url}")
        await app.serve(host=host, port=port, workers=workers)


def cli() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    cli()
