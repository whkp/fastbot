"""Tests for the lightweight model-managed ``update_plan`` tool."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from nanobot.agent.loop import AgentLoop
from nanobot.agent.tools.context import RequestContext, request_context
from nanobot.agent.tools.plan import PLAN_STATE_KEY, UpdatePlanTool, plan_overlay
from nanobot.bus.queue import MessageBus
from nanobot.config.schema import PlanConfig
from nanobot.providers.base import GenerationSettings, LLMResponse, ToolCallRequest
from nanobot.session.manager import SessionManager


def _context() -> RequestContext:
    return RequestContext(channel="test", chat_id="c1", session_key="test:c1")


def _tool(tmp_path) -> tuple[SessionManager, UpdatePlanTool]:
    sessions = SessionManager(tmp_path)
    config = PlanConfig(enabled=True)
    return sessions, UpdatePlanTool(sessions, config)


def test_plan_feature_flag_controls_tool_registration(tmp_path) -> None:
    provider = MagicMock()
    provider.get_default_model.return_value = "test-model"
    provider.generation = GenerationSettings()

    disabled = AgentLoop(
        bus=MessageBus(),
        provider=provider,
        workspace=tmp_path / "disabled",
        model="test-model",
        plan_config=PlanConfig(enabled=False),
    )
    enabled = AgentLoop(
        bus=MessageBus(),
        provider=provider,
        workspace=tmp_path / "enabled",
        model="test-model",
        plan_config=PlanConfig(enabled=True),
    )

    assert not disabled.tools.has("update_plan")
    assert enabled.tools.has("update_plan")


@pytest.mark.asyncio
async def test_update_plan_persists_and_renders_active_snapshot(tmp_path) -> None:
    sessions, tool = _tool(tmp_path)

    with request_context(_context()):
        result = await tool.execute(
            explanation="Fix authentication flow",
            plan=[
                {"step": "Inspect the failing path", "status": "completed"},
                {"step": "Repair the session handling", "status": "in_progress"},
                {"step": "Run focused tests", "status": "pending"},
            ],
        )

    assert "revision 1" in result
    persisted = SessionManager(tmp_path).get_or_create("test:c1").metadata[PLAN_STATE_KEY]
    assert persisted["revision"] == 1
    overlay = plan_overlay({PLAN_STATE_KEY: persisted}, max_context_chars=3_000)
    assert overlay is not None
    assert "Revision: 1" in overlay
    assert "[~] Repair the session handling" in overlay


@pytest.mark.asyncio
async def test_completed_plan_stops_rendering_but_remains_persisted(tmp_path) -> None:
    sessions, tool = _tool(tmp_path)

    with request_context(_context()):
        result = await tool.execute(
            plan=[{"step": "Verify the fix", "status": "completed"}],
        )

    assert "Plan completed" in result
    metadata = sessions.get_or_create("test:c1").metadata
    assert metadata[PLAN_STATE_KEY]["active"] is False
    assert plan_overlay(metadata, max_context_chars=3_000) is None


@pytest.mark.asyncio
async def test_update_plan_rejects_invalid_snapshot_without_writing(tmp_path) -> None:
    sessions, tool = _tool(tmp_path)

    with request_context(_context()):
        result = await tool.execute(
            plan=[
                {"step": "A", "status": "pending"},
                {"step": "B", "status": "pending"},
            ],
        )

    assert result.is_error
    assert "in_progress" in result
    assert PLAN_STATE_KEY not in sessions.get_or_create("test:c1").metadata


@pytest.mark.asyncio
async def test_update_plan_rolls_back_metadata_when_save_fails(tmp_path, monkeypatch) -> None:
    sessions, tool = _tool(tmp_path)
    session = sessions.get_or_create("test:c1")
    session.metadata["keep"] = "value"

    def fail_save(*_args, **_kwargs) -> None:
        raise OSError("disk unavailable")

    monkeypatch.setattr(sessions, "save", fail_save)
    with request_context(_context()):
        result = await tool.execute(
            plan=[{"step": "Investigate", "status": "in_progress"}],
        )

    assert result.is_error
    assert session.metadata == {"keep": "value"}


@pytest.mark.asyncio
async def test_plan_update_is_visible_on_the_next_request_in_same_react_turn(tmp_path) -> None:
    provider = MagicMock()
    provider.get_default_model.return_value = "test-model"
    provider.generation = GenerationSettings()
    provider.chat_with_retry = AsyncMock(side_effect=[
        LLMResponse(
            content="",
            tool_calls=[ToolCallRequest(
                id="plan-1",
                name="update_plan",
                arguments={
                    "explanation": "Fix the reported failure",
                    "plan": [
                        {"step": "Inspect the failure", "status": "completed"},
                        {"step": "Apply the fix", "status": "in_progress"},
                    ],
                },
            )],
        ),
        LLMResponse(content="done"),
    ])
    loop = AgentLoop(
        bus=MessageBus(),
        provider=provider,
        workspace=tmp_path,
        model="test-model",
        plan_config=PlanConfig(enabled=True),
    )
    session = loop.sessions.get_or_create("test:c1")

    final, _tools, messages, _reason, _injected = await loop._run_agent_loop(
        [{"role": "system", "content": "system"}, {"role": "user", "content": "fix it"}],
        runtime=loop.llm_runtime(),
        session=session,
        channel="test",
        chat_id="c1",
        session_key="test:c1",
    )

    assert final == "done"
    first_context = provider.chat_with_retry.await_args_list[0].kwargs.get("provider_context")
    second_context = provider.chat_with_retry.await_args_list[1].kwargs.get("provider_context")
    assert first_context is not None
    assert first_context.ephemeral_context is None
    assert second_context is not None
    assert "Revision: 1" in second_context.ephemeral_context
    assert "Apply the fix" in second_context.ephemeral_context
    assert "<task_state>" not in str(messages)
    assert "<task_state>" not in str(session.messages)


def test_update_plan_stays_core_only() -> None:
    assert UpdatePlanTool._scopes == {"core"}


def test_plan_overlay_ignores_inconsistent_persisted_state() -> None:
    assert plan_overlay(
        {
            PLAN_STATE_KEY: {
                "revision": 1,
                "active": True,
                "explanation": "",
                "plan": [{"step": "Already done", "status": "completed"}],
            }
        },
        max_context_chars=3_000,
    ) is None
