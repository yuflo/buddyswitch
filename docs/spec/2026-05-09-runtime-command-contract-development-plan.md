# Runtime Command Contract Development Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` or `superpowers:subagent-driven-development` before implementing this plan. Track progress with the checklist below.

**Goal:** Eliminate the launcher-managed buddy instance `prepare` approval popup by replacing the current ambiguous host-facing runtime invocation contract with one canonical executable contract.

**Outcome:** A user can type an ordinary request in any buddy instance, the host can run runtime preflight without asking for an approval caused by `scripts/turn_runtime.py prepare`, and AGENTS stays short, framework-level, and free of business-specific prompt rules.

**Architecture:** Keep `prepare -> skill work -> persist -> receipt` as the main path. Move executable runtime invocation details into the runtime contract and structured feedback. Keep buddy AGENTS as concise framework guidance that points to runtime-returned context instead of hardcoding fragile command details or payload recipes.

**Implementation style:** Direct replacement only. Do not add wrapper scripts, chmod-based compatibility, long-lived dual command paths, approval-prefix workarounds, or business-specific prompt examples.

---

## Working Directory

Run all work from:

```bash
cd /Users/chen/Dev/buddyswitch/.worktrees/dev0210
```

Do not edit the main checkout at `/Users/chen/Dev/buddyswitch`.

## Problem Statement

Current buddy AGENTS tell the host to run:

```bash
scripts/turn_runtime.py prepare "<request>"
```

But `scripts/turn_runtime.py` is tracked as `100644`, so direct execution fails with `permission denied`. Codex then surfaces the failure as a sandbox retry prompt. That makes a normal user request look like it needs extra authorization before the buddy can even start.

The problem is a runtime contract mismatch:

- The user request is ordinary text.
- `prepare` is supposed to run as an internal preflight step.
- The script is not executable as a bare shell command.
- The host-facing instruction currently names the non-executable form.
- The failure is presented as an approval problem even though the stable command is `python3 scripts/turn_runtime.py ...`.

## Confirmed Facts

- This is not caused by `projects/app` write permissions.
- This is not caused by buddy routing from user text.
- This is not caused by legacy `switch ...` command parsing.
- `dev0210` already accepts switch-prefixed user text as ordinary `request_text`.
- Current buddy AGENTS are mostly framework-level and not business-specific.
- The remaining drift is that AGENTS still carries an incorrect runtime CLI contract.
- The recently exposed failure likely became stable after `832262e`, which made `prepare` a more explicit first step.

## Residue Policy

This iteration must leave zero active residue of the old runtime command contract.

Definitions:

- **Active host-facing surface:** anything a running buddy host, launcher-managed instance, validator, runtime feedback path, or current developer runbook can use as present-tense guidance.
- **Replaced residue:** any active instruction, validation requirement, fixture, helper, wrapper, or doc wording that preserves bare `scripts/turn_runtime.py prepare` or bare `scripts/turn_runtime.py persist` as a valid current path.
- **Historical-only text:** bug history or memo material that describes the old command as a past failure and is not consumed by runtime, validators, launcher assets, or current runbooks.

Required cleanup rule:

- Active host-facing surfaces must have zero replaced residue.
- Historical-only text may remain only when clearly written as history and excluded from active contract checks.
- Every remaining old-command string found by search must be classified in a residue inventory as `deleted`, `rewritten`, or `historical-only retained`.
- No implementation task is complete until the residue inventory shows no `active retained` entry.

## Target Contract

There must be exactly one canonical host-facing runtime invocation form:

```bash
python3 scripts/turn_runtime.py prepare "<request>"
python3 scripts/turn_runtime.py persist --context <context> --result <result>
```

The contract must be available where the host actually needs it:

- `prepare.runtime_context` or an adjacent runtime-returned contract block must expose canonical command hints.
- Structured runtime errors must refer to canonical executable commands when command recovery is useful.
- AGENTS must remain short and framework-level, pointing to runtime context and structured feedback rather than expanding into a manual.
- Host-facing docs, validators, and tests must agree on the same canonical command.

## Non-Goals

- Do not make `scripts/turn_runtime.py` executable as the primary fix.
- Do not add a shell wrapper or alias as a compatibility layer.
- Do not teach Codex to approve failed `scripts/turn_runtime.py ...` commands.
- Do not add buddy-specific examples such as demo pages, landing pages, market research cases, or calendar products.
- Do not rework skill schemas, artifact semantics, or buddy capabilities unless required by the command contract.
- Do not change the `prepare -> skill work -> persist` lifecycle.
- Do not reintroduce text-driven buddy switching.

