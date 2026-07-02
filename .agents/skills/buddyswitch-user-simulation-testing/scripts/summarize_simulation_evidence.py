#!/usr/bin/env python3
"""Validate and summarize BuddySwitch user simulation evidence."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


VALID_RESULTS = {"FULL PASS", "PARTIAL PASS", "FAIL", "BLOCKED"}
VALID_MEANS_FAMILIES = {
    "visible-operation",
    "scripted-invocation",
    "state-log-audit",
    "stress-recovery-drive",
    "live-dependency-smoke",
    "static-residue-audit",
}
REQUIRED_PROCESS_FILES = (
    "process/00-user-requirements.md",
    "process/01-memo-analysis.md",
    "process/02-simulation-checkpoint.md",
)
REQUIRED_STRATEGY_FILES = (
    "strategy/00-strategy-decision.md",
)
VALID_CONFIRMED_BY = {"explicit_user_reply", "stated_default_no_blocker", "user_requested_run"}


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _command_records(commands_dir: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted(commands_dir.glob("*.json")):
        try:
            payload = _load_json(path)
        except Exception as exc:
            records.append({"path": str(path), "invalid": str(exc)})
            continue
        payload["path"] = str(path)
        records.append(payload)
    return records


def _unexpected_command_failures(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for record in records:
        if "invalid" in record:
            failures.append(record)
            continue
        expected = record.get("expected_returncode")
        actual = record.get("returncode")
        if expected is not None and actual != expected:
            failures.append(
                {
                    "path": record.get("path"),
                    "name": record.get("name"),
                    "expected_returncode": expected,
                    "returncode": actual,
                }
            )
    return failures


def _gate_statuses(summary: dict[str, Any]) -> list[dict[str, Any]]:
    gates = summary.get("gates")
    return [gate for gate in gates if isinstance(gate, dict)] if isinstance(gates, list) else []


def _means_records(summary: dict[str, Any]) -> list[dict[str, Any]]:
    means = summary.get("means")
    return [item for item in means if isinstance(item, dict)] if isinstance(means, list) else []


def _assertion_ids(summary: dict[str, Any]) -> set[str]:
    assertions = summary.get("assertions")
    if not isinstance(assertions, list):
        return set()
    return {item.get("id") for item in assertions if isinstance(item, dict) and isinstance(item.get("id"), str)}


def _subagent_records(summary: dict[str, Any]) -> list[dict[str, Any]]:
    subagents = summary.get("subagents")
    return [item for item in subagents if isinstance(item, dict)] if isinstance(subagents, list) else []


def _required_gate_failures(gates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    failed: list[dict[str, Any]] = []
    for gate in gates:
        if gate.get("required") is True and gate.get("status") not in {"pass"}:
            failed.append(gate)
    return failed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence_root", help="Evidence directory containing summary.json.")
    parser.add_argument("--write", action="store_true", help="Update command counts and finished_at in summary.json.")
    args = parser.parse_args()

    root = Path(args.evidence_root).expanduser()
    summary_path = root / "summary.json"
    summary = _load_json(summary_path)
    commands = _command_records(root / "commands")
    unexpected = _unexpected_command_failures(commands)
    gates = _gate_statuses(summary)
    means = _means_records(summary)
    assertion_ids = _assertion_ids(summary)
    subagents = _subagent_records(summary)
    required_gate_failures = _required_gate_failures(gates)

    issues: list[str] = []
    result = summary.get("claim_result")
    if result not in VALID_RESULTS:
        issues.append("claim_result must be one of FULL PASS, PARTIAL PASS, FAIL, BLOCKED")
    invalid_means = [
        item
        for item in means
        if item.get("family") not in VALID_MEANS_FAMILIES
    ]
    if invalid_means:
        issues.append(
            "summary.means contains invalid family values; use "
            + ", ".join(sorted(VALID_MEANS_FAMILIES))
        )
    if result in {"FULL PASS", "PARTIAL PASS"} and not means:
        issues.append("pass result requires summary.means with at least one means family and adapter")
    if not (root / "plan.md").exists():
        issues.append("missing plan.md")
    missing_process = [name for name in REQUIRED_PROCESS_FILES if not (root / name).exists()]
    if missing_process and result in {"FULL PASS", "PARTIAL PASS"}:
        issues.append(f"pass result requires process records: {', '.join(missing_process)}")
    missing_strategy = [name for name in REQUIRED_STRATEGY_FILES if not (root / name).exists()]
    strategy_decision = summary.get("strategy_decision") if isinstance(summary.get("strategy_decision"), dict) else {}
    if result in {"FULL PASS", "PARTIAL PASS"}:
        if missing_strategy:
            issues.append(f"pass result requires strategy records: {', '.join(missing_strategy)}")
        if not strategy_decision.get("required_means"):
            issues.append("pass result requires strategy_decision.required_means")
        if not strategy_decision.get("required_gates"):
            issues.append("pass result requires strategy_decision.required_gates")
    confirmations = summary.get("confirmations") if isinstance(summary.get("confirmations"), dict) else {}
    if result in {"FULL PASS", "PARTIAL PASS"}:
        if confirmations.get("checkpoint_recorded") is not True:
            issues.append("pass result requires confirmations.checkpoint_recorded=true")
        if confirmations.get("confirmed_by") not in VALID_CONFIRMED_BY:
            issues.append(
                "pass result requires confirmations.confirmed_by to be one of "
                + ", ".join(sorted(VALID_CONFIRMED_BY))
            )
        if confirmations.get("risk_confirmation_required") is True and confirmations.get("risk_confirmed") is not True:
            issues.append("pass result requires risk_confirmed=true when risk confirmation was required")
    if not commands:
        issues.append("no command evidence found")
    if unexpected:
        issues.append("unexpected command failures present")
    cleanup = summary.get("cleanup") if isinstance(summary.get("cleanup"), dict) else {}
    if cleanup.get("passed") is not True and result in {"FULL PASS", "PARTIAL PASS"}:
        issues.append("pass result requires cleanup.passed=true")
    if summary.get("codex_surface") == "fake" and result == "FULL PASS":
        live_required = any(gate.get("id") == "G4" and gate.get("required") is True for gate in gates)
        if live_required:
            issues.append("fake codex surface cannot FULL PASS when G4 live gate is required")
    if required_gate_failures and result == "FULL PASS":
        issues.append("FULL PASS cannot include required gates that did not pass")
    probe_only = summary.get("probe_only") if isinstance(summary.get("probe_only"), dict) else {}
    if result in {"FULL PASS", "PARTIAL PASS"}:
        if probe_only.get("source_edits") != "forbidden":
            issues.append("pass result requires probe_only.source_edits=forbidden")
        if "probe-only-source-unchanged" not in assertion_ids:
            issues.append("pass result requires probe-only-source-unchanged assertion")
    claim_downgrades = summary.get("claim_downgrades")
    if result == "FULL PASS" and isinstance(claim_downgrades, list) and claim_downgrades:
        issues.append("FULL PASS cannot include claim_downgrades")
    for subagent in subagents:
        if subagent.get("status") in {"pass", "fail", "blocked"}:
            if not subagent.get("records_root"):
                issues.append(f"subagent {subagent.get('name', '<unknown>')} requires records_root")
            if subagent.get("source_edits") is not False:
                issues.append(f"subagent {subagent.get('name', '<unknown>')} must report source_edits=false")
            evidence = subagent.get("evidence")
            if not isinstance(evidence, list) or not evidence:
                issues.append(f"subagent {subagent.get('name', '<unknown>')} requires evidence")
    if not summary.get("remaining_risks") and result == "PARTIAL PASS":
        issues.append("PARTIAL PASS requires remaining_risks")

    if args.write:
        summary.setdefault("commands", {})
        if isinstance(summary["commands"], dict):
            summary["commands"]["count"] = len(commands)
            summary["commands"]["failed_unexpected"] = len(unexpected)
        summary["finished_at"] = _now()
        summary_path.write_text(json.dumps(summary, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")

    output = {
        "ok": not issues,
        "evidence_root": str(root),
        "commands": len(commands),
        "means": len(means),
        "unexpected_command_failures": unexpected,
        "required_gate_failures": required_gate_failures,
        "issues": issues,
    }
    print(json.dumps(output, ensure_ascii=True, indent=2))
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
