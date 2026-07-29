"""Demand aggregate repository atomicity and ownership integration tests."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest
from unittest.mock import patch

from buddyswitch.modules.demand.private.state import demands
from tests.support.paths import REPO_ROOT
from tests.support.processes import ResourceLedger
from tests.support.runtime import RuntimeWorkspaceTestCase


ACTOR_TARGET = {"actor_id": "act-pm-demand-repo", "role_id": "pm"}


class DemandRepositoryAtomicityTests(RuntimeWorkspaceTestCase):
    def _aggregate_path(self) -> Path:
        return demands.actor_state_path(ACTOR_TARGET)

    def _child_env(self) -> dict[str, str]:
        env = os.environ.copy()
        env.pop("PYTHONPATH", None)
        return env

    def test_absent_actor_state_loads_one_empty_schema_v5_aggregate(self) -> None:
        expected = {
            "schema_version": 5,
            "actor_target": ACTOR_TARGET,
            "demands": {},
            "demand_pool_revision": 0,
            "ingress_receipts": {},
        }

        first = demands.load_actor_state(ACTOR_TARGET)
        first["demands"]["demand-local-mutation"] = {"id": "demand-local-mutation"}

        self.assertEqual(demands.load_actor_state(ACTOR_TARGET), expected)
        self.assertFalse(self._aggregate_path().exists())

    def test_successful_transaction_persists_one_actor_aggregate(self) -> None:
        demand_id = "demand-first"

        def add_demand(state: dict[str, object]) -> tuple[bool, dict[str, str]]:
            demands_by_id = state["demands"]
            assert isinstance(demands_by_id, dict)
            demands_by_id[demand_id] = {"id": demand_id}
            return True, {"demand_id": demand_id}

        with patch.object(
            demands.runtime_files,
            "write_json_object",
            wraps=demands.runtime_files.write_json_object,
        ) as write_json_object:
            result = demands.transact_actor_state(ACTOR_TARGET, add_demand)

        self.assertEqual(result, {"demand_id": demand_id})
        write_json_object.assert_called_once()
        self.assertEqual(
            demands.load_actor_state(ACTOR_TARGET),
            {
                "schema_version": 5,
                "actor_target": ACTOR_TARGET,
                "demands": {demand_id: {"id": demand_id}},
                "demand_pool_revision": 0,
                "ingress_receipts": {},
            },
        )

    def test_unchanged_transaction_does_not_create_actor_aggregate(self) -> None:
        mutator_calls = 0

        def inspect_only(state: dict[str, object]) -> tuple[bool, str]:
            nonlocal mutator_calls
            mutator_calls += 1
            self.assertEqual(state["demands"], {})
            return False, "unchanged"

        self.assertEqual(
            demands.transact_actor_state(ACTOR_TARGET, inspect_only),
            "unchanged",
        )
        self.assertEqual(mutator_calls, 1)
        self.assertFalse(self._aggregate_path().exists())

    def test_invalid_mutator_result_is_rejected_without_write(self) -> None:
        mutator_calls = 0

        def invalid_result(state: dict[str, object]) -> tuple[str, None]:
            nonlocal mutator_calls
            mutator_calls += 1
            return "yes", None

        with self.assertRaisesRegex(ValueError, "mutator must return"):
            demands.transact_actor_state(ACTOR_TARGET, invalid_result)  # type: ignore[arg-type]

        self.assertEqual(mutator_calls, 1)
        self.assertFalse(self._aggregate_path().exists())

    def test_changed_transaction_validates_complete_aggregate_before_write(self) -> None:
        def corrupt_aggregate(state: dict[str, object]) -> tuple[bool, None]:
            state["schema_version"] = 2
            return True, None

        with self.assertRaisesRegex(ValueError, "schema_version"):
            demands.transact_actor_state(ACTOR_TARGET, corrupt_aggregate)

        self.assertFalse(self._aggregate_path().exists())

    def test_failed_mutator_keeps_previous_aggregate_byte_identical(self) -> None:
        def seed(state: dict[str, object]) -> tuple[bool, None]:
            demands_by_id = state["demands"]
            assert isinstance(demands_by_id, dict)
            demands_by_id["demand-existing"] = {"id": "demand-existing"}
            return True, None

        demands.transact_actor_state(ACTOR_TARGET, seed)
        state_path = self._aggregate_path()
        before = state_path.read_bytes()

        def fail_after_mutation(state: dict[str, object]) -> tuple[bool, None]:
            demands_by_id = state["demands"]
            assert isinstance(demands_by_id, dict)
            demands_by_id["demand-uncommitted"] = {"id": "demand-uncommitted"}
            raise RuntimeError("domain mutation failed")

        with self.assertRaisesRegex(RuntimeError, "domain mutation failed"):
            demands.transact_actor_state(ACTOR_TARGET, fail_after_mutation)

        self.assertEqual(state_path.read_bytes(), before)
        self.assertNotIn(
            "demand-uncommitted",
            demands.load_actor_state(ACTOR_TARGET)["demands"],
        )

    def test_two_process_writers_serialize_without_losing_either_change(self) -> None:
        marker_path = self.runtime_root / "first-writer-entered"
        child_source = """
