"""Current application-selected Host Control start input."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import subprocess
import sys

from buddyswitch.application.build import activate_application
from buddyswitch.application.entrypoints.actor_build import resolve_actor_bootstrap
from buddyswitch.foundation.actor_runtime.environment import (
    ActorEnvironmentBuilder,
    ActorEnvironmentBuildError,
    ActorEnvironmentSpec,
)
from buddyswitch.foundation.process_runtime.invocation import (
    current_runtime_identity,
    run_verified,
)


PACKAGE_ROOT = Path(__file__).resolve().parents[2]
LAUNCHER_SHELL = PACKAGE_ROOT / "launcher" / "shell"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build")
    build.add_argument("--project-source", type=Path, required=True)
    build.add_argument("--shared-root", type=Path, required=True)
    build.add_argument("--actor-id", required=True)
    build.add_argument("--role-id", required=True)
    build.add_argument("--source-codex-home", type=Path, required=True)
    configure = commands.add_parser("configure")
    configure.add_argument("--actor-id", required=True)
    configure.add_argument("--role-id", required=True)
    configure.add_argument("--broker-socket", required=True)
    configure.add_argument(
        "--phase",
        choices=("codex-config", "env-mcp", "browser-register"),
        required=True,
    )
    return parser


def _build(args: argparse.Namespace) -> int:
    application = activate_application()
    try:
        result = ActorEnvironmentBuilder().build(
            ActorEnvironmentSpec(
                project_source=args.project_source,
                shared_root=args.shared_root,
                actor_id=args.actor_id,
                source_codex_home=args.source_codex_home,
                runtime_identity=current_runtime_identity(),
                bootstrap=resolve_actor_bootstrap(
                    args.role_id,
                    application=application,
                ),
            )
        )
    except ActorEnvironmentBuildError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    payload = asdict(result)
    for key, value in tuple(payload.items()):
        if isinstance(value, Path):
            payload[key] = str(value)
        elif isinstance(value, tuple):
            payload[key] = list(value)
    print(json.dumps(payload, ensure_ascii=True))
    return 0


def _configure(args: argparse.Namespace) -> int:
    script = f'''\
source "{LAUNCHER_SHELL / "env.sh"}"
source "{LAUNCHER_SHELL / "browser_cockpit.sh"}"
buddyswitch_env_init
buddyswitch_env_bind_instance "$1"
export BUDDYSWITCH_START_ROLE="$2"
export BUDDYSWITCH_RUNTIME_BROKER_SOCKET="$3"
case "$4" in
  codex-config) buddyswitch_patch_codex_config ;;
  env-mcp) buddyswitch_env_mcp_ensure ;;
  browser-register) buddyswitch_browser_register_cockpit_mcp ;;
esac
'''
    completed = subprocess.run(
        [
            "/bin/bash",
            "-c",
            script,
            "buddyswitch-host-start",
            args.actor_id,
            args.role_id,
            args.broker_socket,
            args.phase,
        ],
        env=os.environ.copy(),
        text=True,
        check=False,
    )
    return int(completed.returncode)


def main() -> int:
    args = _parser().parse_args()
    if args.command == "build":
        return _build(args)
    if args.command == "configure":
        return _configure(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(run_verified(main))
