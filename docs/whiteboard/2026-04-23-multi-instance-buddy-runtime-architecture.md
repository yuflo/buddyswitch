# Multi-Instance Buddy Runtime Architecture

## Bottom Line

BuddySwitch should move to a **multi-instance, buddy-locked runtime** with this exact shape:

- one `buddyswitch-codex` process = one locked `active buddy`
- BuddySwitch **state** is shared across instances
- the **execution surface** is isolated per instance
- the canonical BuddySwitch loop stays:
  - `resolve_context`
  - host chooses one `skill_id`
  - host executes the selected canonical BuddySwitch `SKILL.md`
  - `persist_skill_result`
  - `refreshed_context`

This is a **replacement cut**. It is not a compatibility bridge.

## Core Decision

The correct split is:

- **shared:** BuddySwitch canonical state
- **isolated:** Codex process environment, prompt surface, browser, and execution workspace

In one line:

`shared state, isolated execution`

## Non-Goals

This cut does **not** introduce:

- a workflow engine
- a second native Codex skill registry
- in-session buddy switching
- one shared execution workspace root
- one shared `CODEX_HOME`
- one shared browser profile
- one shared generic runtime `AGENTS.md`
- implicit instance reuse logic

## Buddy Authority

Buddy authority must exist in exactly one place.

The target rule is:

- `buddyswitch-codex start --buddy <buddy>` selects the buddy
- after launch, that session is already bound to the selected buddy
- inside that session, the user sends normal task requests
- product-mode runtime does **not** require `switch <buddy>: ...` inside the session

So after the cut:

- launcher startup owns buddy selection
- in-session text owns demand only

This removes the current double-authority shape where both launcher startup and in-session text can try to select the buddy.

`.codex/agents/router.toml` and the generic `runtime-AGENTS.md` are current repo surfaces, but they are **not** the target product-mode authority after this cut.

## Session Input Contract

The runtime wire grammar stays canonical:

```text
switch <buddy>(<task-id>) -> <track-id>: <demand>
```

The product-mode input rule changes like this:

- plain user text inside a buddy-locked session is launcher-adapted to `switch <active-buddy>: <demand>`
- if the user needs explicit task or track targeting, the session may still accept the full canonical `switch ...` form
- if a canonical in-session `switch ...` command names a different buddy than the locked one, the launcher/session adapter rejects it before `resolve`

So the cut is:

- **wire format stays `switch ...`**
- **product-mode UX may accept plain demand text**

This keeps `parse_switch.py` and `resolve` input semantics stable in the first cut while removing buddy selection from user-facing product-mode behavior.

## What Stays Canonical

The runtime data contract remains:

- `buddyswitch/manifest.toml`
- `buddyswitch/skills/**/skill.toml`
- `buddyswitch/skills/**/SKILL.md`
- `framework/contracts/resolve-context.json`
- `framework/contracts/persist-skill-result.json`
- `framework/docs/switch-spec.md`
- `framework/docs/skill-runtime-shared-rules.md`
- `framework/docs/browser-cockpit.md` after it is updated to instance-scoped browser semantics

The redesign changes isolation and launcher behavior. It does **not** change the meaning of:

- `buddy`
- `skill_id`
- `resolve_context`
- `persist_skill_result`
- `refreshed_context`

It also does **not** change the first-cut wire meaning of canonical `switch ...` strings. The launcher adapts product-mode UX to that wire contract.

## Shared Vs Isolated

