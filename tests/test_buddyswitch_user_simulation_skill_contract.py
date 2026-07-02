#!/usr/bin/env python3
"""Target-locked contract tests for the BuddySwitch user simulation skill."""

from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / ".agents" / "skills" / "buddyswitch-user-simulation-testing"
SKILL_FILE = SKILL_ROOT / "SKILL.md"
REFERENCE_DIR = SKILL_ROOT / "references"
OPENAI_YAML = SKILL_ROOT / "agents" / "openai.yaml"

OLD_ABSTRACTION_FILES = (
    REFERENCE_DIR / "invocation-and-pairing.md",
    REFERENCE_DIR / "simulation-means.md",
    REFERENCE_DIR / "gate-levels.md",
    REFERENCE_DIR / "scenario-matrix.md",
    REFERENCE_DIR / "evidence-schema.md",
    SKILL_ROOT / "scripts" / "init_simulation_evidence.py",
    SKILL_ROOT / "scripts" / "summarize_simulation_evidence.py",
)


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _frontmatter_description(skill_text: str) -> str:
    match = re.match(r"---\n(?P<body>.*?)\n---\n", skill_text, flags=re.DOTALL)
    if not match:
        raise AssertionError("SKILL.md is missing YAML frontmatter")
    for line in match.group("body").splitlines():
        if line.startswith("description:"):
            return line.removeprefix("description:").strip().strip('"')
    raise AssertionError("SKILL.md frontmatter is missing description")


def _section(text: str, heading: str, end_heading: str | None = None) -> str:
    start = text.find(heading)
    if start < 0:
        raise AssertionError(f"missing section {heading!r}")
    if end_heading is not None:
        end = text.find(end_heading, start + len(heading))
        if end < 0:
            raise AssertionError(f"missing end section {end_heading!r}")
        return text[start:end]
    next_heading = re.search(r"\n## ", text[start + len(heading) :])
    if not next_heading:
        return text[start:]
    return text[start : start + len(heading) + next_heading.start()]


def _assert_order(testcase: unittest.TestCase, text: str, *needles: str) -> None:
    last = -1
    for needle in needles:
        idx = text.find(needle, last + 1)
        testcase.assertGreater(idx, last, msg=f"{needle!r} not found after previous term")
        last = idx


