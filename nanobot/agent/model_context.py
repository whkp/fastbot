"""Model-only context overlay for a single provider request.

The overlay carries dynamic per-request context (e.g. the current TASK_STATE
plan snapshot) that must be visible to the model on *every* request within a
ReAct turn but must never be persisted into the transcript, session history,
checkpoints, or provider conversation state.

Design (see design.md §4.5):
- ``ModelContextOverlay`` is a frozen value object; it is rebuilt per request
  from authoritative session metadata (never replayed from history).
- ``merge_overlay_into_messages`` appends the overlay to the first system
  message of a model-only message copy. It never mutates the caller's list.
- Providers consume the overlay through ``ProviderCallContext.ephemeral_context``
  (added in Phase 0) so it travels with a single request and is dropped when the
  request completes.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any


@dataclass(frozen=True)
class ModelContextOverlay:
    """Immutable, model-only context to attach to one provider request.

    ``blocks`` are rendered in order inside a single ``<task_state>``-style
    wrapper; callers may choose a wrapper by supplying ``wrapper_tag``.
    """

    blocks: tuple[str, ...] = ()
    wrapper_tag: str = "task_state"
    # Diagnostic aid only; never sent to the model or persisted.
    sources: tuple[str, ...] = field(default=(), repr=False)

    @property
    def text(self) -> str:
        """Render the overlay body (block text only, no wrapper)."""
        return "\n".join(block.strip() for block in self.blocks if block.strip())

    @property
    def is_empty(self) -> bool:
        return not self.blocks or not any(b.strip() for b in self.blocks)

    def merged_with(self, *overlays: ModelContextOverlay) -> ModelContextOverlay:
        """Return a new overlay combining this and *overlays* block text."""
        blocks = list(self.blocks)
        sources = list(self.sources)
        for other in overlays:
            blocks.extend(other.blocks)
            sources.extend(other.sources)
        return replace(self, blocks=tuple(blocks), sources=tuple(sources))

    def render(self) -> str:
        """Render the full overlay including the wrapper tag."""
        body = self.text
        if not body:
            return ""
        tag = self.wrapper_tag or "task_state"
        return f"<{tag}>\n{body}\n</{tag}>"


def merge_overlay_into_messages(
    messages: list[dict[str, Any]],
    overlay_text: str | None,
) -> list[dict[str, Any]]:
    """Return a *copy* of *messages* with *overlay_text* appended to the first
    system message. The caller's list is never mutated; the returned list is a
    per-request model copy and must not be persisted.

    If there is no system message (rare but defensive), a system message
    containing the overlay is prepended. This keeps tool-call/tool-result
    adjacency intact: we only touch the head of the transcript.
    """
    if not overlay_text or not messages:
        return messages
    copy: list[dict[str, Any]] = []
    for index, message in enumerate(messages):
        item = dict(message)
        if index == 0:
            role = item.get("role")
            if role == "system":
                content = item.get("content", "")
                if isinstance(content, str):
                    item["content"] = f"{content}\n\n{overlay_text}".strip()
                else:
                    # Non-string system content: keep it and append overlay as a
                    # second system message immediately after (still before any
                    # assistant/user turn).
                    copy.append(item)
                    copy.append({"role": "system", "content": overlay_text})
                    continue
            else:
                # No leading system message: prepend one with the overlay.
                copy.append({"role": "system", "content": overlay_text})
        copy.append(item)
    return copy
