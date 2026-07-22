# Web Actor Start Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan inline and `buddyswitch-testing` for every executable proof. Steps use checkbox (`- [ ]`) syntax for resumable tracking.

**Goal:** Make Start and Retry appear as one actor lifecycle in the Team room: one row progresses through Starting/Retrying to Active or Start failed, non-ready actors never trigger identity-backed reads, and Retry is one backend-owned Delete + Start(same role, fresh actor id) action.

**Architecture:** Private Host Control owns attempt identity, Start failure cleanup, retry validation, and ordered Delete + Start composition. Web Management projects Host Control instance facts and active lifecycle operations into one browser actor DTO with one `lifecycle_state`; the browser renders that state and never treats an operation id as a teammate. Existing operation polling remains transient progress infrastructure, not actor identity or a second lifecycle owner.

**Tech Stack:** Python Host Control facade and Web service; Bash lifecycle owner and JSON instance records; dependency-free JavaScript/HTML/CSS; Python `unittest`, Node `node:test`, system launcher fixtures, and the repository-only `./buddyswitch-test focused` entry; real in-app browser acceptance against a locally started Web service.

**Commit policy:** The user explicitly overrides the generic frequent-commit recommendation. Keep the work uncommitted while RED/GREEN/refactor and browser acceptance are in progress, then create one coherent implementation commit after final proof and review. Do not force-add ignored files.

---

## Acceptance Sentence

When a user starts an actor, the Team room shows exactly one actor row with a stable preassigned actor id; that row moves from `Starting` to `Active` or `Start failed`, startup-only states make no actor-console or conversation request, a failed published actor exposes only `Retry` and `Delete`, and Retry replaces it through one server action with the same role and a fresh actor id without duplicate rows.

Consumer paths:

```text
Start(role)
  -> Host Control allocates actor id
  -> Web operation targets actor id before enqueue
  -> Host Control starts that exact id
  -> Web /api/actors merges operation + instance + failure
  -> browser renders one Starting row
  -> Active, or Start failed with Retry/Delete

Retry(failed actor)
  -> Host Control validates inactive + last_failure and captures role
  -> Host Control allocates replacement id
  -> one Web retry operation correlates previous + replacement ids
  -> Host Control Delete(previous) then Start(role, replacement)
  -> browser keeps one Retrying row
  -> replacement Active, replacement Start failed, or Start panel failure
```

Protected contracts: none. Host Control and Web are private internal interfaces in Sharp mode. Replace retired empty-id Start operations, independent operation teammate rows, eager startup interaction reads, and Resume on failed Start directly; do not add aliases or fallback rendering.

## Current Evidence And Root-Cause Hypothesis

- `tools/launcher/host_control.sh::start_codex` currently allocates the actor id only inside the blocking launcher command.
- `start_locked_bootstrap` publishes `instance.json` as `inactive` before runtime startup finishes.
- `_run_lifecycle_operation_worker` patches `operation.target.actor_id` only after command success.
- `_list_actor_rows` currently projects only instance rows, while `renderActorRowsHtml` separately renders active Start operations as `op-*` teammate rows.
- `loadActorSelection` unconditionally requests `/api/actors/{id}/console` and the direct conversation for every actor row, including an early inactive startup record.
- published failures before app-server startup and daemon failure do not all flow through `buddyswitch_start_failure_cleanup`; `instance_status_json` and `buddyswitch_instance_list` omit the already persisted `last_failure` fact.

Single hypothesis to prove: the escaped defect exists because attempt identity and published-failure facts are unavailable at the Web projection boundary, forcing the browser to combine unrelated partial facts. Giving Host Control one preassigned attempt id, one failure-cleanup path, and Web one lifecycle projection removes both duplicate identity and premature interaction without a new state engine.

## File Responsibility Map

**Create**

- `tests/unit/web/ui_state_start_recovery.test.js` — exact browser states, interaction gating, Retry/Delete actions, and old/new id reconciliation.

**Modify**

