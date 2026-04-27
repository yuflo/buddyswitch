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
- a generic input proxy around Codex
- a process supervisor
- a distributed lock service
- a migration framework

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

- plain user text inside a buddy-locked session is launcher-adapted based on the instance session binding
- if the user needs explicit task or track targeting, the session may still accept the full canonical `switch ...` form
- if a canonical in-session `switch ...` command names a different buddy than the locked one, the launcher/session adapter rejects it before `resolve`

First-cut adapter boundary:

- `parse_switch.py` remains strict and canonical-only
- product-mode adaptation happens in the `scripts/switch_runtime.py resolve` CLI path before `parse_switch`
- the launcher sets `BUDDYSWITCH_ACTIVE_BUDDY=<buddy>`, `BUDDYSWITCH_INSTANCE_ID=<instance-id>`, and `BUDDYSWITCH_INSTANCE_JSON=<instance.json>`
- when those env vars are absent, `resolve` keeps the current strict canonical behavior
- partial product-mode env is invalid: if any product-mode binding env is present but `BUDDYSWITCH_ACTIVE_BUDDY`, `BUDDYSWITCH_INSTANCE_ID`, and `BUDDYSWITCH_INSTANCE_JSON` are not all present and valid, reject before parse/resolve mutation
- no terminal keystroke interception or generic Codex proxy is introduced

Continuation rule:

- if the instance has no current task binding yet, plain text becomes `switch <active-buddy>: <demand>` and enters create-mode
- if the instance already has a current task binding, plain text becomes `switch <active-buddy>(<current_task_id>) -> <current_track_id>: <demand>` when track is known, otherwise `switch <active-buddy>(<current_task_id>): <demand>`

So the cut is:

- **wire format stays `switch ...`**
- **product-mode UX may accept plain demand text**

This keeps `parse_switch.py` stable while removing buddy selection from user-facing product-mode behavior.

Adapter rejection rules:

- empty text rejects as current parse behavior does
- product-mode treats input as an explicit canonical switch only when it structurally matches `switch <buddy>...: <demand>`
- text that merely starts with the English word `switch` but lacks canonical `switch <buddy>...:` structure is plain demand text
- plain text becomes a canonical `switch <active-buddy>...: <demand>` string before parse
- canonical `switch ...` naming the active buddy is allowed
- canonical `switch ...` naming another buddy rejects with a session-lock error before parse/resolve mutation
- unknown active buddy in `BUDDYSWITCH_ACTIVE_BUDDY` rejects before parse/resolve mutation

Session binding update rules:

- binding updates run inside the same exclusive runtime lock as the `resolve` or `persist` command that changes them
- `resolve` updates `instance.json.current_task_id` / `current_track_id` only after a successful `resolve_context`
- if `resolve` writes a reservation but cannot write `instance.json`, it clears the just-written reservation and returns failure
- this first cut does not attempt broad rollback of zero-run task materialization if binding write fails; the important safety rule is that no stale reservation or binding is left behind
- `persist` updates the same fields only after a successful `persist_skill_result`
- if `refreshed_context.ok = true`, the binding comes from `refreshed_context`
- if `refreshed_context.error.code = E_RUNTIME_REFRESH_CONTEXT` and there is no `W_INSTANCE_BINDING_UPDATE_FAILED` warning, the binding remains the just-persisted task/track
- if canonical persist writes commit but the binding update fails, canonical state wins and the top-level persist result remains `ok = true`
- in that committed-binding-failure case, clear any just-created refreshed reservation, leave the previous binding unchanged, and return a `receipt.warnings[]` entry with `code = W_INSTANCE_BINDING_UPDATE_FAILED`
- the warning object shape is `{ "code": "W_INSTANCE_BINDING_UPDATE_FAILED", "message": "...", "instance_id": "...", "instance_json": "..." }`
- the same response returns `refreshed_context = { "ok": false, "error": { "code": "E_RUNTIME_REFRESH_CONTEXT", "message": "instance binding update failed after persist commit; rerun resolve for next turn", "instance_id": "...", "instance_json": "..." } }`
- hosts must key off `W_INSTANCE_BINDING_UPDATE_FAILED`; after that warning, plain-text continuation is unsafe until the next successful `resolve`
- failed `resolve` or failed `persist` before canonical commit leaves the existing binding unchanged

