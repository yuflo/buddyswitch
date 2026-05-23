#!/usr/bin/env python3
"""Helpers for routing BuddySwitch write tests into a temporary runtime workspace."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import env_legacy_store as env_store  # noqa: E402
import turn_runtime  # noqa: E402
from env.repos import runtime_files  # noqa: E402


RUNTIME_WORKSPACE_HEADER = "# BuddySwitch Runtime Workspace\n"


class RuntimeWorkspaceSandbox:
    """Patch script modules to use an isolated launcher-style runtime root."""

    def __init__(self) -> None:
        self.root: Path | None = None
        self._tmp_dir: tempfile.TemporaryDirectory[str] | None = None
        self._patchers: list[object] = []

    def start(self) -> Path:
        self._tmp_dir = tempfile.TemporaryDirectory(dir=ROOT)
        self.root = Path(self._tmp_dir.name)
        (self.root / "AGENTS.md").write_text(
            RUNTIME_WORKSPACE_HEADER
            + "\nThis file exists only for tests that need launcher-owned runtime writes.\n",
            encoding="utf-8",
        )

        runtime_files.set_runtime_root_override(self.root)

        patches = [
            patch.object(turn_runtime, "ROOT", self.root),
        ]
        self._patchers = patches
        for patcher in self._patchers:
            patcher.start()
        return self.root

    def stop(self) -> None:
        for patcher in reversed(self._patchers):
            patcher.stop()
        self._patchers = []
        runtime_files.reset_runtime_root_override()
        if self._tmp_dir is not None:
            self._tmp_dir.cleanup()
        self._tmp_dir = None
        self.root = None


class RuntimeWorkspaceTestMixin:
    """Mixin for tests that should write into a temporary runtime workspace."""

    def setUp(self) -> None:
        super().setUp()
        self._runtime_sandbox = RuntimeWorkspaceSandbox()
        # Unit-style tests intentionally use one isolated root for both visible workspace and state.
        self.runtime_root = self._runtime_sandbox.start()
        self.runtime_state_root = self.runtime_root

    def tearDown(self) -> None:
        self._runtime_sandbox.stop()
        super().tearDown()

    def _runtime_path(self, repo_path: str) -> Path:
        return self.runtime_root / repo_path

    def _state_path(self, repo_path: str) -> Path:
        return self.runtime_state_root / repo_path
