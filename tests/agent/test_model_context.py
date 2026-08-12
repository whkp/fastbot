"""Tests for model-only ephemeral request context."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from agent.runner_helpers import make_run_spec
from nanobot.agent.runner import AgentRunner
from nanobot.config.schema import AgentDefaults
from nanobot.providers.base import (
    LLMProvider,
    LLMResponse,
    ProviderCallContext,
    ToolCallRequest,
)

_MAX_TOOL_RESULT_CHARS = AgentDefaults().max_tool_result_chars


class TestEphemeralContextMerge:
    def test_merges_into_a_request_copy(self) -> None:
        messages = [
            {"role": "system", "content": "base"},
            {"role": "user", "content": "hi"},
        ]

        merged = LLMProvider._apply_ephemeral_context(
            {"messages": messages},
            ProviderCallContext(ephemeral_context="<task_state>plan</task_state>"),
        )["messages"]

        assert merged[0]["content"].startswith("base\n\n<task_state>plan</task_state>")
        assert messages[0]["content"] == "base"

    def test_prepends_without_breaking_tool_result_adjacency(self) -> None:
        messages = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "", "tool_calls": [{"id": "c1"}]},
            {"role": "tool", "tool_call_id": "c1", "content": "result"},
        ]

        merged = LLMProvider._apply_ephemeral_context(
            {"messages": messages},
            ProviderCallContext(ephemeral_context="overlay"),
        )["messages"]

        assert merged[0] == {"role": "system", "content": "overlay"}
        assert merged[2:] == messages[1:]

    def test_empty_context_is_a_noop(self) -> None:
        kwargs = {"messages": [{"role": "system", "content": "base"}]}

        assert LLMProvider._apply_ephemeral_context(kwargs, ProviderCallContext()) is kwargs


@pytest.mark.asyncio
async def test_runner_rebuilds_ephemeral_context_for_every_request() -> None:
    provider = MagicMock(spec=LLMProvider)
    contexts: list[ProviderCallContext | None] = []
    requests = 0

    async def chat_with_retry(*, provider_context=None, **_kwargs):
        nonlocal requests
        contexts.append(provider_context)
        requests += 1
        if requests == 1:
            return LLMResponse(
                content="",
                tool_calls=[ToolCallRequest(id="call_1", name="list_dir", arguments={})],
            )
        return LLMResponse(content="done")

    provider.chat_with_retry = chat_with_retry
    tools = MagicMock()
    tools.get_definitions.return_value = []
    tools.execute = MagicMock(return_value="tool result")
    runner = AgentRunner()

    await runner.run(make_run_spec(
        provider,
        initial_messages=[
            {"role": "system", "content": "system"},
            {"role": "user", "content": "do task"},
        ],
        tools=tools,
        model="test-model",
        max_iterations=3,
        max_tool_result_chars=_MAX_TOOL_RESULT_CHARS,
        overlay_provider=lambda: "<task_state>current plan</task_state>",
    ))

    assert len(contexts) >= 2
    assert all(context and context.ephemeral_context for context in contexts)


@pytest.mark.asyncio
async def test_runner_omits_context_when_no_active_plan() -> None:
    provider = MagicMock(spec=LLMProvider)

    async def chat_with_retry(*, provider_context=None, **_kwargs):
        assert provider_context is None or provider_context.ephemeral_context is None
        return LLMResponse(content="done")

    provider.chat_with_retry = chat_with_retry
    tools = MagicMock()
    tools.get_definitions.return_value = []

    result = await AgentRunner().run(make_run_spec(
        provider,
        initial_messages=[
            {"role": "system", "content": "system"},
            {"role": "user", "content": "hi"},
        ],
        tools=tools,
        model="test-model",
        max_iterations=2,
        max_tool_result_chars=_MAX_TOOL_RESULT_CHARS,
    ))

    assert result.final_content == "done"


def test_provider_call_context_defaults_to_no_ephemeral_context() -> None:
    assert ProviderCallContext().ephemeral_context is None
    assert ProviderCallContext(context_window_tokens=100).ephemeral_context is None
