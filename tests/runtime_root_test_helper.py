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

import env_store  # noqa: E402
import turn_runtime  # noqa: E402
import workspace_data  # noqa: E402


RUNTIME_WORKSPACE_HEADER = "# BuddySwitch Runtime Workspace\n"


def _relative_to_runtime_or_repo(path: Path) -> str:
    candidate = path.resolve()
    for base in (workspace_data.ROOT, ROOT):
        try:
            return candidate.relative_to(base.resolve()).as_posix()
        except ValueError:
            continue
    return candidate.as_posix()


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

        objects_root = self.root / "buddyswitch" / "objects"
        content_root = self.root / "buddyswitch" / "content"
        local_root = self.root / "buddyswitch" / "local"
        workspace_root = self.root

        def _runtime_workspace_root(instance_payload=None):  # type: ignore[no-untyped-def]
            if isinstance(instance_payload, dict):
                candidate = instance_payload.get("workspace_dir")
                if isinstance(candidate, str) and candidate.strip():
                    return Path(candidate.strip()).expanduser().resolve(strict=False)
            return workspace_root

        def _buddybox_local_dir(instance_payload=None):  # type: ignore[no-untyped-def]
            return _runtime_workspace_root(instance_payload) / "buddyswitch" / "local" / "buddybox"

        patches = [
            patch.object(env_store, "ROOT", self.root),
            patch.object(env_store, "STATE_ROOT", self.root),
            patch.object(env_store, "OBJECTS_ROOT", objects_root),
            patch.object(env_store, "TRACKS_DIR", objects_root / "tracks"),
            patch.object(env_store, "TASKS_DIR", objects_root / "tasks"),
            patch.object(env_store, "ARTIFACT_OBJECTS_DIR", objects_root / "artifacts"),
            patch.object(env_store, "CONTENT_ROOT", content_root),
            patch.object(env_store, "LOCAL_ROOT", local_root),
            patch.object(env_store, "BUDDYBOX_LOCAL_DIR", local_root / "buddybox"),
            patch.object(env_store, "runtime_workspace_root", _runtime_workspace_root),
            patch.object(env_store, "buddybox_local_dir", _buddybox_local_dir),
            patch.object(turn_runtime, "ROOT", self.root),
            patch.object(workspace_data, "ROOT", self.root),
            patch.object(workspace_data, "rel", _relative_to_runtime_or_repo),
        ]
        self._patchers = patches
        for patcher in self._patchers:
            patcher.start()
        return self.root

    def stop(self) -> None:
        for patcher in reversed(self._patchers):
            patcher.stop()
        self._patchers = []
        if self._tmp_dir is not None:
            self._tmp_dir.cleanup()
        self._tmp_dir = None
        self.root = None


class RuntimeWorkspaceTestMixin:
    """Mixin for tests that should write into a temporary runtime workspace."""

    def setUp(self) -> None:
        super().setUp()
        self._runtime_sandbox = RuntimeWorkspaceSandbox()
        self.runtime_root = self._runtime_sandbox.start()

    def tearDown(self) -> None:
        self._runtime_sandbox.stop()
        super().tearDown()

    def _runtime_path(self, repo_path: str) -> Path:
        return self.runtime_root / repo_path
