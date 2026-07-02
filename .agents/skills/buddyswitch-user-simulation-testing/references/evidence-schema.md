# Evidence Schema

Use this structure for every simulation evidence directory.

## Table Of Contents

- [`summary.json`](#summaryjson)
- [Command Record](#command-record)
- [Mandatory Assertions](#mandatory-assertions)
- [Log Scan](#log-scan)
- [Cleanup Proof](#cleanup-proof)
- [Process Record Proof](#process-record-proof)
- [Strategy Decision Proof](#strategy-decision-proof)
- [Probe-Only Proof](#probe-only-proof)
- [Sub-Agent Proof](#sub-agent-proof)
- [Means Proof](#means-proof)

```text
evidence-YYYY-MM-DD[-label]/
  process/
    00-user-requirements.md
    01-memo-analysis.md
    02-simulation-checkpoint.md
  strategy/
    00-strategy-decision.md
  plan.md
  summary.json
  scripts/
    <temporary-probe-script>
  subagents/
    <name>/
      summary.md
      commands/
      snapshots/
      logs/
      scripts/
  commands/
    001-<name>.json
  snapshots/
    <name>-instance.json
    <name>-status.json
    <name>-app-server-state.json
    <name>-calls.jsonl
  logs/
    <actor>-app-server.log
    <actor>-daemon.log
    <actor>-runtime-broker.log
    central-daemon.log
  cleanup/
    actors.json
    worktrees.txt
    processes.jsonl
    residue-check.json
```

## `summary.json`

Required fields:

```json
{
  "schema_version": 1,
  "feature_memo": "docs/memo/example.md",
  "target_claim": "string",
  "confirmed_effects": [
    {
      "priority": "P0 | P1 | P2",
      "effect": "string",
      "source": "memo section or user confirmation"
    }
  ],
  "user_requirements": {
    "records_root": "string",
    "mode": "Design | Run | Audit | Extend",
    "source_edits": "allowed | forbidden",
    "cleanup": "required | preserve-with-reason",
    "constraints": ["string"]
  },
  "probe_only": {
    "source_edits": "forbidden",
    "allowed_write_roots": ["string"],
    "temp_scripts": ["scripts/<name>.py"],
    "source_unchanged_evidence": ["relative/path"]
  },
  "strategy_decision": {
    "required_means": ["scripted-invocation"],
    "required_gates": ["G1"],
    "adapters": ["CLI"],
    "subagent_plan": "none | planned | used | unavailable",
    "downgrade_rules": ["string"],
    "evidence": ["strategy/00-strategy-decision.md"]
  },
  "confirmations": {
    "checkpoint_recorded": true,
    "confirmed_by": "explicit_user_reply | stated_default_no_blocker | user_requested_run",
    "risk_confirmation_required": false,
    "risk_confirmed": true,
    "evidence": ["process/02-simulation-checkpoint.md"]
  },
  "claim_result": "FULL PASS | PARTIAL PASS | FAIL | BLOCKED",
  "codex_surface": "fake | live | mixed",
  "means": [
    {
      "family": "visible-operation | scripted-invocation | state-log-audit | stress-recovery-drive | live-dependency-smoke | static-residue-audit",
      "adapter": "Playwright/browser MCP | Chrome DevTools MCP | Desktop @Chrome | CLI | HTTP API | IM message script | Track comment script | fake Codex | live Codex | other",
      "required": true,
      "status": "pass | fail | blocked | skipped",
      "evidence": ["relative/path"]
    }
  ],
  "subagents": [
    {
      "name": "web-side-lifecycle",
      "purpose": "string",
      "status": "pass | fail | blocked | skipped | not_available",
      "records_root": "subagents/web-side-lifecycle",
      "source_edits": false,
      "evidence": ["subagents/web-side-lifecycle/summary.md"]
    }
  ],
  "claim_downgrades": [
    {
      "claim": "string",
      "reason": "string",
      "missing_gate_or_means": "string"
    }
  ],
  "started_at": "ISO-8601 string",
  "finished_at": "ISO-8601 string",
  "gates": [
    {
      "id": "G1",
      "name": "Fake Product Simulation",
      "required": true,
      "run": true,
      "status": "pass | fail | blocked | skipped",
      "evidence": ["relative/path"]
    }
  ],
  "actors": [
    {
      "role": "test",
      "actor_id": "act-test-example",
      "status": "deleted | stopped | active | unknown"
    }
  ],
  "assertions": [
    {
      "id": "no-thread-turns-list",
      "status": "pass | fail | blocked | skipped",
      "evidence": ["relative/path"],
      "message": "string"
    }
  ],
  "commands": {
    "count": 0,
    "failed_unexpected": 0
  },
  "logs": {
    "scanned": true,
    "unexpected_errors": []
  },
  "cleanup": {
    "attempted": true,
    "passed": true,
    "evidence": ["relative/path"]
  },
  "remaining_risks": ["string"]
}
```

## Command Record

Each command JSON must include:

```json
{
  "index": 1,
  "name": "start-test",
  "argv": ["./buddyswitch-codex", "instance", "start", "--role", "test", "--json"],
  "cwd": "/repo",
  "env": {
    "HOME": "/tmp/isolated-home",
    "CODEX_HOME": "/tmp/isolated-codex-home",
    "BUDDYSWITCH_SHARED_ROOT": "/tmp/shared-root",
    "PATH_note": "fake codex first | real codex"
  },
  "returncode": 0,
  "expected_returncode": 0,
  "stdout": "",
  "stderr": "",
  "duration_seconds": 0.0,
  "parsed_json": {}
}
```

Do not store secrets in `env`. Redact auth tokens, API keys, cookies, and full credential files.

## Mandatory Assertions

Use assertion ids consistently:

- `status-healthy`
- `task-sys-side-processing`
- `side-lease-created`
- `side-send-same-target`
- `side-close-unregistered`
- `stale-side-rejected`
- `cross-actor-rejected`
- `no-thread-turns-list`
- `interrupt-failure-unregisters`
- `web-route-covered`
- `im-wake-covered`
- `track-comment-wake-covered`
- `stop-resume-semantics-covered`
- `high-frequency-covered`
- `live-codex-smoke-covered`
- `strategy-decision-recorded`
- `probe-only-source-unchanged`
- `subagent-evidence-merged`
- `cleanup-passed`

## Log Scan

Scan relevant logs for:

```text
Traceback|ERROR|Exception|refusing|unavailable|failed
```

Expected failures must be named in `assertions`; unexpected log matches fail the relevant gate until explained.

## Cleanup Proof

Required cleanup evidence:

- stop/delete command records for each actor;
- `instance list --json` or equivalent actor list when available;
- run root removed or intentionally preserved with reason;
- git worktree residue check;
- process registry check for fake/live child processes;
- no open side lease for deleted actors.

## Process Record Proof

The `process/` files are required for any evidence-backed pass or audit claim:

- `00-user-requirements.md`: feature memo path or pasted source, mode, records root, live/fake policy, source-edit policy, cleanup policy, time/cost limits, preserved actor/data requests.
- `01-memo-analysis.md`: extracted product effects, out-of-scope items, source memo sections, and any structural challenge.
- `02-simulation-checkpoint.md`: one correction checkpoint containing inferred effects, selected means/gates, records path, skipped claims, and whether it was confirmed by `explicit_user_reply`, `stated_default_no_blocker`, or `user_requested_run`.

If risk confirmation was required, `summary.json.confirmations.risk_confirmed` must be `true` before any pass result.

## Strategy Decision Proof

The `strategy/00-strategy-decision.md` file is required for any evidence-backed pass or audit claim. It must state:

- required means families inferred from the target effects;
- required gates and why;
- selected adapters under each means family;
- sub-agent plan or reason sub-agents were skipped/unavailable;
- claims that will be downgraded if a means family or gate cannot run.

## Probe-Only Proof

A run must prove it stayed probe-only:

- `summary.json.probe_only.source_edits` is `forbidden`;
- temporary scripts are stored only under `scripts/` or `subagents/<name>/scripts/`;
- no product source, checked-in test, role guidance, runtime contract, or runtime object file was modified by the simulation;
- if `git status --short` changed outside the records root, the run is `BLOCKED` or `FAIL` until explained as pre-existing/user-owned.

The recommended assertion id is `probe-only-source-unchanged`.

## Sub-Agent Proof

When sub-agents are used, each sub-agent must write a compact summary under `subagents/<name>/summary.md` and list command/evidence paths it produced. The main summary must merge every sub-agent status. If sub-agent tooling was planned but unavailable, record a `claim_downgrades` entry with `missing_gate_or_means: "subagent_not_available"` and continue sequentially where possible.

## Means Proof

For any `FULL PASS` or `PARTIAL PASS`, `summary.json.means` must contain at least one top-level means family. Use adapter names only inside each family record. Do not place Web API, CLI, IM wake, Track wake, Chrome DevTools MCP, Playwright, or fake Codex as top-level families.
