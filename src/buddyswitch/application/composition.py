"""The one explicit current product-module selection and concrete wiring."""

from buddyswitch.modules.demand import public as demand_public
from buddyswitch.modules.demand.module import DEMAND
from buddyswitch.modules.search.module import SEARCH
from buddyswitch.modules.task import public as task_public
from buddyswitch.modules.task.module import build_task_module


TASK = build_task_module(
    demand_selection_resolver=demand_public.resolve_demand_ref,
)
COMPONENTS = (DEMAND, TASK, SEARCH)
DAEMON_HANDLER_ORDER = (
    "demand_triage",
    "task_goal",
    "demand_orchestration",
)
ACTIVE_TASK_PROBE = task_public.has_active_task