- `docs/memo/2026-07-18-web-actor-start-recovery-design.md` — mark the approved design as implementation-authorized.
- `tools/launcher/host_control.py` — own actor-id allocation, supplied-id Start, retry planning/validation, ordered Delete + Start composition, and nullable failure contract validation.
- `tools/launcher/host_control.sh` — accept the preassigned id, route every post-publication Start phase through one cleanup owner, and expose `last_failure` in status/list JSON.
- `tools/launcher/env.sh` — atomically clear invalid startup runtime fields and persist the canonical `last_failure` record in one instance-record write.
- `tools/launcher/web_management.py` — add Retry API, preassign Start/Retry ids before enqueue, and compose the unified `/api/actors` lifecycle projection.
- `tools/launcher/assets/web-management/app.js` — consume `lifecycle_state`, remove operation-as-teammate state/rendering, gate interaction loads, and reconcile Retry identity replacement.
- `tools/launcher/assets/web-management/index.html` — add the single Retry action beside existing lifecycle actions.
- `tools/launcher/assets/web-management/styles.css` — style `Needs attention` and pending rows using existing visual tokens only.
- `tests/process/cli/test_host_control.py` — RED/GREEN private owner contract for supplied ids, failure facts, and Retry ordering/failure effects.
- `tests/integration/web/management_harness.py` — current Host Control fake methods for allocation, retry planning, and retry execution.
- `tests/integration/web/test_management_http.py` — Start/Retry operation and HTTP failure semantics.
- `tests/integration/web/test_management_product_api.py` — one-row lifecycle projection and external IM separation.
- `tests/unit/web/ui_state_create.test.js` — replace empty-id/operation-context expectations with stable actor-row behavior while retaining concurrent Start coverage.
- `tests/unit/web/ui_state_lifecycle.test.js` — action-state and terminal reconciliation coverage for `start_failed`/`retrying`.
- `tests/unit/web/ui_state_roster_actions.test.js` — lifecycle grouping and selection assertions without `data-operation-id` rows.
- `tests/unit/web/ui_state_selection_refresh.test.js` — current actor-id Start completion behavior.
- `tests/unit/web/ui_state_harness.js` — Retry element and lifecycle-aware actor fixture support.
- `tests/unit/web/asset_contract_html.test.js` and `tests/unit/web/asset_contract_javascript.test.js` — production Retry control/API and retired operation-row absence.

**Verify unchanged**

- `tests/process/launcher/test_instance_commands.py` — private shell arity/identity and current-record output assertions.
- `tests/system/instance_lifecycle/test_startup.py` — real published-failure cleanup and residue proof.
- `tests/unit/architecture/test_external_control.py` — external-control dependency boundary.

No new persistence service, database, operation store, event bus, state-machine module, public CLI command, or compatibility DTO is created.

## Resumable State

- FRAME: complete in the approved design memo and acceptance sentence above.
- TRACE: complete for Host Control Start/cleanup, Web operation/projection, browser roster/selection, and direct affected tests.
- PROVE: begins at Task 1 with exact RED targets.
- Current worktree baseline at plan creation: `56becff`; design memo is the only task commit and no executable changes exist.
- Only public test entry: `./buddyswitch-test focused <explicit-target>...`.
- Browser acceptance must use a real Web service and real DOM interaction; static HTML inspection is supplementary only.

## Task 1: Establish The Private Host Control Attempt Contract

**Files:**

- Modify: `tests/process/cli/test_host_control.py`
- Modify: `tools/launcher/host_control.py`
- Modify: `tools/launcher/host_control.sh`