| Surface | Shared | Isolated | Decision |
|---|---|---|---|
| BuddySwitch durable state | yes | no | one canonical state plane for `tasks / tracks / artifacts / runs` |
| `resolve` / `persist` durable write target | yes | no | all instances write to the same BuddySwitch state |
| Context Panel data source | yes | no | all instances read the same canonical BuddySwitch state |
| source repository / repo `HEAD` | common origin | no live-sharing | instances may be created from the same repo source, but do not share one execution root |
| execution workspace / worktree | no | yes | every instance gets its own execution root |
| root `AGENTS.md` in execution workspace | no | yes | launcher copies the selected buddy’s prompt asset into that instance root |
| `active buddy` | no | yes | one process owns one buddy only |
| `HOME` | no | yes | no profile bleed |
| `CODEX_HOME` | no | yes | no memory / config / history contamination |
| `XDG_CONFIG_HOME` | no | yes | no config bleed |
| Codex session history / memory / logs | no | yes | each buddy keeps its own session context |
| browser profile / port / PID / log | no | yes | no cookie / tab / debugger collision |
| `runs/raw/` and `projects/app/.runtime/` | no | yes | instance-local scratch/runtime state only; never projected into shared durable state |
| auth bootstrap source | copy-in allowed | live-sharing forbidden | bootstrap may copy auth into an instance; runtime may not share it live |

## Runtime Layout

The target runtime layout is:

```text
${BUDDYSWITCH_SHARED_ROOT}/
  state/
    buddyswitch/objects/tasks/
    buddyswitch/objects/tracks/
    buddyswitch/objects/artifacts/
    buddyswitch/content/runs/
    locks/runtime-state.lock
  instances/
    <instance-id>/
      workspace/
        runs/raw/
        projects/app/.runtime/
      home/
      codex-home/
      xdg-config/
      run/
      browser/
```

## Shared State Projection

The critical rule is:

- canonical state lives once under `${BUDDYSWITCH_SHARED_ROOT}/state`
- each instance workspace exposes the existing repo-relative runtime paths by projecting them into that shared state

Projected paths inside every instance workspace:

- `buddyswitch/objects/tasks`
- `buddyswitch/objects/tracks`
- `buddyswitch/objects/artifacts`
- `buddyswitch/content/runs`

`runs/raw/` and `projects/app/.runtime/` stay instance-local inside the instance workspace and are **not** projected into shared state.

The projection mechanism must preserve repo-relative path semantics in `/api/workspace`. The architecture decision is:

- runtime Python code continues to read and write the current repo-relative paths
- launcher owns how those paths are attached to the shared state store
- plain symlink projection is not sufficient unless the projection/path-helper layer is updated so `/api/workspace` still emits canonical repo-relative paths

This cut therefore explicitly includes the projection/path-helper update required to keep workspace-projection paths canonical if symlink-based projection is used.

This still avoids a repo-wide runtime writer rewrite, but it does include the targeted projection/context-panel path fix needed for implementation.

But it is still a real migration at the launcher/repo boundary. This cut must update together:

- launcher workspace bootstrap
- launcher sync/reset/cleanup behavior
- repo docs that currently say runtime state lives under one shared execution workspace
- tests that currently freeze that shared-workspace state model

## Session Model

Target launcher entrypoint:

```text
buddyswitch-codex start --buddy <buddy>
```

This starts one fresh buddy-locked instance.

That instance:

- creates one isolated execution workspace
- copies the selected buddy’s `AGENTS.md` into that workspace root
- creates one isolated `HOME`
- creates one isolated `CODEX_HOME`
- creates one isolated `XDG_CONFIG_HOME`
- creates one isolated browser profile and port
- runs Codex with `cwd` set to that instance-local execution workspace

Inside that session:

- all requests are for the locked buddy
- there is no in-session buddy switching
- there is no implicit instance reuse

If explicit resume/reopen behavior is needed later, that is a separate cut. It is not part of this architecture decision.

## Follow-Up Contract

The current runtime serializes follow-up control through canonical `switch ...` strings in:

- `receipt.reference_switches`
- `receipt.recommended_switch`

That contract remains wire-stable in the first cut.

The first-cut rule is:

- BuddySwitch may continue to emit canonical `switch ...` follow-up commands
- in a buddy-locked session, any emitted follow-up command must match the active buddy or be treated as an external handoff
- cross-buddy handoff is not executed in-session; the host renders it as: `Start buddy <next-buddy> in another instance, then run <wire-command>`
- `refreshed_context` remains only the next-turn resolve handoff for the current buddy/task path; it is not the host-facing command surface

So this cut does **not** pretend follow-up is launcher-only cleanup. It is an explicit product-mode adapter over the existing switch-command follow-up contract.