from pathlib import Path
import sys
import time

from buddyswitch.modules.demand.private.state import demands

actor_target = {"actor_id": "act-pm-demand-repo", "role_id": "pm"}
demand_id = sys.argv[1]
marker = None if sys.argv[2] == "-" else Path(sys.argv[2])
delay = float(sys.argv[3])

def mutate(state):
    if marker is not None:
        marker.write_text("entered", encoding="utf-8")
    if delay:
        time.sleep(delay)
    state["demands"][demand_id] = {"id": demand_id}
    return True, demand_id

demands.transact_actor_state(actor_target, mutate)
"""
        ledger = ResourceLedger.from_environment()
        first = ledger.start_process(
            [
                sys.executable,
                "-c",
                child_source,
                "demand-first-process",
                str(marker_path),
                "0.4",
            ],
            cwd=REPO_ROOT,
            env=self._child_env(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        deadline = time.monotonic() + 5.0
        while not marker_path.exists() and time.monotonic() < deadline:
            if first.poll() is not None:
                stdout, stderr = first.communicate()
                self.fail(
                    "first writer exited before entering its transaction: "
                    f"stdout={stdout!r} stderr={stderr!r}"
                )
            time.sleep(0.01)
        self.assertTrue(marker_path.exists(), "first writer did not enter its transaction")

        second = ledger.start_process(
            [
                sys.executable,
                "-c",
                child_source,
                "demand-second-process",
                "-",
                "0",
            ],
            cwd=REPO_ROOT,
            env=self._child_env(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        first_stdout, first_stderr = first.communicate(timeout=5.0)
        second_stdout, second_stderr = second.communicate(timeout=5.0)
        ledger.reconcile_descriptors()

        self.assertEqual(
            (first.returncode, first_stdout, first_stderr),
            (0, "", ""),
        )
        self.assertEqual(
            (second.returncode, second_stdout, second_stderr),
            (0, "", ""),
        )
        self.assertEqual(
            set(demands.load_actor_state(ACTOR_TARGET)["demands"]),
            {"demand-first-process", "demand-second-process"},
        )
        aggregate_path = self._aggregate_path()
        self.assertEqual(list(aggregate_path.parent.iterdir()), [aggregate_path])

    def test_schema_v1_or_wrong_actor_target_is_rejected_without_rewrite(self) -> None:
        state_path = self._aggregate_path()
        invalid_aggregates = {
            "wrong schema": {
                "schema_version": 1,
                "actor_target": ACTOR_TARGET,
                "demands": {},
            },
            "wrong actor target": {
                "schema_version": 5,
                "actor_target": {"actor_id": "act-pm-other", "role_id": "pm"},
                "demands": {},
                "demand_pool_revision": 0,
                "ingress_receipts": {},
            },
            "retired actor creation receipts": {
                "schema_version": 5,
                "actor_target": ACTOR_TARGET,
                "demands": {},
                "demand_pool_revision": 0,
                "ingress_receipts": {},
                "actor_creation_receipts": {},
            },
        }
        for label, payload in invalid_aggregates.items():
            with self.subTest(label=label):
                state_path.parent.mkdir(parents=True, exist_ok=True)
                state_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
                before = state_path.read_bytes()
                mutator_called = False

                def must_not_run(state: dict[str, object]) -> tuple[bool, None]:
                    nonlocal mutator_called
                    mutator_called = True
                    return True, None

                with self.assertRaisesRegex(
                    ValueError,
                    "schema_version must be 5|actor_target|must contain exactly",
                ):
                    demands.transact_actor_state(ACTOR_TARGET, must_not_run)

                self.assertFalse(mutator_called)
                self.assertEqual(state_path.read_bytes(), before)

    def test_actor_target_requires_exact_canonical_ids(self) -> None:
        invalid_targets = (
            {"actor_id": "act-pm-demand-repo"},
            {"actor_id": "act-pm-demand-repo", "role_id": "pm", "extra": True},
            {"actor_id": "../escape", "role_id": "pm"},
        )
        for actor_target in invalid_targets:
            with self.subTest(actor_target=actor_target):
                with self.assertRaises(ValueError):
                    demands.actor_state_path(actor_target)


if __name__ == "__main__":
    unittest.main()
