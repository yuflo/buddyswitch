"""Current Skill boundary for Demand orchestration and native-Goal Tasks."""

from __future__ import annotations

import tomllib
from pathlib import Path

from env.tool_runtime import registry as tool_registry
from tests.support.paths import REPO_ROOT

ROOT = REPO_ROOT
MANIFEST = ROOT / "buddyswitch" / "manifest.toml"
TRIAGE = ROOT / "buddyswitch/skills/shared/demand-triage/SKILL.md"
ORCHESTRATION = ROOT / "buddyswitch/skills/shared/demand-orchestration/SKILL.md"
RETIRED_TASK_SKILL = ROOT / "buddyswitch/skills/shared/task-management/SKILL.md"


def _manifest() -> dict:
    return tomllib.loads(MANIFEST.read_text(encoding="utf-8"))


def _active_skill_files(manifest: dict) -> list[Path]:
    rows: list[Path] = []
    for skill in manifest.get("skills", []):
        if not isinstance(skill, dict) or not isinstance(skill.get("path"), str):
            continue
        rows.append(ROOT / skill["path"] / "SKILL.md")
    return rows


def test_task_management_is_not_an_active_skill_or_role_dependency() -> None:
    manifest = _manifest()
    skill_ids = {
        row.get("id")
        for row in manifest.get("skills", [])
        if isinstance(row, dict)
    }

    assert "task-management" not in skill_ids
    for role in manifest.get("roles", []):
        if isinstance(role, dict):
            assert "task-management" not in set(role.get("skills", []))
            assert "demand-orchestration" in set(role.get("skills", []))


def test_demand_orchestration_skill_owns_terminal_reconciliation_and_exact_selection() -> None:
    text = ORCHESTRATION.read_text(encoding="utf-8")
    lowered = " ".join(text.lower().split())

    for token in (
        "task_sys__list",
        "task_sys__get",
        "demand_sys__list",
        "demand_sys__get",
        "demand_sys__complete",
        "demand_sys__cancel",
        "demand_sys__revise",
        "task_sys__create",
        "selection_reason",
        "select exactly one",
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
    assert "do not automatically complete or cancel" in lowered
    assert "leave the demand live" in lowered
    assert "one task per demand" in lowered
    assert "task_sys.outcome_frame" not in text
    assert "task_sys.side_frame" not in text
    assert "task_sys.parent_frame" not in text
    assert "need_parent" not in text
    assert "choose at most one" not in lowered
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


def test_triage_skill_is_side_only_and_has_no_parent_or_task_selection_branch() -> None:
    text = TRIAGE.read_text(encoding="utf-8")
    lowered = text.lower()

    assert "demand_triage.resolve" in text
    assert "no_action_needed" in text
    assert "merge_intake" in text
    assert "needs_parent_judgment" not in text
    assert "parent judgment" not in lowered
    assert "task_sys__create" not in text
    assert "task_sys." not in text
    assert "message__send" not in text


def test_active_skills_teach_no_retired_task_execution_model() -> None:
    manifest = _manifest()
    retired = (
        "task_sys.side_frame",
        "task_sys.parent_frame",
        "task_sys.outcome_frame",
        "task_sys.need_parent",
        "task_sys.close",
        "task progress check",
        "recoverable_tasks",
    )
    for path in _active_skill_files(manifest):
        text = path.read_text(encoding="utf-8").lower()
        for token in retired:
            assert token not in text, (path, token)


def test_actor_task_tool_surface_is_exactly_minimal() -> None:
    expected = {"list", "get", "create", "cancel"}

    assert set(tool_registry.supported_actions("task_sys")) == expected
    assert set(tool_registry.env_tools_description()["task_sys"]["operations"]) == expected
    assert not hasattr(__import__("env.domain.task_sys", fromlist=["record_task_close"]), "record_task_close")


def test_retired_task_skill_is_not_treated_as_current_policy() -> None:
    if RETIRED_TASK_SKILL.exists():
        assert "task-management" not in {
            row.get("id")
            for row in _manifest().get("skills", [])
            if isinstance(row, dict)
        }