## Buddy Prompt Asset

Buddy-specific prompt assets must be explicit.

The target source is:

```text
tools/launcher/assets/buddies/<buddy>/AGENTS.md
```

The rule is:

- one buddy prompt asset per buddy
- launcher copies that file into the instance workspace root as `AGENTS.md`
- shared state contains no buddy-specific prompt files
- `CODEX_HOME/AGENTS.override.md` is not the primary isolation mechanism
- every buddy-specific `AGENTS.md` must preserve `# BuddySwitch Runtime Workspace` as line 1 until the runtime write marker is replaced explicitly
- every buddy-specific `AGENTS.md` is defined as: `generic runtime baseline + buddy-specific overlay`

This keeps the product-mode prompt surface visible and local to the instance workspace instead of hiding it in profile-only config.

That header requirement is not incidental. Current runtime writes are authorized through that workspace-header check, so the first cut must preserve and test it unless a separate explicit runtime marker replaces it.

## Browser Isolation

Browser isolation is mandatory.

Every instance must get its own:

- browser profile dir
- remote debugging port
- PID file
- log file
- Codex MCP bootstrap pointing at that instance’s browser endpoint

The old market/browser assumption:

- `browser_profile = "shared-browser"`
- `session_continuity = "shared-cockpit"`

must be removed from the product-mode contract.

The canonical replacement semantics are:

- `browser_profile = "instance-browser"`
- `session_continuity = "instance-cockpit"`
- `browser_executor = "chrome-devtools-cockpit"` remains unchanged unless a later cut replaces it

These metadata changes must be updated together in:

- `scripts/env_manifest.py`
- market skill `skill.toml`
- market/browser contract docs
- any runtime validation that currently hard-codes shared-browser assumptions

After the cut, browser continuity is:

- per instance
- not global across all buddy instances

If continuity is needed across restarts of the **same** instance, reuse that instance’s browser profile only.

## Host Surface

Runtime mode should continue to restrict the host skill/plugin surface.

Per-instance `CODEX_HOME/config.toml` should keep the same basic runtime policy as today:

- bundled skills disabled by default
- plugins disabled by default unless explicitly reintroduced by architecture

The scope change is:

- same runtime policy
- instance-local config and MCP bootstrap

not one shared launcher profile for every buddy instance.

## Canonical Execution Loop

The canonical loop remains:

1. BuddySwitch resolves one demand into `resolve_context`
2. the host chooses one `skill_id` from `resolve_context.skills`
3. the host executes that selected canonical BuddySwitch skill
4. BuddySwitch persists the result through `persist_skill_result`
5. BuddySwitch returns `refreshed_context`

This proposal does **not** add a workflow engine.

BuddySwitch remains the only source of truth for:

- which skills exist
- which buddy owns them
- which schema they write
- which host execution metadata they require
- which durable writes are valid

## Shared State Correctness

Multi-instance correctness requires one explicit serialized runtime lock.

Lock file:

```text
${BUDDYSWITCH_SHARED_ROOT}/state/locks/runtime-state.lock
```

The lock covers exactly these write critical sections:

### Critical Section A: any reservation-writing resolve

Exclusive lock required from:

- task/track validation against shared state
- any task-state read used to derive `sequence`, `context_revision`, or reservation identity

through:

- create-mode task materialization when applicable
- run envelope reservation
- any other shared-state mutation performed by `resolve_context`

This applies to both:

- create-mode resolve
- reuse-mode resolve

### Critical Section B: persist

Exclusive lock required from:

- revision / fingerprint / run validation against shared state

through:

- all task / track / artifact / run writes
- follow-up `refreshed_context` reservation when persist succeeds

The runtime consistency model is:

- shared-state projection readers such as `/api/workspace` take a shared/read lock
- resolve, persist, and maintenance mutations take the exclusive/write lock
- concurrent reads are allowed only among readers that hold the shared/read lock

This is intentionally blunt.

Clarity is more important than optimistic multi-writer behavior.

### Critical Section C: maintenance operations

