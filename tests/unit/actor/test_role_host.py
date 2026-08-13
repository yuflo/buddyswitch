"""Narrow reviewed Role-package and RoleHost contracts."""

from __future__ import annotations

import importlib
from pathlib import Path
import textwrap

import pytest

import buddyswitch
from buddyswitch.application.build import build_application
from buddyswitch.foundation.composition import SkillExport
from buddyswitch.modules.artifact import public as artifact_public


def _api():
    try:
        module = importlib.import_module("buddyswitch.foundation.role_host")
    except ModuleNotFoundError:
        pytest.fail("RoleHost public contract is not implemented")
    return module.RoleHost, module.RoleHostError


def _role_source(
    *,
    role_id: str,
    skills: tuple[str, ...] = ("private-skill", "component-skill"),
    source_access: str = "read-only",
    artifact_templates: tuple[str, ...] = ("brief",),
) -> str:
    return textwrap.dedent(
        f'''\
        from buddyswitch.foundation.role_host import RoleDescriptor

        ROLE = RoleDescriptor(
            id={role_id!r},
            label="Probe",
            scope="Exercise reviewed package discovery.",
            skills={skills!r},
            artifact_templates={artifact_templates!r},
            project_path="projects/app",
            source_access={source_access!r},
            browser_cockpit="available",
            search_api="available",
        )
        '''
    )


def _write_role(
    roles_root: Path,
    directory: str,
    *,
    role_id: str,
    skills: tuple[str, ...] = ("private-skill", "component-skill"),
    private_skill: str | None = "private-skill",
) -> Path:
    role_root = roles_root / directory
    role_root.mkdir(parents=True)
    (role_root / "role.py").write_text(
        _role_source(role_id=role_id, skills=skills),
        encoding="utf-8",
    )
    (role_root / "AGENTS.md").write_text(f"# {role_id}\n", encoding="utf-8")
    assets_root = role_root / "assets"
    assets_root.mkdir()
    (assets_root / "result-schema.json").write_text("{}\n", encoding="utf-8")
    if private_skill is not None:
        skill_root = role_root / "skills" / private_skill
        skill_root.mkdir(parents=True)
        (skill_root / "SKILL.md").write_text(
            f"---\nname: {private_skill}\ndescription: probe\n---\n",
            encoding="utf-8",
        )
    return role_root


def _component_skill(package_root: Path) -> SkillExport:
    skill_root = package_root / "modules" / "probe" / "skills" / "component-skill"
    skill_root.mkdir(parents=True)
    (skill_root / "SKILL.md").write_text(
        "---\nname: component-skill\ndescription: probe\n---\n",
        encoding="utf-8",
    )
    return SkillExport(
        id="component-skill",
        package_path="modules/probe/skills/component-skill",
    )


def test_installed_role_host_projects_every_discovered_role_package() -> None:
    RoleHost, _ = _api()
    package_root = Path(buddyswitch.__file__).resolve().parent

    host = RoleHost.discover(
        package_root=package_root,
        component_skills=build_application().skills,
        valid_artifact_templates=artifact_public.VALID_ARTIFACT_TEMPLATES,
    )

    package_directories = tuple(
        path
        for path in sorted((package_root / "roles").iterdir())
        if path.is_dir() and not path.name.startswith("_")
    )
    assert package_directories
    assert len(host.roles) == len(package_directories)
    assert tuple(role.id for role in host.roles) == tuple(
        sorted(host.valid_role_ids)
    )
    for summary in host.roles:
        runtime = host.runtime(summary.id)
        bootstrap = host.actor_bootstrap(summary.id, codex_config="")
        assert runtime.id == summary.id
        assert runtime.artifact_templates
        assert set(runtime.artifact_templates) <= set(
            artifact_public.VALID_ARTIFACT_TEMPLATES
        )
        assert bootstrap.agents_source.name == "AGENTS.md"
        assert bootstrap.skills
        assert len({skill.skill_id for skill in bootstrap.skills}) == len(
            bootstrap.skills
        )