This is deliberately not a new workflow layer. It is a small product-mode pre-parse adapter around the existing canonical CLI path.

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
${BUDDYSWITCH_SHARED_ROOT}.lock
${BUDDYSWITCH_SHARED_ROOT}/
  run/
    launcher-*.json
  state/
    buddyswitch/objects/tasks/
    buddyswitch/objects/tracks/
    buddyswitch/objects/artifacts/
    buddyswitch/content/runs/
  instances/
    <instance-id>/
      instance.json
      workspace/
        runs/raw/
        projects/app/.runtime/
      home/
      codex-home/
      xdg-config/
      run/
      browser/
```

`${BUDDYSWITCH_SHARED_ROOT}.lock` is the single runtime lock. It sits outside `${BUDDYSWITCH_SHARED_ROOT}/` because `buddyswitch-codex reset --yes` deletes the launcher root and must still serialize against concurrent start, resolve, persist, and maintenance paths.

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
- first cut uses directory symlinks from each instance workspace to `${BUDDYSWITCH_SHARED_ROOT}/state`
- no bind mounts, FUSE layer, or repo-wide writer rewrite is introduced
- path helpers must preserve canonical repo-relative output even when filesystem resolution crosses the symlink target

Concrete symlink map:

```text
instances/<instance-id>/workspace/buddyswitch/objects/tasks
  -> ${BUDDYSWITCH_SHARED_ROOT}/state/buddyswitch/objects/tasks
instances/<instance-id>/workspace/buddyswitch/objects/tracks
  -> ${BUDDYSWITCH_SHARED_ROOT}/state/buddyswitch/objects/tracks
instances/<instance-id>/workspace/buddyswitch/objects/artifacts
  -> ${BUDDYSWITCH_SHARED_ROOT}/state/buddyswitch/objects/artifacts
instances/<instance-id>/workspace/buddyswitch/content/runs
  -> ${BUDDYSWITCH_SHARED_ROOT}/state/buddyswitch/content/runs
