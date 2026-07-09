#!/usr/bin/env python3
"""Tests for actor-local model config loading and resolution."""

from __future__ import annotations

import json
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
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
                    "parent": {"model": "gpt-5.5", "effort": "medium"},
                    "side": {"model": "gpt-5.5", "effort": "medium"},
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

    def test_missing_file_resolves_creation_defaults_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_json = self._instance_json(Path(temp_root))
            path = actor_model_config.model_config_path(instance_json)

            loaded = actor_model_config.load_model_config(instance_json)
            parent = actor_model_config.resolve_parent_options(instance_json)
            side = actor_model_config.resolve_side_options(instance_json)

            self.assertFalse(path.exists())
            self.assertEqual(loaded.schema_version, 1)
            self.assertEqual(loaded.parent, {"model": "gpt-5.5", "effort": "medium"})
            self.assertEqual(loaded.side, {"model": "gpt-5.5", "effort": "medium"})
            self.assertTrue(parent.has_values)
            self.assertEqual(parent.model, "gpt-5.5")
            self.assertEqual(parent.effort, "medium")
            self.assertEqual(parent.model_source, "actor_config")
            self.assertEqual(parent.effort_source, "actor_config")
            self.assertTrue(side.has_values)
            self.assertEqual(side.model, "gpt-5.5")
            self.assertEqual(side.effort, "medium")
            self.assertEqual(side.model_source, "actor_config")
            self.assertEqual(side.effort_source, "actor_config")

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

    def test_empty_side_config_reports_codex_defaults_when_reset(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_json = self._instance_json(Path(temp_root))
            self._write_config(
                instance_json,
                {
                    "schema_version": 1,
                    "parent": {},
                    "side": {},
                },
            )
            options = actor_model_config.resolve_side_options(instance_json)

            payload = actor_model_config.apply_side_source_metadata({"action": "start"}, options)

            self.assertNotIn("model", payload)
            self.assertNotIn("model_reasoning_effort", payload)
            self.assertEqual(payload["model_source"], "codex_default")
            self.assertEqual(payload["model_reasoning_effort_source"], "codex_default")
            self.assertEqual(payload["model_config_durability"], "thread_fork_only")

    def test_management_read_projects_missing_fields_as_null_interface_dto(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_json = self._instance_json(Path(temp_root))
            self._write_config(
                instance_json,
                {
                    "schema_version": 1,
                    "parent": {"model": "gpt-5.4"},
                    "side": {"effort": "medium"},
                },
            )

            payload = actor_model_config.read_management_payload(instance_json)

            self.assertEqual(
                payload,
                {
                    "schema_version": 1,
                    "parent": {"model": "gpt-5.4", "effort": None},
                    "side": {"model": None, "effort": "medium"},
                    "allowed_efforts": ["high", "low", "medium", "minimal", "ultra"],
                    "effects": {
                        "parent": "applies_before_next_parent_submit",
                        "side": "applies_to_new_side_threads_only",
                    },
                },
            )

    def test_management_read_missing_file_returns_creation_defaults_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_json = self._instance_json(Path(temp_root))
            path = actor_model_config.model_config_path(instance_json)

            payload = actor_model_config.read_management_payload(instance_json)

            self.assertFalse(path.exists())
            self.assertEqual(payload["parent"], {"model": "gpt-5.5", "effort": "medium"})
            self.assertEqual(payload["side"], {"model": "gpt-5.5", "effort": "medium"})
            self.assertEqual(payload["allowed_efforts"], ["high", "low", "medium", "minimal", "ultra"])

    def test_management_replace_all_null_resets_to_codex_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_json = self._instance_json(Path(temp_root))

            payload = actor_model_config.replace_management_payload(
                instance_json,
                {
                    "parent": {"model": None, "effort": None},
                    "side": {"model": None, "effort": None},
                },
            )

            self.assertEqual(
                json.loads(actor_model_config.model_config_path(instance_json).read_text(encoding="utf-8")),
                {
                    "schema_version": 1,
                    "parent": {},
                    "side": {},
                },
            )
            self.assertEqual(payload["parent"], {"model": None, "effort": None})
            self.assertEqual(payload["side"], {"model": None, "effort": None})

            parent = actor_model_config.resolve_parent_options(instance_json)
            side = actor_model_config.resolve_side_options(instance_json)
            self.assertFalse(parent.has_values)
            self.assertFalse(side.has_values)
            self.assertEqual(parent.model_source, "codex_default")
            self.assertEqual(parent.effort_source, "codex_default")
            self.assertEqual(side.model_source, "codex_default")
            self.assertEqual(side.effort_source, "codex_default")

    def test_management_replace_trims_writes_non_null_disk_schema_and_updates_runtime_resolve(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_json = self._instance_json(Path(temp_root))

            payload = actor_model_config.replace_management_payload(
                instance_json,
                {
                    "parent": {"model": " gpt-5.4 ", "effort": " high "},
                    "side": {"model": None, "effort": "medium"},
                },
            )

            self.assertEqual(
                json.loads(actor_model_config.model_config_path(instance_json).read_text(encoding="utf-8")),
                {
                    "schema_version": 1,
                    "parent": {"model": "gpt-5.4", "effort": "high"},
                    "side": {"effort": "medium"},
                },
            )
            self.assertEqual(payload["parent"], {"model": "gpt-5.4", "effort": "high"})
            self.assertEqual(payload["side"], {"model": None, "effort": "medium"})

            parent = actor_model_config.resolve_parent_options(instance_json)
            side = actor_model_config.resolve_side_options(instance_json)
            self.assertEqual(parent.model, "gpt-5.4")
            self.assertEqual(parent.effort, "high")
            self.assertIsNone(side.model)
            self.assertEqual(side.effort, "medium")

    def test_management_replace_requires_full_sections_and_preserves_existing_file_on_invalid_payload(self) -> None:
        invalid_cases: list[tuple[str, dict[str, object], str]] = [
            (
                "unknown top-level key",
                {
                    "parent": {"model": None, "effort": None},
                    "side": {"model": None, "effort": None},
                    "legacy": {},
                },
                "unknown top-level",
            ),
            ("missing parent", {"side": {"model": None, "effort": None}}, "parent"),
            ("missing side", {"parent": {"model": None, "effort": None}}, "side"),
            (
                "missing section field",
                {"parent": {"model": None}, "side": {"model": None, "effort": None}},
                "parent",
            ),
            (
                "unknown section key",
                {
                    "parent": {"model": None, "effort": None, "provider": "openai"},
                    "side": {"model": None, "effort": None},
                },
                "provider",
            ),
            (
                "empty model",
                {"parent": {"model": " ", "effort": None}, "side": {"model": None, "effort": None}},
                "model",
            ),
            (
                "invalid effort",
                {"parent": {"model": None, "effort": "max"}, "side": {"model": None, "effort": None}},
                "effort",
            ),
        ]

        for name, payload, error_text in invalid_cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp_root:
                instance_json = self._instance_json(Path(temp_root))
                path = self._write_config(
                    instance_json,
                    {
                        "schema_version": 1,
                        "parent": {"model": "gpt-5.4", "effort": "high"},
                        "side": {"model": "gpt-5.4-mini", "effort": "medium"},
                    },
                )
                before = path.read_text(encoding="utf-8")

                with self.assertRaisesRegex(actor_model_config.ActorModelConfigError, error_text):
                    actor_model_config.replace_management_payload(instance_json, payload)

                self.assertEqual(path.read_text(encoding="utf-8"), before)

    def test_management_cli_get_and_replace_emit_json_results(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_json = self._instance_json(Path(temp_root))

            replace_stdout = io.StringIO()
            with redirect_stdout(replace_stdout):
                replace_code = actor_model_config.main(
                    [
                        "replace",
                        "--instance-json",
                        str(instance_json),
                        "--payload-json",
                        json.dumps(
                            {
                                "parent": {"model": "gpt-5.4", "effort": "high"},
                                "side": {"model": None, "effort": None},
                            }
                        ),
                    ]
                )
            get_stdout = io.StringIO()
            with redirect_stdout(get_stdout):
                get_code = actor_model_config.main(["get", "--instance-json", str(instance_json)])

            self.assertEqual(replace_code, 0)
            self.assertEqual(get_code, 0)
            replace_payload = json.loads(replace_stdout.getvalue())
            get_payload = json.loads(get_stdout.getvalue())
            self.assertTrue(replace_payload["ok"])
            self.assertTrue(get_payload["ok"])
            self.assertEqual(replace_payload["model_config"], get_payload["model_config"])
            self.assertEqual(get_payload["model_config"]["parent"], {"model": "gpt-5.4", "effort": "high"})

    def test_management_cli_rejects_invalid_replace_json_without_mutating_existing_file(self) -> None:
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
            before = path.read_text(encoding="utf-8")
            stderr = io.StringIO()

            with redirect_stderr(stderr):
                code = actor_model_config.main(
                    [
                        "replace",
                        "--instance-json",
                        str(instance_json),
                        "--payload-json",
                        '{"parent": {"model": null, "effort": "max"}, "side": {"model": null, "effort": null}}',
                    ]
                )

            self.assertEqual(code, 1)
            self.assertIn("effort", stderr.getvalue())
            self.assertEqual(path.read_text(encoding="utf-8"), before)


if __name__ == "__main__":
    unittest.main()
