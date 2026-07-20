"""Task-management architecture contract tests."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

from tests.support.paths import REPO_ROOT

ROOT = REPO_ROOT
SCRIPTS = ROOT / "scripts"

import env_manifest  # noqa: E402
from env.tool_runtime import registry as tool_router  # noqa: E402
from tests.support.runtime import RuntimeWorkspaceTestCase  # noqa: E402

TASK_SYS_OPERATIONS = {"create", "list", "get", "close", "cancel", "need_parent"}


class TaskManagementSkillArchitectureTests(RuntimeWorkspaceTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.manifest_path = ROOT / "buddyswitch" / "manifest.toml"
        self.manifest = env_manifest.load_manifest(self.manifest_path)
        self.actor_id = self._runtime_actor_id(role="pm", label="act-pm-task-arch")
        self.instance_root = self._runtime_path(f"instances/{self.actor_id}")
        self.instance_json = self.instance_root / "instance.json"
        self.instance_payload = {
            "actor_id": self.actor_id,
            "role": "pm",
            "status": "active",
            "instance_root": str(self.instance_root),
            "workspace_dir": str(self.runtime_root),
        }
        self.instance_json.parent.mkdir(parents=True, exist_ok=True)
        self.instance_json.write_text(json.dumps(self.instance_payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")

    def _dispatch(self, *, role: str, tool: str, action: str, args: dict[str, object]) -> dict[str, object]:
        actor_id = self._runtime_actor_id(role=role, label="act-pm-task-arch")
        return tool_router.dispatch_env_tool_request(
            payload={"tool": tool, "action": action, "args": args},
            active_role=role,
            actor_id=actor_id,
            instance_json=self.instance_json,
            instance_payload={**self.instance_payload, "actor_id": actor_id, "role": role},
            manifest=self.manifest,
            manifest_path=self.manifest_path,
        )

    def test_task_management_skill_points_actor_guidance_to_task_sys(self) -> None:
        skill_path = ROOT / "buddyswitch" / "skills" / "shared" / "task-management" / "SKILL.md"
        self.assertTrue(skill_path.exists(), msg=skill_path)
        self.assertFalse((ROOT / "buddyswitch" / "skills" / "shared" / "task-tool" / "SKILL.md").exists())
        skill_text = skill_path.read_text(encoding="utf-8")
        lowered = skill_text.lower()
        self.assertIn("task sys", lowered)
        self.assertIn("[demand check]", lowered)
        self.assertIn("task_sys.completion_frame", skill_text)
        self.assertIn("task_sys.create", skill_text)
        self.assertIn("task_sys.list", skill_text)
        self.assertIn("task_sys.get", skill_text)
        self.assertIn("task_sys.close", skill_text)
        self.assertIn("task_sys.cancel", skill_text)
        self.assertIn("task_sys.need_parent", skill_text)
        self.assertNotIn("task_sys.checkpoint", skill_text)
        self.assertNotIn("task_sys.checkpoint_update", skill_text)
        self.assertNotIn("checkpoint_update", skill_text)
        self.assertIn("env.tool", lowered)
        for old_token in (
            "taskbox",
            "taskviewmodel",
            "task.current",
            "task.capture",
            "task.checkout",
            "task__current",
            "task__checkout",
        ):
            with self.subTest(token=old_token):
                self.assertNotIn(old_token, lowered)

    def test_task_management_skill_teaches_frame_specific_task_sys_operations(self) -> None:
        skill_path = ROOT / "buddyswitch" / "skills" / "shared" / "task-management" / "SKILL.md"
        skill_text = skill_path.read_text(encoding="utf-8")

        self.assertIn("On `task_sys.side_frame`, call `task_sys.close`", skill_text)
        self.assertIn("On `task_sys.parent_frame`, complete the requested parent work and call `task_sys.close`", skill_text)
        self.assertIn("choose at most one", skill_text.lower())
        self.assertIn("latest demand revision", skill_text.lower())
        self.assertIn("task_sys.task", skill_text)
        self.assertIn('{"type":"task_sys.task","ref":{"task_id":"<task_id>"}}', skill_text)
        self.assertIn("pass the frame's `evidence_ref` unchanged", skill_text.lower())
        self.assertIn("acknowledge the returned completed revision", skill_text.lower())
        self.assertIn("continue now with the task selection rule", skill_text.lower())
        self.assertIn("keep the demand live", skill_text.lower())
        self.assertIn("call `demand_sys.get`", skill_text.lower())
        self.assertIn("already terminal, do not mutate it", skill_text.lower())
        self.assertNotIn("For IM source frames", skill_text)
        self.assertNotIn("message.send(reply_to=...)", skill_text)
        self.assertNotIn("message.mark(..., disposition=absorbed)", skill_text)
        self.assertNotIn("source-" + "bound", skill_text)
        self.assertIn("Use `task_sys.list` or `task_sys.get` to read ongoing Task Sys task state.", skill_text)
        self.assertIn("Task `status` is the only lifecycle truth", skill_text)
        self.assertIn("Use `task_sys.cancel` when the actor decides an active Task must stop without completion.", skill_text)
        self.assertIn("continue parent work without changing status", skill_text)
        self.assertNotIn("task_desc", skill_text)
        self.assertNotIn("task_relation", skill_text)
        self.assertNotIn("update_task_analysis", skill_text)
        self.assertNotIn("checkpoint", skill_text.lower())
        stale_finish = "finish with exactly one Task Sys side " + "result"
        stale_label = "Task Sys side " + "result"
        self.assertNotIn(stale_finish, skill_text)
        self.assertNotIn(stale_label, skill_text)

    def test_task_sys_close_surfaces_use_frame_work_not_source_bound_work(self) -> None:
        close_action = tool_router.get_action_definition("task_sys", "close")
        surface_text = "\n".join((close_action.description, *close_action.use_when))
        self.assertIn("required frame work", surface_text)
        self.assertNotIn("source-" + "bound work", surface_text)

        impl_text = (ROOT / "scripts" / "env" / "tools" / "task_sys" / "_impl.py").read_text(encoding="utf-8")
        self.assertIn("required task work", impl_text)
        self.assertNotIn("source-" + "bound task", impl_text)

    def test_runtime_role_guidance_prefers_task_sys_tools(self) -> None:
        for path in sorted((ROOT / "tools" / "launcher" / "assets" / "roles").glob("*/AGENTS.md")):
            text = path.read_text(encoding="utf-8")
            with self.subTest(role=path.parent.name):
                self.assertIn("task_sys__list", text)
                self.assertIn("task_sys__create", text)
                self.assertIn("task_sys__get", text)
                self.assertIn("task_sys__close", text)
                self.assertIn("task_sys__cancel", text)
                self.assertIn("task_sys__need_parent", text)
                self.assertNotIn("task_sys__update_task_analysis", text)
                self.assertNotIn("task_sys__checkpoint_update", text)
                self.assertNotIn("task__current", text)
                self.assertNotIn("choose at most one", text.lower())
                self.assertNotIn("latest demand revision", text.lower())

    def test_task_sys_is_the_only_actor_facing_task_tool(self) -> None:
        self.assertNotIn("task", tool_router.supported_tools())
        self.assertIn("task_sys", tool_router.supported_tools())
        catalog = tool_router.env_tools_description()
        self.assertNotIn("task", catalog)
        self.assertEqual(set(catalog["task_sys"]["operations"]), TASK_SYS_OPERATIONS)
        self.assertEqual(set(tool_router.supported_actions("task_sys")), TASK_SYS_OPERATIONS)

    def test_context_decision_surface_names_task_sys_operations(self) -> None:
        payload = self._dispatch(role="pm", tool="context", action="get", args={})
        self.assertTrue(payload["ok"], msg=payload)
        operation_semantics = payload["operation_semantics"]
        for operation in TASK_SYS_OPERATIONS:
            self.assertIn(f"task_sys.{operation}", operation_semantics)
        self.assertNotIn("task.current", operation_semantics)
        self.assertNotIn("task.capture", operation_semantics)
        self.assertEqual(payload["decision_surface"]["binding_state"]["state"], "runless")

    def test_old_task_tool_is_retired(self) -> None:
        rejected = self._dispatch(role="pm", tool="task", action="current", args={})
        self.assertFalse(rejected["ok"], msg=rejected)
        self.assertEqual((rejected.get("error") or {}).get("code"), "E_ENV_TOOL")
        self.assertIn("unsupported env.tool payload.tool: task", str(rejected.get("error", {}).get("message")))

    def test_live_task_surfaces_do_not_teach_old_task_operations(self) -> None:
        live_paths = [
            ROOT / "buddyswitch" / "skills" / "shared" / "task-management" / "SKILL.md",
            ROOT / "scripts" / "env" / "tool_runtime" / "context.py",
            ROOT / "scripts" / "env" / "tool_runtime" / "role_auth.py",
            ROOT / "scripts" / "env" / "tools" / "context" / "_impl.py",
        ]
        forbidden = (
            "task.propose",
            "task.confirm",
            "task__propose",
            "task__confirm",
            "Task Handling Cue",
            "TaskViewModel",
            "task_sys.checkpoint",
            "task_sys.checkpoint_update",
            "task_sys__checkpoint_update",
            "checkpoint_update",
        )
        for path in live_paths:
            text = path.read_text(encoding="utf-8")
            for token in forbidden:
                with self.subTest(path=path, token=token):
                    self.assertNotIn(token, text)

    def test_im_message_frame_capability_surfaces_do_not_teach_source_bound_only_rules(self) -> None:
        surfaces = [
            ROOT / "tools" / "launcher" / ("task_sys_" + "runtime.py"),
            ROOT / "buddyswitch" / "skills" / "shared" / "task-management" / "SKILL.md",
            ROOT / "scripts" / "env" / "tools" / "task_sys" / "tool.py",
            ROOT / "scripts" / "env" / "tools" / "task_sys" / "_impl.py",
        ]
        stale_tokens = (
            "Current-source IM " + "closure",
            "Do not start a new IM " + "conversation",
            "Do not send to target_identity_id " + "from side",
            "Only after the source-" + "bound IM action succeeds",
            "source-" + "bound work",
            "source-" + "bound task",
        )
        for path in surfaces:
            text = path.read_text(encoding="utf-8")
            for token in stale_tokens:
                with self.subTest(path=str(path.relative_to(ROOT)), token=token):
                    self.assertNotIn(token, text)