def test_role_host_resolves_only_selected_agents_and_skills(tmp_path: Path) -> None:
    RoleHost, _ = _api()
    package_root = tmp_path / "buddyswitch"
    roles_root = package_root / "roles"
    _write_role(roles_root, "directory_name", role_id="durable-id")
    component = _component_skill(package_root)

    host = RoleHost.discover(
        package_root=package_root,
        component_skills=(component,),
        valid_artifact_templates=artifact_public.VALID_ARTIFACT_TEMPLATES,
    )
    bootstrap = host.actor_bootstrap("durable-id", codex_config="[features]\n")

    assert bootstrap.agents_source == roles_root / "directory_name" / "AGENTS.md"
    assert tuple(skill.skill_id for skill in bootstrap.skills) == (
        "private-skill",
        "component-skill",
    )
    assert bootstrap.source_root == package_root


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        ("missing-agents", "AGENTS"),
        ("missing-result-schema", "result schema"),
        ("invalid-result-schema", "valid UTF-8 JSON"),
        ("unknown-skill", "unknown Skill"),
        ("duplicate-selected-skill", "duplicate selected Skill"),
        ("absolute-component-path", "relative"),
        ("escaping-component-path", "must not contain"),
        ("escaping-project-path", "contained relative path"),
        ("invalid-source-access", "source_access"),
        ("invalid-artifact-template", "artifact_templates"),
    ),
)
def test_role_host_fails_closed_for_invalid_package_contracts(
    tmp_path: Path,
    mutation: str,
    message: str,
) -> None:
    RoleHost, RoleHostError = _api()
    package_root = tmp_path / "buddyswitch"
    roles_root = package_root / "roles"
    role_root = _write_role(roles_root, "probe", role_id="probe")
    component = _component_skill(package_root)

    if mutation == "missing-agents":
        (role_root / "AGENTS.md").unlink()
    elif mutation == "missing-result-schema":
        (role_root / "assets" / "result-schema.json").unlink()
    elif mutation == "invalid-result-schema":
        (role_root / "assets" / "result-schema.json").write_text(
            "{invalid\n",
            encoding="utf-8",
        )
    elif mutation == "unknown-skill":
        (role_root / "role.py").write_text(
            _role_source(role_id="probe", skills=("missing",)),
            encoding="utf-8",
        )
    elif mutation == "duplicate-selected-skill":
        (role_root / "role.py").write_text(
            _role_source(
                role_id="probe",
                skills=("private-skill", "private-skill"),
            ),
            encoding="utf-8",
        )
    elif mutation == "absolute-component-path":
        component = SkillExport(
            id="component-skill",
            package_path=str((package_root / "outside").resolve()),
        )
    elif mutation == "escaping-component-path":
        component = SkillExport(
            id="component-skill",
            package_path="../outside",
        )
    elif mutation == "escaping-project-path":
        source = _role_source(role_id="probe").replace(
            'project_path="projects/app"',
            'project_path="../outside"',
        )
        (role_root / "role.py").write_text(source, encoding="utf-8")
    elif mutation == "invalid-source-access":
        source = _role_source(role_id="probe").replace(
            "source_access='read-only'",
            "source_access='admin'",
        )
        (role_root / "role.py").write_text(source, encoding="utf-8")
    elif mutation == "invalid-artifact-template":
        (role_root / "role.py").write_text(
            _role_source(
                role_id="probe",
                artifact_templates=("not-an-artifact-template",),
            ),
            encoding="utf-8",
        )

    with pytest.raises(RoleHostError, match=message):
        RoleHost.discover(
            package_root=package_root,
            component_skills=(component,),
            valid_artifact_templates=artifact_public.VALID_ARTIFACT_TEMPLATES,
        )


def test_role_host_rejects_duplicate_role_ids(tmp_path: Path) -> None:
    RoleHost, RoleHostError = _api()
    package_root = tmp_path / "buddyswitch"
    roles_root = package_root / "roles"
    _write_role(roles_root, "one", role_id="duplicate")
    _write_role(roles_root, "two", role_id="duplicate")
    component = _component_skill(package_root)

    with pytest.raises(RoleHostError, match="duplicate Role id"):
        RoleHost.discover(
            package_root=package_root,
            component_skills=(component,),
            valid_artifact_templates=artifact_public.VALID_ARTIFACT_TEMPLATES,
        )


