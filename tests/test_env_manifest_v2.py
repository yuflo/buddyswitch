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


EXPECTED_MARKET_TOOL_SCOPE = {
    "profile": "market-browser-native",
    "mode": "allowlist",
    "allowed_tool_servers": ["chrome-devtools-cockpit"],
    "downgrade_policy": "user-approved-one-off",
    "temporary_allowed_tool_servers": ["web"],
    "downgrade_reason": "browser-native-blocked",
}


class SkillPackageLoaderTests(unittest.TestCase):
    def _load_demo_market_manifest(self, skill_toml_body: str) -> dict[str, object]:
        with tempfile.TemporaryDirectory(dir=ROOT) as temp_dir:
            package_root = Path(temp_dir) / "demo-skill"
            package_root.mkdir()
            (package_root / "skill.toml").write_text(textwrap.dedent(skill_toml_body), encoding="utf-8")
            (package_root / "SKILL.md").write_text(
                textwrap.dedent(
                    """\
                    # demo-skill

                    ## Purpose
                    - Validate market demand.

                    ## Use when
                    - The task is about market research.

                    ## Do not use when
                    - The task is implementation or testing.

                    ## Inputs
                    - Research question context.

                    ## Outputs
                    - A structured market scan result.

                    ## Verification
                    - Confirm evidence quality and open questions.

                    ## Examples
                    - `Validate a workflow for the current market goal`

                    ## Counterexamples
                    - `Implement the workflow in project code`

                    ## Gotchas
                    - Keep evidence grounded in sources.
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

                    [[skills]]
                    id = "demo-skill"
                    path = "{package_root.relative_to(ROOT).as_posix()}"

                    [[buddies]]
                    id = "market"
                    label = "Market"
                    scope = "Owns market research."
                    skills = ["demo-skill"]
                    permissions = ["task.read", "task.create", "task.update", "artifact.read", "artifact.create", "artifact.update"]
                    """
                ),
                encoding="utf-8",
            )

            return env_manifest.load_manifest(manifest_path)

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
                    - `Define scope for the current product request`

                    ## Counterexamples
                    - `Implement the approved scope`

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

    def test_manifest_allows_buddy_with_no_registered_skills(self) -> None:
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
                    - `Define scope for the current product request`

                    ## Counterexamples
                    - `Implement the approved scope`

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

                    [[skills]]
                    id = "demo-skill"
                    path = "{package_root.relative_to(ROOT).as_posix()}"

                    [[buddies]]
                    id = "pm"
                    label = "PM"
                    scope = "Owns scope."
                    skills = ["demo-skill"]
                    permissions = ["task.read", "task.create", "task.update", "artifact.read", "artifact.create", "artifact.update"]

                    [[buddies]]
                    id = "design"
                    label = "Design"
                    scope = "Owns design direction."
                    skills = []
                    permissions = ["task.read", "task.create", "task.update", "artifact.read", "artifact.create", "artifact.update"]
                    """
                ),
                encoding="utf-8",
            )

            manifest = env_manifest.load_manifest(manifest_path)

        buddies = {buddy["id"]: buddy for buddy in manifest["buddies"]}
        self.assertEqual(buddies["design"]["skills"], [])

    def test_live_manifest_registers_shape_prototype_for_design(self) -> None:
        manifest = env_manifest.load_manifest(ROOT / "buddyswitch" / "manifest.toml")

        buddies = {buddy["id"]: buddy for buddy in manifest["buddies"]}
        skills = {skill["id"]: skill for skill in manifest["skills"]}

        self.assertEqual(buddies["design"]["skills"], ["shape-prototype"])
        runtime = skills["shape-prototype"]["runtime"]
        self.assertEqual(runtime["output_slot"], "design-handoff")
        self.assertEqual(
            runtime["input_slots"],
            ["market-scan", "prd", "requirements", "track", "design-handoff"],
        )

    def test_load_manifest_reads_optional_host_execution_metadata(self) -> None:
        manifest = self._load_demo_market_manifest(
            """\
            id = "demo-skill"
            buddy = "market"
            description = "Use when demo market work is requested."
            objects = ["task", "artifact"]
            produces_artifact = true
            output_slot = "market-scan"
            input_slots = ["research-question"]
            output_schema = "framework/schemas/market/research-scan.json"
            produces = ["market-scan"]
            consumes = ["research-question"]
            side_effect_level = "medium"
            required_tools = ["chrome-devtools-cockpit"]
            required_env = []
            execution_mode = "browser-cockpit-native"
            browser_mode = "headed-only"
            browser_profile = "instance-browser"
            browser_executor = "chrome-devtools-cockpit"
            discovery_mode = "browser-native"
            login_policy = "mandatory-takeover"
            fallback_policy = "no-silent-degrade"
            session_continuity = "instance-cockpit"
            evidence_capture_level = "medium"
            allowed_task_kinds = ["research"]
            """
        )

        runtime = manifest["skills"][0]["runtime"]
        self.assertEqual(runtime["required_tools"], ["chrome-devtools-cockpit"])
        self.assertEqual(
            runtime["host_execution"],
            {
                "execution_mode": "browser-cockpit-native",
                "browser_mode": "headed-only",
                "browser_profile": "instance-browser",
                "browser_executor": "chrome-devtools-cockpit",
                "discovery_mode": "browser-native",
                "login_policy": "mandatory-takeover",
                "fallback_policy": "no-silent-degrade",
                "session_continuity": "instance-cockpit",
                "evidence_capture_level": "medium",
            },
        )

    def test_load_manifest_rejects_market_skill_with_missing_cockpit_metadata(self) -> None:
        with self.assertRaisesRegex(env_manifest.ManifestError, "browser_executor"):
            self._load_demo_market_manifest(
                """\
                id = "demo-skill"
                buddy = "market"
                description = "Use when demo market work is requested."
                objects = ["task", "artifact"]
                produces_artifact = true
                output_slot = "market-scan"
                input_slots = ["research-question"]
                output_schema = "framework/schemas/market/research-scan.json"
                produces = ["market-scan"]
                consumes = ["research-question"]
                side_effect_level = "medium"
                required_tools = ["chrome-devtools-cockpit"]
                required_env = []
                execution_mode = "browser-cockpit-native"
                browser_mode = "headed-only"
                browser_profile = "instance-browser"
                discovery_mode = "browser-native"
                login_policy = "mandatory-takeover"
                fallback_policy = "no-silent-degrade"
                session_continuity = "instance-cockpit"
                evidence_capture_level = "medium"
                allowed_task_kinds = ["research"]
                """
            )

        with self.assertRaisesRegex(env_manifest.ManifestError, "discovery_mode"):
            self._load_demo_market_manifest(
                """\
                id = "demo-skill"
                buddy = "market"
                description = "Use when demo market work is requested."
                objects = ["task", "artifact"]
                produces_artifact = true
                output_slot = "market-scan"
                input_slots = ["research-question"]
                output_schema = "framework/schemas/market/research-scan.json"
                produces = ["market-scan"]
                consumes = ["research-question"]
                side_effect_level = "medium"
                required_tools = ["chrome-devtools-cockpit"]
                required_env = []
                execution_mode = "browser-cockpit-native"
                browser_mode = "headed-only"
                browser_profile = "instance-browser"
                browser_executor = "chrome-devtools-cockpit"
                login_policy = "mandatory-takeover"
                fallback_policy = "no-silent-degrade"
                session_continuity = "instance-cockpit"
                evidence_capture_level = "medium"
                allowed_task_kinds = ["research"]
                """
            )

    def test_load_manifest_rejects_market_skill_with_invalid_cockpit_metadata_value(self) -> None:
        with self.assertRaisesRegex(env_manifest.ManifestError, "login_policy"):
            self._load_demo_market_manifest(
                """\
                id = "demo-skill"
                buddy = "market"
                description = "Use when demo market work is requested."
                objects = ["task", "artifact"]
                produces_artifact = true
                output_slot = "market-scan"
                input_slots = ["research-question"]
                output_schema = "framework/schemas/market/research-scan.json"
                produces = ["market-scan"]
                consumes = ["research-question"]
                side_effect_level = "medium"
                required_tools = ["chrome-devtools-cockpit"]
                required_env = []
                execution_mode = "browser-cockpit-native"
                browser_mode = "headed-only"
                browser_profile = "instance-browser"
                browser_executor = "chrome-devtools-cockpit"
                discovery_mode = "browser-native"
                login_policy = "optional"
                fallback_policy = "no-silent-degrade"
                session_continuity = "instance-cockpit"
                evidence_capture_level = "medium"
                allowed_task_kinds = ["research"]
                """
            )

    def test_load_manifest_rejects_market_skill_with_invalid_discovery_mode_value(self) -> None:
        with self.assertRaisesRegex(env_manifest.ManifestError, "discovery_mode"):
            self._load_demo_market_manifest(
                """\
                id = "demo-skill"
                buddy = "market"
                description = "Use when demo market work is requested."
                objects = ["task", "artifact"]
                produces_artifact = true
                output_slot = "market-scan"
                input_slots = ["research-question"]
                output_schema = "framework/schemas/market/research-scan.json"
                produces = ["market-scan"]
                consumes = ["research-question"]
                side_effect_level = "medium"
                required_tools = ["chrome-devtools-cockpit"]
                required_env = []
                execution_mode = "browser-cockpit-native"
                browser_mode = "headed-only"
                browser_profile = "instance-browser"
                browser_executor = "chrome-devtools-cockpit"
                discovery_mode = "manual"
                login_policy = "mandatory-takeover"
                fallback_policy = "no-silent-degrade"
                session_continuity = "instance-cockpit"
                evidence_capture_level = "medium"
                allowed_task_kinds = ["research"]
                """
            )

    def test_load_manifest_reads_market_tool_scope_profile(self) -> None:
        manifest = self._load_demo_market_manifest(
            """\
            id = "demo-skill"
            buddy = "market"
            description = "Use when demo market work is requested."
            objects = ["task", "artifact"]
            produces_artifact = true
            output_slot = "market-scan"
            input_slots = ["research-question"]
            output_schema = "framework/schemas/market/research-scan.json"
            produces = ["market-scan"]
            consumes = ["research-question"]
            side_effect_level = "medium"
            required_tools = ["chrome-devtools-cockpit"]
            required_env = []
            execution_mode = "browser-cockpit-native"
            browser_mode = "headed-only"
            browser_profile = "instance-browser"
            browser_executor = "chrome-devtools-cockpit"
            discovery_mode = "browser-native"
            login_policy = "mandatory-takeover"
            fallback_policy = "no-silent-degrade"
            session_continuity = "instance-cockpit"
            evidence_capture_level = "medium"
            tool_scope_profile = "market-browser-native"
            allowed_task_kinds = ["research"]
            """
        )

        runtime = manifest["skills"][0]["runtime"]
        self.assertEqual(runtime["tool_scope_profile"], "market-browser-native")
        self.assertEqual(runtime["tool_scope"], EXPECTED_MARKET_TOOL_SCOPE)

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
                    - `Define scope for the current product request`

                    ## Counterexamples
                    - `Implement the approved scope`

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
                    - `Update the current track summary`

                    ## Counterexamples
                    - `Implement the approved code changes`

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
