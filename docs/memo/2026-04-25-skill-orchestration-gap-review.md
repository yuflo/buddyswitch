# SKILL Orchestration Gap Review

Date: 2026-04-25
Branch: `docs/multi-instance-buddy-runtime-architecture`
Worktree: `/Users/chen/Dev/buddyswitch/.worktrees/multi-instance-buddy-runtime-architecture`

## Bottom Line

The multi-instance checkpoint gives BuddySwitch the right runtime substrate:

- buddy-locked instances
- shared canonical BuddySwitch state
- isolated workspace, `CODEX_HOME`, browser profile, and scratch paths
- one runtime lock
- canonical `resolve -> host run -> persist -> refreshed_context`

It does not yet deliver the target SKILL orchestration experience.

Current execution still depends on the host Codex session manually following `AGENTS.md`: run `resolve`, choose a skill, read `SKILL.md`, hand-write a schema result, run `persist`, then remember to print a receipt. The observed failures are mostly host/SKILL orchestration failures, not multi-instance state isolation failures.

## Review Inputs

Two review sub-agents were launched for this memo:

- Architecture review completed and was incorporated.
- Evidence review failed once due remote compact stream disconnect, then the replacement timed out and was closed. Those failed/timeout reviews are not treated as approval evidence.

Local evidence was verified directly from the shared runtime state under `/Users/chen/.codex-buddyswitch/state` and the instance workspaces under `/Users/chen/.codex-buddyswitch/instances`.

## What Worked

- `pm`, `market`, `dev`, and `test` all resolved to the expected buddy skill surfaces.
- Formal state writes landed in the canonical projected paths:
  - `buddyswitch/objects/tasks/*.json`
  - `buddyswitch/objects/artifacts/*.json`
  - `buddyswitch/content/runs/*.json`
- `dev` code changes landed inside the dev instance workspace and did not dirty the main checkout.
- `projects/app/.runtime/` worked as instance-local scratch.
- Shared state projection behaved as intended: instances saw the same task/artifact/run state while keeping workspaces and browser profiles separate.

## Observed Gaps

### P0: `resolve` Is Being Misused As A Repeated Query

Observed in all tested flows:

- the host first ran `python3 scripts/switch_runtime.py resolve` without the required text argument
- later, the host reran valid `resolve` commands multiple times
- create-mode `resolve` can materialize a task and reserve a run, so repeated use is not harmless

Concrete runtime residue:

- empty orphan market task:
  - `task-market-ai-2025-2026-0a9888c4-0d33372452`
  - zero artifacts, zero runs
- residual test reservation:
  - `buddyswitch/content/runs/reserved/run-3cf6b02229.json`
  - bound to `task-test-buddyswitc-test-681639e9-53e2e73b13`

Root issue:

`resolve` is currently exposed as a manual CLI step. The host model treats it like a read-only probe, but in product-mode create/reuse flows it has reservation side effects.

Required constraint:

One user turn must have one controlled runtime envelope:

```text
native skill selected -> begin/resolve once -> execute canonical package -> finish/persist once -> render receipt
```

The host must not freely rerun create-mode `resolve`.

### P0: Host-Written Result JSON Is Too Loose

Observed examples:

- PM wrote intermediate result JSON manually and then manually patched a run audit path after noticing a wrong artifact prefix.
- Test artifact content said final readiness depended on persist succeeding even though persist had already succeeded.
- Market wrote a markdown report in `reports/` and a result file in `tmp/`, while the canonical artifact already contained structured report content.

Root issue:

The host is hand-authoring the persistence result before `persist`, but also hand-authoring user-facing summary after `persist`. This creates time-of-check/time-of-use drift.

Required constraint:

- The runtime/native skill wrapper produces a schema result in `projects/app/.runtime/buddyswitch/<run_id>/result.json`.
- User-facing receipt is generated from the persisted `persist` response, not from pre-persist assumptions.
- Canonical product output is the artifact object, not a free markdown side file.

### P0: Receipt Contract Is Not Enforced

Runtime instructions require:

```text
Receipt
Commands
Summary
```

with explicit `Task`, `Artifact`, `Run`, and recommended next switch.

Observed:

- PM omitted the standard receipt entirely.
- Market printed artifact/run but not the full receipt.
- Dev said the runtime wrote task/artifact records but did not print IDs.
- Test printed IDs but still not the exact contract.

