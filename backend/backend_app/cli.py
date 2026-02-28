"""CLI entrypoint for the Remora demo backend."""

from __future__ import annotations

import uvicorn


def main() -> None:
    uvicorn.run("backend_app.chat_service:app", host="127.0.0.1", port=8420)
