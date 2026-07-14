"""Normal environment-bound runtime workspaces for same-process tests."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import turn_runtime
from env.domain import task_sys
from env.repos import runtime_files


RUNTIME_WORKSPACE_HEADER = "# BuddySwitch Runtime Workspace\n"


class RuntimeTestWorkspace:
    """Bind production runtime environment inputs to isolated temporary state."""

    def __init__(self) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.base = Path(self._temporary.name).resolve()
        self.shared_root = self.base / "shared"
        self.root = self.shared_root
        self.state_root = self.shared_root / "state"
        self.state_root.mkdir(parents=True)
        (self.root / "AGENTS.md").write_text(
            RUNTIME_WORKSPACE_HEADER
            + "\nThis workspace is isolated by normal runtime environment inputs.\n",
            encoding="utf-8",
        )
        self._environment = patch.dict(
            os.environ,
            {
                "BUDDYSWITCH_ACTOR_ID": "act-test-runtime",
                "BUDDYSWITCH_SHARED_ROOT": str(self.shared_root),
                "BUDDYSWITCH_STATE_ROOT": str(self.state_root),
                "BUDDYSWITCH_WORKSPACE_DIR": str(self.root),
                "BUDDYSWITCH_RUNTIME_WORKSPACE_ROOT": str(self.root),
            },
        )
        self._turn_root = patch.object(turn_runtime, "ROOT", self.root)
        self._environment.start()
        self._turn_root.start()
        runtime_files.refresh_runtime_roots_from_env()

    def close(self) -> None:
        self._turn_root.stop()
        self._environment.stop()
        runtime_files.refresh_runtime_roots_from_env()
        self._temporary.cleanup()

    def path(self, repo_path: str) -> Path:
        return self.root / repo_path

    def actor_id(self, *, role: str, label: str) -> str:
        if isinstance(label, str) and label.startswith(f"act-{role}-"):
            suffix = label.removeprefix(f"act-{role}-")
            if len(suffix) == 12 and all(
                char in "0123456789abcdef" for char in suffix
            ):
                return label
        digest = hashlib.sha1(f"{role}:{label}".encode("utf-8")).hexdigest()[:12]
        return f"act-{role}-{digest}"

    def instance_root(self, actor_id: str) -> Path:
        return self.root / "instances" / actor_id

    def write_task(
        self,
        *,
        actor_id: str,
        role: str,
        task_slug: str,
        title: str,
        summary: str = "",
        track_id: str | None = None,
    ) -> str:
        source_ref: dict[str, object] = {
            "slug": runtime_files.slugify(task_slug),
            "title": title,
        }
        if summary:
            source_ref["summary"] = summary
        if track_id is not None:
            source_ref["track_id"] = track_id
        result = task_sys.ingest(
            {
                "source": {"type": "test.fixture", "ref": source_ref},
                "actor_target": {"actor_id": actor_id, "role_id": role},
                "context": {"fixture": "task sys test task"},
            }
        )
        return str(result["task_id"])

    def seed_active_task(
        self,
        *,
        instance_json: Path,
        role: str,
        actor_id: str,
        task_slug: str = "active-task",
    ) -> str:
        del instance_json
        result = task_sys.ingest(
            {
                "source": {
                    "type": "test.fixture",
                    "ref": {"slug": runtime_files.slugify(task_slug)},
                },
                "actor_target": {"actor_id": actor_id, "role_id": role},
                "context": {"fixture": "active task"},
            }
        )
        return str(result["task_id"])


class RuntimeWorkspaceTestCase(unittest.TestCase):
    """TestCase base that exposes one environment-bound runtime workspace."""

    def setUp(self) -> None:
        super().setUp()
        self.runtime_workspace = RuntimeTestWorkspace()
        self.runtime_root = self.runtime_workspace.root
        self.runtime_state_root = self.runtime_workspace.state_root

    def tearDown(self) -> None:
        self.runtime_workspace.close()
        super().tearDown()

    def _runtime_path(self, repo_path: str) -> Path:
        return self.runtime_workspace.path(repo_path)

    def _state_path(self, repo_path: str) -> Path:
        return self.runtime_state_root / repo_path

    def _runtime_actor_id(self, *, role: str, label: str) -> str:
        return self.runtime_workspace.actor_id(role=role, label=label)

    def _instance_root(self, actor_id: str) -> Path:
        return self.runtime_workspace.instance_root(actor_id)

    def _write_task_sys_task(self, **kwargs: object) -> str:
        return self.runtime_workspace.write_task(**kwargs)  # type: ignore[arg-type]

    def _seed_active_task_for_instance(self, **kwargs: object) -> str:
        return self.runtime_workspace.seed_active_task(**kwargs)  # type: ignore[arg-type]
