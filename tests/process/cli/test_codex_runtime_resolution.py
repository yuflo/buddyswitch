"""Tests for the concrete Codex runtime descriptor owner."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.support.processes import run_process
from buddyswitch.foundation.actor_runtime import codex_runtime


class CodexRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        patcher = mock.patch.object(codex_runtime.subprocess, "run", side_effect=run_process)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _write_codex(self, path: Path, version: str) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "#!/bin/sh\n"
            "if [ \"${1:-}\" = \"--version\" ]; then\n"
            f"  printf '%s\\n' {version!r}\n"
            "  exit 0\n"
            "fi\n"
            "exit 0\n",
            encoding="utf-8",
        )
        path.chmod(0o755)
        return path

    def test_resolve_explicit_runtime_returns_canonical_path_and_version(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            root = Path(temp_root)
            executable = self._write_codex(root / "bin" / "codex", "codex-cli test-1")

            runtime = codex_runtime.resolve_codex_runtime(str(executable))

            self.assertEqual(runtime.executable, executable.resolve())
            self.assertEqual(runtime.version, "codex-cli test-1")
            self.assertEqual(
                runtime.to_record(),
                {"executable": str(executable.resolve()), "version": "codex-cli test-1"},
            )

    def test_resolve_without_candidate_uses_path_once(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            root = Path(temp_root)
            executable = self._write_codex(root / "bin" / "codex", "codex-cli path-test")
            with mock.patch.dict(os.environ, {"PATH": str(executable.parent)}, clear=False):
                runtime = codex_runtime.resolve_codex_runtime()

            self.assertEqual(runtime.executable, executable.resolve())
            self.assertEqual(runtime.version, "codex-cli path-test")

    def test_resolve_rejects_relative_missing_non_executable_and_empty_version(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            root = Path(temp_root)
            missing = root / "missing-codex"
            non_executable = root / "not-executable"
            non_executable.write_text("#!/bin/sh\n", encoding="utf-8")
            empty_version = self._write_codex(root / "empty-version", "")

            for candidate in ("relative/codex", str(missing), str(non_executable), str(empty_version)):
                with self.subTest(candidate=candidate):
                    with self.assertRaises(codex_runtime.CodexRuntimeError) as raised:
                        codex_runtime.resolve_codex_runtime(candidate)
                    self.assertEqual(raised.exception.code, "RUNTIME_UNAVAILABLE")

    def test_validate_rejects_recorded_version_change(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            executable = self._write_codex(Path(temp_root) / "codex", "codex-cli before")
            runtime = codex_runtime.resolve_codex_runtime(str(executable))
            self._write_codex(executable, "codex-cli after")

            with self.assertRaises(codex_runtime.CodexRuntimeError) as raised:
                codex_runtime.validate_codex_runtime(runtime)

            self.assertEqual(raised.exception.code, "RUNTIME_MISMATCH")
            self.assertIn("codex-cli before", str(raised.exception))
            self.assertIn("codex-cli after", str(raised.exception))