- [x] Add `test_start_uses_owner_allocated_actor_id_at_every_private_boundary` with a patched deterministic UUID. Assert `allocate_actor_id("pm") == "act-pm-0123456789ab"`, `start("pm", actor_id=...)` passes exactly `[role, executable, version, actor_id]` to the script runner, and the returned payload must contain the identical id.
- [x] Add `test_start_rejects_private_result_with_different_actor_id` and assert `HostControlError("COMMAND_FAILED", ...)` rather than aliasing or accepting the mismatch.
- [x] Update the exact public-facade signature assertion to include `allocate_actor_id(role_id)`, `start(role_id, actor_id)`, `prepare_retry(actor_id)`, and `retry(actor_id, replacement_actor_id)` as current interfaces; remove the retired three-argument private Start expectation.
- [x] Run RED:

  ```bash
  ./buddyswitch-test focused \
    tests/process/cli/test_host_control.py::HostControlTests::test_start_uses_owner_allocated_actor_id_at_every_private_boundary \
    tests/process/cli/test_host_control.py::HostControlTests::test_start_rejects_private_result_with_different_actor_id
  ```

  Expected: failure because allocation and supplied-id Start do not exist.

- [x] Implement `HostControl.allocate_actor_id(role_id)` with `validate_role_id` and `uuid4().hex[:12]`; keep id allocation in this owner, not Web or Bash.
- [x] Change `HostControl.start(role_id, actor_id=None)` to allocate when omitted, validate a supplied id, call the shell with four exact arguments, and fail if the result id differs.
- [x] Change `host_control.sh::start_codex` and `host_control_start` to require the fourth preassigned actor id, validate it before binding/mutation, and remove Bash UUID generation from the Start path. Keep `buddyswitch_generate_actor_id` only if another live caller exists; otherwise remove it as residue.
- [x] Re-run the exact RED command and expect GREEN.

## Task 2: Make Published Start Failure One Canonical Host Control Fact

**Files:**

- Modify: `tests/system/instance_lifecycle/test_startup.py`
- Modify: `tests/process/cli/test_host_control.py`
- Modify: `tools/launcher/env.sh`
- Modify: `tools/launcher/host_control.sh`
- Modify: `tools/launcher/host_control.py`

- [x] Extend `test_start_bootstrap_retry_failure_cleans_state_and_records_failure` to assert the single failed record has `status=inactive`, null app-server fields, null browser port, null top-level thread id, a structured `last_failure`, and no app-server/runtime-broker/daemon/browser process, socket, pid, or marker residue.
- [x] Add a structural owner test that extracts `start_locked_bootstrap` and asserts every post-`buddyswitch_instance_activate` phase name appears in a call to the one phase wrapper: `capability_seed`, `runtime_broker_ensure`, `codex_config_patch`, `env_mcp_ensure`, `browser_register`, `app_server_ensure`, `thread_start`, `thread_bootstrap`, and `daemon_start`. Assert no direct failure cleanup block remains for an individual phase.
- [x] Add facade tests that valid status/list rows require a present nullable `last_failure`, accept either `null` or an object, and reject a non-object value.
- [x] Run RED:

  ```bash
  ./buddyswitch-test focused \
    tests/system/instance_lifecycle/test_startup.py \
    tests/process/cli/test_host_control.py
  ```

  Expected: failure because failure facts are omitted from status/list and not all phases share cleanup.

- [x] Replace the current multi-write cleanup with one `buddyswitch_instance_record_failure` write that sets `status="inactive"`, clears `app_server_pid`, `app_server_socket`, `app_server_log`, `browser_port`, and top-level `thread_id`, and persists `{phase,message,failed_at}` plus diagnostic thread/browser identifiers only when present.
- [x] Expand `buddyswitch_start_failure_cleanup` to idempotently stop daemon, app server, runtime broker, and browser manager before the canonical record write. Preserve the primary phase failure message; print cleanup warnings only to diagnostics/stderr.
- [x] Add one small `buddyswitch_run_published_start_phase` wrapper that captures output/status, calls the common cleanup on failure, and returns output to the caller on success. Route every phase listed above through it; keep pre-publication actor-environment failure outside it.
- [x] Include `last_failure` in `instance_status_json`, `buddyswitch_instance_list`, invalid-row shape (`null`), `_runtime_row` only where diagnostics need it, and Host Control facade validators.
- [x] Re-run the same focused command and expect GREEN with the runner reporting clean residual state.

## Task 3: Define Retry As One Ordered Host Control Capability

**Files:**

- Modify: `tests/process/cli/test_host_control.py`
- Modify: `tools/launcher/host_control.py`

