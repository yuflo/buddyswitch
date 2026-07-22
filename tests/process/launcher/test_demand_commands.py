"""Public read-only Demand CLI contracts."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from tests.process.launcher._harness import ProcessLauncherHarness
from tests.support.paths import REPO_ROOT
from tests.support.processes import run_process


ROOT = REPO_ROOT
LAUNCHER = ROOT / "buddyswitch-codex"


class DemandCommandTests(ProcessLauncherHarness, unittest.TestCase):
    def _env(self, source_home: Path, state_root: Path) -> dict[str, str]:
        env = os.environ.copy()
        env["HOME"] = str(source_home)
        env["BUDDYSWITCH_SHARED_ROOT"] = str(state_root.parent.parent)
        env["BUDDYSWITCH_STATE_ROOT"] = str(state_root)
        env.pop("CODEX_HOME", None)
        return env

    def _write_aggregate(
        self,
        state_root: Path,
        *,
        actor_id: str = "act-dev-demand",
        role_id: str = "dev",
    ) -> Path:
        target = {"actor_id": actor_id, "role_id": role_id}
        path = (
            state_root
            / "buddyswitch"
            / "objects"
            / "demand-sys"
            / "actors"
            / f"{actor_id}-{role_id}.json"
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        records = {
            "demand-older": {
                "id": "demand-older",
                "intake_key": "inbound:older",
                "description": "Older need",
                "detail": "Private detail must not leave the external projection.",
                "source_refs": [{"type": "inbound", "ref": {"id": "info-older"}}],
                "revision": 2,
                "checked_revision": 1,
                "terminal": None,
                "created_at": "2026-07-19T01:00:00+08:00",
                "updated_at": "2026-07-19T01:10:00+08:00",
            },
            "demand-newer": {
                "id": "demand-newer",
                "intake_key": "actor:newer",
                "description": "Newer need",
                "detail": "Another private detail.",
                "source_refs": [],
                "revision": 3,
                "checked_revision": 3,
                "terminal": {
                    "type": "completed",
                    "at": "2026-07-19T02:10:00+08:00",
                    "summary": "Satisfied.",
                    "evidence_refs": [],
                },
                "created_at": "2026-07-19T02:00:00+08:00",
                "updated_at": "2026-07-19T02:10:00+08:00",
            },
        }
        path.write_text(
            json.dumps(
                {"schema_version": 2, "actor_target": target, "demands": records},
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return path

    def _run(self, env: dict[str, str], *args: str):
        return run_process(
            [str(LAUNCHER), *args],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_list_and_get_return_exact_actor_scoped_external_projections(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            state_root = source_home_path / ".codex-buddyswitch" / "state"
            self._write_aggregate(state_root)
            env = self._env(source_home_path, state_root)

            listed = self._run(env, "demand", "list", "--actor", "act-dev-demand")
            self.assertEqual(listed.returncode, 0, msg=listed.stdout + listed.stderr)
            rows = self._cli_success_data(listed, kind="demand.list")["demands"]
            self.assertEqual([row["demand_id"] for row in rows], ["demand-newer", "demand-older"])
            expected_fields = {
                "demand_id",
                "intake_key",
                "description",
                "actor",
                "revision",
                "checked_revision",
                "terminal",
                "created_at",
                "updated_at",
            }
            self.assertEqual(set(rows[0]), expected_fields)
            self.assertEqual(rows[0]["actor"], {"actor_id": "act-dev-demand", "role_id": "dev"})
            self.assertEqual(rows[0]["terminal"]["type"], "completed")
            self.assertNotIn("parent_id", rows[0])
            self.assertNotIn("depends_on", rows[0])

            fetched = self._run(
                env,
                "demand",
                "get",
                "demand-older",
                "--actor",
                "act-dev-demand",
            )
            self.assertEqual(fetched.returncode, 0, msg=fetched.stdout + fetched.stderr)
            demand = self._cli_success_data(fetched, kind="demand.get")["demand"]
            self.assertEqual(set(demand), expected_fields)
            self.assertEqual(demand["demand_id"], "demand-older")
            self.assertNotIn("detail", demand)
            self.assertNotIn("source_refs", demand)
            self.assertNotIn("parent_id", demand)
            self.assertNotIn("depends_on", demand)

            wrong_actor = self._run(
                env,
                "demand",
                "get",
                "demand-older",
                "--actor",
                "act-pm-demand",
            )
            self.assertEqual(wrong_actor.returncode, 3)
            self._cli_error(wrong_actor, code="NOT_FOUND")

    def test_cli_exposes_only_list_and_get_without_mutating_demand_state(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            state_root = source_home_path / ".codex-buddyswitch" / "state"
            aggregate = self._write_aggregate(state_root)
            env = self._env(source_home_path, state_root)
            before = aggregate.read_bytes()

            for action in ("create", "revise", "absorb_into", "complete", "cancel"):
                with self.subTest(action=action):
                    result = self._run(env, "demand", action)
                    self.assertEqual(result.returncode, 2)
                    self._cli_error(result, code="UNKNOWN_COMMAND")
                    self.assertEqual(aggregate.read_bytes(), before)

            help_result = self._run(env, "help")
            self.assertEqual(help_result.returncode, 0)
            self.assertIn("buddyswitch-codex demand list --actor <actor-id>", help_result.stdout)
            self.assertIn("buddyswitch-codex demand get <demand-id> --actor <actor-id>", help_result.stdout)
            for action in ("create", "revise", "absorb_into", "complete", "cancel"):
                self.assertNotIn(f"buddyswitch-codex demand {action}", help_result.stdout)

    def test_malformed_or_unscoped_arguments_fail_before_state_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            state_root = source_home_path / ".codex-buddyswitch" / "state"
            aggregate = self._write_aggregate(state_root)
            env = self._env(source_home_path, state_root)
            before = aggregate.read_bytes()
            cases = (
                ("demand", "list"),
                ("demand", "list", "--actor", "act-DEV-bad"),
                ("demand", "get", "demand-older"),
                ("demand", "get", "../bad", "--actor", "act-dev-demand"),
            )
            for argv in cases:
                with self.subTest(argv=argv):
                    result = self._run(env, *argv)
                    self.assertEqual(result.returncode, 2)
                    self._cli_error(result, code="INVALID_ARGUMENT")
                    self.assertEqual(aggregate.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