Root issue:

Receipt rendering is prompt-only. The host model often summarizes naturally instead of following the exact terminal contract.

Required constraint:

Receipt must be generated mechanically by one runtime receipt helper from the `persist` response. It must not rely on model memory.

### P0: Browser-Native Downgrade Is Prompt-Enforced, Not Gate-Enforced

Market flow observed:

- browser-native search started in `chrome-devtools-cockpit`
- host then used web search and described it as an explicit downgrade
- there was no separate user approval before the downgrade

Additional browser cockpit evidence:

- `chrome-devtools-cockpit` MCP can time out after 30 seconds
- old instance `chrome.pid` markers existed with dead processes and unreachable `/json/version` endpoints
- instance config lacked `startup_timeout_sec`

Root issue:

Browser-native skill preflight is not a deterministic gate. The host can reinterpret missing cockpit readiness as a reason to continue with web search.

Required constraint:

Market/browser-native skills need preflight before execution:

- verify instance cockpit endpoint is reachable
- fail closed if the required browser executor is unavailable
- require explicit user approval before any temporary downgrade
- record downgrade reason only after approval

### P1: Scratch And Derived Output Paths Are Inconsistent

Allowed scratch:

- `runs/raw/`
- `projects/app/.runtime/`

Observed:

- PM wrote `.runtime/...` at workspace root
- Market wrote `tmp/...` and `reports/...`
- Dev and Test used `projects/app/.runtime/...`, which is acceptable

Root issue:

Path rules live in prompt text but are not enforced by the execution wrapper.

Required constraint:

Generated runtime inputs/results should be placed only under `projects/app/.runtime/buddyswitch/<run_id>/`. Durable outputs must only be task/artifact/run objects. `tmp/`, root `.runtime/`, and `reports/` are not valid runtime result or report destinations.

### P1: Skill Execution Starts Before Successful Runtime Preflight

Dev flow observed:

- empty `resolve` failed
- host read files and started replacing `projects/app`
- only later did it run successful `resolve` and `persist`

Root issue:

The host can begin side-effectful work before it has a valid `resolve_context`.

Required constraint:

For side-effecting skills, no file edits, browser work, or shell actions should start until the wrapper has:

- successfully resolved the turn
- selected or confirmed the skill
- checked selected skill preflight
- established the reserved run envelope

## What Is Not A Multi-Instance Skeleton Problem

These are not evidence that shared/isolated paths are broken:

- task/artifact/run objects were generated in the canonical shared state paths
- `dev` code edits stayed inside the dev instance workspace
- main checkout stayed clean during the product-mode tests
- missing or non-standard terminal IDs were display/receipt issues, not missing state
- market report side files were host free-form output, not projection failure

The multi-instance skeleton should be kept as the foundation.

## Architecture Direction

The next step should not add a workflow engine, event bus, process supervisor, second LLM router, or second durable skill registry.

The sharp target is:

```text
BuddySwitch remains the control plane.
Codex native-visible skills become an instance-local projection of BuddySwitch skill packages.
```

Source of truth stays:

- `buddyswitch/manifest.toml`
- `buddyswitch/skills/**/skill.toml`
- `buddyswitch/skills/**/SKILL.md`
- output schemas
- `scripts/switch_runtime.py resolve/persist`

Native skill materialization must be a disposable generated surface under the instance runtime environment, not a new canonical registry.

## Native Skill Projection Contract

This is the minimum executable shape for the next cut.

### Location And Lifecycle

Generated native skills live under the active instance `CODEX_HOME`:

```text
${BUDDYSWITCH_SHARED_ROOT}/instances/<instance-id>/codex-home/skills/buddyswitch-<buddy>-<skill-id>/SKILL.md
```

Launcher ownership:

- `./buddyswitch-codex start --buddy <buddy>` generates the native skill projection before launching Codex.
- The projection is regenerated on every start for that instance.
- Regeneration deletes stale `codex-home/skills/buddyswitch-*` directories first.
- Only skills allowlisted for the active buddy in `buddyswitch/manifest.toml` are generated.
- No non-active buddy skills may exist in that instance `codex-home/skills/` projection.

This uses Codex's native skill loading convention (`$CODEX_HOME/skills/<skill-name>/SKILL.md`). It does not use repo-local `.agents/skills` and does not re-enable plugins.

