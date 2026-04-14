#!/usr/bin/env python3
"""V2 skill package metadata loading tests."""

from __future__ import annotations

import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import env_manifest  # noqa: E402


class SkillPackageLoaderTests(unittest.TestCase):
    def test_load_manifest_reads_skill_package_root(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as temp_dir:
            package_root = Path(temp_dir) / "demo-skill"
            package_root.mkdir()
            (package_root / "skill.toml").write_text(
                textwrap.dedent(
                    """\
                    id = "demo-skill"
                    buddy = "pm"
                    description = "Demo skill package."
                    objects = ["task", "artifact"]
                    produces_artifact = true
                    output_slot = "prd"
                    input_slots = ["research-report"]
                    output_schema = "framework/schemas/pm/write-prd.json"
                    produces = ["prd"]
                    consumes = ["research-report"]
                    side_effect_level = "medium"
                    required_tools = []
                    required_env = []
                    allowed_task_kinds = ["definition"]
                    """
                ),
                encoding="utf-8",
            )
            (package_root / "SKILL.md").write_text(
                textwrap.dedent(
                    """\
                    # demo-skill

                    ## Purpose
                    - Define product scope.

                    ## Use when
                    - The task is about product definition.

                    ## Do not use when
                    - The task is implementation or testing.

                    ## Inputs
                    - Research and scope context.

                    ## Outputs
                    - A structured PRD result.

                    ## Verification
                    - Confirm scope and open questions.

                    ## Examples
                    - `switch pm: define scope`

                    ## Counterexamples
                    - `switch dev: implement scope`

                    ## Gotchas
                    - Keep scope narrow.
                    """
                ),
                encoding="utf-8",
            )

            manifest_path = Path(temp_dir) / "manifest.toml"
            manifest_path.write_text(
                textwrap.dedent(
                    f"""\
                    schema_version = 1

                    [env]
                    id = "demo"
                    label = "Demo"

                    [[adapters]]
                    id = "codex"
                    path = "scripts/codex_router.py"
                    description = "Demo router."

                    [[skills]]
                    id = "demo-skill"
                    path = "{package_root.relative_to(ROOT).as_posix()}"

                    [[buddies]]
                    id = "pm"
                    label = "PM"
                    scope = "Owns scope."
                    skills = ["demo-skill"]
                    permissions = ["task.read", "task.create", "task.update", "artifact.read", "artifact.create", "artifact.update"]
                    """
                ),
                encoding="utf-8",
            )

            manifest = env_manifest.load_manifest(manifest_path)

        runtime = manifest["skills"][0]["runtime"]
        self.assertEqual(runtime["description"], "Demo skill package.")
        self.assertEqual(runtime["objects"], ["task", "artifact"])
        self.assertEqual(runtime["output_slot"], "prd")
        self.assertTrue(runtime["produces_artifact"])
        self.assertEqual(runtime["input_slots"], ["research-report"])

    def test_load_manifest_rejects_non_directory_skill_path(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as temp_dir:
            skill_file = Path(temp_dir) / "demo-skill.md"
            skill_file.write_text(
                textwrap.dedent(
                    """\
                    ---
                    name: demo-skill
                    description: Legacy skill file.
                    default_artifact_kind: prd
                    auto_summary: true
                    output_schema: framework/schemas/pm/write-prd.json
                    ---

                    # demo-skill
                    """
                ),
                encoding="utf-8",
            )

            manifest_path = Path(temp_dir) / "manifest.toml"
            manifest_path.write_text(
                textwrap.dedent(
                    f"""\
                    schema_version = 1

                    [env]
                    id = "demo"
                    label = "Demo"

                    [[adapters]]
                    id = "codex"
                    path = "scripts/codex_router.py"
                    description = "Demo router."

                    [[skills]]
                    id = "demo-skill"
                    path = "{skill_file.relative_to(ROOT).as_posix()}"

                    [[buddies]]
                    id = "pm"
                    label = "PM"
                    scope = "Owns scope."
                    skills = ["demo-skill"]
                    permissions = ["task.read", "task.create", "task.update", "artifact.read", "artifact.create", "artifact.update"]
                    """
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(env_manifest.ManifestError, "must point to a skill package directory"):
                env_manifest.load_manifest(manifest_path)

    def test_load_manifest_rejects_skill_package_frontmatter(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as temp_dir:
            package_root = Path(temp_dir) / "demo-skill"
            package_root.mkdir()
            (package_root / "skill.toml").write_text(
                textwrap.dedent(
                    """\
                    id = "demo-skill"
                    buddy = "pm"
                    description = "Demo skill package."
                    objects = ["task", "artifact"]
                    produces_artifact = true
                    output_slot = "prd"
                    input_slots = ["research-report"]
                    output_schema = "framework/schemas/pm/write-prd.json"
                    produces = ["prd"]
                    consumes = ["research-report"]
                    side_effect_level = "medium"
                    required_tools = []
                    required_env = []
                    allowed_task_kinds = ["definition"]
                    """
                ),
                encoding="utf-8",
            )
            (package_root / "SKILL.md").write_text(
                textwrap.dedent(
                    """\
                    ---
                    name: demo-skill
                    description: Legacy skill file metadata.
                    default_artifact_kind: prd
                    auto_summary: true
                    output_schema: framework/schemas/pm/write-prd.json
                    ---

                    # demo-skill
                    """
                ),
                encoding="utf-8",
            )

            manifest_path = Path(temp_dir) / "manifest.toml"
            manifest_path.write_text(
                textwrap.dedent(
                    f"""\
                    schema_version = 1

                    [env]
                    id = "demo"
                    label = "Demo"

                    [[adapters]]
                    id = "codex"
                    path = "scripts/codex_router.py"
                    description = "Demo router."

                    [[skills]]
                    id = "demo-skill"
                    path = "{package_root.relative_to(ROOT).as_posix()}"

                    [[buddies]]
                    id = "pm"
                    label = "PM"
                    scope = "Owns scope."
                    skills = ["demo-skill"]
                    permissions = ["task.read", "task.create", "task.update", "artifact.read", "artifact.create", "artifact.update"]
                    """
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(env_manifest.ManifestError, "move metadata to skill.toml"):
                env_manifest.load_manifest(manifest_path)

    def test_load_manifest_rejects_skill_missing_from_runtime_buddy_membership(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as temp_dir:
            demo_root = Path(temp_dir) / "demo-skill"
            demo_root.mkdir()
            (demo_root / "skill.toml").write_text(
                textwrap.dedent(
                    """\
                    id = "demo-skill"
                    buddy = "pm"
                    description = "Demo skill package."
                    objects = ["task", "artifact"]
                    produces_artifact = true
                    output_slot = "prd"
                    input_slots = ["research-report"]
                    output_schema = "framework/schemas/pm/write-prd.json"
                    produces = ["prd"]
                    consumes = ["research-report"]
                    side_effect_level = "medium"
                    required_tools = []
                    required_env = []
                    allowed_task_kinds = ["definition"]
                    """
                ),
                encoding="utf-8",
            )
            (demo_root / "SKILL.md").write_text(
                textwrap.dedent(
                    """\
                    # demo-skill

                    ## Purpose
                    - Define product scope.

                    ## Use when
                    - The task is about product definition.

                    ## Do not use when
                    - The task is implementation or testing.

                    ## Inputs
                    - Research and scope context.

                    ## Outputs
                    - A structured PRD result.

                    ## Verification
                    - Confirm scope and open questions.

                    ## Examples
                    - `switch pm: define scope`

                    ## Counterexamples
                    - `switch dev: implement scope`

                    ## Gotchas
                    - Keep scope narrow.
                    """
                ),
                encoding="utf-8",
            )

            other_root = Path(temp_dir) / "other-skill"
            other_root.mkdir()
            (other_root / "skill.toml").write_text(
                textwrap.dedent(
                    """\
                    id = "other-skill"
                    buddy = "pm"
                    description = "Other skill package."
                    objects = ["task"]
                    produces_artifact = false
                    input_slots = []
                    output_schema = "framework/schemas/pm/track-manager.json"
                    produces = ["track-state"]
                    consumes = []
                    side_effect_level = "low"
                    required_tools = []
                    required_env = []
                    allowed_task_kinds = ["track-management"]
                    """
                ),
                encoding="utf-8",
            )
            (other_root / "SKILL.md").write_text(
                textwrap.dedent(
                    """\
                    # other-skill

                    ## Purpose
                    - Manage tracks.

                    ## Use when
                    - The task is about track lifecycle.

                    ## Do not use when
                    - The task is about implementation.

                    ## Inputs
                    - Track context.

                    ## Outputs
                    - A structured track result.

                    ## Verification
                    - Confirm the requested track change.

                    ## Examples
                    - `switch pm: update track`

                    ## Counterexamples
                    - `switch dev: implement code`

                    ## Gotchas
                    - Keep scope narrow.
                    """
                ),
                encoding="utf-8",
            )

            manifest_path = Path(temp_dir) / "manifest.toml"
            manifest_path.write_text(
                textwrap.dedent(
                    f"""\
                    schema_version = 1

                    [env]
                    id = "demo"
                    label = "Demo"

                    [[adapters]]
                    id = "codex"
                    path = "scripts/codex_router.py"
                    description = "Demo router."

                    [[skills]]
                    id = "demo-skill"
                    path = "{demo_root.relative_to(ROOT).as_posix()}"

                    [[skills]]
                    id = "other-skill"
                    path = "{other_root.relative_to(ROOT).as_posix()}"

                    [[buddies]]
                    id = "pm"
                    label = "PM"
                    scope = "Owns scope."
                    skills = ["other-skill"]
                    permissions = ["task.read", "task.create", "task.update", "artifact.read", "artifact.create", "artifact.update"]
                    """
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(env_manifest.ManifestError, "runtime buddy 'pm' must be declared"):
                env_manifest.load_manifest(manifest_path)


if __name__ == "__main__":
    unittest.main()
