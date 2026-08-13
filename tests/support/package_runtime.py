"""Isolated non-editable package build/install support for process tests."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import json
import os
from pathlib import Path
import shutil
import subprocess
from typing import Sequence

from tests.support.paths import REPO_ROOT
from tests.support.python import PYTHON


SourcePreparer = Callable[[Path], None]
RUNTIME_ASSET = Path("modules/artifact/assets/artifact-selection-v1.json")
COLOCATED_TEST = Path("modules/probe/tests/test_probe.py")


@dataclass(frozen=True)
class InstalledRuntime:
    source_root: Path
    wheel: Path
    runtime_dir: Path
    python: Path
    work_root: Path

    def run_module(
        self,
        module: str,
        args: Sequence[str] = (),
    ) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        environment.pop("PYTHONPATH", None)
        environment["BUDDYSWITCH_RUNTIME_DIR"] = str(self.runtime_dir)
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        return subprocess.run(
            [str(self.python), "-m", module, *args],
            cwd=self.work_root,
            env=environment,
            text=True,
            capture_output=True,
            check=False,
        )

    @staticmethod
    def json_payload(completed: subprocess.CompletedProcess[str]) -> dict[str, object]:
        assert completed.stdout.count("\n") == 1, completed
        payload = json.loads(completed.stdout)
        assert isinstance(payload, dict)
        return payload


def _run(command: Sequence[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run(
        list(command),
        cwd=cwd,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, (
        f"command failed: {command}\nstdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
    )
    return completed


def add_correspondence_probe(source_root: Path) -> None:
    package_root = source_root / "src" / "buddyswitch"

    for relative, content in (
        (Path("modules/__init__.py"), '"""modules."""\n'),
        (Path("modules/probe/__init__.py"), "PROBE = True\n"),
        (Path("modules/probe/tests/__init__.py"), '"""tests."""\n'),
        (COLOCATED_TEST, "def test_probe():\n    assert True\n"),
    ):
        target = package_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    cache = package_root / "modules" / "probe" / "__pycache__" / "probe.pyc"
    cache.parent.mkdir()
    cache.write_bytes(b"not-a-real-pyc")


def install_clean_runtime(
    work_root: Path,
    *,
    prepare_source: SourcePreparer | None = None,
) -> InstalledRuntime:
    source_root = work_root / "source"
    source_root.mkdir(parents=True)
    shutil.copy2(REPO_ROOT / "pyproject.toml", source_root / "pyproject.toml")
    shutil.copytree(REPO_ROOT / "src", source_root / "src", symlinks=True)
    if prepare_source is not None:
        prepare_source(source_root)

    wheel_dir = work_root / "wheels"
    wheel_dir.mkdir()
    _run(
        [
            PYTHON,
            "-m",
            "pip",
            "wheel",
            "--no-deps",
            "--no-build-isolation",
            "--wheel-dir",
            str(wheel_dir),
            str(source_root),
        ],
        cwd=work_root,
    )
    wheels = sorted(wheel_dir.glob("buddyswitch-0.1.0-*.whl"))
    assert len(wheels) == 1, wheels

    runtime_dir = work_root / "runtime"
    _run([PYTHON, "-m", "venv", str(runtime_dir / "venv")], cwd=work_root)
    runtime_python = (runtime_dir / "venv" / "bin" / "python").absolute()
    _run(
        [
            str(runtime_python),
            "-m",
            "pip",
            "install",
            "--no-deps",
            "--no-index",
            "--find-links",
            str(wheel_dir),
            "buddyswitch==0.1.0",
        ],
        cwd=work_root,
    )
    return InstalledRuntime(
        source_root=source_root.resolve(strict=True),
        wheel=wheels[0].resolve(strict=True),
        runtime_dir=runtime_dir.resolve(strict=True),
        python=runtime_python,
        work_root=work_root.resolve(strict=True),
    )
