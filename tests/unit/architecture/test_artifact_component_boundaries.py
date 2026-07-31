"""Machine-enforced ownership boundaries for the Artifact capability."""

from __future__ import annotations

import ast
import json
from pathlib import Path

from tests.support.paths import REPO_ROOT


ARTIFACT_ROOT = Path("src/buddyswitch/modules/artifact")
ARTIFACT_PRIVATE = ARTIFACT_ROOT / "private"
ARTIFACT_PUBLIC = ARTIFACT_ROOT / "public"
MODULE_TESTS = (
    ARTIFACT_ROOT / "tests/unit/test_artifact_selection.py",
)
ROOT_CROSS_COMPONENT_TESTS = (
    Path("tests/integration/env_tool/_artifact_env_tool_case.py"),
    Path("tests/integration/env_tool/test_artifact_attachments.py"),
    Path("tests/integration/env_tool/test_artifact_listing.py"),
    Path("tests/integration/env_tool/test_artifact_publication.py"),
    Path("tests/integration/env_tool/test_artifact_relations.py"),
    Path("tests/integration/env_tool/test_artifact_validation.py"),
    Path("tests/integration/env_tool/test_response_artifact.py"),
)
RETIRED_PATHS = (
    Path("src/buddyswitch/config/artifact-selection-v1.json"),
    Path("src/buddyswitch/config/artifact-selection-v2.json"),
    Path("src/buddyswitch/env/domain/artifact_relations.py"),
    Path("src/buddyswitch/env/domain/artifact_visibility.py"),
    Path("src/buddyswitch/env/domain/source_refs.py"),
    Path("src/buddyswitch/env/repos/artifacts.py"),
    Path("src/buddyswitch/env/tools/artifact"),
    Path("src/buddyswitch/runtime_support/artifact_selection.py"),
    Path("src/buddyswitch/skills/shared/artifact-tool"),
    Path("tests/unit/env_tool/test_artifact_selection.py"),
)


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if node.level == 0:
                if module:
                    imports.add(module)
                continue
            package_parts = path.relative_to(
                REPO_ROOT / "src"
            ).parent.parts
            retained = len(package_parts) - (node.level - 1)
            if retained < 0:
                continue
            resolved = (*package_parts[:retained], *module.split("."))
            imports.add(".".join(part for part in resolved if part))
    return imports


def _module_test_private_violations(
    module_root: Path,
) -> list[tuple[str, str]]:
    owner = module_root.name
    violations: list[tuple[str, str]] = []
    for path in sorted((REPO_ROOT / module_root / "tests").rglob("*.py")):
        for imported in _imports(path):
            parts = imported.split(".")
            if (
                len(parts) >= 4
                and parts[:2] == ["buddyswitch", "modules"]
                and parts[3] == "private"
                and parts[2] != owner
            ):
                violations.append(
                    (path.relative_to(REPO_ROOT).as_posix(), imported)
                )
    return violations


def test_artifact_has_one_physical_owner_and_no_retired_live_path() -> None:
    expected = (
        ARTIFACT_ROOT / "module.py",
        ARTIFACT_PUBLIC / "contracts.py",
        ARTIFACT_PUBLIC / "operations.py",
        ARTIFACT_PRIVATE / "state/artifacts.py",
        ARTIFACT_PRIVATE / "domain/artifact_relations.py",
        ARTIFACT_PRIVATE / "domain/artifact_visibility.py",
        ARTIFACT_PRIVATE / "domain/source_refs.py",
        ARTIFACT_PRIVATE / "adapters/tool/tool.py",
        ARTIFACT_PRIVATE / "adapters/tool/_impl.py",
        ARTIFACT_PRIVATE / "adapters/track_port.py",
        ARTIFACT_PRIVATE / "adapters/cleanup.py",
        ARTIFACT_ROOT / "entrypoints/artifact_selection.py",
        ARTIFACT_ROOT / "assets/artifact-selection-v1.json",
        ARTIFACT_ROOT / "assets/artifact-selection-v2.json",
        ARTIFACT_ROOT / "skills/artifact-tool/SKILL.md",
        *MODULE_TESTS,
        *ROOT_CROSS_COMPONENT_TESTS,
    )
    assert [
        path.as_posix()
        for path in expected
        if not (REPO_ROOT / path).is_file()
    ] == []
    assert tuple(
        path.relative_to(REPO_ROOT)
        for path in sorted(
            (REPO_ROOT / ARTIFACT_ROOT / "tests").rglob("test_*.py")
        )
    ) == tuple(sorted(MODULE_TESTS))
    for retired in RETIRED_PATHS:
        assert not (REPO_ROOT / retired).exists(), retired

    for version in (1, 2):
        asset = (
            REPO_ROOT
            / ARTIFACT_ROOT
            / f"assets/artifact-selection-v{version}.json"
        )
        assert isinstance(json.loads(asset.read_text(encoding="utf-8")), dict)


