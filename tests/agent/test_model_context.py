"""Phase 0 tests: model-only context overlay (ephemeral context).

Covers design.md §4.5 and Phase 0:
- ``ModelContextOverlay`` value-object rendering and composition.
- ``merge_overlay_into_messages`` merges into the first system message without
  mutating the caller's list or breaking tool-call/tool-result adjacency.
- The runner injects the overlay as ``ProviderCallContext.ephemeral_context``
  on every provider request path (main loop, no-tools retries).
- Providers consume ``ephemeral_context`` without persisting it.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from agent.runner_helpers import make_run_spec
from nanobot.agent.model_context import (
    ModelContextOverlay,
    merge_overlay_into_messages,
)
from nanobot.agent.runner import AgentRunner
from nanobot.config.schema import AgentDefaults
from nanobot.providers.base import (
    LLMProvider,
    LLMResponse,
    ProviderCallContext,
    ToolCallRequest,
)

_MAX_TOOL_RESULT_CHARS = AgentDefaults().max_tool_result_chars


class TestModelContextOverlay:
    def test_render_wraps_blocks(self) -> None:
        overlay = ModelContextOverlay(
            blocks=("- [x] read", "- [~] analyze"),
            wrapper_tag="task_state",
        )
        assert overlay.text == "- [x] read\n- [~] analyze"
        rendered = overlay.render()
        assert rendered.startswith("<task_state>")
        assert rendered.endswith("</task_state>")
        assert "- [x] read" in rendered

    def test_empty_overlay(self) -> None:
        assert ModelContextOverlay().is_empty
        assert ModelContextOverlay(blocks=("",)).is_empty
        assert ModelContextOverlay().render() == ""

    def test_merged_with_combines_blocks_and_sources(self) -> None:
        a = ModelContextOverlay(blocks=("a",), sources=("s1",))
        b = ModelContextOverlay(blocks=("b",), sources=("s2",))
        merged = a.merged_with(b)
        assert merged.blocks == ("a", "b")
        assert merged.sources == ("s1", "s2")
        # Originals unchanged (frozen value objects).
        assert a.blocks == ("a",)
        assert b.blocks == ("b",)


class TestMergeOverlayIntoMessages:
    def test_merges_into_first_system_message(self) -> None:
        messages = [
            {"role": "system", "content": "base"},
            {"role": "user", "content": "hi"},
        ]
        merged = merge_overlay_into_messages(messages, "<task_state>x</task_state>")
        assert merged[0]["role"] == "system"
        assert merged[0]["content"].startswith("base\n\n<task_state>x</task_state>")
        # Original list untouched (per-request copy).
        assert messages[0]["content"] == "base"

    def test_does_not_mutate_caller_list(self) -> None:
        messages = [{"role": "system", "content": "base"}]
        _ = merge_overlay_into_messages(messages, "overlay")
        assert messages == [{"role": "system", "content": "base"}]

    def test_prepends_system_when_no_leading_system(self) -> None:
        messages = [{"role": "user", "content": "hi"}]
        merged = merge_overlay_into_messages(messages, "overlay")
        assert merged[0]["role"] == "system"
        assert merged[0]["content"] == "overlay"
        assert merged[1] == {"role": "user", "content": "hi"}

    def test_empty_overlay_is_noop(self) -> None:
        messages = [{"role": "system", "content": "base"}]
        merged = merge_overlay_into_messages(messages, None)
        assert merged == messages

    def test_keeps_tool_result_adjacency(self) -> None:
        # Overlay only touches the head; an assistant tool call / tool result
        # pair deeper in the transcript stays intact.
        messages = [
            {"role": "system", "content": "base"},
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "", "tool_calls": [{"id": "c1"}]},
            {"role": "tool", "tool_call_id": "c1", "content": "result"},
        ]
        merged = merge_overlay_into_messages(messages, "overlay")
        assert merged[2] == messages[2]
        assert merged[3] == messages[3]


@pytest.mark.asyncio
async def test_runner_injects_overlay_as_ephemeral_context():
    """The overlay text reaches every provider request as ephemeral context."""
    provider = MagicMock(spec=LLMProvider)
    captured_contexts: list[ProviderCallContext | None] = []
    call_count = {"n": 0}

    async def chat_with_retry(*, messages, provider_context=None, **kwargs):
        captured_contexts.append(provider_context)
        call_count["n"] += 1
        if call_count["n"] == 1:
            return LLMResponse(
                content="",
                tool_calls=[ToolCallRequest(id="call_1", name="list_dir", arguments={"path": "."})],
            )
        return LLMResponse(content="done", tool_calls=[], usage={})

    provider.chat_with_retry = chat_with_retry
    tools = MagicMock()
    tools.get_definitions.return_value = []
    tools.execute = MagicMock(return_value=LLMResponse(content="tool result"))

    def overlay_provider() -> ModelContextOverlay:
        return ModelContextOverlay(blocks=("- [~] working"), wrapper_tag="task_state")

    runner = AgentRunner()
    await runner.run(make_run_spec(provider,
        initial_messages=[
            {"role": "system", "content": "system"},
            {"role": "user", "content": "do task"},
        ],
        tools=tools,
        model="test-model",
        max_iterations=3,
        max_tool_result_chars=_MAX_TOOL_RESULT_CHARS,
        overlay_provider=overlay_provider,
    ))

    assert len(captured_contexts) >= 2
    for ctx in captured_contexts:
        assert ctx is not None
        assert ctx.ephemeral_context is not None
        assert "<task_state>" in ctx.ephemeral_context


@pytest.mark.asyncio
async def test_runner_without_overlay_provider_passes_no_ephemeral():
    provider = MagicMock(spec=LLMProvider)

    async def chat_with_retry(*, messages, provider_context=None, **kwargs):
        assert provider_context is None or provider_context.ephemeral_context is None
        return LLMResponse(content="done", tool_calls=[], usage={})

    provider.chat_with_retry = chat_with_retry
    tools = MagicMock()
    tools.get_definitions.return_value = []

    runner = AgentRunner()
    result = await runner.run(make_run_spec(provider,
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


@pytest.mark.asyncio
async def test_runner_injects_overlay_on_no_tools_retry_path():
    """Finalization/no-tools retries also receive the overlay."""
    provider = MagicMock(spec=LLMProvider)
    captured_contexts: list[ProviderCallContext | None] = []

    async def chat_with_retry(*, messages, provider_context=None, **kwargs):
        captured_contexts.append(provider_context)
        # Force the no-tools finalization path by returning tool_calls but with
        # a name that will be dropped as malformed.
        return LLMResponse(
            content="",
            tool_calls=[ToolCallRequest(id="c1", name=None, arguments={})],
            finish_reason="tool_calls",
        )

    provider.chat_with_retry = chat_with_retry
    tools = MagicMock()
    tools.get_definitions.return_value = []

    def overlay_provider() -> ModelContextOverlay:
        return ModelContextOverlay(blocks=("still active",), wrapper_tag="task_state")

    runner = AgentRunner()
    await runner.run(make_run_spec(provider,
        initial_messages=[
            {"role": "system", "content": "system"},
            {"role": "user", "content": "do task"},
        ],
        tools=tools,
        model="test-model",
        max_iterations=2,
        max_tool_result_chars=_MAX_TOOL_RESULT_CHARS,
        overlay_provider=overlay_provider,
    ))

    assert len(captured_contexts) >= 2
    assert all(ctx.ephemeral_context for ctx in captured_contexts)


def test_provider_call_context_defaults_ephemeral_none() -> None:
    assert ProviderCallContext().ephemeral_context is None
    pc = ProviderCallContext(context_window_tokens=100)
    assert pc.ephemeral_context is None
