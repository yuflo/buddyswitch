"""Exact cross-component contracts owned by Task."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol


class DemandSelectionResolver(Protocol):
    """Resolve one current Demand reference before Task creation."""

    def __call__(
        self,
        *,
        actor_target: Mapping[str, Any],
        demand_ref: Any,
    ) -> dict[str, Any]:
        """Return the exact current Demand selection reference."""


class TaskCompletionEvidenceError(ValueError):
    """A Task cannot serve as completed evidence for the requested Demand."""

    code = "E_TASK_SYS_COMPLETION_EVIDENCE"
