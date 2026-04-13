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
                    description = "Demo skill package."
                    buddies = ["pm"]
                    objects = ["task", "artifact"]

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
        self.assertEqual(runtime["output_slot"], "prd")
        self.assertTrue(runtime["produces_artifact"])
        self.assertEqual(runtime["input_slots"], ["research-report"])


if __name__ == "__main__":
    unittest.main()

