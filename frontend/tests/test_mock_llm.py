"""Tests for the enhanced MockLLMClient."""

from __future__ import annotations

import pytest

from remora_demo.mock_llm import MockLLMClient, parse_context


@pytest.fixture
def mock():
    return MockLLMClient()


def _system(name: str, node_type: str = "function", extension: str = "") -> dict:
    ext_line = f"\nExtension: {extension}" if extension else ""
    return {
        "role": "system",
        "content": f"You are the agent for `{name}`. node_type: {node_type}{ext_line}",
    }


# ---------------------------------------------------------------------------
# parse_context tests
# ---------------------------------------------------------------------------


def test_parse_context_extracts_agent_name():
    messages = [
        {
            "role": "system",
            "content": "You are the agent for `validate`. node_type: function",
        },
    ]
    ctx = parse_context(messages)
    assert ctx.agent_name == "validate"
    assert ctx.agent_type == "function"


def test_parse_context_agent_message():
    messages = [
        {
            "role": "system",
            "content": "You are the agent for `validate`. node_type: function",
        },
        {
            "role": "user",
            "content": "[From load_config]: please check validation rules",
        },
    ]
    ctx = parse_context(messages)
    assert ctx.agent_name == "validate"
    assert ctx.trigger_type == "agent_message"
    assert ctx.from_agent == "load_config"
    assert ctx.round_number == 0


def test_parse_context_human_chat():
    messages = [
        _system("load_config"),
        {"role": "user", "content": "what do you do?"},
    ]
    ctx = parse_context(messages)
    assert ctx.trigger_type == "human_chat"
    assert ctx.round_number == 0


def test_parse_context_rejection():
    messages = [
        _system("test_load_yaml", extension="TestFunction"),
        {"role": "user", "content": "[Feedback on rejected proposal] not good enough"},
    ]
    ctx = parse_context(messages)
    assert ctx.trigger_type == "rejection"


def test_parse_context_tool_followup():
    messages = [
        _system("test_load_yaml", extension="TestFunction"),
        {"role": "user", "content": "[From load_config]: update tests"},
        {"role": "assistant", "content": "Let me read the source."},
        {
            "role": "user",
            "content": "[Tool result for read_node]: def load_config(...): ...",
        },
    ]
    ctx = parse_context(messages)
    assert ctx.trigger_type == "tool_followup"
    assert ctx.round_number == 1


def test_parse_context_counts_rounds():
    messages = [
        _system("foo"),
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi"},
        {"role": "user", "content": "more"},
        {"role": "assistant", "content": "ok"},
        {"role": "user", "content": "again"},
    ]
    ctx = parse_context(messages)
    assert ctx.round_number == 2


def test_parse_context_test_function_extension():
    messages = [
        {
            "role": "system",
            "content": "You are the agent for `test_load_yaml`. node_type: function\nYou are a test function agent.",
        },
    ]
    ctx = parse_context(messages)
    assert ctx.extension_name == "TestFunction"


def test_parse_context_package_init_extension():
    messages = [
        {
            "role": "system",
            "content": "You are the agent for `__init__.py`. node_type: file\nYou represent a Python package. __init__",
        },
    ]
    ctx = parse_context(messages)
    assert ctx.extension_name == "PackageInit"


# ---------------------------------------------------------------------------
# MockLLMClient dispatch tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_human_chat_known_agent(mock):
    """Golden path beat 5: user asks load_config 'what do you do?'"""
    messages = [_system("load_config"), {"role": "user", "content": "what do you do?"}]
    resp = await mock.chat(messages, tools=[])
    assert "load_config" in resp.content
    assert resp.tool_calls == []


@pytest.mark.asyncio
async def test_human_chat_unknown_agent(mock):
    """Fallback for agents without specific chat scripts."""
    messages = [_system("some_random_function"), {"role": "user", "content": "hello"}]
    resp = await mock.chat(messages, tools=[])
    assert "some_random_function" in resp.content
    assert resp.tool_calls == []


@pytest.mark.asyncio
async def test_content_changed_triggers_message_node(mock):
    """Golden path beat 7: load_config detects parameter change, messages test agent."""
    messages = [
        _system("load_config"),
        {
            "role": "user",
            "content": "The parameter `timeout` was added to load_config.",
        },
    ]
    resp = await mock.chat(messages, tools=[])
    assert resp.content is not None
    assert "timeout" in resp.content
    assert len(resp.tool_calls) == 1
    assert resp.tool_calls[0].name == "message_node"
    assert "test_load_yaml" in resp.tool_calls[0].arguments["target_id"]


