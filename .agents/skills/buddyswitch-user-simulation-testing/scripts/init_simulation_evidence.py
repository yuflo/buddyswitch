#!/usr/bin/env python3
"""Initialize a BuddySwitch user simulation evidence directory."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, help="Evidence directory to create.")
    parser.add_argument("--target-claim", required=True, help="Behavior/stability claim under test.")
    parser.add_argument("--feature-memo", default=None, help="Feature memo path or identifier.")
    parser.add_argument("--mode", choices=("Design", "Run", "Audit", "Extend"), default="Run", help="Simulation mode.")
    parser.add_argument(
        "--codex-surface",
        choices=("fake", "live", "mixed"),
        required=True,
        help="Codex app-server surface used by the planned run.",
    )
    args = parser.parse_args()

    root = Path(args.root).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    for child in ("process", "strategy", "scripts", "subagents", "commands", "snapshots", "logs", "cleanup"):
        (root / child).mkdir(exist_ok=True)

    process_files = {
        "00-user-requirements.md": (
            "# User Requirements\n\n"
            f"Created: {_now()}\n\n"
            f"- Feature memo: {args.feature_memo or 'not provided'}\n"
            f"- Mode: {args.mode}\n"
            f"- Records root: {root}\n"
            f"- Codex surface: {args.codex_surface}\n"
            "- Source edits: forbidden\n"
            "- Temporary probe scripts: records-root/scripts/ only\n"
            "- Sub-agent outputs: records-root/subagents/ only\n"
            "- Cleanup: required unless explicitly overridden\n"
            "- Other constraints: not recorded\n"
        ),
        "01-memo-analysis.md": (
            "# Memo Analysis\n\n"
            "## Extracted Effects\n\n"
            "| Priority | Effect | Source | Notes |\n"
            "| --- | --- | --- | --- |\n\n"
            "## Not In Scope\n\n"
            "- Not recorded yet.\n\n"
            "## Structural Challenges\n\n"
            "- Not recorded yet.\n"
        ),
        "02-simulation-checkpoint.md": (
            "# Simulation Checkpoint\n\n"
            "Status: recorded-default\n\n"
            "Confirmed by: stated_default_no_blocker\n\n"
            "## I Will Prove\n\n"
            "- Not recorded yet.\n\n"
            "## I Will Use\n\n"
            "- Means: not recorded yet.\n"
            "- Gates: not recorded yet.\n"
            "- Sub-agents: not recorded yet.\n"
            "- Records: not recorded yet.\n\n"
            "## I Will Not Claim\n\n"
            "- Not recorded yet.\n\n"
            "## I Will Write Only Under\n\n"
            f"- Records: {root}\n\n"
            "Record whether the run continued by explicit user reply, stated default, or user-requested run.\n"
        ),
    }
    process_root = root / "process"
    for name, text in process_files.items():
        path = process_root / name
        if not path.exists():
            path.write_text(text, encoding="utf-8")

    strategy = root / "strategy" / "00-strategy-decision.md"
    if not strategy.exists():
        strategy.write_text(
            "\n".join(
                (
                    "# Strategy Decision",
                    "",
                    f"Created: {_now()}",
                    "",
                    "## Required Means",
                    "",
                    "| Family | Required | Effect Source | Adapter(s) | Downgrade If Skipped |",
                    "| --- | --- | --- | --- | --- |",
                    "",
                    "## Required Gates",
                    "",
                    "| Gate | Required | Reason | Planned Evidence |",
                    "| --- | --- | --- | --- |",
                    "",
                    "## Sub-Agent Plan",
                    "",
                    "| Workstream | Use Sub-Agent | Records Path | Isolation Rule |",
                    "| --- | --- | --- | --- |",
                    "",
                    "## Probe-Only Boundary",
                    "",
                    f"- All writes stay under: {root}",
                    "- Temporary scripts stay under scripts/ or subagents/<name>/scripts/.",
                    "- Product source, checked-in tests, role guidance, runtime contracts, and runtime objects are not edited.",
                    "",
                    "## Claim Downgrades",
                    "",
                    "| Claim | Missing Gate / Means | Reason |",
                    "| --- | --- | --- |",
                    "",
                )
            ),
            encoding="utf-8",
        )

    plan = root / "plan.md"
    if not plan.exists():
        plan.write_text(
            "\n".join(
                (
                    "# BuddySwitch User Simulation Plan",
                    "",
                    f"Created: {_now()}",
                    "",
                    "## Source Memo",
                    "",
                    args.feature_memo or "Not provided.",
                    "",
                    "## User Requirements",
                    "",
                    f"- Mode: {args.mode}",
                    f"- Records root: {root}",
                    f"- Codex surface: {args.codex_surface}",
                    "- Source edits: forbidden",
                    "- Temporary probe scripts: scripts/ only unless a sub-agent owns subagents/<name>/scripts/",
                    "- Cleanup: required unless explicitly overridden",
                    "",
                    "## Confirmed Effects",
                    "",
                    "| Priority | Effect | Source |",
                    "| --- | --- | --- |",
                    "",
                    "## Target Claim",
                    "",
                    args.target_claim,
                    "",
                    "## Strategy Decision",
                    "",
                    "See strategy/00-strategy-decision.md.",
                    "",
                    "## Means",
                    "",
                    "| Family | Adapter | Required | Evidence |",
                    "| --- | --- | --- | --- |",
                    "",
                    "## Required Gates",
                    "",
                    "| Gate | Required | Planned | Reason |",
                    "| --- | --- | --- | --- |",
                    "| G0 Contract |  |  |  |",
                    "| G1 Fake Product Simulation |  |  |  |",
                    "| G2 Entry Surface Simulation |  |  |  |",
                    "| G3 Stress And Recovery |  |  |  |",
                    "| G4 Live Codex Smoke |  |  |  |",
                    "",
                    "## Scenarios",
                    "",
                    "| Scenario | Actor(s) | Entry surface / adapter | Commands/API | Expected assertions |",
                    "| --- | --- | --- | --- | --- |",
                    "",
                    "## Sub-Agent Plan",
                    "",
                    "| Workstream | Records Path | Status | Notes |",
                    "| --- | --- | --- | --- |",
                    "",
                    "## Cleanup Plan",
                    "",
                    "- Stop/delete every actor created by this run.",
                    "- Check run root, worktrees, process registry, sockets, and side leases.",
                    "",
                )
            ),
            encoding="utf-8",
        )

    summary = root / "summary.json"
    if not summary.exists():
        summary.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "feature_memo": args.feature_memo,
                    "target_claim": args.target_claim,
                    "confirmed_effects": [],
                    "user_requirements": {
                        "records_root": str(root),
                        "mode": args.mode,
                        "source_edits": "forbidden",
                        "cleanup": "required",
                        "constraints": [],
                    },
                    "probe_only": {
                        "source_edits": "forbidden",
                        "allowed_write_roots": [str(root)],
                        "temp_scripts": [],
                        "source_unchanged_evidence": [],
                    },
                    "strategy_decision": {
                        "required_means": [],
                        "required_gates": [],
                        "adapters": [],
                        "subagent_plan": "none",
                        "downgrade_rules": [],
                        "evidence": ["strategy/00-strategy-decision.md"],
                    },
                    "confirmations": {
                        "checkpoint_recorded": False,
                        "confirmed_by": None,
                        "risk_confirmation_required": False,
                        "risk_confirmed": True,
                        "evidence": ["process/02-simulation-checkpoint.md"],
                    },
                    "claim_result": "BLOCKED",
                    "codex_surface": args.codex_surface,
                    "means": [],
                    "subagents": [],
                    "claim_downgrades": [],
                    "started_at": _now(),
                    "finished_at": None,
                    "gates": [],
                    "actors": [],
                    "assertions": [],
                    "commands": {"count": 0, "failed_unexpected": 0},
                    "logs": {"scanned": False, "unexpected_errors": []},
                    "cleanup": {"attempted": False, "passed": False, "evidence": []},
                    "remaining_risks": [],
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    print(json.dumps({"ok": True, "evidence_root": str(root), "plan": str(plan), "summary": str(summary)}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