- [x] Add `test_prepare_retry_requires_inactive_start_failure_and_allocates_same_role_replacement` covering: missing actor, active actor, normally stopped actor (`last_failure=null`), malformed role, and accepted failed actor. Accepted output must be exactly previous id, replacement id, and role.
- [x] Add `test_retry_revalidates_then_deletes_before_starting_same_role_with_replacement_id`. Use a recording runner/facade boundary and assert the ordered calls are status -> delete -> start; the replacement differs from the previous id and the same role is passed to Start.
- [x] Add `test_retry_delete_failure_does_not_start` and `test_retry_start_failure_keeps_delete_effect_without_restoring_old_actor`. Assert errors propagate unchanged and no rollback/old-id restart occurs.
- [x] Run RED:

  ```bash
  ./buddyswitch-test focused \
    tests/process/cli/test_host_control.py::HostControlTests::test_prepare_retry_requires_inactive_start_failure_and_allocates_same_role_replacement \
    tests/process/cli/test_host_control.py::HostControlTests::test_retry_revalidates_then_deletes_before_starting_same_role_with_replacement_id \
    tests/process/cli/test_host_control.py::HostControlTests::test_retry_delete_failure_does_not_start \
    tests/process/cli/test_host_control.py::HostControlTests::test_retry_start_failure_keeps_delete_effect_without_restoring_old_actor
  ```

  Expected: failure because Retry does not exist.

- [x] Implement one private validator used by both `prepare_retry` and `retry`: require valid actor id, status `inactive`, non-empty valid role, and dict `last_failure`; report `LIFECYCLE_BLOCKED` for active/stopped instances.
- [x] `prepare_retry` performs synchronous validation and returns the owner-issued replacement id for the Web operation target.
- [x] `retry` revalidates immediately before mutation, verifies the supplied replacement id, calls existing `delete`, then ordinary `start(role, actor_id=replacement)`, and returns the Start result plus `previous_actor_id` and replacement `actor_id`.
- [x] Do not add a shell retry command, transaction, rollback, copied failure state, or browser orchestration; Python Host Control is the composition owner over existing private lifecycle capabilities.
- [x] Re-run the exact RED command and expect GREEN.

## Task 4: Build The Unified Web Actor Projection And Retry API

**Files:**

- Modify: `tests/integration/web/management_harness.py`
- Modify: `tests/integration/web/test_management_http.py`
- Modify: `tests/integration/web/test_management_product_api.py`
- Modify: `tools/launcher/web_management.py`

- [x] Extend `RecordingHostControl` with deterministic `allocate_actor_id`, `prepare_retry`, and `retry` methods whose call arguments are recorded exactly; update `start` to accept a supplied actor id.
- [x] Change the existing Start HTTP RED test to assert the accepted operation already has non-empty `target.actor_id`, the worker calls `start(role, actor_id)`, and the target id never changes after completion.
- [x] Add `test_retry_route_returns_one_operation_with_previous_and_replacement_ids` and assert `POST /api/instances/{failed}/retry` synchronously calls `prepare_retry`, returns 202, protects conflicts through the failed id, and asynchronously calls `retry(failed,replacement)` once.
- [x] Add Retry failure tests for validation (no operation/mutation), Delete failure (failed operation, original row), unpublished replacement failure (failed operation with both ids), and success (result previous id + replacement id + replacement status).
- [x] Add projection tests with exact actor DTO assertions:
  - active Start + no instance -> one synthetic `starting` row;
  - active Start + early inactive instance -> one merged `starting` row with no health presentation override;
  - inactive + `last_failure` -> `start_failed`;
  - inactive + null failure -> `stopped`;
  - active -> `active`;
  - active Retry before publication -> one `retrying` row using previous id and carrying replacement id;
  - active Retry after replacement publication -> one `retrying` row using replacement id and carrying previous id;
  - no separate row exists for operation/previous/replacement during Retry.