def test_artifact_contributes_exact_surfaces_and_is_selected_once() -> None:
    from buddyswitch.application.build import build_application
    from buddyswitch.application.composition import ARTIFACT, COMPONENTS
    from buddyswitch.env.tool_runtime import registry
    from buddyswitch.foundation.composition import ModuleAssembly

    assert isinstance(ARTIFACT, ModuleAssembly)
    assert ARTIFACT.name == "artifact"
    assert ARTIFACT.daemon_handlers == ()
    assert ARTIFACT.cli_commands == ()
    assert ARTIFACT.actor_console_sections == ()
    assert ARTIFACT.inbound_sources == ()
    assert [registration.definition.id for registration in ARTIFACT.tools] == [
        "artifact"
    ]
    assert [export.id for export in ARTIFACT.skills] == ["artifact-tool"]
    assert [item.category for item in ARTIFACT.cleanup] == [
        "artifact_objects",
        "artifact_attachments",
    ]
    assert [component.name for component in COMPONENTS].count("artifact") == 1
    application = build_application()
    assert [module.name for module in application.modules].count("artifact") == 1
    assert [
        registration.definition.id for registration in application.tools
    ].count("artifact") == 1
    assert "artifact" not in registry.discover_tool_ids()


def test_artifact_dependency_direction_and_composition_wiring_are_exact() -> None:
    assert _module_test_private_violations(ARTIFACT_ROOT) == []

    artifact_private_root = REPO_ROOT / ARTIFACT_PRIVATE
    for path in sorted(artifact_private_root.rglob("*.py")):
        assert not [
            imported
            for imported in _imports(path)
            if imported.startswith("buddyswitch.modules.track.private")
        ], path

    for path in sorted((REPO_ROOT / ARTIFACT_PUBLIC).rglob("*.py")):
        assert not [
            imported
            for imported in _imports(path)
            if imported.startswith("buddyswitch.modules.track")
        ], path

    track_port_imports = _imports(
        artifact_private_root / "adapters/track_port.py"
    )
    assert "buddyswitch.modules.track.public.contracts" in track_port_imports
    relation_imports = _imports(
        artifact_private_root / "domain/artifact_relations.py"
    )
    visibility_imports = _imports(
        artifact_private_root / "domain/artifact_visibility.py"
    )
    assert "buddyswitch.modules.track" in (
        relation_imports | visibility_imports
    )

    composition = (
        REPO_ROOT / "src/buddyswitch/application/composition.py"
    ).read_text(encoding="utf-8")
    assert composition.count("build_track_module(") == 1
    assert (
        "resolve_publication_candidate="
        "artifact_public.resolve_publication_candidate"
    ) in composition
    assert (
        "read_reference_metadata=artifact_public.read_reference_metadata"
    ) in composition

    track_private = REPO_ROOT / "src/buddyswitch/modules/track/private"
    assert not [
        (path.relative_to(REPO_ROOT).as_posix(), imported)
        for path in sorted(track_private.rglob("*.py"))
        for imported in _imports(path)
        if imported.startswith("buddyswitch.modules.artifact")
    ]

    package_root = REPO_ROOT / "src/buddyswitch"
    artifact_root = REPO_ROOT / ARTIFACT_ROOT
    assert [
        (path.relative_to(REPO_ROOT).as_posix(), imported)
        for path in sorted(package_root.rglob("*.py"))
        if path != artifact_root and artifact_root not in path.parents
        for imported in _imports(path)
        if imported.startswith("buddyswitch.modules.artifact.private")
    ] == []


def test_artifact_stable_storage_package_assets_and_guidance_are_exact() -> None:
    state_source = (
        REPO_ROOT / ARTIFACT_PRIVATE / "state/artifacts.py"
    ).read_text(encoding="utf-8")
    runtime_source = (
        REPO_ROOT / "src/buddyswitch/env/repos/runtime_files.py"
    ).read_text(encoding="utf-8")
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'OBJECTS_ROOT / "artifacts"' in state_source
    assert 'OBJECTS_ROOT / "artifact-attachments"' in state_source
    assert "ARTIFACTS_DIR" not in runtime_source
    assert "ARTIFACT_ATTACHMENTS_DIR" not in runtime_source
    assert '"buddyswitch.modules.artifact"' in pyproject
    assert '"assets/**/*.json"' in pyproject
    assert '"skills/**/*.md"' in pyproject

    guidance_paths = (
        REPO_ROOT / "README.md",
        *sorted((REPO_ROOT / "docs/arch").glob("*.md")),
    )
    retired = (
        "src/buddyswitch/env/tools/artifact",
        "src/buddyswitch/env/repos/artifacts.py",
        "src/buddyswitch/config/artifact-selection",
        "src/buddyswitch/skills/shared/artifact-tool",
    )
    assert [
        (path.relative_to(REPO_ROOT).as_posix(), token)
        for path in guidance_paths
        for token in retired
        if token in path.read_text(encoding="utf-8")
    ] == []