Operations that stage, rebuild, sync, reset, or delete shared runtime state must not run concurrently with live instances.

The rule is:

- maintenance commands are forbidden while any BuddySwitch instance is active
- maintenance commands that still touch the shared state plane must also hold the same exclusive runtime lock
- any maintenance path that swaps projected runtime state must do so atomically so `/api/workspace` readers never observe torn state

This applies to any remaining equivalents of:

- `workspace sync`
- shared-state cleanup
- launcher reset
- projection/worktree rebuild touching projected runtime paths

## Maintenance Commands

The shared-root maintenance commands from the current launcher do not survive unchanged.

Target rule:

- `start --buddy <buddy>` is product-mode
- maintenance operations are not part of the normal runtime hot path
- no per-instance maintenance command is introduced in this cut
- any retained maintenance command operates only when there are zero active instances

So the first cut decides:

- remove standalone `browser status`
- remove standalone `browser ensure`
- keep `workspace sync` as a zero-active-only global maintenance command that rebuilds every stored instance workspace from repo `HEAD` and leaves shared canonical state untouched
- keep launcher reset/cleanup as zero-active-only global maintenance commands that operate on both the shared canonical state root and all stored instance trees

## Launcher Responsibilities

The launcher should do exactly this:

1. prepare the shared BuddySwitch state root
2. create an instance-local execution workspace
3. project shared runtime state paths into that workspace
4. create instance-local `HOME`, `CODEX_HOME`, `XDG_CONFIG_HOME`
5. copy the selected buddy’s `AGENTS.md` into the instance workspace root
6. bootstrap instance-local Codex config and MCP wiring
7. bootstrap instance-local browser profile and port
8. start Codex with that instance’s env vars

The launcher should no longer:

- copy one generic runtime `AGENTS.md` into one shared workspace root
- run all buddy instances against one shared browser profile
- run all buddy instances against one shared `CODEX_HOME`
- decide buddy authority in more than one place
- imply smart instance reuse behavior
- leave shared-root maintenance command semantics ambiguous

## Runtime Authority After The Cut

After the cut, product-mode runtime authority should be split cleanly:

Runtime data and execution contracts:

- `buddyswitch/manifest.toml`
- canonical skill packages under `buddyswitch/skills/**`
- `framework/contracts/resolve-context.json`
- `framework/contracts/persist-skill-result.json`
- `framework/docs/switch-spec.md`
- `framework/docs/skill-runtime-shared-rules.md`
- updated browser/runtime policy docs

Launcher prompt assets:

- `tools/launcher/assets/buddies/<buddy>/AGENTS.md`

Development mirrors that must stay explicitly aligned until removed:

- `tools/launcher/assets/runtime-AGENTS.md`
- `.codex/agents/router.toml`

Parity scope is explicit:

- `runtime-AGENTS.md` is the generic runtime baseline
- buddy assets must include that baseline plus buddy-specific overlay content
- `.codex/agents/router.toml` mirrors only the generic runtime baseline that remains relevant in dev-mode, not the full per-buddy overlay set

Everything else is either:

- development-only
- transitional
- or a mirror surface that is not product-mode runtime authority

Repo consistency checks must keep the surviving development mirrors aligned with the buddy-locked runtime contract until those mirrors are deleted.

## What Must Be Removed

The hot path should delete, not preserve:

- generic runtime `AGENTS.md` copy into one shared execution workspace
- router-driven multi-buddy product-mode session behavior
- shared `CODEX_HOME`
- shared browser profile assumptions
- implicit instance reuse behavior
- packet-era runtime concepts
- stale docs that preserve the wrong runtime model

## Final Target

The target architecture is:

`multi-instance, buddy-locked BuddySwitch with one shared canonical state store, one isolated execution workspace per instance, one buddy-specific AGENTS.md per instance workspace, one isolated Codex/browser profile per instance, one canonical resolve/persist loop, and no double buddy authority`

That is the clearest shape that matches the product requirement:

- multi-buddy collaboration
- clear isolation
- minimal runtime ambiguity
- no compatibility-heavy drag