```

The required path-helper rule is:

- when building `/api/workspace`, repo-relative object paths are derived from the logical workspace path first
- resolved symlink targets must not leak absolute `${BUDDYSWITCH_SHARED_ROOT}/state/...` paths into API output
- object paths stay like `buddyswitch/objects/tasks/<id>.json` and `buddyswitch/content/runs/<id>.json`

Projection deletion rule:

- deleting an instance workspace or instance-local scratch must unlink projected symlinks, not recursively follow them into `${BUDDYSWITCH_SHARED_ROOT}/state`
- only commands explicitly deleting shared BuddySwitch state may delete files under `${BUDDYSWITCH_SHARED_ROOT}/state`

This still avoids a repo-wide runtime writer rewrite, but it does include the targeted projection/context-panel path fix needed for implementation.

But it is still a real migration at the launcher/repo boundary. This cut must update together:

- launcher workspace bootstrap
- launcher sync/reset/cleanup behavior
- repo docs that currently say runtime state lives under one shared execution workspace
- tests that currently freeze that shared-workspace state model

Migration rule:

- this cut does not add a general migration framework
- state is considered empty when the four durable projected paths contain no regular files after ignoring empty directories, `.DS_Store`, and `buddyswitch/content/runs/reserved/**`
- invalid JSON files under the durable projected paths are not ignored; they count as data and make migration fail closed when read
- `buddyswitch/content/runs/reserved/**` is transient reservation state, not durable run audit
- zero-active migration prunes `buddyswitch/content/runs/reserved/**` from old workspace and new shared state before empty/conflict checks, and never migrates reservations
- if those four durable state paths are empty and the old `${BUDDYSWITCH_SHARED_ROOT}/workspace` contains durable BuddySwitch state, first product-mode startup moves only the four durable projected paths into `state`, excluding `buddyswitch/content/runs/reserved/**`
- `runs/raw/` and `projects/app/.runtime/` are not migrated into shared state
- if both old workspace durable state and new shared state contain data, startup fails closed with a clear reset/cleanup instruction instead of guessing a merge
- `buddyswitch-codex reset --yes` remains the clean destructive escape hatch

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

> Superseded for lifecycle CLI: explicit `instance open <instance-id>` and `instance delete <instance-id> --yes` are now planned as a narrow product-facing lifecycle cut. Smart reuse, broad per-instance maintenance APIs, and workspace rebuild/sync remain out of scope.

Stored instance rule:

- closed instances remain on disk until maintenance removes them
- every stored instance must have `instances/<instance-id>/instance.json`
- `instance.json` is the deterministic binding record for maintenance and cleanup

Minimum fields in `instance.json`:

- `instance_id`
- `buddy`
- `status` (`active` or `inactive`)
- `current_task_id` (nullable)
- `current_track_id` (nullable)
- `workspace_dir`
- `browser_port` (nullable until allocated)
- `created_at`
- `updated_at`

Plain-text continuation uses `current_task_id` / `current_track_id`. Maintenance targeting uses `buddy` plus `status`.

Session binding transition rule:

- on instance creation, `current_task_id = null` and `current_track_id = null`
- on successful `resolve`, replace `current_task_id` / `current_track_id` with the resolved task/track target for that turn
- on failed `resolve`, leave both fields unchanged
- on successful `persist` with `refreshed_context.ok = true`, replace `current_task_id` / `current_track_id` with the task/track in `refreshed_context`
- on successful `persist` with `E_RUNTIME_REFRESH_CONTEXT` and no `W_INSTANCE_BINDING_UPDATE_FAILED` warning, keep the current binding from the just-completed turn
- on failed `persist` before canonical writes commit, leave the current binding unchanged
- on committed `persist` with binding update failure, leave the current binding unchanged and return the committed-binding-failure response shape defined above
- on an explicit same-buddy `switch ...` that retargets another task/track, rebinding happens through the successful `resolve` rule above

This is intentionally simple: plain-text continuation always follows the latest successful bound task/track for the active instance.

Liveness authority rule:

- launcher PID markers under `${BUDDYSWITCH_SHARED_ROOT}/run/launcher-*.json` are the authoritative source for whether live instances exist
- `instance.json.status` is an observable launcher record, but it is not the destructive-maintenance authority
- launcher startup publishes `launcher-*.json` and `instance.json.status = active` while holding the same exclusive runtime lock used by maintenance zero-active checks
- launcher marks `instance.json.status = active` on start and `inactive` on normal exit
- before any zero-active-only maintenance, launcher must recompute live status from PID markers, delete stale markers, and repair `instance.json.status` when it disagrees with live process state
- if PID-marker truth and stored status disagree, PID-marker truth wins
- during the cutover, maintenance must also inspect legacy `${BUDDYSWITCH_SHARED_ROOT}/run/launcher-*.pid` markers; a live legacy launcher PID blocks maintenance, and a stale marker is deleted

PID marker shape:

```json
{
  "pid": 12345,
  "instance_id": "inst-...",
  "buddy": "pm",
  "workspace_dir": ".../instances/inst-.../workspace",
  "started_at": "..."
}
```

The first cut uses `kill -0` plus marker cleanup as the liveness check. That is intentionally simple. A stronger process supervisor or PID-reuse detector is out of scope because a false positive blocks maintenance safely; it does not authorize destructive writes.

Browser PID markers are not the authority for whether a BuddySwitch instance is live. They are deletion guards:

- live `instances/*/browser/chrome.pid` blocks maintenance that would delete that instance's browser/profile tree
- live legacy `${BUDDYSWITCH_SHARED_ROOT}/run/browser-cockpit.pid` blocks reset and storage cleanup that would delete shared browser/profile state
- stale browser PID markers are deleted during the same pre-maintenance liveness repair pass

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

First-cut browser layout:

```text
instances/<instance-id>/browser/profile/
instances/<instance-id>/browser/chrome.pid
instances/<instance-id>/browser/chrome.log
```

Port rule:

- launcher allocates the browser port during instance startup
- allocation and final `instance.json.browser_port` write happen while holding the runtime lock
- prefer the first free port in `9222..9321`
- if Chrome fails because the chosen port became unavailable before startup publishes the launcher marker, retry the next free port in that range under the same startup/bootstrap critical section
- store the final port in `instance.json.browser_port`

MCP rule:

- the MCP server name may remain `chrome-devtools-cockpit`
- uniqueness comes from the per-instance `CODEX_HOME/config.toml`, not from globally unique MCP names
- each instance config points that server at its own `http://127.0.0.1:<browser_port>` endpoint
- product-mode host execution must use only instance-scoped browser MCP endpoints
- product-mode `CODEX_HOME/config.toml` loads only the instance-bound `chrome-devtools-cockpit` endpoint
- any generic `chrome-devtools` MCP bootstrap, if retained, must live in a separate debug config that product-mode sessions do not load

