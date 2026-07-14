from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import tempfile
import uuid

from tests.support.paths import REPO_ROOT


@dataclass(frozen=True)
class RunEnvironment:
    run_id: str
    root: Path
    ledger_path: Path
    environ: dict[str, str]

    @classmethod
    def create(cls) -> "RunEnvironment":
        run_id = uuid.uuid4().hex
        short_system_temp = Path("/tmp")
        temp_parent = short_system_temp if short_system_temp.is_dir() else None
        root = Path(
            tempfile.mkdtemp(prefix=f"bs-test-{run_id[:8]}-", dir=temp_parent)
        )
        root = root.resolve(strict=True)
        if root == REPO_ROOT or root.is_relative_to(REPO_ROOT):
            shutil.rmtree(root)
            raise RuntimeError(f"test run root must be outside the repository: {root}")

        paths = {
            "HOME": root / "home",
            "CODEX_HOME": root / "codex-home",
            "XDG_CACHE_HOME": root / "xdg" / "cache",
            "XDG_CONFIG_HOME": root / "xdg" / "config",
            "XDG_DATA_HOME": root / "xdg" / "data",
            "XDG_STATE_HOME": root / "xdg" / "state",
            "TMPDIR": root / "tmp",
            "BUDDYSWITCH_STATE_ROOT": root / "state",
            "BUDDYSWITCH_SHARED_ROOT": root / "shared",
        }
        for path in paths.values():
            path.mkdir(parents=True, exist_ok=True)
        for path in (
            root / "workspace",
            root / "instances",
            root / "fake-bin",
        ):
            path.mkdir(parents=True, exist_ok=True)

        ledger_path = root / "owned-resources.jsonl"
        ledger_path.touch()
        configured_python = os.environ.get("BUDDYSWITCH_PYTHON")
        environ = {
            name: value
            for name, value in os.environ.items()
            if not name.startswith("BUDDYSWITCH_")
        }
        if configured_python:
            environ["BUDDYSWITCH_PYTHON"] = configured_python
        environ.update({name: str(path) for name, path in paths.items()})
        environ.update(
            {
                "BUDDYSWITCH_TEST_RUN_ID": run_id,
                "BUDDYSWITCH_TEST_RUN_ROOT": str(root),
                "BUDDYSWITCH_TEST_RESOURCE_LEDGER": str(ledger_path),
                "BUDDYSWITCH_TEST_RUNNER_PID": str(os.getpid()),
                "PYTHONDONTWRITEBYTECODE": "1",
            }
        )
        return cls(
            run_id=run_id,
            root=root,
            ledger_path=ledger_path,
            environ=environ,
        )

    def cleanup(self) -> None:
        if self.root == REPO_ROOT or self.root.is_relative_to(REPO_ROOT):
            raise RuntimeError(f"refusing to remove repository path: {self.root}")
        shutil.rmtree(self.root, ignore_errors=False)
