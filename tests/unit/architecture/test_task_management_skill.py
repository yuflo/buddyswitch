"""Current Skill boundary for Demand orchestration and native-Goal Tasks."""

from __future__ import annotations

from pathlib import Path

from buddyswitch.foundation.tool_runtime import registry as tool_registry
from tests.support.paths import REPO_ROOT

ROOT = REPO_ROOT
TRIAGE = ROOT / "src/buddyswitch/modules/demand/skills/demand-triage/SKILL.md"
ORCHESTRATION = ROOT / "src/buddyswitch/modules/demand/skills/demand-orchestration/SKILL.md"
RETIRED_TASK_SKILL = ROOT / "src/buddyswitch/skills/shared/task-management/SKILL.md"
ROLE_ROOT = ROOT / "src/buddyswitch/roles"
ROLE_AGENTS = tuple(sorted(ROLE_ROOT.glob("*/AGENTS.md")))
TRIAGE_HANDLER = ROOT / "src/buddyswitch/modules/demand/private/adapters/daemon/demand_triage_handler.py"
ORCHESTRATION_HANDLER = ROOT / "src/buddyswitch/modules/demand/private/adapters/daemon/demand_orchestration_handler.py"


def _active_skill_files() -> list[Path]:
    return sorted(
        {
            *ROLE_ROOT.rglob("SKILL.md"),
            *(ROOT / "src/buddyswitch/modules").glob("*/skills/*/SKILL.md"),
        }
    )


def test_task_management_is_not_an_active_skill_or_role_dependency() -> None:
    from buddyswitch.application.build import activate_application

    application = activate_application()
    assert "task-management" not in {export.id for export in application.skills}
    for role_id in application.role_host.valid_role_ids:
        bootstrap = application.role_host.actor_bootstrap(role_id, codex_config="")
        selected = {skill.skill_id for skill in bootstrap.skills}
        assert "task-management" not in selected
        assert "demand-orchestration" in selected


def test_demand_orchestration_skill_owns_terminal_reconciliation_and_bounded_selection() -> None:
    text = ORCHESTRATION.read_text(encoding="utf-8")
    lowered = " ".join(text.lower().split())

    for token in (
        "task_sys__list",
        "task_sys__get",
        "demand_sys__list",
        "demand_sys__get",
        "demand_sys__complete",
        "task_sys__create",
        "selection_reason",
        "select at most one",
        "native goal",
        "update_goal",
        "user-facing delivery",
    ):
        assert token in lowered
    for criterion in (
        "urgency",
        "user commitment",
        "blocked downstream work",
        "continuity",
        "evidence readiness",
        "staleness",
    ):
        assert criterion in lowered


def test_orchestration_skill_keeps_task_and_demand_completion_decoupled() -> None:
    text = ORCHESTRATION.read_text(encoding="utf-8")
    lowered = " ".join(text.lower().split())

    assert "task completion is evidence, not demand completion" in lowered
    assert "do not automatically complete a demand" in lowered
    assert "leave the demand live" in lowered
    assert "if one task is active, stop" in lowered
    assert "if more than one is active" in lowered
    assert "task_sys.outcome_frame" not in text
    assert "task_sys.side_frame" not in text
    assert "task_sys.parent_frame" not in text
    assert "need_parent" not in text
    assert "select exactly one" not in lowered
    assert "one task per demand" not in lowered
    assert "execution brief" not in lowered


def test_orchestration_skill_makes_im_delivery_a_durable_completion_condition() -> None:
    text = ORCHESTRATION.read_text(encoding="utf-8")
    lowered = " ".join(text.lower().split())

    for token in (
        "im.message.created",
        "source message_id",
        "message__send",
        "reply_to",
        "message__get",
        "matching durable reply",
        "a codex final answer is not a central im delivery",
        "task and native goal completion do not prove delivery",
        "do not call `demand_sys__complete`",
    ):
        assert token in lowered
    assert "task objective must name the exact source message_id" in lowered
    assert "`id` equal to the reply message id" in lowered
    assert "`key` equal to `reply_to:<source message_id>`" in lowered
    assert "leave the demand live" in lowered