Auth bootstrap rule:

- launcher may copy existing Codex auth into instance-local `codex-home/auth.json`
- launcher must not live-share the source `CODEX_HOME`
- browser cookies/session state come only from the instance browser profile, not a shared browser profile

Shutdown rule:

- when launcher started the browser process, normal launcher exit terminates that browser PID and removes the PID marker
- if browser termination fails, the launcher leaves the PID marker as a deletion guard and still clears launcher liveness only after recomputing launcher marker state
- standalone `browser ensure/status` commands are not part of the product-mode hot path; they may remain temporarily as debug/compatibility commands if they are zero-active safe

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
${BUDDYSWITCH_SHARED_ROOT}.lock
```

First-cut lock rule:

- this is the only runtime lock; do not introduce a second state-internal lock
- the lock path is outside the launcher root so `reset --yes` can delete and recreate `${BUDDYSWITCH_SHARED_ROOT}/` while still serializing with concurrent runtime commands
- use one exclusive file lock, not a reader/writer lock
- implement the lock once in Python with `fcntl.flock`
- shell launcher and cleanup paths acquire it through that Python helper instead of open-coding lock behavior
- timeout defaults to 30 seconds, then fails with a clear "runtime state busy" error
- no stale-lock cleanup is needed because `flock` releases on process exit

The lock covers exactly these critical sections:

### Critical Section 0: startup/bootstrap

Exclusive lock required from the first `start --buddy <buddy>` read or write of `${BUDDYSWITCH_SHARED_ROOT}` through:

- shared-root directory preparation
- zero-active migration and migration conflict checks
- instance directory creation
- projection symlink setup
- initial `instance.json` creation
- browser port allocation and final `instance.json.browser_port` write
- `launcher-*.json` publish and `instance.json.status = active`

Startup must either publish the launcher marker and active status before releasing the lock, or roll back its partial marker/status writes before releasing it. There must be no window where startup has mutated shared runtime state but zero-active maintenance can pass because no launcher marker is visible.

The lock is not held for the interactive Codex session lifetime.

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

Reservation invariants:

- each reservation records `run_id`, `task_id`, `context_revision`, `sequence`, and product-mode `instance_id`
- new reservations always record `instance_id`; product-mode uses the actual instance id and dev-mode uses the literal `dev`
- active means a reservation file exists with `status = "reserved"` for a task whose product-mode `instance_id` is live
- `dev` reservations are local/debug reservations; later dev-mode resolves may replace them, and product-mode resolves may prune them before enforcing the one-active-reservation rule
- at most one active reserved run may exist per task
- `resolve` rejects a second active reservation for the same task from another live instance
- `resolve` from the same instance deletes that instance's previous still-reserved reservation for the same task, then writes the new reservation
- product-mode `resolve` keeps at most one still-reserved reservation per live instance across all tasks; before a successful resolve writes a new reservation, it deletes that instance's prior still-reserved reservation even when it belongs to another task
- `resolve` deletes stale reservations for inactive instances before checking the one-active-reservation rule
- `persist` validates the consumed reservation, commits canonical writes, deletes the consumed reservation, then writes the next `refreshed_context` reservation inside the same lock hold
- `persist` validates reservation `instance_id` when product-mode env is present
- zero-active maintenance may delete leftover reservations from inactive instances
- a rejected second resolve should tell the host to finish the active turn or retry after the active reservation clears rather than silently producing another same-sequence context

### Critical Section B: persist

Exclusive lock required from:

- revision / fingerprint / run validation against shared state

through:

- all task / track / artifact / run writes
- follow-up `refreshed_context` reservation when persist succeeds

The runtime consistency model is:

- shared-state projection readers such as `/api/workspace` take the same exclusive lock briefly while building a JSON snapshot
- resolve, persist, and maintenance mutations take the same exclusive lock
- this may serialize more than strictly necessary, but it is simpler and safer for the first cut

This is intentionally blunt.

Clarity is more important than optimistic multi-writer behavior. If this becomes a measured bottleneck, a later cut can replace the exclusive lock with a reader/writer lock.

### Critical Section C: maintenance operations

Operations that stage, rebuild, sync, reset, or delete shared runtime state must not run concurrently with live instances.

The rule is:

- maintenance commands are forbidden while any BuddySwitch instance is active
- maintenance commands that still touch the shared state plane must also hold the same exclusive runtime lock
- any maintenance path that swaps projected runtime state must do so atomically so `/api/workspace` readers never observe torn state

This applies to any remaining equivalents of:

- legacy `workspace sync` if retained during the cut
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

- product-mode startup no longer depends on standalone `browser status`
- product-mode startup no longer depends on standalone `browser ensure`
- target product-mode runtime has no shared execution workspace for `workspace sync` to refresh
- any retained `workspace sync` command is legacy development compatibility only
- if retained, `workspace sync` may operate only on the old `${BUDDYSWITCH_SHARED_ROOT}/workspace` when no `instances/` tree exists and no launcher is active
- if an `instances/` tree exists, `workspace sync` must fail closed with a clear "no product-mode sync target" message
- `workspace sync` must not rebuild stored inactive instance workspaces because resume/reopen is out of scope
- start creates each new instance workspace from repo `HEAD`; that is the first-cut code refresh path
- keep `scripts/cleanup_buddyswitch.sh` as the scoped zero-active-only cleanup helper
- keep `buddyswitch-codex reset --yes` as the full-root wipe command

Maintenance command meanings are explicit:

- `scripts/cleanup_buddyswitch.sh --agent <buddy>`
  deletes shared BuddySwitch state attributable to that buddy, prunes deleted task ids from shared tracks, deletes empty tracks, leaves surviving track routing fields untouched, and deletes instance-local runtime scratch for all stored instances bound to that buddy. Run attribution reads `switch.buddy_id` first and legacy `switch.buddy` second.
- `scripts/cleanup_buddyswitch.sh --all-agents`
  deletes shared BuddySwitch state for all buddies and deletes instance-local runtime scratch for all stored instances
- `scripts/cleanup_buddyswitch.sh --project app`
  deletes only instance-local `projects/app/.runtime/` data across stored instances
- `scripts/cleanup_buddyswitch.sh --all-storage`
  deletes shared BuddySwitch state plus every stored instance `workspace/`, `run/`, `home/`, `codex-home/`, `xdg-config/`, and `browser/`; it does not delete any external auth source outside the launcher root
- `buddyswitch-codex reset --yes`
  acquires `${BUDDYSWITCH_SHARED_ROOT}.lock`, then deletes the entire launcher root, including shared state, all instance trees, and launcher-managed profile/bootstrap state

> Superseded for lifecycle CLI: explicit `instance open <instance-id>` and `instance delete <instance-id> --yes` are now planned as a narrow product-facing lifecycle cut. Smart reuse, broad per-instance maintenance APIs, and workspace rebuild/sync remain out of scope.

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

Required env for product-mode Codex:

```text
BUDDYSWITCH_ACTIVE_BUDDY=<buddy>
BUDDYSWITCH_INSTANCE_ID=<instance-id>
BUDDYSWITCH_INSTANCE_JSON=<path-to-instance.json>
BUDDYSWITCH_SHARED_ROOT=<launcher-root>
HOME=<instance-home>
CODEX_HOME=<instance-codex-home>
XDG_CONFIG_HOME=<instance-xdg-config>
```

These env vars are the implementation boundary for the session adapter, state projection, and browser bootstrap. They avoid hidden global runtime state.

`BUDDYSWITCH_SHARED_ROOT` is for launcher/runtime helper discovery of the lock and projection roots. Canonical resolve/persist code must continue to read and write the repo-relative projected paths, not use an env var as a second state authority.

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

Prompt asset drift rule:

- `tools/launcher/assets/runtime-AGENTS.md` remains the generic baseline source during the cut
- buddy assets are checked-in concrete files under `tools/launcher/assets/buddies/<buddy>/AGENTS.md`
- repo consistency tests check the runtime header, canonical loop, and session adapter rules across every buddy asset
- tests should not require byte-for-byte duplication of the generic baseline, because buddy overlays are expected
- no runtime prompt generator is introduced in the first cut

## What Must Be Removed

The hot path should delete, not preserve:

- generic runtime `AGENTS.md` copy into one shared execution workspace
- router-driven multi-buddy product-mode session behavior
- shared `CODEX_HOME`
- shared browser profile assumptions
- implicit instance reuse behavior
- packet-era runtime concepts
- stale docs that preserve the wrong runtime model

## First-Cut Implementation Order

The implementation plan for this architecture should follow this order:

1. Add the single exclusive runtime lock helper and wrap startup/reset/maintenance critical sections before any product-mode shared-state mutation is enabled.
2. Add instance identity and launcher env wiring without changing runtime state semantics yet.
3. Move durable state to `${BUDDYSWITCH_SHARED_ROOT}/state` and project the four repo-relative paths into each instance workspace.
4. Add the product-mode session adapter in the `switch_runtime.py resolve/persist` CLI path, with resolve/persist binding writes inside the same runtime lock.
5. Switch browser bootstrap to per-instance profile, port, PID, log, and per-instance MCP config.
6. Add buddy prompt assets and update product-mode launcher copy behavior.
7. Update docs and tests that freeze the old shared-workspace/shared-browser model.

Do not batch unrelated cleanup into this cut. If a legacy surface is not on the hot path and is not blocking the migration, remove or document it only when it intersects one of the steps above.

## Verification Matrix

Minimum verification before declaring the cut implemented:

| Contract | Required proof |
|---|---|
| buddy-locked input | plain text resolves for active buddy; malformed `switch` text without canonical structure is treated as plain demand; same-buddy canonical switch resolves; wrong-buddy canonical switch rejects before mutation; unknown buddy and partial product env reject before mutation |
| binding update | successful resolve/persist updates `instance.json`; failed resolve clears its reservation; failed pre-commit persist leaves binding unchanged; committed persist with binding failure returns the frozen committed-binding-failure response shape |
| state projection | two instances see the same task/track/artifact/run objects through repo-relative paths |
| `/api/workspace` paths | projected objects render canonical `buddyswitch/...` paths, never `${BUDDYSWITCH_SHARED_ROOT}/state/...` paths |
| lock correctness | concurrent same-task resolves cannot create two same-sequence active reservations |
| reset lock safety | concurrent reset and start/resolve/persist/maintenance serialize on `${BUDDYSWITCH_SHARED_ROOT}.lock`, even while reset deletes `${BUDDYSWITCH_SHARED_ROOT}/` |
| startup/bootstrap lock | startup migration, projection setup, instance creation, browser port allocation, launcher marker publish, and active status write happen under `${BUDDYSWITCH_SHARED_ROOT}.lock`; maintenance cannot pass zero-active during partial startup |
| reservation lifecycle | same-instance re-resolve replaces the prior still-reserved reservation; same-instance retarget clears the old task reservation; other-instance resolve rejects; inactive-instance reservation is pruned |
| persist atomicity | persist consumes the old reservation and writes the next refreshed reservation under one lock; double persist of the old reservation rejects without new writes |
| binding failure | resolve binding-write failure clears its reservation; committed persist with binding-write failure returns top-level `ok = true`, explicit `W_INSTANCE_BINDING_UPDATE_FAILED`, `refreshed_context.error.code = E_RUNTIME_REFRESH_CONTEXT`, preserves canonical writes, and makes plain-text continuation unsafe until rerun resolve |
| `/api/workspace` lock | workspace snapshot under concurrent persist shows either pre-write or post-write state, never torn projected paths |
| maintenance atomicity | cleanup/reset/retained legacy workspace sync hold the runtime lock for shared-state mutation or projection swaps, and `/api/workspace` never observes torn state |
| projection deletion safety | instance workspace/scratch cleanup unlinks projected symlinks without following them into shared state; shared-state deletion happens only in commands that explicitly delete shared BuddySwitch state |
| maintenance safety | cleanup and reset refuse while any live launcher marker is active; retained legacy workspace sync refuses while live launcher markers are active and fails closed once `instances/` exists |
| startup liveness race | start publishes `launcher-*.json` and `instance.json.status = active` under the runtime lock before maintenance can pass a zero-active check |
| legacy marker safety | live legacy `launcher-*.pid` blocks maintenance; live legacy `browser-cockpit.pid` blocks reset/storage cleanup; stale legacy markers are removed |
| liveness repair | stale launcher markers are removed and `instance.json.status` is repaired from PID-marker truth before zero-active maintenance |
| browser deletion guard | live per-instance `browser/chrome.pid` blocks deletion of that instance browser/profile tree |
| cleanup attribution | cleanup reads run attribution from `switch.buddy_id` first and legacy `switch.buddy` second, prunes deleted task ids from shared tracks, and deletes empty tracks |
| browser isolation | two active instances get different profile dirs, ports, PID files, logs, and MCP endpoints; product-mode `CODEX_HOME/config.toml` loads only the instance-bound cockpit MCP endpoint; any generic `chrome-devtools` config is separate and not loaded by product sessions |
| prompt isolation | each instance root gets the selected buddy's `AGENTS.md` and preserves the runtime header |
| migration | old shared-workspace durable state moves once into shared state when state is empty; empty dirs and `.DS_Store` count empty; invalid durable JSON fails closed; `reserved/**` is pruned and ignored for empty/conflict checks; conflicting old/new state fails closed |

## Final Target

The target architecture is:

`multi-instance, buddy-locked BuddySwitch with one shared canonical state store, one isolated execution workspace per instance, one buddy-specific AGENTS.md per instance workspace, one isolated Codex/browser profile per instance, one canonical resolve/persist loop, and no double buddy authority`

That is the clearest shape that matches the product requirement:

- multi-buddy collaboration
- clear isolation
- minimal runtime ambiguity
- no compatibility-heavy drag
