"""Start the Remora LSP demo server with EventStore and MockLLM.

Usage (from Neovim or directly)::

    python -m remora_demo

This entry point:
1. Imports the existing Remora LSP server singleton.
2. Hooks into the ``initialized`` notification to wire up:
   - An EventStore backed by ``.remora/indexer.db`` in the workspace root.
   - An AgentRunner using MockLLMClient for deterministic demo responses.
3. Starts the server in stdio mode (for Neovim LSP client).

Requires the ``remora`` library (Python 3.13+) and ``remora_demo.mock_llm``.
"""

from __future__ import annotations

import asyncio
import logging
import os

from lsprotocol import types as lsp

from remora.core.event_store import EventStore
from remora.lsp.runner import AgentRunner
from remora.lsp.server import server

logger = logging.getLogger("remora.demo")


@server.feature(lsp.INITIALIZED)
async def _on_initialized(params: lsp.InitializedParams) -> None:
    """Wire EventStore and MockLLM after the LSP handshake completes."""
    # Resolve workspace root from the LSP initialize params
    root_uri = server.workspace.root_uri or ""
    if root_uri:
        from pygls.uris import to_fs_path

        root_path = to_fs_path(root_uri)
    else:
        root_path = "."

    # Create EventStore at the same DB the graph viewer reads
    db_path = os.path.join(root_path, ".remora", "indexer.db")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    event_store = EventStore(db_path)
    server.event_store = event_store
    logger.info("EventStore initialized at %s", db_path)

    # Create runner with MockLLMClient
    from remora_demo.mock_llm import MockLLMClient

    llm = MockLLMClient()
    runner = AgentRunner(server=server, llm=llm)
    server.runner = runner
    logger.info("AgentRunner created with MockLLMClient")

    # Start the runner's background loops
    asyncio.ensure_future(runner.run_forever())


def main() -> None:
    """Start the Remora LSP demo server in stdio mode."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )
    logger.info("Starting Remora Demo LSP server")
    server.start_io()


if __name__ == "__main__":
    main()
