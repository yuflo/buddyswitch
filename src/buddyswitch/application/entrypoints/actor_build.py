"""Verified application entrypoint for resolved Actor workspace publication."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

from buddyswitch.application.build import ApplicationRuntime, activate_application
from buddyswitch.application.cli_runtime import assemble_cli_runtime
from buddyswitch.foundation.actor_runtime.environment import (
    ActorEnvironmentBuilder,
    ActorEnvironmentBuildError,
    ActorEnvironmentResult,
    ActorEnvironmentSpec,
    ResolvedActorBootstrap,
)
from buddyswitch.foundation.process_runtime.invocation import (
    current_runtime_identity,
    run_verified,
)
from buddyswitch.foundation.cli_runtime import config as codex_config


def _base_codex_config(application: ApplicationRuntime) -> str:
    disabled_skills = [
        export.id
        for export in application.skills
        if not export.enabled_by_default
    ]
    skill_rows = "".join(
        (
            "\n[[skills.config]]\n"
            f'name = "{skill_id}"\n'
            "enabled = false\n"
        )
        for skill_id in disabled_skills
    )
    return (
        "[skills.bundled]\n"
        "enabled = false\n"
        f"{skill_rows}\n"
        "[features]\n"
        "plugins = false\n"
        "goals = true\n"
    )


def resolve_actor_bootstrap(
    role_id: str,
    *,
    application: ApplicationRuntime,
) -> ResolvedActorBootstrap:
    """Resolve one validated RoleHost Actor projection exactly once."""

    try:
        return application.role_host.actor_bootstrap(
            role_id,
            codex_config=_base_codex_config(application),
        )
    except ValueError as exc:
        raise ActorEnvironmentBuildError(f"invalid runtime role surface: {exc}") from exc


def _result_payload(result: ActorEnvironmentResult) -> dict[str, object]:
    payload = asdict(result)
    for key, value in tuple(payload.items()):
        if isinstance(value, Path):
            payload[key] = str(value)
        elif isinstance(value, tuple):
            payload[key] = list(value)
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build one Actor environment.")
    parser.add_argument("--project-source", type=Path, required=True)
    parser.add_argument("--shared-root", type=Path, required=True)
    parser.add_argument("--actor-id", required=True)
    parser.add_argument("--role-id", required=True)
    parser.add_argument("--source-codex-home", type=Path, required=True)
    return parser


def main() -> int:
    application = activate_application()
    cli_runtime_input = assemble_cli_runtime(application)
    command_args = list(sys.argv[1:])
    if command_args[:1] == ["patch-config"]:
        return codex_config.main(
            command_args[1:],
            application_input=cli_runtime_input,
        )
    args = build_parser().parse_args(command_args)
    try:
        bootstrap = resolve_actor_bootstrap(
            args.role_id,
            application=application,
        )
        spec = ActorEnvironmentSpec(
            project_source=args.project_source,
            shared_root=args.shared_root,
            actor_id=args.actor_id,
            source_codex_home=args.source_codex_home,
            runtime_identity=current_runtime_identity(),
            bootstrap=bootstrap,
        )
        result = ActorEnvironmentBuilder().build(spec)
    except ActorEnvironmentBuildError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(_result_payload(result), ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(run_verified(main))