### Generated Skill Shape

Each generated native skill maps to exactly one canonical BuddySwitch skill.

Generated `SKILL.md` frontmatter:

```yaml
---
name: buddyswitch-<buddy>-<skill-id>
description: <derived activation description from canonical skill.toml/SKILL.md>
---
```

Generated body must be a wrapper, not a copied second source of truth:

- fixed `buddy_id`
- fixed `skill_id`
- canonical package path: `buddyswitch/skills/<buddy>/<skill-id>/`
- canonical instruction path: `buddyswitch/skills/<buddy>/<skill-id>/SKILL.md`
- output schema path from canonical skill metadata
- instruction to read the canonical `SKILL.md` before execution
- instruction to use the wrapper contract below for begin/finish/receipt

Do not hand-maintain generated native skill content. The generator derives it from:

- `buddyswitch/manifest.toml`
- `buddyswitch/skills/**/skill.toml`
- `buddyswitch/skills/**/SKILL.md`

Generated native skill files are cache/projection output. Canonical edits happen only in BuddySwitch skill packages.

### No Second Router

Native Codex skill selection chooses a concrete generated skill. After that, BuddySwitch still validates the turn:

- generated native skill has fixed `skill_id`
- wrapper calls `resolve` once for the user demand
- wrapper verifies the resolved candidate set allows that fixed `skill_id`
- wrapper rejects if the selected generated skill is not allowed by the current `resolve_context`

This keeps Codex native activation useful while keeping BuddySwitch as the state/authority control plane. It does not add another semantic router.

## Wrapper Turn Contract

The generated native skill should instruct the host to use a deterministic wrapper command/API with two phases.

### Begin

Input:

- raw user demand text
- fixed `buddy_id`
- fixed `skill_id`
- current instance env: `BUDDYSWITCH_ACTIVE_BUDDY`, `BUDDYSWITCH_INSTANCE_ID`, `BUDDYSWITCH_INSTANCE_JSON`

Behavior:

- validate the instance is locked to `buddy_id`
- run `scripts/switch_runtime.py resolve` exactly once
- reject cross-buddy switches before state mutation
- write the resolved payload to:
  - `projects/app/.runtime/buddyswitch/<run_id>/resolved.json`
- return a turn envelope

Turn envelope fields:

```json
{
  "active_buddy": "<buddy_id>",
  "instance_id": "<instance_id>",
  "generated_skill_id": "buddyswitch-<buddy>-<skill-id>",
  "canonical_skill_id": "<skill_id>",
  "canonical_package_path": "buddyswitch/skills/<buddy>/<skill-id>",
  "resolved_context_path": "projects/app/.runtime/buddyswitch/<run_id>/resolved.json",
  "result_path": "projects/app/.runtime/buddyswitch/<run_id>/result.json",
  "persist_response_path": "projects/app/.runtime/buddyswitch/<run_id>/persist-response.json",
  "receipt_path": "projects/app/.runtime/buddyswitch/<run_id>/receipt.txt",
  "run_id": "<reserved_run_id>",
  "reservation_instance_id": "<instance_id>"
}
```

The host should execute the canonical skill using this envelope. It should not call `resolve` directly after begin.

### Execute

The host reads the canonical `SKILL.md` and any needed canonical supporting files, executes the skill, and writes only schema result JSON to:

```text
projects/app/.runtime/buddyswitch/<run_id>/result.json
```

The result may reference changed project files for dev/test skills, but it must not make `reports/`, `tmp/`, root `.runtime/`, `artifacts/*.md`, or `runs/summaries/**` the canonical output.

### Finish

Input:

- turn envelope path or fields
- `result.json`

Behavior:

- validate `result.json` against the selected skill schema
- run `scripts/switch_runtime.py persist` exactly once with the envelope's `resolved.json`
- write persist response to `persist-response.json`
- render receipt mechanically to `receipt.txt`
- print `receipt.txt` as terminal output

The receipt renderer is a single helper/interface. The host model must not author `Receipt`, `Commands`, or `Summary` from memory.

### Re-Resolve And Stale Reservation Policy

Default wrapper behavior: do not re-resolve inside one turn.

Recovery behavior must be deterministic:

- if begin created the reservation and finish fails before persist commit, the wrapper reports the reserved run id and recovery command
- same-instance stale reservation handling should adopt the existing architecture target: a same-instance re-resolve may replace the previous still-reserved run for the same task; cross-instance active reservation remains fail-closed
- if this rule is not implemented in the same cut, the wrapper must fail with a clear recovery path instead of silently creating another task or reservation

## Browser-Native Preflight Contract

For skills whose resolved metadata requires browser-native execution:

- read the active instance browser port from `BUDDYSWITCH_INSTANCE_JSON`
- verify `http://127.0.0.1:<browser_port>/json/version` responds before browser work starts
- verify the selected skill's `browser_executor` is available to the Codex session
- treat stale `browser/chrome.pid` with unreachable endpoint as not ready
- fail closed with a structured preflight error before any downgrade or web search

Downgrade rule:

- web search or non-cockpit browsing requires an explicit user approval step
- the approval decision and downgrade reason are written into the turn envelope or result metadata
- without approval, the run stays blocked and must not fabricate browser-native evidence

## Minimal Target For The Next Cut

1. Active buddy instance exposes only that buddy's allowlisted skills to Codex-native skill discovery.
2. A native-visible BuddySwitch skill wraps exactly one canonical turn:
   `begin/resolve once -> load selected canonical package -> execute -> validate result -> finish/persist once -> render receipt`.
3. `resolve` side effects are hidden behind the wrapper so the host cannot repeatedly probe create-mode state.
4. `persist` remains the only canonical writer for task/artifact/run state.
5. Receipt is mechanically rendered from `persist` output.
6. Browser-native skills perform deterministic cockpit preflight and require explicit user approval before downgrade.
7. Retired outputs remain retired: no `artifacts/*.md`, no `runs/summaries/**`, no free-form `reports/` as the canonical result.

## Boundaries

Keep:

- shared durable BuddySwitch state
- one runtime lock
- instance-local workspace, `CODEX_HOME`, browser profile, and scratch paths
- thin `persist` as a technical gate, not a business-quality reviewer
- host Codex as the executor of real tools and reasoning

Do not include in this cut:

- cross-buddy workflow automation
- artifact revision redesign
- broad skill catalog expansion
- internal semantic routing by a second model/backend
- general orchestration platform abstractions

## Open Questions Before Implementation

1. Exact Codex native skill visibility path.

   Decision for this memo: use instance-local `$CODEX_HOME/skills/buddyswitch-<buddy>-<skill-id>/SKILL.md`. The implementation plan still must confirm Codex CLI in product mode loads that directory when `CODEX_HOME` is instance-scoped.

2. Same-instance re-resolve semantics.

   Current code blocks any active reservation for the same task. The native wrapper can avoid duplicate resolve, but the implementation should also decide whether same-instance re-resolve should replace stale same-instance reservations or fail with a clean recovery path.

3. Browser MCP startup policy.

   Need a product-mode decision: increase `startup_timeout_sec`, pre-warm cockpit earlier, or fail fast with a clear repair command. This should be deterministic and visible before market work starts.

4. Cleanup of failed reservations.

   The product needs either a safe reservation expiry/recovery mechanism or a stricter wrapper that prevents abandoned reservations in normal operation.

## P0 Acceptance Tests For The Next Cut

- Starting `./buddyswitch-codex start --buddy pm` makes only PM BuddySwitch skills visible to the Codex session.
- The generated native skill set exactly equals the active buddy allowlist from `buddyswitch/manifest.toml`.
- Restarting an instance removes stale generated `buddyswitch-*` skills that are no longer allowlisted.
- Generated native skill metadata is derived from canonical `skill.toml` / `SKILL.md`, not hand-maintained.
- No non-active buddy generated skill exists under the instance `CODEX_HOME/skills`.
- A plain PM request creates exactly one task, one artifact, one run, and no leftover reservation.
- Repeating the same command path does not create an orphan task through duplicate create-mode resolve.
- Wrapper begin calls `resolve` once and finish calls `persist` once for a normal turn.
- The terminal response always contains `Receipt`, `Commands`, and `Summary` generated from persisted state.
- Market browser-native skill fails closed when the cockpit endpoint is unavailable.
- Market downgrade requires an explicit approval step before web search or non-cockpit browsing.
- `reports/`, root `.runtime/`, and `tmp/` are not used as canonical outputs.
- Main checkout remains clean after product-mode execution.
