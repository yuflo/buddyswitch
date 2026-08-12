"""Verified application entrypoint for resolved Actor workspace publication."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import re
import sys

from buddyswitch.application.build import ApplicationAssembly, activate_application
from buddyswitch.foundation.actor_runtime.environment import (
    ActorEnvironmentBuilder,
    ActorEnvironmentBuildError,
    ActorEnvironmentResult,
    ActorEnvironmentSpec,
    ResolvedActorBootstrap,
    ResolvedActorSkill,
)
from buddyswitch.foundation.process_runtime.invocation import (
    current_runtime_identity,
    run_verified,
)
from buddyswitch.launcher import codex_config
from buddyswitch.runtime_support import runtime_skills
from buddyswitch.runtime_support.env_manifest import DEFAULT_MANIFEST, ManifestError


PACKAGE_ROOT = Path(__file__).resolve().parents[2]
ROLE_ASSETS_ROOT = PACKAGE_ROOT / "launcher" / "assets" / "roles"
_ROLE_ID_RE = re.compile(r"^[a-z][a-z0-9-]*$")


def _base_codex_config(application: ApplicationAssembly) -> str:
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
    application: ApplicationAssembly,
) -> ResolvedActorBootstrap:
    """Resolve the current central Role/Skill truth exactly once."""

    if not _ROLE_ID_RE.fullmatch(role_id):
        raise ActorEnvironmentBuildError(f"invalid role id: {role_id}")
    try:
        resolved_skills = runtime_skills.resolve_runtime_skills(
            manifest_path=DEFAULT_MANIFEST,
            role_id=role_id,
            package_root=PACKAGE_ROOT,
        )
    except (ManifestError, runtime_skills.RuntimeSkillsError) as exc:
        raise ActorEnvironmentBuildError(f"invalid runtime role surface: {exc}") from exc
    return ResolvedActorBootstrap(
        source_root=PACKAGE_ROOT,
        agents_source=ROLE_ASSETS_ROOT / role_id / "AGENTS.md",
        skills=tuple(
            ResolvedActorSkill(skill_id=skill.skill_id, source=skill.source)
            for skill in resolved_skills
        ),
        codex_config=_base_codex_config(application),
    )


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
    command_args = list(sys.argv[1:])
    if command_args[:1] == ["patch-config"]:
        return codex_config.main(command_args[1:])
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
