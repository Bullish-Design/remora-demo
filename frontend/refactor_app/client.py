"""HTTP client for the refactor swarm backend."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import AsyncIterator

import httpx


@dataclass
class StreamEvent:
    event_type: str
    payload: dict


class RefactorClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    async def health(self) -> bool:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.base_url}/health")
            return response.status_code == 200
        except Exception:
            return False

    async def config(self) -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.base_url}/config")
        response.raise_for_status()
        return response.json()

    async def plan(self, target_path: str, bundle: str | None = None) -> dict:
        payload = {"target_path": target_path}
        if bundle:
            payload["bundle"] = bundle
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{self.base_url}/plan", json=payload)
        response.raise_for_status()
        return response.json()

    async def run(self, target_path: str, bundle: str | None = None) -> dict:
        payload = {"target_path": target_path}
        if bundle:
            payload["bundle"] = bundle
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{self.base_url}/run", json=payload)
        response.raise_for_status()
        return response.json()

    async def submit_input(self, request_id: str, response_text: str) -> dict:
        payload = {"request_id": request_id, "response": response_text}
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{self.base_url}/input", json=payload)
        response.raise_for_status()
        return response.json()

    async def send_agent_message(self, agent_id: str, message: str) -> dict:
        payload = {"agent_id": agent_id, "message": message}
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{self.base_url}/agent-message", json=payload)
        response.raise_for_status()
        return response.json()

    async def ask_agent(self, agent_id: str, message: str, target_path: str, bundle: str | None) -> dict:
        payload = {
            "agent_id": agent_id,
            "message": message,
            "target_path": target_path,
            "bundle": bundle or "",
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{self.base_url}/agent-ask", json=payload)
        response.raise_for_status()
        return response.json()

    async def stream_events(self) -> AsyncIterator[StreamEvent]:
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("GET", f"{self.base_url}/events") as response:
                response.raise_for_status()
                async for event in _parse_sse(response.aiter_lines()):
                    yield event


async def _parse_sse(lines: AsyncIterator[str]) -> AsyncIterator[StreamEvent]:
    event_name: str | None = None
    data_lines: list[str] = []

    async for raw_line in lines:
        line = raw_line.rstrip("\n")
        if not line:
            if data_lines:
                payload_text = "\n".join(data_lines)
                try:
                    payload = json.loads(payload_text)
                except json.JSONDecodeError:
                    payload = {"raw": payload_text}
                yield StreamEvent(event_type=event_name or "event", payload=payload)
            event_name = None
            data_lines = []
            continue

        if line.startswith(":"):
            continue
        if line.startswith("event:"):
            event_name = line.split(":", 1)[1].strip()
            continue
        if line.startswith("data:"):
            data_lines.append(line.split(":", 1)[1].lstrip())
