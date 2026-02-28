"""Application state model for the demo UI."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field


@dataclass
class ToolCall:
    """Record of a tool invocation."""

    name: str
    arguments: dict
    result: str | None
    is_error: bool
    timestamp: float
    call_id: str | None = None


@dataclass
class ChatMessage:
    """A message in the chat."""

    id: str
    role: str
    content: str
    timestamp: float
    tool_calls: list[ToolCall] = field(default_factory=list)


@dataclass
class AgentConfig:
    """Configuration for the agent."""

    system_prompt: str = "You are a helpful assistant with access to file operations."
    enabled_presets: list[str] = field(default_factory=lambda: ["file_ops"])


@dataclass
class DemoState:
    """Complete application state (inbox/outbox pattern)."""

    # Workspace
    workspace_path: str = ""
    workspace_valid: bool = False

    # Agent configuration
    agent_config: AgentConfig = field(default_factory=AgentConfig)
    available_presets: list[str] = field(default_factory=lambda: ["file_ops", "code_analysis", "all"])

    # Session
    session_id: str | None = None
    session_active: bool = False

    # Chat state (inbox/outbox)
    inbox: list[ChatMessage] = field(default_factory=list)
    outbox: list[ChatMessage] = field(default_factory=list)

    # Tool log
    tool_log: list[ToolCall] = field(default_factory=list)

    # UI state
    is_processing: bool = False
    error_message: str | None = None
    backend_connected: bool = False
    event_stream_active: bool = False

    # Internal
    event_stream_task: asyncio.Task | None = field(default=None, repr=False)

    @property
    def messages(self) -> list[ChatMessage]:
        """Interleaved inbox/outbox for display."""
        combined = self.inbox + self.outbox
        return sorted(combined, key=lambda m: m.timestamp)

    @classmethod
    def initial(cls) -> "DemoState":
        return cls()

    def add_user_message(self, id: str, content: str, timestamp: float) -> ChatMessage:
        msg = ChatMessage(id=id, role="user", content=content, timestamp=timestamp)
        self.inbox.append(msg)
        return msg

    def add_agent_message(
        self,
        id: str,
        content: str,
        timestamp: float,
        tool_calls: list[ToolCall] | None = None,
    ) -> ChatMessage:
        msg = ChatMessage(
            id=id,
            role="assistant",
            content=content,
            timestamp=timestamp,
            tool_calls=tool_calls or [],
        )
        self.outbox.append(msg)
        return msg

    def log_tool_call(
        self,
        name: str,
        arguments: dict,
        result: str | None = None,
        is_error: bool = False,
        call_id: str | None = None,
        timestamp: float | None = None,
    ) -> ToolCall:
        call = ToolCall(
            name=name,
            arguments=arguments,
            result=result,
            is_error=is_error,
            timestamp=timestamp or time.time(),
            call_id=call_id,
        )
        self.tool_log.append(call)
        return call

    def update_tool_result(
        self,
        name: str,
        result: str | None,
        is_error: bool,
        call_id: str | None,
        timestamp: float | None = None,
    ) -> ToolCall:
        for call in reversed(self.tool_log):
            if call_id and call.call_id == call_id and call.result is None:
                call.result = result
                call.is_error = is_error
                if timestamp is not None:
                    call.timestamp = timestamp
                return call
            if call_id is None and call.name == name and call.result is None:
                call.result = result
                call.is_error = is_error
                if timestamp is not None:
                    call.timestamp = timestamp
                return call
        return self.log_tool_call(
            name=name,
            arguments={},
            result=result,
            is_error=is_error,
            call_id=call_id,
            timestamp=timestamp,
        )

    def reset_chat(self) -> None:
        self.inbox.clear()
        self.outbox.clear()
        self.tool_log.clear()
