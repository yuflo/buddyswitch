"""Tests for the concrete Codex runtime descriptor owner."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from buddyswitch.launcher import codex_runtime


class CodexRuntimeTests(unittest.TestCase):
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

    def test_runtime_from_instance_requires_exact_record_shape(self) -> None:
        valid = {
            "codex_runtime": {
                "executable": "/tmp/codex",
                "version": "codex-cli test-1",
            }
        }
        runtime = codex_runtime.runtime_from_instance(valid)
        self.assertEqual(runtime.executable, Path("/tmp/codex"))
        self.assertEqual(runtime.version, "codex-cli test-1")

        invalid_payloads = (
            {},
            {"codex_runtime": None},
            {"codex_runtime": {}},
            {"codex_runtime": {"executable": "codex", "version": "codex-cli test-1"}},
            {"codex_runtime": {"executable": "~/codex", "version": "codex-cli test-1"}},
            {"codex_runtime": {"executable": "/tmp/codex", "version": ""}},
            {"codex_runtime": {"executable": "/tmp/codex", "version": "codex-cli test-1", "extra": True}},
        )
        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                with self.assertRaises(codex_runtime.CodexRuntimeError) as raised:
                    codex_runtime.runtime_from_instance(payload)
                self.assertEqual(raised.exception.code, "INVALID_RUNTIME_RECORD")
