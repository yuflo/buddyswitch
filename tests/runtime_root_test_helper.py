#!/usr/bin/env python3
"""Helpers for routing BuddySwitch write tests into a temporary runtime workspace."""

from __future__ import annotations

import json
import sys
import tempfile
import hashlib
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

    def _runtime_actor_id(self, *, role: str, label: str) -> str:
        if isinstance(label, str) and label.startswith(f"act-{role}-"):
            suffix = label.removeprefix(f"act-{role}-")
            if len(suffix) == 12 and all(char in "0123456789abcdef" for char in suffix):
                return label
        digest = hashlib.sha1(f"{role}:{label}".encode("utf-8")).hexdigest()[:12]
        return f"act-{role}-{digest}"

    def _instance_root(self, actor_id: str) -> Path:
        return self.runtime_root / "instances" / actor_id

    def _taskbox_root(self, *, actor_id: str, role: str) -> Path:
        return self._instance_root(actor_id) / "taskbox" / role

    def _ensure_taskbox(self, *, actor_id: str, role: str) -> Path:
        root = self._taskbox_root(actor_id=actor_id, role=role)
        (root / "tasks").mkdir(parents=True, exist_ok=True)
        history_file = root / "history.md"
        if not history_file.exists():
            history_file.write_text("", encoding="utf-8")
        return root

    def _write_taskbox_task(
        self,
        *,
        actor_id: str,
        role: str,
        task_id: str,
        title: str,
        summary: str = "",
        status: str = "active",
        priority: str = "normal",
        track_id: str | None = None,
        refs: list[dict[str, object]] | None = None,
        created_at: str = "2026-05-23T12:00:00+08:00",
        updated_at: str = "2026-05-23T12:00:00+08:00",
        closed_at: str | None = None,
    ) -> Path:
        if closed_at is None and status in {"done", "archived"}:
            closed_at = updated_at
        root = self._ensure_taskbox(actor_id=actor_id, role=role)
        task_path = root / "tasks" / f"{task_id}.json"
        task_path.write_text(
            json.dumps(
                {
                    "id": task_id,
                    "owner_actor": {"actor_id": actor_id, "role_id": role},
                    "title": title,
                    "summary": summary,
                    "status": status,
                    "priority": priority,
                    "track_id": track_id,
                    "refs": refs or [],
                    "created_at": created_at,
                    "updated_at": updated_at,
                    "closed_at": closed_at,
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return task_path
