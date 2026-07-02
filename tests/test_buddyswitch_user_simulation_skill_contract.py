#!/usr/bin/env python3
"""Contract tests for the BuddySwitch user simulation testing skill."""

from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / ".agents" / "skills" / "buddyswitch-user-simulation-testing"
SKILL_FILE = SKILL_ROOT / "SKILL.md"
REFERENCE_DIR = SKILL_ROOT / "references"
INVOCATION_REFERENCE = SKILL_ROOT / "references" / "invocation-and-pairing.md"
SIMULATION_MEANS_REFERENCE = SKILL_ROOT / "references" / "simulation-means.md"
GATE_LEVELS_REFERENCE = SKILL_ROOT / "references" / "gate-levels.md"
SCENARIO_MATRIX_REFERENCE = SKILL_ROOT / "references" / "scenario-matrix.md"
OPENAI_YAML = SKILL_ROOT / "agents" / "openai.yaml"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _frontmatter_description(skill_text: str) -> str:
    match = re.match(r"---\n(?P<body>.*?)\n---\n", skill_text, flags=re.DOTALL)
    if not match:
        raise AssertionError("SKILL.md is missing YAML frontmatter")
    for line in match.group("body").splitlines():
        if line.startswith("description:"):
            return line.removeprefix("description:").strip()
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