def test_role_private_skill_ids_are_local_to_each_role(tmp_path: Path) -> None:
    RoleHost, _ = _api()
    package_root = tmp_path / "buddyswitch"
    roles_root = package_root / "roles"
    for directory, role_id in (("one", "first-role"), ("two", "second-role")):
        _write_role(
            roles_root,
            directory,
            role_id=role_id,
            skills=("shared-private", "component-skill"),
            private_skill="shared-private",
        )
    component = _component_skill(package_root)

    host = RoleHost.discover(
        package_root=package_root,
        component_skills=(component,),
        valid_artifact_templates=artifact_public.VALID_ARTIFACT_TEMPLATES,
    )

    first = host.actor_bootstrap("first-role", codex_config="")
    second = host.actor_bootstrap("second-role", codex_config="")
    first_private = first.skills[0]
    second_private = second.skills[0]
    assert first_private.skill_id == second_private.skill_id == "shared-private"
    assert first_private.source == roles_root / "one" / "skills" / "shared-private"
    assert second_private.source == roles_root / "two" / "skills" / "shared-private"


def test_role_cannot_select_another_roles_private_skill(tmp_path: Path) -> None:
    RoleHost, RoleHostError = _api()
    package_root = tmp_path / "buddyswitch"
    roles_root = package_root / "roles"
    _write_role(
        roles_root,
        "owner",
        role_id="owner-role",
        skills=("owner-private", "component-skill"),
        private_skill="owner-private",
    )
    _write_role(
        roles_root,
        "consumer",
        role_id="consumer-role",
        skills=("owner-private", "component-skill"),
        private_skill=None,
    )
    component = _component_skill(package_root)

    with pytest.raises(
        RoleHostError,
        match="Role 'consumer-role' selects unknown Skill 'owner-private'",
    ):
        RoleHost.discover(
            package_root=package_root,
            component_skills=(component,),
            valid_artifact_templates=artifact_public.VALID_ARTIFACT_TEMPLATES,
        )


def test_role_private_and_component_skill_collision_names_the_role(
    tmp_path: Path,
) -> None:
    RoleHost, RoleHostError = _api()
    package_root = tmp_path / "buddyswitch"
    roles_root = package_root / "roles"
    _write_role(
        roles_root,
        "probe",
        role_id="probe",
        skills=("component-skill",),
        private_skill="component-skill",
    )
    component = _component_skill(package_root)

    with pytest.raises(
        RoleHostError,
        match=(
            "Role 'probe' private Skill 'component-skill' conflicts with "
            "component Skill 'component-skill'"
        ),
    ):
        RoleHost.discover(
            package_root=package_root,
            component_skills=(component,),
            valid_artifact_templates=artifact_public.VALID_ARTIFACT_TEMPLATES,
        )


def test_role_host_rejects_symlink_boundaries_before_selection(tmp_path: Path) -> None:
    RoleHost, RoleHostError = _api()
    package_root = tmp_path / "buddyswitch"
    roles_root = package_root / "roles"
    role_root = _write_role(roles_root, "probe", role_id="probe")
    component = _component_skill(package_root)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "SKILL.md").write_text("outside", encoding="utf-8")
    (role_root / "skills" / "linked").symlink_to(outside, target_is_directory=True)

    with pytest.raises(RoleHostError, match="symlink"):
        RoleHost.discover(
            package_root=package_root,
            component_skills=(component,),
            valid_artifact_templates=artifact_public.VALID_ARTIFACT_TEMPLATES,
        )


def test_role_host_rejects_unknown_roles_without_fallback(tmp_path: Path) -> None:
    RoleHost, RoleHostError = _api()
    package_root = tmp_path / "buddyswitch"
    roles_root = package_root / "roles"
    _write_role(roles_root, "probe", role_id="probe")
    component = _component_skill(package_root)
    host = RoleHost.discover(
        package_root=package_root,
        component_skills=(component,),
        valid_artifact_templates=artifact_public.VALID_ARTIFACT_TEMPLATES,
    )

    with pytest.raises(RoleHostError, match="Unknown Role 'ghost'.*probe"):
        host.runtime("ghost")