- [x] Run RED:

  ```bash
  ./buddyswitch-test focused \
    tests/integration/web/test_management_http.py \
    tests/integration/web/test_management_product_api.py
  ```

  Expected: failure on empty Start target, absent Retry route, and absent lifecycle projection.

- [x] In `_create_instance`, call Host Control allocation before `_start_lifecycle_operation`; set `target={actor_id,role}` and pass the exact id to `_create_instance_under_lock`.
- [x] Parse `/retry` as an explicit instance action before the generic Delete route. `_retry` calls `prepare_retry` synchronously, then enqueues one action `retry` with `actor_id`, `replacement_actor_id`, and `role`; `_retry_under_lock` delegates to Host Control retry and fetches replacement status only on success.
- [x] Replace `_list_actor_rows` with one direct projection function. Snapshot active operations under `_operation_lock`; classify instance rows once; merge Start by exact id; correlate Retry by previous/replacement ids; attach the active operation payload for polling restoration; enforce classifier precedence `retrying -> starting -> start_failed -> active -> stopped`.
- [x] Keep `_external_im_actor_rows` on raw Host Control instance rows rather than the browser lifecycle projection so synthetic Starting/Retrying rows do not become IM identities.
- [x] Remove worker `target_patch`; a lifecycle target is immutable after enqueue. Reject result/target actor-id mismatch at the owner boundary instead of reconciling it.
- [x] Re-run the exact RED command and expect GREEN.

## Task 5: Replace Operation Teammates With Lifecycle Actor Rows

**Files:**

- Create: `tests/unit/web/ui_state_start_recovery.test.js`
- Modify: `tests/unit/web/ui_state_create.test.js`
- Modify: `tests/unit/web/ui_state_lifecycle.test.js`
- Modify: `tests/unit/web/ui_state_roster_actions.test.js`
- Modify: `tests/unit/web/ui_state_selection_refresh.test.js`
- Modify: `tests/unit/web/ui_state_harness.js`
- Modify: `tools/launcher/assets/web-management/app.js`

- [x] Add RED renderer tests asserting `starting`, `active`, `start_failed`, `retrying`, and `stopped` rows land in `Starting`, `Active`, `Needs attention`, `Starting`, and `Stopped` groups respectively; a starting instance never also appears under Stopped; health is absent for Starting/Retrying; operation ids and `data-operation-id` are absent.
- [x] Add `test_starting_retrying_and_failed_selection_never_fetch_identity_surfaces`. Select each state with a fetch spy and assert zero `/console` and `/api/im/conversations/direct` requests while the row remains selected and readable.
- [x] Add `test_create_selects_preassigned_actor_row_without_operation_context`. The Start response contains `target.actor_id`; assert one actor row, `selectedActorId` is that id, no `selectedLifecycleOperationId` state exists, actions/composer are disabled, and polling remains active.
- [x] Add terminal tests: successful Start upgrades the same row and only then loads console/conversation; unpublished failure removes the provisional row and preserves selected role/error; published failure refreshes into one `start_failed` row.
- [x] Add Retry tests: action posts once to `/retry`; selected failed row becomes `retrying`; success removes previous id and selects the replacement; published failure shows one replacement `start_failed`; unpublished failure removes the row and preserves the role; no moment renders two rows.
- [x] Replace old tests that explicitly protect blank actor ids, `op-*` roster rows, operation selection context, or all-inactive Resume. Preserve meaningful concurrent Start, stale-request, newer-user-selection, and polling tests using preassigned actor ids.
- [x] Run RED:

  ```bash
  ./buddyswitch-test focused \
    tests/unit/web/ui_state_start_recovery.test.js \
    tests/unit/web/ui_state_create.test.js \
    tests/unit/web/ui_state_lifecycle.test.js \
    tests/unit/web/ui_state_roster_actions.test.js \
    tests/unit/web/ui_state_selection_refresh.test.js
  ```

  Expected: failures against operation-row rendering, eager selection reads, and missing Retry.

