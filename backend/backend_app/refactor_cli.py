"""CLI entrypoint for the refactor swarm backend."""

from __future__ import annotations

import uvicorn


def main() -> None:
    uvicorn.run("backend_app.refactor_service:app", host="127.0.0.1", port=8421)

