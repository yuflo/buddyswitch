"""Task Public operations earned by current cross-component consumers."""

from buddyswitch.modules.task.public.contracts import (
    DemandSelectionResolver,
    TaskCompletionEvidenceError,
)
from buddyswitch.modules.task.public.operations import (
    actor_task_projection,
    demand_attention,
    has_active_task,
    require_completed_task_for_demand,
)

__all__ = [
    "DemandSelectionResolver",
    "TaskCompletionEvidenceError",
    "actor_task_projection",
    "demand_attention",
    "has_active_task",
    "require_completed_task_for_demand",
]