- [x] Make `actor.lifecycle_state` the only roster classifier. `actorIsStopped` means only `stopped`; add small predicates for interactive (`active` or `stopped`) and startup-only (`starting`, `retrying`, `start_failed`) states.
- [x] Delete `renderStartOperationRowHtml`, `selectedLifecycleOperationId`, `selectLifecycleOperationContext`, operation-row click handling, and operation-id selected context. Record active operations from actor payloads and responses only for polling/action protection.
- [x] Start response upserts a lifecycle actor from its target id, records the operation, selects the actor row through the normal selection owner, and relies on readiness gating to avoid network reads.
- [x] Gate `loadActorSelection`, periodic console refresh, manual refresh, capability/attach/message tools, and conversation fetches with the interactive predicate. Startup-only selection renders lifecycle detail and settles immediately without an AbortController-backed request.
- [x] Reconcile terminal Start/Retry by refreshing `/api/actors`; follow previous/replacement ids supplied by Retry; remove provisional rows only when no published replacement exists. Do not maintain a browser-side Delete+Start sequence.
- [x] Re-run the exact RED command and expect GREEN.

## Task 6: Expose Only Retry/Delete For Start Failure

**Files:**

- Modify: `tests/unit/web/asset_contract_html.test.js`
- Modify: `tests/unit/web/asset_contract_javascript.test.js`
- Modify: `tests/unit/web/asset_contract_styles.test.js`
- Modify: `tools/launcher/assets/web-management/index.html`
- Modify: `tools/launcher/assets/web-management/styles.css`
- Modify: `tools/launcher/assets/web-management/app.js`

- [x] Add asset RED assertions for exactly one `retry-button`, one `/retry` API path, a `Needs attention` group, and no operation-row selector/renderer markers.
- [x] Add action-state assertions:

  ```javascript
  computeInstanceActionState({ lifecycle_state: 'start_failed' }, ...)
  // canRetry: true, canDelete: true; every other action false
  ```

  Assert `stopped` retains Resume/Delete and `starting`/`retrying` expose no actions.
- [x] Run RED:

  ```bash
  ./buddyswitch-test focused \
    tests/unit/web/asset_contract_html.test.js \
    tests/unit/web/asset_contract_javascript.test.js \
    tests/unit/web/asset_contract_styles.test.js \
    tests/unit/web/ui_state_start_recovery.test.js
  ```

  Expected: failure because the production control/API/state styles do not exist.

- [x] Add `Retry` to the compact header without a confirmation modal. Bind it through the same lifecycle-action runner and render it only for `start_failed`; keep Delete's existing exact-id confirmation unchanged.
- [x] Render safe failure phase/message in selected detail, `start failed` badge, and `Needs attention` roster group. Reuse current button/badge tokens; add only narrow attention/pending selectors needed for visual hierarchy and focus.
- [x] Hide Resume for `start_failed`; hide console, capability, tools, composer interaction, and health for all startup-only states.
- [x] Re-run the exact RED command and expect GREEN.

## Task 7: Replacement, Architecture, And Focused Impact Proof

**Files:** all changed source/tests above.

- [x] Run one frozen focused IMPACT set after implementation/refactor stops changing:

  ```bash
  ./buddyswitch-test focused \
    tests/process/cli/test_host_control.py \
    tests/process/launcher/test_instance_commands.py \
    tests/system/instance_lifecycle/test_startup.py \
    tests/integration/web/test_management_http.py \
    tests/integration/web/test_management_product_api.py \
    tests/unit/web/ui_state_start_recovery.test.js \
    tests/unit/web/ui_state_create.test.js \
    tests/unit/web/ui_state_lifecycle.test.js \
    tests/unit/web/ui_state_roster_actions.test.js \
    tests/unit/web/ui_state_selection_refresh.test.js \
    tests/unit/web/asset_contract_html.test.js \
    tests/unit/web/asset_contract_javascript.test.js \
    tests/unit/web/asset_contract_styles.test.js \
    tests/unit/architecture/test_external_control.py
  ```

