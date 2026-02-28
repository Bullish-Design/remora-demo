"""Chat session wrapper for single-agent interactions."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from structured_agents import AgentKernel, ModelAdapter, build_client
from structured_agents.agent import get_response_parser
from structured_agents.types import Message as KernelMessage

from remora.core.cairn_bridge import CairnWorkspaceService
from remora.core.config import WorkspaceConfig
from remora.core.event_bus import EventBus
from remora.core.tool_registry import ToolRegistry, WorkspaceContext


@dataclass
class Message:
    """A message in the conversation."""

    id: str
    role: str
    content: str
    timestamp: float
    tool_calls: list[dict] = field(default_factory=list)

    @classmethod
    def user(cls, content: str) -> "Message":
        return cls(
            id=str(uuid.uuid4()),
            role="user",
            content=content,
            timestamp=time.time(),
        )

    @classmethod
    def assistant(cls, content: str, tool_calls: list[dict] | None = None) -> "Message":
        return cls(
            id=str(uuid.uuid4()),
            role="assistant",
            content=content,
            timestamp=time.time(),
            tool_calls=tool_calls or [],
        )


@dataclass
class ChatConfig:
    """Configuration for a chat session."""

    workspace_path: str
    system_prompt: str
    tool_presets: list[str] = field(default_factory=lambda: ["file_ops"])
    model_name: str = "Qwen/Qwen3-4B"
    model_base_url: str = "http://localhost:8000/v1"
    model_api_key: str = "EMPTY"
    model_family: str = "qwen"
    max_turns: int = 10
    timeout: float = 120.0


@dataclass
class AgentResponse:
    """Response from the agent."""

    message: Message
    turn_count: int


class ChatSession:
    """Simplified single-agent chat interface."""

    def __init__(
        self,
        session_id: str,
        config: ChatConfig,
        event_bus: EventBus,
    ):
        self.session_id = session_id
        self.config = config
        self.event_bus = event_bus

        self._history: list[Message] = []
        self._workspace_service: CairnWorkspaceService | None = None
        self._tools: list[Any] = []
        self._kernel: AgentKernel | None = None
        self._initialized = False

    @classmethod
    async def create(
        cls,
        config: ChatConfig,
        event_bus: EventBus | None = None,
    ) -> "ChatSession":
        session_id = str(uuid.uuid4())
        event_bus = event_bus or EventBus()

        session = cls(
            session_id=session_id,
            config=config,
            event_bus=event_bus,
        )
        await session._initialize()
        return session

    async def _initialize(self) -> None:
        workspace_path = Path(self.config.workspace_path).expanduser().resolve()
        workspace_config = WorkspaceConfig(
            base_path=str(workspace_path / ".remora" / "workspaces"),
        )
        self._workspace_service = CairnWorkspaceService(
            config=workspace_config,
            graph_id=self.session_id,
            project_root=workspace_path,
        )
        await self._workspace_service.initialize()

        agent_workspace = await self._workspace_service.get_agent_workspace(self.session_id)
        externals = self._workspace_service.get_externals(self.session_id, agent_workspace)

        workspace_context = WorkspaceContext(
            root_path=workspace_path,
            externals=externals,
        )
        self._tools = ToolRegistry.get_tools(
            workspace=workspace_context,
            presets=self.config.tool_presets,
        )

        parser = get_response_parser(self.config.model_family)
        adapter = ModelAdapter(name=self.config.model_family, response_parser=parser)
        client = build_client(
            {
                "base_url": self.config.model_base_url,
                "api_key": self.config.model_api_key,
                "model": self.config.model_name,
                "timeout": self.config.timeout,
            }
        )

        self._kernel = AgentKernel(
            client=client,
            adapter=adapter,
            tools=self._tools,
            observer=self.event_bus,
        )

        self._initialized = True

    async def send(self, content: str) -> AgentResponse:
        if not self._initialized or not self._kernel:
            raise RuntimeError("Session not initialized")

        user_msg = Message.user(content)
        self._history.append(user_msg)

        kernel_messages = [KernelMessage(role="system", content=self.config.system_prompt)]
        for msg in self._history:
            kernel_messages.append(KernelMessage(role=msg.role, content=msg.content))

        prior_count = len(kernel_messages)
        tool_schemas = [tool.schema for tool in self._tools]

        result = await self._kernel.run(
            kernel_messages,
            tool_schemas,
            max_turns=self.config.max_turns,
        )

        tool_calls: list[dict[str, Any]] = []
        for msg in result.history[prior_count:]:
            if msg.role == "assistant" and msg.tool_calls:
                for tc in msg.tool_calls:
                    tool_calls.append(
                        {"id": tc.id, "name": tc.name, "arguments": tc.arguments}
                    )

        assistant_content = ""
        for msg in reversed(result.history):
            if msg.role == "assistant":
                assistant_content = msg.content or ""
                break

        assistant_msg = Message.assistant(
            content=assistant_content,
            tool_calls=tool_calls,
        )
        self._history.append(assistant_msg)

        return AgentResponse(
            message=assistant_msg,
            turn_count=result.turn_count,
        )

    @property
    def history(self) -> list[Message]:
        return self._history.copy()

    def reset(self) -> None:
        self._history.clear()

    async def close(self) -> None:
        if self._kernel:
            await self._kernel.close()
            self._kernel = None
        if self._workspace_service:
            await self._workspace_service.close()
            self._workspace_service = None
        self._initialized = False


__all__ = ["ChatSession", "ChatConfig", "AgentResponse", "Message"]
