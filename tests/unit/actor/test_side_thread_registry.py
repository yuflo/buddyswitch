"""Tests for the actor side-thread registry helper."""

from __future__ import annotations

import importlib
import json
import tempfile
import unittest
from itertools import count
from pathlib import Path
from typing import Any


from tests.support.paths import REPO_ROOT

ROOT = REPO_ROOT
REGISTRY_PATH = ROOT / "src" / "buddyswitch" / "launcher" / "side_thread_registry.py"
MODULE_COUNTER = count()


def load_registry() -> Any:
    if not REGISTRY_PATH.exists():
        raise AssertionError(f"expected module to exist: {REGISTRY_PATH}")
    return importlib.reload(importlib.import_module("buddyswitch.launcher.side_thread_registry"))


class SideThreadRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = load_registry()

    def _instance_json(self, temp_root: str, *, actor_id: str = "act-dev-side") -> Path:
        instance_root = Path(temp_root) / "instances" / actor_id
        instance_root.mkdir(parents=True, exist_ok=True)
        instance_json = instance_root / "instance.json"
        instance_json.write_text(
            json.dumps(
                {
                    "actor_id": actor_id,
                    "role": "dev",
                    "thread_id": "thr-main",
                    "side_threads": [],
                },
                ensure_ascii=True,
            )
            + "\n",
            encoding="utf-8",
        )
        return instance_json

    def _payload(self, instance_json: Path) -> dict[str, Any]:
        return json.loads(instance_json.read_text(encoding="utf-8"))

    def test_register_writes_open_side_thread_row_with_timestamps(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_json = self._instance_json(temp_root)

            row = self.registry.register_side_thread(
                instance_json,
                actor_id="act-dev-side",
                parent_thread_id="thr-main",
                side_thread_id="thr-side-1",
                now=lambda: "2026-06-02T00:00:00Z",
            )

            self.assertEqual(row["thread_id"], "thr-side-1")
            self.assertEqual(row["parent_thread_id"], "thr-main")
            self.assertEqual(row["status"], "open")
            self.assertEqual(row["created_at"], "2026-06-02T00:00:00Z")
            self.assertEqual(row["updated_at"], "2026-06-02T00:00:00Z")
            payload = self._payload(instance_json)
            self.assertEqual(payload["side_threads"], [row])
            self.assertEqual(payload["updated_at"], "2026-06-02T00:00:00Z")

    def test_register_can_write_purpose_and_turn_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_json = self._instance_json(temp_root)

            row = self.registry.register_side_thread(
                instance_json,
                actor_id="act-dev-side",
                parent_thread_id="thr-main",
                side_thread_id="thr-side-triage",
                purpose="demand-triage",
                turn_id="turn-side-1",
                now=lambda: "2026-06-30T00:00:00Z",
            )

            self.assertEqual(row["thread_id"], "thr-side-triage")
            self.assertEqual(row["purpose"], "demand-triage")
            self.assertEqual(row["turn_id"], "turn-side-1")
            payload = self._payload(instance_json)
            self.assertEqual(payload["side_threads"], [row])

    def test_register_replaces_existing_side_thread_without_duplicate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_json = self._instance_json(temp_root)
            self.registry.register_side_thread(
                instance_json,
                actor_id="act-dev-side",
                parent_thread_id="thr-main",
                side_thread_id="thr-side-1",
                now=lambda: "2026-06-02T00:00:00Z",
            )

            row = self.registry.register_side_thread(
                instance_json,
                actor_id="act-dev-side",
                parent_thread_id="thr-main",
                side_thread_id="thr-side-1",
                now=lambda: "2026-06-02T00:01:00Z",
            )

            payload = self._payload(instance_json)
            self.assertEqual(len(payload["side_threads"]), 1)
            self.assertEqual(payload["side_threads"][0], row)
            self.assertEqual(row["created_at"], "2026-06-02T00:01:00Z")

    def test_update_side_thread_rewrites_turn_metadata_without_duplicate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_json = self._instance_json(temp_root)
            self.registry.register_side_thread(
                instance_json,
                actor_id="act-dev-side",
                parent_thread_id="thr-main",
                side_thread_id="thr-side-1",
                turn_id="turn-old",
                now=lambda: "2026-06-02T00:00:00Z",
            )

            row = self.registry.update_side_thread(
                instance_json,
                actor_id="act-dev-side",
                parent_thread_id="thr-main",
                side_thread_id="thr-side-1",
                turn_id="turn-new",
                now=lambda: "2026-06-02T00:01:00Z",
            )

            self.assertEqual(row["thread_id"], "thr-side-1")
            self.assertEqual(row["turn_id"], "turn-new")
            self.assertEqual(row["created_at"], "2026-06-02T00:00:00Z")
            self.assertEqual(row["updated_at"], "2026-06-02T00:01:00Z")
            payload = self._payload(instance_json)
            self.assertEqual(payload["side_threads"], [row])
            self.assertEqual(payload["updated_at"], "2026-06-02T00:01:00Z")

    def test_transition_side_turn_is_compare_and_set_for_progress_check_claims(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_json = self._instance_json(temp_root)
            self.registry.register_side_thread(
                instance_json,
                actor_id="act-dev-side",
                parent_thread_id="thr-main",
                side_thread_id="thr-side-1",
                turn_id="turn-work-1",
                turn_kind="work",
                now=lambda: "2026-06-02T00:00:00Z",
            )

            claimed = self.registry.transition_side_thread_turn(
                instance_json,
                actor_id="act-dev-side",
                parent_thread_id="thr-main",
                side_thread_id="thr-side-1",
                expected_turn_id="turn-work-1",
                expected_turn_kind="work",
                turn_kind="progress_check_pending",
                now=lambda: "2026-06-02T00:01:00Z",
            )
            duplicate = self.registry.transition_side_thread_turn(
                instance_json,
                actor_id="act-dev-side",
                parent_thread_id="thr-main",
                side_thread_id="thr-side-1",
                expected_turn_id="turn-work-1",
                expected_turn_kind="work",
                turn_kind="progress_check_pending",
                now=lambda: "2026-06-02T00:02:00Z",
            )

            self.assertIsNotNone(claimed)
            self.assertEqual(claimed["turn_kind"], "progress_check_pending")
            self.assertIsNone(duplicate)
            self.assertEqual(self._payload(instance_json)["side_threads"][0], claimed)

    def test_require_accepts_open_side_thread_for_actor_and_parent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_json = self._instance_json(temp_root)
            expected = self.registry.register_side_thread(
                instance_json,
                actor_id="act-dev-side",
                parent_thread_id="thr-main",
                side_thread_id="thr-side-1",
                now=lambda: "2026-06-02T00:00:00Z",
            )

            actual = self.registry.require_side_thread(
                instance_json,
                actor_id="act-dev-side",
                parent_thread_id="thr-main",
                side_thread_id="thr-side-1",
            )

            self.assertEqual(actual, expected)

    def test_require_rejects_unknown_wrong_parent_and_main_thread_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_json = self._instance_json(temp_root)
            self.registry.register_side_thread(
                instance_json,
                actor_id="act-dev-side",
                parent_thread_id="thr-main",
                side_thread_id="thr-side-1",
                now=lambda: "2026-06-02T00:00:00Z",
            )

            with self.assertRaisesRegex(self.registry.SideThreadRegistryError, "not registered"):
                self.registry.require_side_thread(
                    instance_json,
                    actor_id="act-dev-side",
                    parent_thread_id="thr-main",
                    side_thread_id="thr-unknown",
                )
            with self.assertRaisesRegex(self.registry.SideThreadRegistryError, "not registered"):
                self.registry.require_side_thread(
                    instance_json,
                    actor_id="act-dev-side",
                    parent_thread_id="thr-other-parent",
                    side_thread_id="thr-side-1",
                )
            with self.assertRaisesRegex(self.registry.SideThreadRegistryError, "main thread"):
                self.registry.require_side_thread(
                    instance_json,
                    actor_id="act-dev-side",
                    parent_thread_id="thr-main",
                    side_thread_id="thr-main",
                )

    def test_unregister_removes_only_matching_side_thread(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_json = self._instance_json(temp_root)
            self.registry.register_side_thread(
                instance_json,
                actor_id="act-dev-side",
                parent_thread_id="thr-main",
                side_thread_id="thr-side-1",
                now=lambda: "2026-06-02T00:00:00Z",
            )
            self.registry.register_side_thread(
                instance_json,
                actor_id="act-dev-side",
                parent_thread_id="thr-main",
                side_thread_id="thr-side-2",
                now=lambda: "2026-06-02T00:01:00Z",
            )

            removed = self.registry.unregister_side_thread(
                instance_json,
                actor_id="act-dev-side",
                parent_thread_id="thr-main",
                side_thread_id="thr-side-1",
                now=lambda: "2026-06-02T00:02:00Z",
            )

            self.assertTrue(removed)
            payload = self._payload(instance_json)
            self.assertEqual([row["thread_id"] for row in payload["side_threads"]], ["thr-side-2"])
            self.assertEqual(payload["updated_at"], "2026-06-02T00:02:00Z")

    def test_invalid_actor_and_missing_instance_fail_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_json = self._instance_json(temp_root)
            before = instance_json.read_text(encoding="utf-8")

            with self.assertRaisesRegex(self.registry.SideThreadRegistryError, "Actor id mismatch"):
                self.registry.register_side_thread(
                    instance_json,
                    actor_id="act-other",
                    parent_thread_id="thr-main",
                    side_thread_id="thr-side-1",
                )
            with self.assertRaisesRegex(self.registry.SideThreadRegistryError, "Instance record missing"):
                self.registry.register_side_thread(
                    Path(temp_root) / "missing.json",
                    actor_id="act-dev-side",
                    parent_thread_id="thr-main",
                    side_thread_id="thr-side-1",
                )

            self.assertEqual(instance_json.read_text(encoding="utf-8"), before)
