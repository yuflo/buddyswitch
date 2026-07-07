#!/usr/bin/env python3
"""Tests for actor-local model config loading and resolution."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HELPER_DIR = ROOT / "tools" / "launcher"
if str(HELPER_DIR) not in sys.path:
    sys.path.insert(0, str(HELPER_DIR))

import actor_model_config  # noqa: E402


class ActorModelConfigTests(unittest.TestCase):
    def _instance_json(self, temp_root: Path) -> Path:
        instance_root = temp_root / "instances" / "act-pm-test"
        instance_root.mkdir(parents=True, exist_ok=True)
        instance_json = instance_root / "instance.json"
        instance_json.write_text(
            json.dumps(
                {
                    "actor_id": "act-pm-test",
                    "role": "pm",
                    "instance_root": str(instance_root),
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return instance_json

    def _write_config(self, instance_json: Path, payload: dict[str, object]) -> Path:
        path = actor_model_config.model_config_path(instance_json)
        path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
        return path

    def test_path_and_default_seed_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_json = self._instance_json(Path(temp_root))

            path = actor_model_config.model_config_path(instance_json)
            self.assertEqual(path, instance_json.parent / "model-config.json")
            self.assertFalse(path.exists())

            returned = actor_model_config.seed_model_config_if_missing(instance_json)

            self.assertEqual(returned, path)
            self.assertEqual(
                json.loads(path.read_text(encoding="utf-8")),
                {
                    "schema_version": 1,
                    "parent": {},
                    "side": {},
                },
            )

    def test_seed_does_not_overwrite_existing_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_json = self._instance_json(Path(temp_root))
            path = self._write_config(
                instance_json,
                {
                    "schema_version": 1,
                    "parent": {"model": "gpt-5.4"},
                    "side": {},
                },
            )

            actor_model_config.seed_model_config_if_missing(instance_json)

            self.assertEqual(
                json.loads(path.read_text(encoding="utf-8")),
                {
                    "schema_version": 1,
                    "parent": {"model": "gpt-5.4"},
                    "side": {},
                },
            )

    def test_missing_file_resolves_empty_defaults_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_json = self._instance_json(Path(temp_root))
            path = actor_model_config.model_config_path(instance_json)

            loaded = actor_model_config.load_model_config(instance_json)
            parent = actor_model_config.resolve_parent_options(instance_json)
            side = actor_model_config.resolve_side_options(instance_json)

            self.assertFalse(path.exists())
            self.assertEqual(loaded.schema_version, 1)
            self.assertEqual(loaded.parent, {})
            self.assertEqual(loaded.side, {})
            self.assertFalse(parent.has_values)
            self.assertIsNone(parent.model)
            self.assertIsNone(parent.effort)
            self.assertEqual(parent.model_source, "codex_default")
            self.assertEqual(parent.effort_source, "codex_default")
            self.assertFalse(side.has_values)
            self.assertEqual(side.model_source, "codex_default")
            self.assertEqual(side.effort_source, "codex_default")

    def test_validation_rejects_invalid_shapes_and_values(self) -> None:
        invalid_cases: list[tuple[str, dict[str, object], str]] = [
            ("missing schema", {"parent": {}, "side": {}}, "schema_version"),
            ("wrong schema", {"schema_version": 2, "parent": {}, "side": {}}, "schema_version"),
            ("parent not object", {"schema_version": 1, "parent": [], "side": {}}, "parent"),
            ("side not object", {"schema_version": 1, "parent": {}, "side": []}, "side"),
            ("empty model", {"schema_version": 1, "parent": {"model": "  "}, "side": {}}, "model"),
            ("invalid effort", {"schema_version": 1, "parent": {}, "side": {"effort": "max"}}, "effort"),
            ("unknown top", {"schema_version": 1, "parent": {}, "side": {}, "legacy": {}}, "legacy"),
            ("unknown nested", {"schema_version": 1, "parent": {"provider": "openai"}, "side": {}}, "provider"),
        ]

        for name, payload, error_text in invalid_cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp_root:
                instance_json = self._instance_json(Path(temp_root))
                self._write_config(instance_json, payload)

                with self.assertRaisesRegex(actor_model_config.ActorModelConfigError, error_text):
                    actor_model_config.load_model_config(instance_json)

    def test_resolves_configured_parent_options(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_json = self._instance_json(Path(temp_root))
            self._write_config(
                instance_json,
                {
                    "schema_version": 1,
                    "parent": {"model": " gpt-5.4 ", "effort": "high"},
                    "side": {},
                },
            )

            options = actor_model_config.resolve_parent_options(instance_json)

            self.assertTrue(options.has_values)
            self.assertEqual(options.model, "gpt-5.4")
            self.assertEqual(options.effort, "high")
            self.assertEqual(options.model_source, "actor_config")
            self.assertEqual(options.effort_source, "actor_config")

    def test_resolves_side_options_with_explicit_field_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_json = self._instance_json(Path(temp_root))
            self._write_config(
                instance_json,
                {
                    "schema_version": 1,
                    "parent": {},
                    "side": {"model": "gpt-5.4-mini", "effort": "medium"},
                },
            )

            file_options = actor_model_config.resolve_side_options(instance_json)
            mixed_options = actor_model_config.resolve_side_options(
                instance_json,
                explicit_model="gpt-5.4",
            )
            override_options = actor_model_config.resolve_side_options(
                instance_json,
                explicit_model="gpt-5.4",
                explicit_effort="high",
            )

            self.assertEqual(file_options.model, "gpt-5.4-mini")
            self.assertEqual(file_options.effort, "medium")
            self.assertEqual(file_options.model_source, "actor_config")
            self.assertEqual(file_options.effort_source, "actor_config")

            self.assertEqual(mixed_options.model, "gpt-5.4")
            self.assertEqual(mixed_options.effort, "medium")
            self.assertEqual(mixed_options.model_source, "override")
            self.assertEqual(mixed_options.effort_source, "actor_config")

            self.assertEqual(override_options.model, "gpt-5.4")
            self.assertEqual(override_options.effort, "high")
            self.assertEqual(override_options.model_source, "override")
            self.assertEqual(override_options.effort_source, "override")

    def test_side_source_metadata_uses_actor_boundary_terms(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_json = self._instance_json(Path(temp_root))
            self._write_config(
                instance_json,
                {
                    "schema_version": 1,
                    "parent": {},
                    "side": {"model": "gpt-5.4-mini"},
                },
            )
            options = actor_model_config.resolve_side_options(
                instance_json,
                explicit_effort="high",
            )

            payload = actor_model_config.apply_side_source_metadata(
                {
                    "action": "start",
                    "side_thread_id": "thread-side-1",
                    "model_source": "parent_thread",
                    "model_reasoning_effort_source": "parent_thread",
                },
                options,
            )

            self.assertEqual(payload["model"], "gpt-5.4-mini")
            self.assertEqual(payload["model_reasoning_effort"], "high")
            self.assertEqual(payload["model_source"], "actor_config")
            self.assertEqual(payload["model_reasoning_effort_source"], "override")
            self.assertEqual(payload["model_config_durability"], "thread_fork_only")

    def test_side_source_metadata_reports_codex_defaults_when_omitted(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_json = self._instance_json(Path(temp_root))
            options = actor_model_config.resolve_side_options(instance_json)

            payload = actor_model_config.apply_side_source_metadata({"action": "start"}, options)

            self.assertNotIn("model", payload)
            self.assertNotIn("model_reasoning_effort", payload)
            self.assertEqual(payload["model_source"], "codex_default")
            self.assertEqual(payload["model_reasoning_effort_source"], "codex_default")
            self.assertEqual(payload["model_config_durability"], "thread_fork_only")


if __name__ == "__main__":
    unittest.main()
