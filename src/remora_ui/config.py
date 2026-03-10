"""Configuration for remora-ui."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RemoraUIConfig:
    """Runtime configuration for the remora-ui server."""

    remora_base_url: str = "http://localhost:8765"
    host: str = "127.0.0.1"
    port: int = 8766

    @classmethod
    def from_env(cls) -> "RemoraUIConfig":
        """Load config from environment variables (all optional)."""
        import os

        return cls(
            remora_base_url=os.environ.get("REMORA_URL", "http://localhost:8765"),
            host=os.environ.get("REMORA_UI_HOST", "127.0.0.1"),
            port=int(os.environ.get("REMORA_UI_PORT", "8766")),
        )
