"""Tests for actor-local capability selection and resolution."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


from tests.support.paths import REPO_ROOT

ROOT = REPO_ROOT
HELPER_DIR = ROOT / "src" / "buddyswitch" / "launcher"

from buddyswitch.launcher import actor_capability  # noqa: E402


class ActorCapabilityTests(unittest.TestCase):
    def _instance_json(self, temp_root: Path) -> Path:
        instance_root = temp_root / "instances" / "act-dev-capability"
        instance_root.mkdir(parents=True, exist_ok=True)
        instance_json = instance_root / "instance.json"
        instance_json.write_text(
            json.dumps({"actor_id": "act-dev-capability", "instance_root": str(instance_root)}) + "\n",
            encoding="utf-8",
        )
        return instance_json

    def _write_config(self, instance_json: Path, payload: object) -> Path:
        path = actor_capability.capability_config_path(instance_json)
        path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
        return path

    def test_catalog_v1_has_exact_order_copy_and_mapping(self) -> None:
        self.assertEqual(actor_capability.CATALOG_VERSION, 1)
        self.assertEqual(
            [
                (row.id, row.label, row.description, row.model, row.effort)
                for row in actor_capability.CAPABILITY_LEVELS
            ],
            [
                ("fast", "Fast", "Responsive, high-strength reasoning", "gpt-5.6-luna", "xhigh"),
                ("balanced", "Balanced", "Strong everyday work", "gpt-5.6-terra", "high"),
                ("deep", "Deep", "Complex reasoning and coding", "gpt-5.6-sol", "xhigh"),
                ("maximum", "Maximum", "Highest capability and cost", "gpt-5.6-sol", "max"),
            ],
        )

    def test_seed_writes_balanced_parent_and_fast_side_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_json = self._instance_json(Path(temp_root))

            path = actor_capability.seed_actor_capabilities(instance_json)

            self.assertEqual(path, instance_json.parent / "capability-config.json")
            self.assertEqual(
                json.loads(path.read_text(encoding="utf-8")),
                {
                    "schema_version": 1,
                    "catalog_version": 1,
                    "parent": {
                        "level": "balanced",
                        "model": "gpt-5.6-terra",
                        "effort": "high",
                    },
                    "side": {
                        "level": "fast",
                        "model": "gpt-5.6-luna",
                        "effort": "xhigh",
                    },
                },
            )

    def test_seed_does_not_overwrite_existing_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_json = self._instance_json(Path(temp_root))
            path = self._write_config(
                instance_json,
                {
                    "schema_version": 1,
                    "catalog_version": 1,
                    "parent": {"level": "deep", "model": "gpt-5.6-sol", "effort": "xhigh"},
                    "side": {"level": "maximum", "model": "gpt-5.6-sol", "effort": "max"},
                },
            )
            before = path.read_text(encoding="utf-8")

            returned = actor_capability.seed_actor_capabilities(instance_json)

            self.assertEqual(returned, path)
            self.assertEqual(path.read_text(encoding="utf-8"), before)

    def test_load_requires_new_exact_snapshot_without_old_file_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_json = self._instance_json(Path(temp_root))
            (instance_json.parent / ("model" + "-config.json")).write_text(
                '{"schema_version":1,"parent":{},"side":{}}\n',
                encoding="utf-8",
            )

            with self.assertRaisesRegex(actor_capability.ActorCapabilityError, "capability config is missing"):
                actor_capability.load_actor_capabilities(instance_json)

    def test_load_preserves_positive_catalog_version_and_saved_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_json = self._instance_json(Path(temp_root))
            self._write_config(
                instance_json,
                {
                    "schema_version": 1,
                    "catalog_version": 7,
                    "parent": {"level": "balanced", "model": "saved-terra", "effort": "saved-high"},
                    "side": {"level": "fast", "model": "saved-luna", "effort": "saved-xhigh"},
                },
            )

            config = actor_capability.load_actor_capabilities(instance_json)
            parent = actor_capability.resolve_parent_capability(instance_json)

            self.assertEqual(config.catalog_version, 7)
            self.assertEqual((parent.model, parent.effort, parent.catalog_version), ("saved-terra", "saved-high", 7))

    def test_replace_deep_and_maximum_writes_one_exact_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_json = self._instance_json(Path(temp_root))
            actor_capability.seed_actor_capabilities(instance_json)

            config = actor_capability.replace_actor_capabilities(
                instance_json,
                parent_level="deep",
                side_level="maximum",
            )

            self.assertEqual((config.parent.level, config.side.level), ("deep", "maximum"))
            self.assertEqual(
                json.loads(actor_capability.capability_config_path(instance_json).read_text(encoding="utf-8")),
                {
                    "schema_version": 1,
                    "catalog_version": 1,
                    "parent": {"level": "deep", "model": "gpt-5.6-sol", "effort": "xhigh"},
                    "side": {"level": "maximum", "model": "gpt-5.6-sol", "effort": "max"},
                },
            )

    def test_invalid_replace_preserves_existing_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_json = self._instance_json(Path(temp_root))
            path = actor_capability.seed_actor_capabilities(instance_json)
            before = path.read_text(encoding="utf-8")

            with self.assertRaisesRegex(actor_capability.ActorCapabilityError, "parent_level must be one of"):
                actor_capability.replace_actor_capabilities(
                    instance_json,
                    parent_level="custom",
                    side_level="fast",
                )

            self.assertEqual(path.read_text(encoding="utf-8"), before)

    def test_atomic_replace_failure_preserves_snapshot_and_removes_temp_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_json = self._instance_json(Path(temp_root))
            path = actor_capability.seed_actor_capabilities(instance_json)
            before = path.read_text(encoding="utf-8")

            with mock.patch.object(actor_capability.os, "replace", side_effect=OSError("denied")):
                with self.assertRaisesRegex(actor_capability.ActorCapabilityError, "failed to write capability config"):
                    actor_capability.replace_actor_capabilities(
                        instance_json,
                        parent_level="deep",
                        side_level="maximum",
                    )

            self.assertEqual(path.read_text(encoding="utf-8"), before)
            self.assertEqual(list(path.parent.glob(".capability-config.json.*.tmp")), [])

    def test_load_rejects_invalid_shapes_and_values(self) -> None:
        invalid_cases = [
            ("not object", [], "must be an object"),
            (
                "unknown top level",
                {
                    "schema_version": 1,
                    "catalog_version": 1,
                    "parent": {"level": "balanced", "model": "model", "effort": "high"},
                    "side": {"level": "fast", "model": "model", "effort": "xhigh"},
                    "legacy": {},
                },
                "unknown top-level capability config key: legacy",
            ),
            (
                "wrong schema",
                {
                    "schema_version": 2,
                    "catalog_version": 1,
                    "parent": {"level": "balanced", "model": "model", "effort": "high"},
                    "side": {"level": "fast", "model": "model", "effort": "xhigh"},
                },
                "schema_version must be 1",
            ),
            (
                "invalid catalog version",
                {
                    "schema_version": 1,
                    "catalog_version": 0,
                    "parent": {"level": "balanced", "model": "model", "effort": "high"},
                    "side": {"level": "fast", "model": "model", "effort": "xhigh"},
                },
                "catalog_version must be a positive integer",
            ),
            (
                "unknown section key",
                {
                    "schema_version": 1,
                    "catalog_version": 1,
                    "parent": {
                        "level": "balanced",
                        "model": "model",
                        "effort": "high",
                        "provider": "openai",
                    },
                    "side": {"level": "fast", "model": "model", "effort": "xhigh"},
                },
                "unknown parent capability key: provider",
            ),
            (
                "invalid saved level",
                {
                    "schema_version": 1,
                    "catalog_version": 1,
                    "parent": {"level": "custom", "model": "model", "effort": "high"},
                    "side": {"level": "fast", "model": "model", "effort": "xhigh"},
                },
                "parent.level must be one of",
            ),
            (
                "empty model",
                {
                    "schema_version": 1,
                    "catalog_version": 1,
                    "parent": {"level": "balanced", "model": " ", "effort": "high"},
                    "side": {"level": "fast", "model": "model", "effort": "xhigh"},
                },
                "parent.model must be a non-empty string",
            ),
        ]

        for name, payload, error_text in invalid_cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp_root:
                instance_json = self._instance_json(Path(temp_root))
                self._write_config(instance_json, payload)

                with self.assertRaisesRegex(actor_capability.ActorCapabilityError, error_text):
                    actor_capability.load_actor_capabilities(instance_json)

    def test_management_description_projects_catalog_selections_and_effects(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_json = self._instance_json(Path(temp_root))
            actor_capability.seed_actor_capabilities(instance_json)

            payload = actor_capability.describe_actor_capabilities(
                actor_capability.load_actor_capabilities(instance_json)
            )

            self.assertEqual(payload["catalog_version"], 1)
            self.assertEqual([row["id"] for row in payload["levels"]], ["fast", "balanced", "deep", "maximum"])
            self.assertEqual(
                payload["parent"],
                {
                    "level": "balanced",
                    "model": "gpt-5.6-terra",
                    "effort": "high",
                    "effect": "applies_before_next_parent_submit",
                },
            )
            self.assertEqual(
                payload["side"],
                {
                    "level": "fast",
                    "model": "gpt-5.6-luna",
                    "effort": "xhigh",
                    "effect": "applies_to_new_side_threads_only",
                },
            )

    def test_side_explicit_level_uses_same_catalog_and_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_json = self._instance_json(Path(temp_root))
            actor_capability.seed_actor_capabilities(instance_json)

            resolved = actor_capability.resolve_side_capability(instance_json, explicit_level="deep")
            payload = actor_capability.apply_side_capability_metadata(
                {"action": "start"},
                resolved,
            )

            self.assertEqual(
                (resolved.level, resolved.model, resolved.effort, resolved.source),
                ("deep", "gpt-5.6-sol", "xhigh", "override"),
            )
            self.assertEqual(payload["model"], "gpt-5.6-sol")
            self.assertEqual(payload["model_reasoning_effort"], "xhigh")
            self.assertEqual(payload["capability_level"], "deep")
            self.assertEqual(payload["capability_source"], "override")
            self.assertEqual(payload["capability_durability"], "new_side_thread_only")
