"""HTTP client for Remora Chat Service."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, AsyncIterator

import httpx


@dataclass
class ToolEvent:
    """A tool execution event."""

    event_type: str
    name: str
    data: dict
    timestamp: float
    call_id: str | None = None


class RemoraClient:
    """Client for the Remora Chat Service."""

    def __init__(self, base_url: str = "http://127.0.0.1:8420"):
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=120.0)

    async def create_session(
        self,
        workspace_path: str,
        system_prompt: str,
        tool_presets: list[str],
    ) -> dict:
        response = await self._client.post(
            f"{self.base_url}/sessions",
            json={
                "workspace_path": workspace_path,
                "system_prompt": system_prompt,
                "tool_presets": tool_presets,
            },
        )
        response.raise_for_status()
        return response.json()

    async def delete_session(self, session_id: str) -> None:
        response = await self._client.delete(
            f"{self.base_url}/sessions/{session_id}"
        )
        response.raise_for_status()

    async def send_message(self, session_id: str, content: str) -> dict:
        response = await self._client.post(
            f"{self.base_url}/sessions/{session_id}/messages",
            json={"content": content},
        )
        response.raise_for_status()
        return response.json()

    async def get_history(self, session_id: str) -> list[dict]:
        response = await self._client.get(
            f"{self.base_url}/sessions/{session_id}/history"
        )
        response.raise_for_status()
        return response.json()["messages"]

    async def stream_events(self, session_id: str) -> AsyncIterator[ToolEvent]:
        import json

        event_type: str | None = None
        data_payload: dict[str, Any] | None = None

        async with self._client.stream(
            "GET",
            f"{self.base_url}/sessions/{session_id}/events",
            headers={"accept": "text/event-stream"},
        ) as response:
            async for line in response.aiter_lines():
                if not line:
                    if event_type and data_payload:
                        yield ToolEvent(
                            event_type=event_type,
                            name=data_payload.get("name", ""),
                            data=data_payload,
                            timestamp=data_payload.get("timestamp", 0.0),
                            call_id=data_payload.get("call_id"),
                        )
                    event_type = None
                    data_payload = None
                    continue

                if line.startswith(":"):
                    continue

                if line.startswith("event:"):
                    event_type = line[6:].strip()
                elif line.startswith("data:"):
                    payload = line[5:].strip()
                    if payload:
                        data_payload = json.loads(payload)
                        if event_type is None:
                            event_type = "message"

        # Stream ended; no further events.

    async def list_tools(self) -> dict[str, list[str]]:
        response = await self._client.get(f"{self.base_url}/tools")
        response.raise_for_status()
        return response.json()["presets"]

    async def health(self) -> bool:
        try:
            response = await self._client.get(f"{self.base_url}/health")
            return response.status_code == 200
        except Exception:
            return False

    async def close(self) -> None:
        await self._client.aclose()