- [x] Record evidence identity: repo root, HEAD, tracked patch hash, non-ignored untracked files, command, environment, exit summary, duration, cleanup result, exact claims, and residual risk.
- [x] Run replacement searches:

  ```bash
  rg -n "renderStartOperationRowHtml|selectedLifecycleOperationId|data-operation-id|target_patch|actor identity profile not found" \
    tools/launcher/web_management.py tools/launcher/assets/web-management tests/unit/web tests/integration/web

  rg -n "last_failure|lifecycle_state|replacement_actor_id|/retry" \
    tools/launcher/host_control.py tools/launcher/host_control.sh tools/launcher/env.sh \
    tools/launcher/web_management.py tools/launcher/assets/web-management tests
  ```

  Expected: first command finds no live retired operation-teammate/late-target path (negative tests may name retired markers only to prove absence); second shows one Host Control failure owner, one Web lifecycle classifier, and direct consumers/tests.

- [x] Inspect `git diff --check`, rename-aware diff, and `git status --short`. Confirm no ignored file was forced into tracking, no unrelated user change was touched, no fallback DTO/classifier remains, and the plan/design accurately describe current truth.
- [x] Perform a reviewer pass over product, contract, architecture, replacement, and operations proofs. Run only finding-specific probes if review identifies a concrete risk; do not rerun unchanged evidence for freshness theater.

## Task 8: Real Web Service And In-App Browser Acceptance

**Runtime scope:** use launcher/service interfaces; do not edit runtime object files directly. Save optional screenshots only under ignored temporary evidence paths.

- [x] Resolve the exact command/process currently serving the BuddySwitch WebUI. Stop/restart only that known process if needed, then start the current worktree service on an available localhost port and verify `/api/health` plus static asset identity.
- [x] Use the in-app browser selected by the user and inspect the complete page documentation before interaction.
- [x] Exercise real normal Start through the UI:
  - choose a role and click Start;
  - immediately observe exactly one row with an `act-*` id under Starting;
  - verify there is no `op-*` teammate row, no Stopped duplicate, no health badge, and no identity-profile error;
  - verify lifecycle buttons, composer, console, capability, and tools are unavailable until Active;
  - wait for the same row to reach Active and verify normal console/conversation interaction becomes available.
- [x] Exercise real failed-state recovery safely. Prefer an existing naturally failed test actor or a test-owned temporary environment; do not sabotage the user's active actor. Verify `Needs attention`, safe failure text, Retry/Delete only, no Resume, no identity-backed requests, and unchanged Delete confirmation.
- [x] Click Retry once and verify one Retrying row, disabled actions, same role wording, no duplicate old/new row, then replacement id + Active or replacement Start failed according to the real result.
- [x] Inspect visual quality at the current desktop viewport and one narrow viewport: grouped roster counts, selection accent, button spacing, clipped/overflow text, status badge tone, header wrapping, no horizontal overflow, focus visibility, and no main-path browser console errors.
- [x] Delete only test-owned failed/replacement actors through the product Delete flow. Confirm service/test processes, sockets, pid files, and temporary acceptance state have no unintended residue. Leave the user's pre-existing actors and unrelated service state intact.

If a safe real failure cannot be induced without changing user runtime state, the real browser must still prove Start -> Active and all production failed/retry DOM states through the same served code using a test-owned Host Control fixture server; report that limitation explicitly rather than claiming a destructive real failure test.

## Task 9: Final Audit And One Coherent Commit

- [x] Re-read the approved design and this plan requirement by requirement. For every product, contract, architecture, replacement, and operations claim, point to current source plus exact automated or browser evidence; continue work for every missing/indirect item.
- [x] Use `superpowers:verification-before-completion`; if browser review changed executable code after IMPACT, rerun only invalidated focused targets, then the frozen IMPACT set once.
- [x] Do not run `./buddyswitch-test full`: the user requested complete task acceptance, not repository-wide merge/release FINAL, and `buddyswitch-testing` reserves full for that explicit boundary unless focused evidence reveals unresolved shared risk.
- [x] Run final source checks:

  ```bash
  git status --short
  git diff --check
  git diff --stat
  git diff --name-status
  ```

