"""Remora Web UI standalone Starlette server."""

from __future__ import annotations

from pathlib import Path

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from remora_ui.config import RemoraUIConfig

STATIC_DIR = Path(__file__).parent / "static"


def create_app(config: RemoraUIConfig | None = None) -> Starlette:
    """Build and return the Starlette application."""
    cfg = config or RemoraUIConfig()

    async def index(_request: Request) -> HTMLResponse:
        html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
        html = html.replace("__REMORA_BASE_URL__", cfg.remora_base_url)
        return HTMLResponse(html)

    async def api_config(_request: Request) -> JSONResponse:
        return JSONResponse({"remora_base_url": cfg.remora_base_url})

    routes = [
        Route("/", index),
        Route("/config.json", api_config),
        Mount("/static", StaticFiles(directory=STATIC_DIR), name="static"),
    ]

    return Starlette(routes=routes)


def main() -> None:
    """CLI entry point for `remora-ui`."""
    import argparse

    import uvicorn

    parser = argparse.ArgumentParser(description="Remora Web UI server")
    parser.add_argument(
        "--remora-url",
        default=None,
        help=(
            "Base URL of remora HTTP server "
            "(default: from env or http://localhost:8765)"
        ),
    )
    parser.add_argument("--host", default=None, help="Bind host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=None, help="Bind port (default: 8766)")
    args = parser.parse_args()

    cfg = RemoraUIConfig.from_env()
    if args.remora_url:
        cfg.remora_base_url = args.remora_url
    if args.host:
        cfg.host = args.host
    if args.port:
        cfg.port = args.port

    app = create_app(cfg)
    uvicorn.run(app, host=cfg.host, port=cfg.port, log_level="info")


if __name__ == "__main__":
    main()
