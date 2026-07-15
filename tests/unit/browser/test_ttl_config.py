"""Host-global browser TTL configuration contract."""

from __future__ import annotations

import importlib
import io
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import unittest


class TestBrowserTtlConfig(unittest.TestCase):
    def setUp(self) -> None:
        self.config = importlib.import_module("env.browser_ttl_config")

    def test_absent_config_is_created_at_shared_root_with_exact_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            shared_root = Path(temp_root) / ".codex-buddyswitch"

            path = self.config.ensure_browser_ttl_config(shared_root=shared_root)
            loaded = self.config.load_browser_ttl_config(shared_root=shared_root)

            self.assertEqual(path, shared_root / "config" / "browser.toml")
            self.assertEqual(
                path.read_text(encoding="utf-8"),
                "schema_version = 1\n\n[ttl]\npage_idle_seconds = 40\nrelease_delay_seconds = 10\n",
            )
            self.assertEqual(loaded.page_idle_seconds, 40)
            self.assertEqual(loaded.release_delay_seconds, 10)

    def test_load_reloads_valid_edits_without_process_restart(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            shared_root = Path(temp_root) / "shared"
            path = self.config.ensure_browser_ttl_config(shared_root=shared_root)
            path.write_text(
                "schema_version = 1\n\n[ttl]\npage_idle_seconds = 2\nrelease_delay_seconds = 0\n",
                encoding="utf-8",
            )

            first = self.config.load_browser_ttl_config(shared_root=shared_root)
            path.write_text(
                "schema_version = 1\n\n[ttl]\npage_idle_seconds = 7\nrelease_delay_seconds = 3\n",
                encoding="utf-8",
            )
            second = self.config.load_browser_ttl_config(shared_root=shared_root)

            self.assertEqual((first.page_idle_seconds, first.release_delay_seconds), (2, 0))
            self.assertEqual((second.page_idle_seconds, second.release_delay_seconds), (7, 3))

    def test_concurrent_ensure_publishes_only_one_complete_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            shared_root = Path(temp_root) / "shared"

            with ThreadPoolExecutor(max_workers=8) as executor:
                paths = list(
                    executor.map(
                        lambda _index: self.config.ensure_browser_ttl_config(shared_root=shared_root),
                        range(16),
                    )
                )

            expected_path = shared_root / "config" / "browser.toml"
            self.assertEqual(set(paths), {expected_path})
            self.assertEqual(expected_path.read_text(encoding="utf-8"), self.config.DEFAULT_CONFIG_TEXT)
            self.assertEqual(list(expected_path.parent.glob(".browser.toml.*.tmp")), [])

    def test_two_actor_instance_roots_resolve_one_shared_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            shared_root = Path(temp_root) / "shared"
            first = shared_root / "instances" / "act-dev-one"
            second = shared_root / "instances" / "act-market-two"

            first_path = self.config.browser_ttl_config_path(instance_root=first)
            second_path = self.config.browser_ttl_config_path(instance_root=second)

            self.assertEqual(first_path, shared_root / "config" / "browser.toml")
            self.assertEqual(second_path, first_path)

    def test_existing_invalid_config_is_not_overwritten_by_ensure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            shared_root = Path(temp_root) / "shared"
            path = shared_root / "config" / "browser.toml"
            path.parent.mkdir(parents=True)
            path.write_text(
                "schema_version = 99\n[ttl]\npage_idle_seconds = 40\nrelease_delay_seconds = 10\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(self.config.BrowserTtlConfigError, "schema_version"):
                self.config.ensure_browser_ttl_config(shared_root=shared_root)

            self.assertEqual(
                path.read_text(encoding="utf-8"),
                "schema_version = 99\n[ttl]\npage_idle_seconds = 40\nrelease_delay_seconds = 10\n",
            )

    def test_invalid_shapes_fail_with_config_path(self) -> None:
        invalid_cases = {
            "malformed": "not = [valid\n",
            "wrong-schema": "schema_version = 2\n[ttl]\npage_idle_seconds = 40\nrelease_delay_seconds = 10\n",
            "missing-field": "schema_version = 1\n[ttl]\npage_idle_seconds = 40\n",
            "unknown-top": "schema_version = 1\nextra = 1\n[ttl]\npage_idle_seconds = 40\nrelease_delay_seconds = 10\n",
            "unknown-ttl": "schema_version = 1\n[ttl]\npage_idle_seconds = 40\nrelease_delay_seconds = 10\nextra = 1\n",
            "bool-page": "schema_version = 1\n[ttl]\npage_idle_seconds = true\nrelease_delay_seconds = 10\n",
            "zero-page": "schema_version = 1\n[ttl]\npage_idle_seconds = 0\nrelease_delay_seconds = 10\n",
            "negative-release": "schema_version = 1\n[ttl]\npage_idle_seconds = 40\nrelease_delay_seconds = -1\n",
        }

        for name, content in invalid_cases.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp_root:
                shared_root = Path(temp_root) / "shared"
                path = shared_root / "config" / "browser.toml"
                path.parent.mkdir(parents=True)
                path.write_text(content, encoding="utf-8")

                with self.assertRaises(self.config.BrowserTtlConfigError) as raised:
                    self.config.load_browser_ttl_config(shared_root=shared_root)

                self.assertIn(str(path), str(raised.exception))

    def test_cli_ensure_prints_machine_readable_path_and_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            shared_root = Path(temp_root) / "shared"

            stdout = io.StringIO()
            exit_code = self.config.main(["ensure", "--shared-root", str(shared_root)], stdout=stdout)

            self.assertEqual(exit_code, 0)
            self.assertEqual(
                json.loads(stdout.getvalue()),
                {
                    "config_path": str(shared_root / "config" / "browser.toml"),
                    "page_idle_seconds": 40,
                    "release_delay_seconds": 10,
                    "schema_version": 1,
                },
            )
