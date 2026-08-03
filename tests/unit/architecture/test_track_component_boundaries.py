"""Machine-enforced ownership boundaries for the Track capability."""

from __future__ import annotations

import ast
from pathlib import Path

from tests.support.paths import REPO_ROOT


TRACK_ROOT = Path("src/buddyswitch/modules/track")
TRACK_PRIVATE = TRACK_ROOT / "private"
TRACK_PUBLIC = TRACK_ROOT / "public"
MODULE_TESTS = (
    TRACK_ROOT / "tests/integration/test_track_comment.py",
    TRACK_ROOT / "tests/unit/test_comments_repo.py",
)
ROOT_CROSS_COMPONENT_TESTS = (
    Path("tests/integration/env_tool/test_track.py"),
    Path("tests/integration/track/test_comment_added_handler.py"),
    Path("tests/integration/track/test_owner_actor_model.py"),
)
RETIRED_PATHS = (
    Path("src/buddyswitch/env/domain/track_comments.py"),
    Path("src/buddyswitch/env/domain/track_artifact_relations.py"),
    Path("src/buddyswitch/env/domain/track_read.py"),
    Path("src/buddyswitch/env/repos/track_comments.py"),
    Path("src/buddyswitch/env/repos/tracks.py"),
    Path("src/buddyswitch/env/tools/track"),
    Path("src/buddyswitch/launcher/track_comment_added_handler.py"),
    Path("src/buddyswitch/launcher/track_comment_inbound.py"),
    Path("src/buddyswitch/skills/pm/triage-track"),
    Path("src/buddyswitch/skills/shared/track-tool"),
    Path("tests/integration/env_tool/test_track_comment.py"),
    Path("tests/unit/track/test_comments_repo.py"),
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


def test_track_has_one_physical_owner_and_no_retired_live_path() -> None:
    expected = (
        TRACK_ROOT / "module.py",
        TRACK_PUBLIC / "contracts.py",
        TRACK_PUBLIC / "operations.py",
        TRACK_PRIVATE / "state/tracks.py",
        TRACK_PRIVATE / "state/track_comments.py",
        TRACK_PRIVATE / "domain/track_artifact_relations.py",
        TRACK_PRIVATE / "domain/track_comments.py",
        TRACK_PRIVATE / "read_model.py",
        TRACK_PRIVATE / "adapters/tool/tool.py",
        TRACK_PRIVATE / "adapters/tool/_impl.py",
        TRACK_PRIVATE / "adapters/daemon/track_comment_inbound.py",
        TRACK_PRIVATE / "adapters/daemon/track_comment_added_handler.py",
        TRACK_PRIVATE / "adapters/cli.py",
        TRACK_PRIVATE / "adapters/web.py",
        TRACK_PRIVATE / "adapters/cleanup.py",
        TRACK_ROOT / "skills/triage-track/SKILL.md",
        TRACK_ROOT / "skills/track-tool/SKILL.md",
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
            (REPO_ROOT / TRACK_ROOT / "tests").rglob("test_*.py")
        )
    ) == tuple(sorted(MODULE_TESTS))
    for retired in RETIRED_PATHS:
        assert not (REPO_ROOT / retired).exists(), retired


def test_track_contributes_exact_surfaces_and_is_selected_once() -> None:
    from buddyswitch.application.build import build_application
    from buddyswitch.application.composition import COMPONENTS, TRACK
    from buddyswitch.env.tool_runtime import registry
    from buddyswitch.foundation.composition import ModuleAssembly

    assert isinstance(TRACK, ModuleAssembly)
    assert TRACK.name == "track"
    assert TRACK.daemon_handlers == ()
    assert [registration.definition.id for registration in TRACK.tools] == [
        "track"
    ]
    assert [registration.name for registration in TRACK.cli_commands] == [
        "track"
    ]
    assert [export.id for export in TRACK.skills] == [
        "triage-track",
        "track-tool",
    ]
    assert [item.category for item in TRACK.cleanup] == [
        "track_objects",
        "comment_objects",
    ]
    assert [
        registration.name for registration in TRACK.actor_console_sections
    ] == ["tracks"]
    assert [
        registration.event_type for registration in TRACK.inbound_sources
    ] == ["track.comment.added"]

    assert [component.name for component in COMPONENTS] == [
        "demand",
        "task",
        "search",
        "artifact",
        "track",
        "evidence",
    ]
    assert [component.name for component in COMPONENTS].count("track") == 1
    application = build_application()
    assert [module.name for module in application.modules].count("track") == 1
    assert [
        registration.definition.id for registration in application.tools
    ].count("track") == 1
    assert [
        registration.event_type for registration in application.inbound_sources
    ].count("track.comment.added") == 1
    assert "track" not in registry.discover_tool_ids()


def test_track_dependency_direction_and_stable_storage_are_exact() -> None:
    assert _module_test_private_violations(TRACK_ROOT) == []

    track_private_root = REPO_ROOT / TRACK_PRIVATE
    for path in sorted(track_private_root.rglob("*.py")):
        assert not [
            imported
            for imported in _imports(path)
            if imported.startswith("buddyswitch.modules.artifact")
        ], path

    package_root = REPO_ROOT / "src/buddyswitch"
    track_root = REPO_ROOT / TRACK_ROOT
    violations: list[tuple[str, str]] = []
    for path in sorted(package_root.rglob("*.py")):
        if path == track_root or track_root in path.parents:
            continue
        for imported in _imports(path):
            if imported.startswith("buddyswitch.modules.track.private"):
                violations.append(
                    (path.relative_to(REPO_ROOT).as_posix(), imported)
                )
    assert violations == []

    tracks_source = (track_private_root / "state/tracks.py").read_text(
        encoding="utf-8"
    )
    comments_source = (
        track_private_root / "state/track_comments.py"
    ).read_text(encoding="utf-8")
    runtime_source = (
        REPO_ROOT / "src/buddyswitch/env/repos/runtime_files.py"
    ).read_text(encoding="utf-8")
    assert 'OBJECTS_ROOT / "tracks"' in tracks_source
    assert 'OBJECTS_ROOT / "track-comments"' in comments_source
    assert "TRACKS_DIR" not in runtime_source
    assert "TRACK_COMMENTS_DIR" not in runtime_source


def test_current_guidance_names_only_the_track_module_owner() -> None:
    guidance_paths = (
        REPO_ROOT / "README.md",
        *sorted((REPO_ROOT / "docs/arch").glob("*.md")),
    )
    retired = (
        "src/buddyswitch/env/tools/track",
        "src/buddyswitch/env/repos/tracks.py",
        "src/buddyswitch/launcher/track_comment_inbound.py",
        "src/buddyswitch/skills/shared/track-tool",
    )
    assert [
        (path.relative_to(REPO_ROOT).as_posix(), token)
        for path in guidance_paths
        for token in retired
        if token in path.read_text(encoding="utf-8")
    ] == []