## File Map

Expected implementation touch points:

- `scripts/turn_runtime.py`: add or adjust runtime-returned command contract fields and structured command hints.
- `framework/contracts/prepare-turn-context.json`: update the prepare response contract if new fields are added.
- `framework/docs/turn-runtime-spec.md`: document the canonical command contract and host expectations.
- `tools/launcher/assets/buddies/*/AGENTS.md`: remove hardcoded bare runtime commands or replace them with references to the runtime contract.
- `scripts/runtime_agents.py`: update AGENTS validation and rendering rules so they enforce framework-level guidance without the bare command.
- `tests/test_turn_runtime.py`: verify prepare output exposes the canonical executable contract.
- `tests/test_runtime_agents.py`: verify buddy AGENTS remain concise and no longer instruct the host to bare-run the script.
- `tests/test_repo_consistency.py`: update any repository-wide command consistency checks.
- `tests/test_buddyswitch_launcher.py`: verify materialized launcher instances receive the updated AGENTS/runtime surface when needed.
- `README.md` or launcher docs if they expose the old host-facing command.

Adjust the exact file list after inspection, but do not broaden scope beyond the runtime command contract.

---

## Implementation Tasks

### Task 1: Lock The Public Contract

- [ ] Search all active host-facing surfaces for `scripts/turn_runtime.py prepare`, `scripts/turn_runtime.py persist`, and `python3 scripts/turn_runtime.py`.
- [ ] Classify each occurrence as active host contract, developer documentation, historical memo, test fixture, or irrelevant history.
- [ ] Record the active surfaces that must change before editing implementation.
- [ ] Confirm there is no remaining requirement for bare script execution.
- [ ] Start a residue inventory table with one row per old-command occurrence and planned disposition.

Expected active surfaces:

- Buddy AGENTS templates.
- Runtime docs.
- Runtime response or feedback strings.
- Validators that assert AGENTS contents.
- Tests that encode command strings.

Stop condition: if an active external contract requires bare execution for a real user path, escalate before continuing.

Residue inventory format:

| File | Occurrence | Classification | Disposition | Verification |
|---|---|---|---|---|
| `path/to/file` | `scripts/turn_runtime.py prepare` | active host contract | rewrite | updated test name |

### Task 2: Add Canonical Runtime Command Hints

- [ ] Define a compact runtime command contract shape in `prepare.runtime_context`.
- [ ] Include a prepare command hint with `python3 scripts/turn_runtime.py prepare "<request>"`.
- [ ] Include a persist command hint with `python3 scripts/turn_runtime.py persist --context <context> --result <result>`.
- [ ] Keep the fields descriptive enough for a host to act, but avoid long prompt prose.
- [ ] Update the prepare JSON contract so the new shape is validated.

Suggested shape:

```json
{
  "runtime_commands": {
    "prepare": "python3 scripts/turn_runtime.py prepare \"<request>\"",
    "persist": "python3 scripts/turn_runtime.py persist --context <context> --result <result>"
  }
}
```

Use a better field name if it fits the current contract style more naturally. Keep the meaning unchanged.

### Task 3: Update Structured Feedback

- [ ] Find runtime and broker errors that return command hints or allowed next actions.
- [ ] Replace bare `scripts/turn_runtime.py ...` references with canonical executable commands.
- [ ] When the error is not recoverable by a command, keep stop conditions concise.
- [ ] Ensure broker-unavailable feedback still tells the host to stop and report rather than bypass product mode.
- [ ] Avoid adding broad troubleshooting prose.

The expected behavior is that runtime failures point to the correct contract or to a clear stop condition. They must not imply that the user needs to grant extra permission for a non-executable command.

### Task 4: Refactor Buddy AGENTS Templates

- [ ] Update every `tools/launcher/assets/buddies/<buddy>/AGENTS.md`.
- [ ] Keep AGENTS as framework-level runtime guidance.
- [ ] Remove the bare command form from active instructions.
- [ ] Prefer wording that tells the host to run runtime preflight using the canonical runtime contract and then read `prepare.runtime_context`.
- [ ] Keep buddy-specific differences limited to capability boundaries already owned by the buddy, such as Dev write access or non-Dev read-only behavior.
- [ ] Do not add examples for specific user requests.

