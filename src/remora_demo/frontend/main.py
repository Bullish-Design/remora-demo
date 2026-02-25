"""
Remora Frontend - Stario app that proxies to hub.

This is a minimal Stario app that:
1. Serves the SPA on /
2. Proxies /subscribe to hub's SSE (pass-through)
3. Proxies API calls to hub
"""

import html
import logging
from dataclasses import dataclass
from pathlib import Path

import aiohttp

from stario import Context, RichTracer, Stario, Writer
from stario.html import Div

from .views import home_view, render_home

HUB_URL = "http://localhost:8000"

logger = logging.getLogger(__name__)


@dataclass
class ExecuteSignals:
    graph_id: str = ""
    bundle: str = "default"
    target: str = ""
    target_path: str = ""


@dataclass
class RespondSignals:
    agent_id: str = ""
    msg_id: str = ""
    question: str = ""
    answer: str = ""


async def home(c: Context, w: Writer) -> None:
    """Serve the SPA."""
    w.html(home_view())


async def subscribe(c: Context, w: Writer) -> None:
    """
    Proxy SSE from hub to browser.

    This is a STREAMING proxy:
    1. Connect to hub's /subscribe
    2. Pass through chunks as they arrive
    3. Datastar on the browser understands these as SSE events

    Key: We're not transforming the data, just passing it through.
    The hub already sends correct Datastar-formatted SSE patches.
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{HUB_URL}/subscribe") as resp:
                async for chunk in resp.content.iter_any():
                    w.write(chunk)
    except aiohttp.ClientError as e:
        logger.error(f"Failed to connect to hub: {e}")
        w.write(b"")


async def execute_graph(c: Context, w: Writer) -> None:
    """Proxy graph execution to hub."""
    signals = await c.signals(ExecuteSignals)

    payload = {"graph_id": signals.graph_id}
    if signals.bundle:
        payload["bundle"] = signals.bundle
    if signals.target:
        payload["target"] = signals.target
    if signals.target_path:
        payload["target_path"] = signals.target_path

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{HUB_URL}/graph/execute", json=payload) as resp:
                result = await resp.json()
                w.json(result)
    except aiohttp.ClientError as e:
        logger.error(f"Failed to execute graph: {e}")
        w.json({"error": str(e)})


async def respond(c: Context, w: Writer) -> None:
    """Proxy agent response to hub - user responds to blocked agent."""
    # Extract agent_id from the tail path (e.g., /agent/agent-1/respond -> agent_id = agent-1)
    tail = c.req.tail or ""
    parts = tail.strip("/").split("/")
    agent_id = parts[0] if parts else ""

    signals = await c.signals(RespondSignals)

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{HUB_URL}/agent/{agent_id}/respond",
                json={
                    "msg_id": signals.msg_id,
                    "question": signals.question,
                    "answer": signals.answer,
                },
            ) as resp:
                result = await resp.json()
                w.json(result)
    except aiohttp.ClientError as e:
        logger.error(f"Failed to send response: {e}")
        w.json({"error": str(e)})


async def list_files(c: Context, w: Writer) -> None:
    """Fetch file list from hub and render the file picker UI."""
    path = c.req.query.get("path", "")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{HUB_URL}/api/files", params={"path": path} if path else {}) as resp:
                result = await resp.json()

                if resp.status >= 400:
                    error = result.get("error", "Unknown error")
                    w.patch(Div({"id": "file-picker-list"}, f"Error: {error}"))
                    w.sync({"filePickerError": error})
                    return

                entries = result.get("entries", [])
                current_path = result.get("path", path)

                items_html = "".join(
                    _render_file_item(e["name"], e["type"] == "directory", e.get("size"))
                    for e in sorted(entries, key=lambda e: (e["type"] != "directory", e["name"]))
                )

                if not items_html:
                    items_html = '<div class="empty-state">No files</div>'

                w.patch(Div({"id": "file-picker-list"}, items_html))
                w.sync({"filePickerPath": current_path, "filePickerError": ""})

    except aiohttp.ClientError as e:
        logger.error(f"Failed to list files: {e}")
        w.patch(Div({"id": "file-picker-list"}, f"Error: {e}"))


def _render_file_item(name: str, is_dir: bool, size: int | None = None) -> str:
    """Render a single file/directory entry. Uses html.escape for security."""
    icon = "📁" if is_dir else "📄"
    size_str = f" ({size})" if size and not is_dir else ""
    safe_name = html.escape(name)

    if is_dir:
        return f"""<div class="file-item directory">
            <button type="button" class="file-item-btn" 
                data-on-click="$graphLauncher.filePickerPath = $graphLauncher.filePickerPath 
                    ? $graphLauncher.filePickerPath + '/{safe_name}' 
                    : '{safe_name}';
                @get('/api/files?path=' + $graphLauncher.filePickerPath);">
                {icon} {safe_name}/
            </button>
        </div>"""
    else:
        return f"""<div class="file-item file">
            <button type="button" class="file-item-btn"
                data-on-click="$graphLauncher.targetPath = $graphLauncher.filePickerPath 
                    ? $graphLauncher.filePickerPath + '/{safe_name}' 
                    : '{safe_name}';
                $graphLauncher.filePickerOpen = false;">
                {icon} {safe_name}{size_str}
            </button>
        </div>"""


async def run_app() -> None:
    """Run the Remora Frontend server."""
    tracer = RichTracer()

    with tracer:
        app = Stario(tracer)

        app.assets("/static", Path("src/remora_demo/static"))

        app.get("/", home)
        app.get("/subscribe", subscribe)
        app.get("/api/files", list_files)
        app.post("/graph/execute", execute_graph)
        app.post("/agent/*", respond)

        await app.serve(host="0.0.0.0", port=8001)


def main() -> None:
    """Entry point for the remora-frontend script."""
    logging.basicConfig(level=logging.INFO)
    import asyncio

    asyncio.run(run_app())


if __name__ == "__main__":
    main()