class BuddySwitchUserSimulationSkillContractTests(unittest.TestCase):
    def test_description_triggers_only_target_locked_skill_use(self) -> None:
        description = _frontmatter_description(_text(SKILL_FILE))
        lowered = description.lower()

        for required in (
            "buddyswitch",
            "probe-only",
            "simulated-user",
            "feature memo",
            "target behavior",
            "existing evidence",
            "user path",
            "cleanup proof",
            "evidence-backed",
        ):
            with self.subTest(required=required):
                self.assertIn(required, lowered)

        for drift in ("means", "gate", "scenario matrix", "plan, run, audit, or extend"):
            with self.subTest(drift=drift):
                self.assertNotIn(drift, lowered)

    def test_main_file_states_the_two_locked_targets(self) -> None:
        skill = _text(SKILL_FILE)
        lowered = skill.lower()

        self.assertIn("memo, target behavior, or existing evidence", lowered)
        self.assertIn("infer", lowered)
        self.assertIn("smallest credible buddyswitch user path", lowered)
        self.assertIn("cleanup proof", lowered)
        self.assertIn("stability conclusion", lowered)
        self.assertIn("interrupt only", lowered)
        self.assertIn("real risk", lowered)
        self.assertIn("semantic ambiguity", lowered)

    def test_run_requests_must_attempt_user_path_before_reporting(self) -> None:
        skill = _text(SKILL_FILE)
        run_section = _section(skill, "## Mandatory User Path", "\n## Minimal Evidence")

        self.assertRegex(run_section.lower(), r"verify|test|prove|run")
        self.assertIn("or record a concrete blocker", run_section.lower())
        _assert_order(
            self,
            run_section,
            "infer effect",
            "choose one user surface",
            "create actor or identify explicit target",
            "capture baseline status",
            "perform user entry action",
            "observe effect",
            "capture state/log/browser evidence",
            "clean up",
            "report bounded claim",
        )
        _assert_order(
            self,
            run_section,
            "./buddyswitch-codex instance start --role <role> --json",
            "./buddyswitch-codex instance status <actor-id> --json",
            "./buddyswitch-codex instance input <actor-id> --text",
            "./buddyswitch-codex instance status <actor-id> --json",
            "./buddyswitch-codex instance stop <actor-id> --json",
            "./buddyswitch-codex instance delete <actor-id> --yes --json",
        )

    def test_browser_claim_requires_actor_facing_page_evidence(self) -> None:
        skill = _text(SKILL_FILE)
        browser = _section(skill, "## Browser And Cockpit Claims", "\n## Minimal Evidence")
        lowered = browser.lower()

        self.assertIn("actor/resource id", lowered)
        self.assertIn("actor-facing browser/cockpit action", lowered)
        self.assertIn("url/page/target/screenshot evidence", lowered)
        self.assertIn("state or log evidence", lowered)
        self.assertIn("cleanup proof", lowered)
        self.assertRegex(lowered, r"missing.*partial|downgrade")

    def test_minimal_evidence_checklist_replaces_large_evidence_framework(self) -> None:
        evidence = _section(_text(SKILL_FILE), "## Minimal Evidence", "\n## Claim Rule")
        lowered = evidence.lower()

        for required in (
            "target effect",
            "primary user surface",
            "actor/resource id",
            "baseline status",
            "user entry action",
            "observed product effect",
            "state/log/browser evidence",
            "cleanup result",
            "probe-only confirmation",
            "claim limit",
            "remaining risk",
        ):
            with self.subTest(required=required):
                self.assertIn(required, lowered)

        self.assertIn("user-path proof is incomplete", lowered)

    def test_claim_rule_is_simple_and_blocks_fake_static_overclaiming(self) -> None:
        claim = _section(_text(SKILL_FILE), "## Claim Rule", "\n## Report Format")
        lowered = claim.lower()

        for result in ("PASS", "PARTIAL", "FAIL", "BLOCKED"):
            with self.subTest(result=result):
                self.assertIn(f"`{result}`", claim)

        self.assertNotIn("FULL PASS", claim)
        self.assertNotIn("CONTROL-PLANE PASS", claim)
        self.assertNotIn("AUDIT ONLY", claim)
        self.assertIn("fake/control-plane/static-only", lowered)
        self.assertIn("not user-path proof", lowered)

    def test_probe_only_and_risk_interruptions_stay_inline(self) -> None:
        skill = _text(SKILL_FILE)
        lowered = skill.lower()

        self.assertIn("## Probe-Only Boundary", skill)
        self.assertIn("## Interrupt Only For Risk", skill)
        self.assertIn("source edits are forbidden", lowered)
        self.assertIn("run live codex", lowered)
        self.assertIn("signed-in chrome", lowered)
        self.assertIn("preserve actors", lowered)
        self.assertIn("delete or mutate user data", lowered)
        self.assertIn("material product meaning", lowered)

    def test_old_abstraction_files_are_removed_not_preserved_as_second_route(self) -> None:
        for path in OLD_ABSTRACTION_FILES:
            with self.subTest(path=str(path.relative_to(ROOT))):
                self.assertFalse(path.exists(), msg=f"{path} should be deleted")

    def test_reference_routing_only_keeps_target_support_references(self) -> None:
        skill = _text(SKILL_FILE)

        self.assertIn("references/memo-to-goals.md", skill)
        self.assertIn("references/buddy-runtime-surfaces.md", skill)

        for forbidden in (
            "references/invocation-and-pairing.md",
            "references/simulation-means.md",
            "references/gate-levels.md",
            "references/scenario-matrix.md",
            "references/evidence-schema.md",
            "scripts/init_simulation_evidence.py",
            "scripts/summarize_simulation_evidence.py",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, skill)

    def test_main_file_mentions_user_path_before_drift_terms(self) -> None:
        skill = _text(SKILL_FILE)
        user_path_idx = skill.find("## Mandatory User Path")
        self.assertGreaterEqual(user_path_idx, 0)

        for drift in (
            "means family",
            "required gate",
            "G0",
            "G1",
            "G2",
            "G3",
            "G4",
            "scenario matrix",
            "bounded sub-agents by default",
            "stress-recovery",
        ):
            with self.subTest(drift=drift):
                self.assertNotIn(drift, skill)

    def test_openai_metadata_matches_low_burden_target(self) -> None:
        metadata = _text(OPENAI_YAML)
        lowered = metadata.lower()

        self.assertIn("buddyswitch", lowered)
        self.assertIn("memo", lowered)
        self.assertIn("target behavior", lowered)
        self.assertIn("existing evidence", lowered)
        self.assertIn("user path", lowered)
        self.assertIn("cleanup proof", lowered)
        self.assertIn("evidence-backed", lowered)
        self.assertNotIn("means", lowered)
        self.assertNotIn("gates", lowered)


if __name__ == "__main__":
    unittest.main()