@pytest.mark.asyncio
async def test_test_agent_round0_reads_source(mock):
    """Golden path beat 8 (first round): test agent reads source node."""
    messages = [
        _system("test_load_yaml", extension="TestFunction"),
        {"role": "user", "content": "[From load_config]: timeout param was added"},
    ]
    resp = await mock.chat(messages, tools=[])
    assert len(resp.tool_calls) == 1
    assert resp.tool_calls[0].name == "read_node"
    assert resp.tool_calls[0].arguments["target_id"] == "load_config"


@pytest.mark.asyncio
async def test_test_agent_round1_rewrites(mock):
    """Golden path beat 8 (second round): test agent proposes rewrite."""
    messages = [
        _system("test_load_yaml", extension="TestFunction"),
        {"role": "user", "content": "[From load_config]: timeout param was added"},
        {"role": "assistant", "content": "Let me read the source."},
        {
            "role": "user",
            "content": "[Tool result for read_node]: def load_config(...): ...",
        },
    ]
    resp = await mock.chat(messages, tools=[])
    assert len(resp.tool_calls) == 1
    assert resp.tool_calls[0].name == "rewrite_self"
    assert "timeout" in resp.tool_calls[0].arguments["new_source"]


@pytest.mark.asyncio
async def test_rejection_feedback(mock):
    """Agent acknowledges rejection feedback."""
    messages = [
        _system("test_load_yaml", extension="TestFunction"),
        {
            "role": "user",
            "content": "[Feedback on rejected proposal] needs more assertions",
        },
    ]
    resp = await mock.chat(messages, tools=[])
    assert "rejected" in resp.content.lower()
    assert resp.tool_calls == []


@pytest.mark.asyncio
async def test_tool_followup(mock):
    """After a tool result, non-test agent wraps up."""
    messages = [
        _system("load_config"),
        {"role": "user", "content": "The parameter `timeout` was added."},
        {"role": "assistant", "content": "Let me notify tests."},
        {"role": "user", "content": "[Tool result for message_node]: delivered"},
    ]
    resp = await mock.chat(messages, tools=[])
    assert resp.content is not None
    assert resp.tool_calls == []


@pytest.mark.asyncio
async def test_fallback_for_no_match(mock):
    """When no script matches, generic fallback is used."""
    messages = [
        _system("deep_merge"),
        # No trigger keywords for content changed, and it's not human_chat
        # Actually this IS human_chat since it doesn't start with [From
        {"role": "user", "content": "hello there"},
    ]
    resp = await mock.chat(messages, tools=[])
    assert resp.content is not None
    # HumanChatScript should match since it's human_chat round 0
    assert resp.tool_calls == []


@pytest.mark.asyncio
async def test_call_count_increments(mock):
    """Each call to chat() increments the call counter."""
    assert mock.call_count == 0
    messages = [_system("foo"), {"role": "user", "content": "hi"}]
    await mock.chat(messages)
    assert mock.call_count == 1
    await mock.chat(messages)
    assert mock.call_count == 2


@pytest.mark.asyncio
async def test_close_is_noop(mock):
    """close() is a no-op but doesn't raise."""
    await mock.close()


@pytest.mark.asyncio
async def test_full_golden_path_cascade(mock):
    """Simulate the full golden path: content change -> message -> read -> rewrite."""
    # Beat 7: source agent detects change
    msgs1 = [
        _system("load_config"),
        {
            "role": "user",
            "content": "The parameter `timeout` was added to load_config.",
        },
    ]
    r1 = await mock.chat(msgs1)
    assert r1.tool_calls[0].name == "message_node"

    # Beat 8 round 0: test agent receives message, reads source
    msgs2 = [
        _system("test_load_yaml", extension="TestFunction"),
        {"role": "user", "content": "[From load_config]: timeout param was added"},
    ]
    r2 = await mock.chat(msgs2)
    assert r2.tool_calls[0].name == "read_node"

    # Beat 8 round 1: test agent gets read result, proposes rewrite
    msgs2.append({"role": "assistant", "content": r2.content or ""})
    msgs2.append(
        {"role": "user", "content": "[Tool result for read_node]: source code here"}
    )
    r3 = await mock.chat(msgs2)
    assert r3.tool_calls[0].name == "rewrite_self"
    assert "test_load_yaml_with_timeout" in r3.tool_calls[0].arguments["new_source"]