- [x] Stage only the coherent task files, review the staged diff and staged `--check`, then create one commit:

  ```bash
  git commit -m "fix(web): unify actor start recovery"
  ```

- [x] Verify the commit tree, clean worktree, and test evidence identity. Final report must name behavior/files, exact RED/GREEN/IMPACT commands, browser interaction evidence, cleanup result, omitted checks, residual risk, and commit id.

## Execution Evidence

- Final focused IMPACT run: `1e843b26f4514737b0165927a9e24f69` from `/Users/chen/Dev/buddyswitch/.worktrees/fea-webui`; Python `128 passed, 211 subtests passed`; JavaScript `96 passed`; exit 0; isolated run root `/private/tmp/bs-test-1e843b26-3zn_7waa` cleaned by the repository runner.
- Browser-discovered regression probes were captured before the frozen run: unrelated actors cannot inherit a Start operation through absent Retry ids; selected Retry detail uses the effective `retrying` state; startup refresh restores polling; failed selection/manual refresh performs no console or direct-conversation request; list skips an instance record removed concurrently by Delete.
- Real product Start acceptance on `http://127.0.0.1:8765/`: one `act-test-c3041757f1ba` Starting row with no operation row, Stopped duplicate, health, or identity error; the same id reached Active and normal identity-backed surfaces became available. The test-owned actor was stopped and deleted through the exact-id product flow; the two pre-existing actors were left unchanged.
- Safe failed/Retry acceptance on the same production assets and Web lifecycle service with a test-owned Host Control fixture at `http://127.0.0.1:8766/`: one Needs attention row, Retry/Delete only, no Resume, no console/direct-conversation request while failed, one `/retry` POST, one Retrying row, then one selected Active replacement `act-pm-replacement`. Fixture service and temporary state were removed.
- Responsive visual proof: default 843 px and desktop 1440 px both had `scrollWidth == viewportWidth`; failure heading/detail spacing, grouping, selection, actions, and status tones were inspected from screenshots; no warning/error console entries remained on the real page.
- Replacement search found retired operation-row/late-target/browser-pending terms only inside negative assertions; `git diff --check` passed; no ignored path, including `docs/superpowers/`, is part of the task diff.
- `./buddyswitch-test full` intentionally omitted because this is claim-scoped acceptance rather than a repository-wide release/merge candidate.
- One coherent local commit was created with subject `fix(web): unify actor start recovery`; the final commit id is recorded by the repository history and final task report.

## Acceptance Matrix

| Proof class | Claim | Required evidence |
|---|---|---|
| Product | Start/Retry remain one actor row; failure offers Retry/Delete only | Real browser interaction plus UI state tests |
| Contract | Start id is preassigned and immutable; Retry is ordered Delete + Start(same role,new id); failure effects are exact | Host Control process tests and Web HTTP integration tests |
| Architecture | Host Control owns identity/failure/retry; Web owns one lifecycle projection; browser only consumes it | Source review, direct contract tests, residue search |
| Replacement | Blank-id Start, operation teammate rows, eager startup reads, and Resume-on-failure are absent | Negative asset/state assertions and `rg` proof |
| Operations | Published failures clean resources and retain one diagnosable failed record; acceptance leaves no test residue | System lifecycle test, runner cleanup output, runtime process checks |

## Plan Self-Review

- Spec coverage: every approved design section maps to Tasks 1-9, including unpublished/published failure, old/new Retry identity, readiness gating, Delete confirmation, non-goals, replacement, and real UI acceptance.
- Type consistency: `actor_id` is the initial/failed correlation id; `replacement_actor_id` is Retry's preassigned new id; terminal Retry result uses `previous_actor_id` plus replacement `actor_id`; browser DTO uses exactly one `lifecycle_state` classifier owned by Web.
- Scope: one vertical slice across the existing lifecycle owner, adapter/projection, consumer, and direct tests. No speculative engine or unrelated lifecycle redesign.
- Placeholder scan: no TBD/TODO/"similar to" steps remain; every task names exact files, behavior, command, and expected RED/GREEN result.
