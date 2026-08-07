from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

from buddyswitch.launcher import app_server
from buddyswitch.foundation.runtime_broker import lifecycle

from tests.support.paths import REPO_ROOT
from tests.support.processes import run_process


def _long_instance_root(tmp_path: Path, leaf: str) -> Path:
    root = tmp_path / ("root-" + leaf) / ("nested-" + "x" * 70) / ("actor-" + "y" * 70)
    root.mkdir(parents=True)
    return root


def _shell_socket(script: Path, function: str, *, instance_root: Path, actor_id: str) -> Path:
    env = dict(os.environ)
    env.update(
        {
            "BUDDYSWITCH_PYTHON": sys.executable,
            "BUDDYSWITCH_INSTANCE_ROOT": str(instance_root),
            "BUDDYSWITCH_ACTOR_ID": actor_id,
        }
    )
    completed = run_process(
        ["bash", "-c", f'source "$1"; {function}', "resolver-test", str(script)],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    return Path(completed.stdout.strip())


def test_long_path_fallback_sockets_are_root_unique_and_match_shell_resolvers(
    tmp_path: Path,
) -> None:
    actor_id = "act-same"
    first_root = _long_instance_root(tmp_path, "first")
    second_root = _long_instance_root(tmp_path, "second")

    first_app = app_server.effective_socket_path(
        actor_id,
        first_root,
        app_server.marker_file(first_root),
    )
    second_app = app_server.effective_socket_path(
        actor_id,
        second_root,
        app_server.marker_file(second_root),
    )
    first_broker = lifecycle.resolve_socket_path(
        actor_id,
        first_root,
        first_root / "runtime" / "runtime-broker.socket",
    )
    second_broker = lifecycle.resolve_socket_path(
        actor_id,
        second_root,
        second_root / "runtime" / "runtime-broker.socket",
    )

    assert first_app != second_app
    assert first_broker != second_broker
    assert first_app == _shell_socket(
        Path(os.environ["BUDDYSWITCH_PACKAGE_ROOT"]) / "launcher" / "shell" / "app_server.sh",
        "_buddyswitch_app_server_effective_socket",
        instance_root=first_root,
        actor_id=actor_id,
    )
    assert first_broker == _shell_socket(
        Path(os.environ["BUDDYSWITCH_PACKAGE_ROOT"]) / "launcher" / "shell" / "runtime_broker.sh",
        "_buddyswitch_runtime_broker_effective_socket",
        instance_root=first_root,
        actor_id=actor_id,
    )