The AGENTS contract should tell the host what lifecycle it must follow, while runtime context tells it the executable details and capability boundary.

### Task 5: Update Validators And Repo Consistency Checks

- [ ] Update AGENTS validators so they no longer require the bare command string.
- [ ] Add a guard that active host-facing surfaces do not instruct bare `scripts/turn_runtime.py prepare` or bare `scripts/turn_runtime.py persist`.
- [ ] Add a guard that canonical command hints use `python3 scripts/turn_runtime.py`.
- [ ] Keep historical docs or memos out of active-surface checks unless the repo already checks them.
- [ ] Ensure the checks fail with messages that point to the contract violation, not to prompt style.
- [ ] Add or update tests so an `active retained` old-command residue fails verification.
- [ ] Make the active-surface scope explicit in the test or helper, so historical-only memos do not accidentally become contract inputs.

This task turns the architecture decision into a durable constraint.

### Task 6: Update Documentation

- [ ] Update `framework/docs/turn-runtime-spec.md` to describe the canonical command contract.
- [ ] Update any README or launcher doc that currently teaches the bare command as an active path.
- [ ] State that `prepare` is runtime preflight and does not execute user task work.
- [ ] State that actual task execution remains with host/skill after prepare.
- [ ] Keep docs short and operational.

### Task 7: Verify Existing Behavior Is Preserved

- [ ] Confirm ordinary user text is preserved as `request_text`.
- [ ] Confirm switch-prefixed ordinary text is still accepted and does not change active buddy.
- [ ] Confirm Dev can still write `projects/app` in the runtime boundary.
- [ ] Confirm non-Dev buddies remain read-only against `projects/app`.
- [ ] Confirm Market evidence and broker stop behavior are unchanged except for command hints.
- [ ] Confirm launcher materialization projects the updated AGENTS into product instances.

### Task 8: Remove Replaced Surfaces And Prove Zero Active Residue

- [ ] Remove stale host-facing references to the old bare command from active docs and tests.
- [ ] Delete obsolete helper constants or fixtures that only exist to preserve the bare form.
- [ ] Do not leave dual contract language such as "use either scripts/... or python3 scripts/...".
- [ ] Rewrite current developer docs that mention the old command as an active instruction.
- [ ] Leave historical memos intact only when they clearly describe the old command as past failure context.
- [ ] Complete the residue inventory with final dispositions for every old-command match.
- [ ] Confirm the final inventory has no `active retained`, `compatibility retained`, or `dual path retained` entry.

---

## Verification Commands

Run focused checks first:

```bash
python3 -m pytest tests/test_turn_runtime.py
python3 -m pytest tests/test_runtime_agents.py
python3 -m pytest tests/test_repo_consistency.py
```

Run launcher coverage if touched:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py
```

Run a direct command proof:

```bash
python3 scripts/turn_runtime.py --help
```

Run an active-surface search:

```bash
rg '(^|[^a-zA-Z0-9_./-])scripts/turn_runtime\.py (prepare|persist)' tools framework scripts tests README.md docs/spec
```

The search must not find active host-facing instructions that tell the host to execute the bare script. Every match must appear in the residue inventory. Historical memos may remain only if the inventory marks them as `historical-only retained` and they are not used by runtime, validators, launcher assets, or current runbooks.

## Acceptance Criteria

- Ordinary buddy instance requests no longer lead the host to attempt bare `scripts/turn_runtime.py prepare`.
- Canonical executable runtime commands are exposed through runtime contract or structured feedback.
- Buddy AGENTS remain concise framework guidance and do not grow business-specific recipes.
- Active docs, validators, and tests agree on one command contract.
- No compatibility wrapper, chmod-based workaround, or dual-path instruction is introduced.
- Residue inventory is complete and contains no active retained old-command contract.
- Existing buddy capability boundaries and `switch` text handling remain unchanged.
- Focused tests pass and a direct `python3 scripts/turn_runtime.py --help` proof succeeds.

## Residual Risks

- The actual Codex UI approval popup may not be directly testable in repository tests. Use host-facing contract checks and product-mode command execution as the observable proxy.
- Existing running instances may need restart or re-materialization before they receive updated AGENTS.
- Historical docs may mention the old command while explaining the bug. Keep those clearly marked as history, list them in the residue inventory, and keep them outside active contract checks.
