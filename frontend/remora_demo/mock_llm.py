"""Enhanced MockLLMClient for deterministic demo scenarios.

Produces scripted responses that drive the golden path demo beats.
Dispatches based on (agent_identity, trigger_type, round_number) extracted
from the messages list.

When running in the LSP process, LLMResponse and ToolCall come from
remora.lsp.runner. For standalone testing, we define compatible dataclasses
here and use them as fallbacks.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Portable types — compatible with remora.lsp.runner.ToolCall / LLMResponse
# ---------------------------------------------------------------------------


@dataclass
class ToolCall:
    """Normalized tool call."""

    name: str
    arguments: dict[str, Any]
    id: str = ""


@dataclass
class LLMResponse:
    """Normalized response from the LLM."""

    content: str | None
    tool_calls: list[ToolCall]


# ---------------------------------------------------------------------------
# Context extraction
# ---------------------------------------------------------------------------


@dataclass
class MockContext:
    """Parsed context from the message list, used by scripts for dispatch."""

    agent_name: str = ""
    agent_type: str = ""  # "function", "class", "file"
    extension_name: str = ""  # "TestFunction", "PackageInit", ""
    trigger_type: str = (
        ""  # "human_chat", "agent_message", "content_changed", "rejection"
    )
    trigger_message: str = ""  # The actual user/agent message content
    from_agent: str = ""  # For agent_message triggers
    round_number: int = 0  # How many assistant messages precede this call
    has_tool: dict[str, bool] = field(default_factory=dict)
    system_prompt: str = ""  # Full system prompt for edge cases


def parse_context(messages: list[dict[str, Any]]) -> MockContext:
    """Extract dispatch context from the messages list."""
    ctx = MockContext()

    # System prompt is always first
    if messages and messages[0]["role"] == "system":
        sys = messages[0]["content"]
        ctx.system_prompt = sys

        # Extract agent name: "You are the agent for `load_config`" or similar
        m = re.search(r"agent for `([^`]+)`", sys)
        if m:
            ctx.agent_name = m.group(1)

        # Extract node type from system prompt
        for nt in ("function", "class", "file"):
            if f"node_type: {nt}" in sys or f"You are a {nt}" in sys:
                ctx.agent_type = nt
                break

        # Extension name
        if "TestFunction" in sys or "test function agent" in sys.lower():
            ctx.extension_name = "TestFunction"
        elif "PackageInit" in sys or ("package" in sys.lower() and "__init__" in sys):
            ctx.extension_name = "PackageInit"

    # Count rounds (assistant messages = completed rounds)
    ctx.round_number = sum(1 for m in messages if m["role"] == "assistant")

    # Find the last user message to determine trigger type
    user_msgs = [m for m in messages if m["role"] == "user"]
    if user_msgs:
        last = user_msgs[-1]["content"]
        ctx.trigger_message = last

        if last.startswith("[From "):
            ctx.trigger_type = "agent_message"
            fm = re.match(r"\[From ([^\]]+)\]", last)
            if fm:
                ctx.from_agent = fm.group(1)
        elif "[Feedback on rejected proposal]" in last:
            ctx.trigger_type = "rejection"
        elif "[Tool result for" in last:
            ctx.trigger_type = "tool_followup"
        else:
            ctx.trigger_type = "human_chat"

    return ctx


# ---------------------------------------------------------------------------
# Script base class and implementations
# ---------------------------------------------------------------------------


class Script(ABC):
    """Base class for mock response scripts."""

    @abstractmethod
    def matches(self, ctx: MockContext) -> bool:
        """Return True if this script handles the given context."""

    @abstractmethod
    def respond(self, ctx: MockContext) -> LLMResponse:
        """Generate the mock response."""


class ContentChangedAnalyzeScript(Script):
    """When a source function is triggered by ContentChanged, it analyzes the
    change and messages dependent test nodes.

    Matches: non-test functions on round 0 when the trigger message mentions
    parameter changes or additions.
    """

    def matches(self, ctx: MockContext) -> bool:
        if ctx.extension_name == "TestFunction":
            return False
        if ctx.agent_type != "function":
            return False
        if ctx.round_number != 0:
            return False
        msg = ctx.trigger_message.lower()
        return any(kw in msg for kw in ("parameter", "changed", "added", "content"))

    def respond(self, ctx: MockContext) -> LLMResponse:
        return LLMResponse(
            content=(
                f"I see that `{ctx.agent_name}` has been updated with a new `timeout` parameter. "
                f"This changes the function signature, which means callers and tests need to know "
                f"about it. Let me notify the test agent."
            ),
            tool_calls=[
                ToolCall(
                    name="message_node",
                    arguments={
                        "target_id": "test_load_yaml",
                        "message": (
                            "The function `load_config` now accepts an optional `timeout: int = 30` "
                            "parameter. Please update your test to verify the default timeout "
                            "behavior — you can check that the returned config dict works correctly "
                            "with the new parameter. No breaking change, but the test should "
                            "demonstrate awareness of the new capability."
                        ),
                    },
                    id="tc_msg_001",
                ),
            ],
        )


class TestAgentUpdateScript(Script):
    """When a test agent receives a message from a source agent, it reads the
    source node first (round 0), then proposes a rewrite (round 1).
    """

    def matches(self, ctx: MockContext) -> bool:
        if ctx.extension_name != "TestFunction":
            return False
        # Round 0: triggered by an agent message
        if ctx.trigger_type == "agent_message":
            return True
        # Round 1+: continuing the cascade after a tool result
        if ctx.trigger_type == "tool_followup" and ctx.round_number > 0:
            return True
        return False

    def respond(self, ctx: MockContext) -> LLMResponse:
        if ctx.round_number == 0:
            return LLMResponse(
                content="I received a notification about changes. Let me read the current source first.",
                tool_calls=[
                    ToolCall(
                        name="read_node",
                        arguments={"target_id": "load_config"},
                        id="tc_read_001",
                    ),
                ],
            )
        else:
            return LLMResponse(
                content=(
                    "I can see that `load_config` now has a `timeout` parameter with a default "
                    "of 30. I'll update my test to verify the default behavior and add an "
                    "explicit timeout test."
                ),
                tool_calls=[
                    ToolCall(
                        name="rewrite_self",
                        arguments={
                            "new_source": (
                                "def test_load_yaml(tmp_path: Path) -> None:\n"
                                '    """Test loading a YAML configuration file."""\n'
                                '    config_file = tmp_path / "config.yaml"\n'
                                '    config_file.write_text("database:\\n  host: localhost\\n  port: 5432\\n")\n'
                                "    result = load_config(config_file)\n"
                                '    assert result["database"]["host"] == "localhost"\n'
                                '    assert result["database"]["port"] == 5432\n'
                                "\n"
                                "\n"
                                "def test_load_yaml_with_timeout(tmp_path: Path) -> None:\n"
                                '    """Test that load_config accepts timeout parameter."""\n'
                                '    config_file = tmp_path / "config.yaml"\n'
                                '    config_file.write_text("debug: true\\n")\n'
                                "    result = load_config(config_file, timeout=60)\n"
                                '    assert result["debug"] is True\n'
                            ),
                        },
                        id="tc_rewrite_001",
                    ),
                ],
            )


class HumanChatScript(Script):
    """When a human chats with an agent, respond with a description of what
    the agent does based on its system prompt context.
    """

    def matches(self, ctx: MockContext) -> bool:
        return ctx.trigger_type == "human_chat" and ctx.round_number == 0

    def respond(self, ctx: MockContext) -> LLMResponse:
        responses = {
            "load_config": (
                "I'm the agent for `load_config`. I load configuration files by detecting "
                "their format (JSON or YAML), parsing them, and running schema validation. "
                "When my source code changes, I analyze the diff and notify dependent agents "
                "— like the test agents that verify my behavior — so they can update too."
            ),
            "detect_format": (
                "I handle format detection for configuration files. I map file extensions "
                "like `.json`, `.yaml`, `.yml`, and `.toml` to their format names. If I see "
                "an unrecognized extension, I raise a ValueError."
            ),
            "validate": (
                "I'm the schema validator. I check that configuration data is a dict and "
                "that all required fields are present. When validation rules change, I notify "
                "the agents that depend on me."
            ),
            "deep_merge": (
                "I recursively merge configuration dictionaries. Override values win over "
                "base values, and nested dicts are merged recursively rather than replaced."
            ),
        }

        content = responses.get(
            ctx.agent_name,
            f"I'm the agent for `{ctx.agent_name}`. I monitor my source code for changes "
            f"and coordinate with related agents when updates are needed.",
        )

        return LLMResponse(content=content, tool_calls=[])


class RejectionFeedbackScript(Script):
    """When a proposal is rejected, the agent reads the feedback and tries again."""

    def matches(self, ctx: MockContext) -> bool:
        return ctx.trigger_type == "rejection"

    def respond(self, ctx: MockContext) -> LLMResponse:
        return LLMResponse(
            content=(
                f"I see my previous proposal was rejected. Let me reconsider based on "
                f"the feedback: {ctx.trigger_message[:200]}"
            ),
            tool_calls=[],
        )


class ToolFollowupScript(Script):
    """After a tool result comes back, continue the conversation naturally."""

    def matches(self, ctx: MockContext) -> bool:
        return ctx.trigger_type == "tool_followup" and ctx.round_number > 0

    def respond(self, ctx: MockContext) -> LLMResponse:
        return LLMResponse(
            content=(
                "Based on the current state of the code, everything looks consistent. "
                "No further action needed from my end."
            ),
            tool_calls=[],
        )


def default_scripts() -> list[Script]:
    """The default script list used for the golden path demo.

    Order matters — first match wins.
    """
    return [
        TestAgentUpdateScript(),
        ContentChangedAnalyzeScript(),
        RejectionFeedbackScript(),
        ToolFollowupScript(),
        HumanChatScript(),
    ]


# ---------------------------------------------------------------------------
# MockLLMClient
# ---------------------------------------------------------------------------


class MockLLMClient:
    """Deterministic LLM mock that produces scripted responses for the demo.

    Dispatches based on (agent_identity, trigger_type, round_number) extracted
    from the messages list. Falls back to a generic acknowledgment if no script
    matches.
    """

    def __init__(self, scripts: list[Script] | None = None) -> None:
        self.scripts = scripts or default_scripts()
        self.call_count = 0

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        self.call_count += 1
        ctx = parse_context(messages)

        for script in self.scripts:
            if script.matches(ctx):
                return script.respond(ctx)

        # Generic fallback: acknowledge with text, no tool calls
        return LLMResponse(
            content=f"Acknowledged. I'm {ctx.agent_name}, monitoring for changes.",
            tool_calls=[],
        )

    async def close(self) -> None:
        pass