def test_triage_skill_owns_one_complete_relationship_sop() -> None:
    text = TRIAGE.read_text(encoding="utf-8")
    normalized = " ".join(text.lower().split())

    required = (
        'demand_sys__list(state="all")',
        "acceptance unit",
        "explicit current user",
        "user-requested grouping",
        "technical separability",
        "does not by itself create",
        "actor-proposed future improvement",
        "independently",
        "testing or research deliverable",
        "terminal demand",
        "correction demand",
        "merge_intake",
        "revise",
        "demand_sys__resolve_inbound",
    )
    for phrase in required:
        assert phrase in normalized

    assert 'demand_sys__list(state="live")' not in normalized
    assert "needs_parent_judgment" not in normalized
    assert "task_sys" not in normalized
    assert "message__send" not in normalized
    assert "demand_sys__complete" not in normalized
    assert "demand_sys__resolve_inbound" not in " ".join(
        ORCHESTRATION.read_text(encoding="utf-8").lower().split()
    )


def test_prompt_skill_and_role_layers_do_not_duplicate_tool_catalog_contracts() -> None:
    triage_skill = TRIAGE.read_text(encoding="utf-8").lower()
    orchestration_skill = ORCHESTRATION.read_text(encoding="utf-8").lower()
    triage_prompt = TRIAGE_HANDLER.read_text(encoding="utf-8").split('TRIAGE_PROMPT = """', 1)[1].split('"""', 1)[0].lower()
    orchestration_prompt = ORCHESTRATION_HANDLER.read_text(encoding="utf-8").split('ORCHESTRATION_PROMPT = """', 1)[1].split('"""', 1)[0].lower()

    assert "all six schema fields" not in triage_skill
    assert "`decision`, `reason`, `demand_ref`, `description`, `detail`" not in triage_skill
    assert "with only `demand_ref`, `objective`, and" not in orchestration_skill

    for reusable_rule in (
        "compare the entire live pool",
        "select exactly one demand",
        "select at most one demand",
        "self-contained native goal objective",
        "task completion is evidence",
    ):
        assert reusable_rule not in orchestration_prompt
    for reusable_rule in (
        "against all live demands visible",
        "do not ask the parent",
        "do not return a json proposal",
    ):
        assert reusable_rule not in triage_prompt

    for path in ROLE_AGENTS:
        text = path.read_text(encoding="utf-8").lower()
        assert "prefer native buddyswitch env mcp tools for durable runtime state:" not in text
        assert "raw inbound information is resolved only by its isolated demand-triage side" in text
        assert "task or goal completion does not itself complete the demand" in text


def test_active_skills_teach_no_retired_task_execution_model() -> None:
    retired = (
        "task_sys.side_frame",
        "task_sys.parent_frame",
        "task_sys.outcome_frame",
        "task_sys.need_parent",
        "task_sys.close",
        "task progress check",
        "recoverable_tasks",
    )
    for path in _active_skill_files():
        text = path.read_text(encoding="utf-8").lower()
        for token in retired:
            assert token not in text, (path, token)


def test_current_actor_surfaces_contain_no_retired_or_future_task_architecture() -> None:
    surfaces = (
        TRIAGE,
        ORCHESTRATION,
        TRIAGE_HANDLER,
        ORCHESTRATION_HANDLER,
        ROOT / "src/buddyswitch/modules/demand/private/adapters/tool/tool.py",
        ROOT / "src/buddyswitch/modules/task/private/adapters/tool/tool.py",
        *ROLE_AGENTS,
    )
    forbidden = (
        "task_sys.side_frame",
        "task_sys.parent_frame",
        "task_sys.outcome_frame",
        "need_parent",
        "control main",
        "work thread",
        "workhandoff",
    )
    for path in surfaces:
        text = path.read_text(encoding="utf-8").lower()
        for token in forbidden:
            assert token not in text, (path, token)


def test_actor_task_tool_surface_is_exactly_minimal() -> None:
    expected = {"list", "get", "create", "cancel"}

    assert set(tool_registry.supported_actions("task_sys")) == expected
    assert set(tool_registry.env_tools_description()["task_sys"]["operations"]) == expected
    assert not (ROOT / "src/buddyswitch/env/domain/task_sys.py").exists()


def test_retired_task_skill_is_not_treated_as_current_policy() -> None:
    assert not RETIRED_TASK_SKILL.exists()