class BuddySwitchUserSimulationSkillContractTests(unittest.TestCase):
    def test_frontmatter_description_is_effect_preserving(self) -> None:
        description = _frontmatter_description(_text(SKILL_FILE))
        lowered = description.lower()

        for required in (
            "buddyswitch",
            "probe-only",
            "simulated-user",
            "feature memo",
            "target behavior",
            "existing evidence",
            "claim downgrade",
            "plan",
            "run",
            "audit",
            "extend",
        ):
            with self.subTest(required=required):
                self.assertIn(required, lowered)
        self.assertNotIn("through codex cli", lowered)

    def test_main_skill_keeps_non_bypassable_boundaries_inline(self) -> None:
        skill = _text(SKILL_FILE)
        lowered = skill.lower()

        self.assertIn("## Probe-Only Boundary", skill)
        self.assertIn("## Risk Confirmation", skill)
        self.assertIn("source edits", lowered)
        self.assertIn("run live codex", lowered)
        self.assertIn("signed-in chrome", lowered)
        self.assertIn("preserve actors", lowered)
        self.assertIn("delete or mutate user data", lowered)

    def test_sop_steps_have_checkable_completion_criteria(self) -> None:
        sop = _section(_text(SKILL_FILE), "## SOP", "\n## Operating Modes")
        steps = re.findall(r"(?m)^\d+\. .+", sop)
        self.assertGreaterEqual(len(steps), 8)

        missing_done = [step for step in steps if "Done when:" not in step]
        self.assertEqual([], missing_done)

    def test_invocation_reference_is_single_source_for_defaults_and_checkpoint(self) -> None:
        skill = _text(SKILL_FILE)
        invocation = _text(INVOCATION_REFERENCE)

        self.assertIn("references/invocation-and-pairing.md", skill)
        self.assertRegex(skill, r"(?is)mode.*defaults.*checkpoint|checkpoint.*defaults.*mode")
        self.assertNotIn("## Minimum Input", skill)
        self.assertNotIn("## Defaults", skill)
        self.assertNotIn("Optional overrides:", skill)
        self.assertNotIn("Best input:", skill)
        self.assertNotIn("## Simulation Checkpoint\nI will prove:", skill)

        self.assertIn("## Defaults When Input Is Sparse", invocation)
        self.assertIn("## One Checkpoint", invocation)
        self.assertIn("## Prompt Templates", invocation)
        self.assertIn("Continue without waiting", invocation)
        self.assertIn("Risk Confirmation", invocation)

    def test_skipped_required_means_or_gate_blocks_full_pass(self) -> None:
        skill = _text(SKILL_FILE).lower()
        means = _text(SIMULATION_MEANS_REFERENCE).lower()
        gates = _text(GATE_LEVELS_REFERENCE).lower()

        self.assertIn("required means", skill)
        self.assertIn("required gate", skill)
        self.assertRegex(skill, r"(cannot|never) (be |report )?`?full pass`?")
        self.assertIn("downgrade", skill)

        self.assertIn("target-relevant", means)
        self.assertIn("required means", means)
        self.assertIn("downgrade", means)
        self.assertRegex(means, r"(cannot|never) (be |report )?`?full pass`?")

        self.assertIn("required gate", gates)
        self.assertIn("downgrade", gates)
        self.assertRegex(gates, r"(cannot|never) (be |report )?`?full pass`?")

    def test_report_format_and_unacceptable_conclusions_stay_inline(self) -> None:
        skill = _text(SKILL_FILE)
        report = _section(skill, "## Report Format", "\n## Unacceptable Conclusions")
        unacceptable = _section(skill, "## Unacceptable Conclusions")

        for heading in (
            "## Result",
            "## Effects Tested",
            "## Claim Proven",
            "## Means Used",
            "## Strategy",
            "## Subagents",
            "## Gates",
            "## Evidence",
            "## Cleanup",
            "## Remaining Risk",
        ):
            with self.subTest(heading=heading):
                self.assertIn(heading, report)

        lowered = unacceptable.lower()
        self.assertIn("fake codex", lowered)
        self.assertIn("live codex", lowered)
        self.assertIn("unit tests passed", lowered)
        self.assertIn("multi-entry stable", lowered)
        self.assertIn("browser user behavior covered", lowered)

    def test_openai_metadata_matches_phase_1_trigger_boundary(self) -> None:
        metadata = _text(OPENAI_YAML)

        short_description_match = re.search(r'^\s*short_description:\s*"([^"]+)"$', metadata, re.MULTILINE)
        self.assertIsNotNone(short_description_match)
        short_description = short_description_match.group(1)
        self.assertGreaterEqual(len(short_description), 25)
        self.assertLessEqual(len(short_description), 64)

        default_prompt_match = re.search(r'^\s*default_prompt:\s*"([^"]+)"$', metadata, re.MULTILINE)
        self.assertIsNotNone(default_prompt_match)
        default_prompt = default_prompt_match.group(1)
        lowered = default_prompt.lower()
        self.assertIn("$buddyswitch-user-simulation-testing", default_prompt)
        self.assertIn("probe-only", lowered)
        self.assertIn("simulated-user", lowered)
        self.assertIn("evidence-backed", lowered)
        self.assertRegex(lowered, r"claim (limit|downgrade)")

    def test_browser_adapter_details_are_routed_by_strong_pointer(self) -> None:
        skill = _text(SKILL_FILE)
        means = _text(SIMULATION_MEANS_REFERENCE)

        self.assertIn("Browser tools are adapters, not top-level means", skill)
        self.assertIn("references/simulation-means.md", skill)
        self.assertIn("Browser Adapter Notes", skill)
        for term in ("browser", "Chrome", "CDP", "Playwright", "profile", "extension", "Desktop", "Computer Use"):
            with self.subTest(term=term):
                self.assertRegex(skill, rf"(?is)Browser Adapter Notes.*{re.escape(term)}|{re.escape(term)}.*Browser Adapter Notes")

        for detail in (
            "Do not spend simulation time reinstalling Chrome/browser plugins",
            "Browser is not available: extension",
            "agent.browsers.list()",
            "untrusted-code-signing-identity",
            "Screen Recording and Accessibility permissions",
        ):
            with self.subTest(detail=detail):
                self.assertNotIn(detail, skill)

        self.assertIn("## Browser Adapter Notes", means)
        self.assertIn("Do not loop on reinstalling Chrome/browser plugins", means)
        self.assertIn("Browser is not available: extension", means)
        self.assertIn("agent.browsers.list()", means)

    def test_subagent_details_are_routed_with_bounded_default(self) -> None:
        skill = _text(SKILL_FILE)
        scenario = _text(SCENARIO_MATRIX_REFERENCE)

        lowered_skill = skill.lower()
        self.assertIn("bounded sub-agents by default", lowered_skill)
        self.assertIn("main agent owns the final claim", lowered_skill)
        self.assertIn("subagents/<name>/", skill)
        self.assertIn("source-edit ban", lowered_skill)

        for split_detail in (
            "G2 has more than two independent surfaces",
            "Static residue audit can run in parallel",
            "Log/state review can run after a scenario",
            "Stress/recovery and failure-analysis probes",
        ):
            with self.subTest(split_detail=split_detail):
                self.assertNotIn(split_detail, skill)
                self.assertIn(split_detail, scenario)

        self.assertIn("## Sub-Agent Fit", scenario)
        self.assertIn("Web API/UI lifecycle", scenario)
        self.assertIn("IM wake", scenario)
        self.assertIn("Track comment wake", scenario)

    def test_long_references_have_table_of_contents(self) -> None:
        long_references: list[Path] = []
        for path in sorted(REFERENCE_DIR.glob("*.md")):
            lines = _text(path).splitlines()
            if len(lines) <= 100:
                continue
            long_references.append(path)
            top = "\n".join(lines[:30])
            with self.subTest(path=str(path.relative_to(ROOT))):
                self.assertIn("## Table Of Contents", top)
                self.assertRegex(top, r"- \[.+\]\(#.+\)")

        self.assertTrue(long_references)

    def test_main_reference_routing_uses_conditional_read_pointers(self) -> None:
        routing = _section(_text(SKILL_FILE), "## Reference Routing", "\n## Probe-Only Boundary")

        for reference in (
            "references/invocation-and-pairing.md",
            "references/memo-to-goals.md",
            "references/simulation-means.md",
            "references/gate-levels.md",
            "references/scenario-matrix.md",
            "references/evidence-schema.md",
            "references/buddy-runtime-surfaces.md",
        ):
            with self.subTest(reference=reference):
                self.assertIn(f"`{reference}`", routing)
                self.assertRegex(routing, rf"`{re.escape(reference)}`.*\b(first|when|before)\b")


if __name__ == "__main__":
    unittest.main()
