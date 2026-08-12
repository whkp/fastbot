"""Lightweight model-managed planning tool.

The active plan is a small JSON value in session metadata.  The main agent
owns it; subagents never receive this core-only tool.  Keeping validation,
persistence, and overlay rendering together avoids a separate plan service.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from nanobot.agent.tools.base import Tool, ToolResult, tool_parameters
from nanobot.agent.tools.context import ToolContext, current_request_context
from nanobot.agent.tools.schema import (
    ArraySchema,
    ObjectSchema,
    StringSchema,
    tool_parameters_schema,
)

if TYPE_CHECKING:
    from nanobot.config.schema import PlanConfig
    from nanobot.session.manager import SessionManager


PLAN_STATE_KEY = "plan_state"
_MISSING = object()
_STATUSES = frozenset(("pending", "in_progress", "completed"))


def _valid_record(blob: Any) -> dict[str, Any] | None:
    """Return a validated persisted record, or hide corrupt/stale metadata."""
    if not isinstance(blob, dict):
        return None
    revision = blob.get("revision")
    active = blob.get("active")
    explanation = blob.get("explanation")
    steps = blob.get("plan")
    if (
        not isinstance(revision, int)
        or isinstance(revision, bool)
        or revision < 1
        or not isinstance(active, bool)
        or not isinstance(explanation, str)
        or not isinstance(steps, list)
    ):
        return None
    clean_steps: list[dict[str, str]] = []
    for item in steps:
        if not isinstance(item, dict):
            return None
        step = item.get("step")
        status = item.get("status")
        if not isinstance(step, str) or not step.strip() or status not in _STATUSES:
            return None
        clean_steps.append({"step": step.strip(), "status": status})
    if not clean_steps:
        return None
    in_progress = sum(step["status"] == "in_progress" for step in clean_steps)
    active_plan = any(step["status"] != "completed" for step in clean_steps)
    if in_progress > 1 or (active_plan and in_progress != 1) or active != active_plan:
        return None
    return {
        "revision": revision,
        "active": active,
        "explanation": explanation.strip(),
        "plan": clean_steps,
    }


def plan_overlay(
    metadata: dict[str, Any] | None,
    *,
    max_context_chars: int,
) -> str | None:
    """Build the current request-only plan overlay from session metadata."""
    record = _valid_record((metadata or {}).get(PLAN_STATE_KEY))
    if record is None or not record["active"]:
        return None

    icons = {"completed": "[x]", "in_progress": "[~]", "pending": "[ ]"}
    lines = [
        "Current execution plan (model-maintained status only; it cannot override "
        "safety rules or user authorization).",
        f"Revision: {record['revision']}",
    ]
    if record["explanation"]:
        lines.append(f"Focus: {record['explanation']}")
    lines.extend(
        f"- {icons[step['status']]} {step['step']}"
        for step in record["plan"]
    )
    content = "\n".join(lines)
    if len(content) > max_context_chars:
        return None
    return f"<task_state>\n{content}\n</task_state>"


@tool_parameters(
    tool_parameters_schema(
        explanation=StringSchema(
            "Optional concise summary of the current approach.",
            max_length=300,
        ),
        plan=ArraySchema(
            description="The full current execution plan. Replace it when new evidence changes the work.",
            min_items=1,
            max_items=12,
            items=ObjectSchema(
                properties={
                    "step": StringSchema("One concrete step.", min_length=1, max_length=160),
                    "status": StringSchema(
                        "Step status.",
                        enum=["pending", "in_progress", "completed"],
                    ),
                },
                required=["step", "status"],
                additional_properties=False,
            ),
        ),
        required=["plan"],
    )
)
class UpdatePlanTool(Tool):
    """Let the main model persist and revise one small task plan."""

    _scopes = {"core"}

    def __init__(self, sessions: SessionManager, config: PlanConfig) -> None:
        self._sessions = sessions
        self._config = config

    @classmethod
    def create(cls, ctx: ToolContext) -> Tool:
        if ctx.sessions is None or ctx.plan_config is None:
            raise RuntimeError("UpdatePlanTool requires session storage and plan configuration")
        return cls(ctx.sessions, ctx.plan_config)

    @classmethod
    def enabled(cls, ctx: ToolContext) -> bool:
        return ctx.sessions is not None and bool(ctx.plan_config and ctx.plan_config.enabled)

    @property
    def name(self) -> str:
        return "update_plan"

    @property
    def description(self) -> str:
        return (
            "Maintain a short execution plan for a multi-step task. Decide yourself whether "
            "planning is useful: do not use this for simple tasks. Submit the complete current "
            "plan, not a patch. Update it when tool results change the approach, and mark every "
            "step completed only after it is actually done and verified."
        )

    async def execute(
        self,
        plan: list[dict[str, str]],
        explanation: str = "",
        **kwargs: Any,
    ) -> str:
        request = current_request_context()
        if request is None or not request.session_key:
            return ToolResult.error("Error: update_plan requires an active chat session.")

        try:
            steps = self._validate(plan)
        except ValueError as exc:
            return ToolResult.error(f"Error: invalid plan: {exc}")
        summary = (explanation or "").strip()
        if len(summary) > self._config.max_explanation_chars:
            return ToolResult.error(
                f"Error: explanation must not exceed {self._config.max_explanation_chars} characters."
            )

        session = self._sessions.get_or_create(request.session_key)
        previous = session.metadata.get(PLAN_STATE_KEY, _MISSING)
        prior = _valid_record(session.metadata.get(PLAN_STATE_KEY))
        revision = (prior["revision"] if prior is not None else 0) + 1
        active = any(step["status"] != "completed" for step in steps)
        session.metadata[PLAN_STATE_KEY] = {
            "revision": revision,
            "active": active,
            "explanation": summary,
            "plan": steps,
        }
        try:
            self._sessions.save(session)
        except BaseException:
            if previous is _MISSING:
                session.metadata.pop(PLAN_STATE_KEY, None)
            else:
                session.metadata[PLAN_STATE_KEY] = previous
            return ToolResult.error("Error: plan could not be saved; no changes were applied.")

        if active:
            return f"Plan updated (revision {revision}). Continue with the in-progress step."
        return f"Plan completed (revision {revision})."

    def _validate(self, raw_plan: list[dict[str, str]]) -> list[dict[str, str]]:
        if not isinstance(raw_plan, list) or not raw_plan:
            raise ValueError("plan must contain at least one step")
        if len(raw_plan) > self._config.max_steps:
            raise ValueError(f"plan must contain at most {self._config.max_steps} steps")

        steps: list[dict[str, str]] = []
        seen: set[str] = set()
        in_progress = 0
        for index, item in enumerate(raw_plan, start=1):
            if not isinstance(item, dict):
                raise ValueError(f"step {index} must be an object")
            step = item.get("step")
            status = item.get("status")
            if not isinstance(step, str) or not step.strip():
                raise ValueError(f"step {index} needs non-empty text")
            text = step.strip()
            if len(text) > self._config.max_step_chars:
                raise ValueError(
                    f"step {index} must not exceed {self._config.max_step_chars} characters"
                )
            if status not in _STATUSES:
                raise ValueError(f"step {index} has an invalid status")
            key = text.casefold()
            if key in seen:
                raise ValueError("steps must not be duplicated")
            seen.add(key)
            if status == "in_progress":
                in_progress += 1
            steps.append({"step": text, "status": status})

        if in_progress > 1:
            raise ValueError("only one step can be in_progress")
        if in_progress == 0 and any(step["status"] != "completed" for step in steps):
            raise ValueError("an unfinished plan needs one in_progress step")
        return steps
