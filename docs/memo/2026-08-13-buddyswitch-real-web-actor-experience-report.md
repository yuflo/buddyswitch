# BuddySwitch Real Web Actor Experience Report

> **Run status:** COMPLETE — overall acceptance REJECTED, core loop functional
>
> **Execution date:** 2026-08-13 (Asia/Shanghai)
>
> **Scope:** observation and source-bound diagnosis only; no product repair
>
> **Plan:** [2026-08-13-buddyswitch-real-web-actor-experience-plan.md](2026-08-13-buddyswitch-real-web-actor-experience-plan.md)

## 1. Acceptance under test

From an empty launcher baseline, a user can discover and start the reviewed
`secondary-market-investor` Role in the Web UI, submit and continue durable
research, observe coherent delivery and progress, preserve the same work across
stop/resume, and delete the Instance with complete host-resource cleanup. Web,
public contracts, durable product state, and runtime terminal truth must agree.

The acceptance sentence is rejected as a whole. The primary product and
lifecycle loops complete, durable work survives restart, and host cleanup is
clean; however, public actor-filtered reads are wrong, accepted work is
temporarily reported as idle, daemon no-op retries are reported as failures, and
deletion briefly surfaces an internal traceback after the destructive effect has
already succeeded.

## 2. Frozen run identity

- repository: `/Users/chen/Dev/buddyswitch/.worktrees/fea-tool`
- entry source HEAD: `4010434`
- execution-plan commit: `84cfb11`
- installed package: `buddyswitch 0.1.0`
- installed source digest: `1b448cb325b59287913d2e2c52efa4303fe277c9669f19a3c3a623e67cc23921`
- installed distribution digest: `85ff440cd64eeb8a895af655a7e9b2372856df8fa03741b0534f24bb9887ce7f`
- runtime verification: `ok=true`
- Web endpoint: `127.0.0.1:8765`
- Role: `secondary-market-investor`
- Actor Instance: `act-secondary-market-investor-987558ab2fa7`
- Actor thread: `019ffacd-c61d-72b2-9f78-921ddc465536`
- entry product/runtime state: zero Instances, Tasks, Tracks, and attributable
  `bs-test-*` roots; Browser inactive; Web port free

## 3. Scenario record

### A. Empty state and Role creation — passed with UX friction

The Web UI loaded with `API Ready`, exposed the reviewed Role catalog, and
created exactly one Actor through the UI. The starting state appeared
immediately and protected destructive controls. The resulting Instance was
`active`, `healthy`, and backed by a live app server, daemon, and runtime broker.
No browser console error or warning was observed.

Evidence:

- [empty Team room](2026-08-13-buddyswitch-real-web-actor-experience-evidence/01-empty-team-room.jpg)
- [Actor starting](2026-08-13-buddyswitch-real-web-actor-experience-evidence/02-actor-starting.jpg)
- [Actor ready](2026-08-13-buddyswitch-real-web-actor-experience-evidence/03-actor-ready.jpg)

### B. First durable research task — passed

The Web composer accepted one request concerning Zhipu `02513`, acknowledged
the outbound Message, created one Demand and one Task, and completed a durable
research loop. The Actor created and later read back:

- Demand: `demand-c96e06188707`
- Task: `task-demand-2b0c4c98c65c`
- Track: `track-zhipu-02513-long-horizon`
- Artifact: `art-153c429248`

The UI reply correctly linked to the original Message and clearly separated
verified facts from unverified ARR/valuation assumptions. Track Studio rendered
the same Track and Artifact after an explicit Team-room refresh. The Task
completed as `goal_terminal / complete` after 228 seconds and reported 99,700
tokens used.

Evidence:

- [message accepted and Task running](2026-08-13-buddyswitch-real-web-actor-experience-evidence/06-active-task-visible.jpg)
- [reply visible](2026-08-13-buddyswitch-real-web-actor-experience-evidence/08-first-reply-visible.jpg)
- [populated Track Studio](2026-08-13-buddyswitch-real-web-actor-experience-evidence/09-track-studio-populated.jpg)

### C. Same-Track continuation — passed with observability and efficiency defects

The second Web message explicitly required reuse of
`track-zhipu-02513-long-horizon` and prohibited broad new research. It was
accepted as Message `msg-2185997022be`. Demand orchestration eventually created
Task `task-demand-4f2a94768581` against the same Actor and generated a goal that
preserves the existing Track and Artifact relationship.

The UI showed no active work for approximately 95 seconds after message
acceptance, despite the daemon and parent Actor already processing the request.
It later converged to `1 active` and displayed the correct goal. The Task
completed in 276 seconds with 99,789 reported tokens, created Artifact
`art-3d86cc71c0`, and attached it to the original Track. Final public state
contains exactly one Track, two Tasks, and the two expected Artifacts.

Evidence:

- [continuation Task active](2026-08-13-buddyswitch-real-web-actor-experience-evidence/10-continuation-active.jpg)
- [continuation reply](2026-08-13-buddyswitch-real-web-actor-experience-evidence/11-continuation-reply.jpg)

### D. Stop, resume, and persistent-state recall — passed with state-language friction

Stopping through Web released the Actor app server, daemon, runtime broker, and
Browser port. Resuming recreated those processes while preserving the exact
Actor ID and thread ID. The conversation, two completed Tasks, one Track, and
two Artifacts remained visible.

A bounded read-only recovery request produced no new Task or Track and correctly
returned `track-zhipu-02513-long-horizon`, both prior Task IDs, latest Artifact
`art-3d86cc71c0`, and three unresolved evidence gaps. Its reply took about 76
seconds after Message acceptance, during which Web again exposed no meaningful
triage/progress state.

Evidence:

- [Actor stopping](2026-08-13-buddyswitch-real-web-actor-experience-evidence/12-actor-stopping.jpg)
- [Actor intentionally stopped](2026-08-13-buddyswitch-real-web-actor-experience-evidence/13-actor-stopped.jpg)
- [Actor resumed with original state](2026-08-13-buddyswitch-real-web-actor-experience-evidence/15-actor-resumed.jpg)
- [resumed persistent conversation state](2026-08-13-buddyswitch-real-web-actor-experience-evidence/16-resume-recovery-reply.jpg)

### E. Delete confirmation and cleanup — passed terminally with a destructive-flow contradiction

The delete dialog moved focus into its confirmation textbox, kept the destructive
button disabled for an incorrect ID, closed on Escape, and restored focus to the
launching Delete control. Exact-ID confirmation then removed the Instance.

During deletion, Web briefly rendered a raw `FileNotFoundError` traceback for the
already removed `instance.json` while still presenting the Actor as `deleting`.
Less than a second later the UI converged to `Deleting ... completed`, no Actor
selected, and an empty roster. The terminal result was correct, but the
intermediate success/error contradiction is unacceptable for a destructive
operation.

Final cleanup proof:

- Instance root absent;
- both generations of app-server, daemon, and runtime-broker PIDs absent;
- attributable app-server socket absent;
- no listener on Browser port `9222`;
- public Instance count zero and Browser state `inactive`;
- no `/private/tmp/bs-test-*` roots;
- Web port `8765` absent after shutdown and no BuddySwitch service process left;
- durable Tasks, Track, and Artifacts intentionally remain in the product state;
  Actor deletion is a host-instance lifecycle action, while data cleanup is a
  separate explicit public command.

Evidence:

- [incorrect confirmation remains disabled](2026-08-13-buddyswitch-real-web-actor-experience-evidence/17-delete-confirmation-guard.jpg)
- [exact destructive confirmation](2026-08-13-buddyswitch-real-web-actor-experience-evidence/18-delete-confirmation-exact.jpg)
- [empty roster after deletion](2026-08-13-buddyswitch-real-web-actor-experience-evidence/19-post-delete-state.jpg)
- [durable Track after Actor deletion](2026-08-13-buddyswitch-real-web-actor-experience-evidence/20-track-survives-actor-delete.jpg)

## 4. Findings

### F-01 — P1 confirmed contract defect: hyphenated Role IDs break actor-filtered Task and Demand reads

- **Scenario:** B/C, public readback of Actor-owned work
- **Expected:** `task list --actor <actor-id>` and
  `demand list --actor <actor-id>` return the live objects visible to the
  unfiltered store/UI.
- **Observed:** unfiltered Task list returns both Tasks, while both actor-filtered
  commands return empty arrays for
  `act-secondary-market-investor-987558ab2fa7`.
- **Reproducibility:** repeated before and during the second active Task.
- **Owner diagnosis:** both CLI adapters independently derive `role_id` with
  `removeprefix("act-").partition("-")`, yielding `secondary` instead of
  `secondary-market-investor`:
  `src/buddyswitch/modules/task/private/adapters/cli.py` and
  `src/buddyswitch/modules/demand/private/adapters/cli.py`.
- **Affected path:** CLI consumer -> adapter Actor target -> Task/Demand read
  model.
- **Disposition:** confirmed defect; no repair in this audit.

### F-02 — P2 confirmed observability defect: accepted work is shown as idle before Task projection catches up

- **Scenario:** C, same-Track continuation
- **Expected:** after accepted delivery, Web immediately exposes a queued,
  triaging, or working state until a Task is visible.
- **Observed:** for about 95 seconds the sent Message was accepted, while Web
  showed `Thread state: idle`, `Task Sys: 0 active`, `No active task`, and no
  primary working indication. Daemon logs showed ongoing app-server items and
  demand processing. The UI later converged to `1 active`.
- **Affected path:** Communication acceptance -> Demand triage/orchestration ->
  Task projection -> Web status projection.
- **Disposition:** confirmed product-observability defect; exact time may vary,
  but the contradictory intermediate state is reproducible in the real path.

### F-03 — P2 confirmed operational semantics defect: matched, idempotently ignored retry is persisted as failed

- **Scenario:** B/C, Demand orchestration retry
- **Expected:** a scheduled retry that reaches its registered handler and finds
  no remaining state transition is delivered/no-op or superseded, not failed.
- **Observed:** schedules such as `schedule-2` and `schedule-7` were stored as
  `failed` with `scheduled trigger had no matching handler`, even though each
  dispatch reports `matched_count=1`, `handled_count=0`, and
  `handling_status=ignored`; the overall Task still completed successfully.
- **Owner diagnosis:** `sweep_due_scheduled_triggers` in
  `src/buddyswitch/foundation/daemon/instance.py` treats every non-`handled`
  scheduled result as failure and emits a false no-matching-handler error.
  `DemandOrchestrationHandler` legitimately returns `ignored` when its durable
  checkpoint already represents the current state.
- **Affected path:** Demand retry -> generic daemon schedule sweep -> operational
  schedule state/status UI.
- **Disposition:** confirmed defect; no repair in this audit.

### F-04 — P2 design risk: activity feedback is action-centric and indirect

- **Scenario:** A/B/C
- **Observed:** the most prominent explanation while the Actor works is
  `Clear disabled: Thread running.` The actual working state is secondary in the
  right panel; the composer provides no progress stage between accepted,
  triaging, Task creation, and Task execution.
- **Disposition:** design risk, reinforced by F-02.

### F-05 — P2 efficiency risk: both bounded Tasks approached 100,000 reported tokens

- **Scenario:** B
- **Observed:** the first Task correctly produced durable work, but reported
  99,700 tokens and 228 seconds. The continuation was explicitly limited to the
  existing Artifact and prohibited broad search, yet reported 99,789 tokens and
  276 seconds.
- **Interpretation:** this is not by itself a correctness defect; it is a
  material product-cost and latency risk. The continuation was deliberately
  constrained to existing evidence to test whether reuse improves the loop.
- **Disposition:** confirmed design/operational efficiency risk. Reported token
  semantics should also be verified because the near-identical values may
  include replayed context rather than only incremental generation.

### F-06 — P3 copy defect: completed creation still says “Starting … completed”

- **Scenario:** A
- **Observed:** after readiness, the completion status reads
  `Starting Secondary Market Investor completed.` rather than a terminal
  `Started ...` confirmation.
- **Disposition:** confirmed copy defect.

### F-07 — P2 state-language defect: an intentionally stopped Actor is “unhealthy”

- **Scenario:** D
- **Expected:** intentional stopped/offline state is distinct from runtime
  failure or degraded health.
- **Observed:** the roster says `stopped`, while selected Actor details say
  `Status: inactive` and `Health: unhealthy`; `Resume this actor first.` is also
  rendered twice in the Tools rail.
- **Affected path:** Host lifecycle projection -> Web Actor state/health model.
- **Disposition:** confirmed UX/state-semantics defect.

### F-08 — P1 confirmed destructive-flow contradiction: delete succeeds while Web exposes a raw traceback

- **Scenario:** E
- **Expected:** after exact confirmation, deletion presents one coherent pending
  state followed by one terminal success or failure.
- **Observed:** the Instance directory was removed and public Instance count
  became zero, while Web briefly displayed a raw Python `FileNotFoundError` for
  the removed `instance.json`; it then changed to successful completion.
- **Source-bound inference:** Web continues asynchronous Actor detail/operation
  polling while Host Control performs an atomic instance-directory removal. A
  stale selected-Actor read races the valid destructive effect and leaks the
  backend traceback into `state.message`.
- **Affected path:** Web lifecycle poll/selected-Actor refresh -> Host Control
  delete -> missing instance runtime read.
- **Disposition:** confirmed defect; exact read owner needs a focused RED before
  repair.

### F-09 — P3 confirmed CLI shutdown defect: ordinary Web Ctrl-C emits a traceback

- **Scenario:** final operational cleanup
- **Expected:** Ctrl-C stops the local Web server quietly or with a concise
  terminal message.
- **Observed:** Ctrl-C released port `8765` and left no service process, but the
  public CLI printed a full `KeyboardInterrupt` traceback through
  `cli_runtime._run_web`.
- **Disposition:** confirmed operability/polish defect; cleanup itself passed.

## 5. Corrected non-findings

- Track Studio did not lose the Track. The earlier empty capture occurred before
  Track creation or before a Team-room refresh. After explicit refresh, the
  Track and Artifact appeared correctly. Track Studio lacks an in-view refresh,
  which is discoverability friction, but no stale-data defect is claimed from
  this run.
- Browser full-page screenshot output was malformed once; viewport screenshots
  were correct. This was evidence-tool behavior, not a BuddySwitch finding.

## 6. Verification and residual risk

Verification used the shortest real consumer loop: Browser interactions and DOM
snapshots, inspected viewport screenshots, public CLI readback, daemon/runtime
status, source diagnosis only for observed contradictions, and final process,
socket, port, Browser, Instance-root, and temporary-root probes. Browser console
diagnostics were empty at final state.

No executable source changed, so no focused or full repository test suite was
run. This audit deliberately does not claim source-level regression coverage or
authorize fixes. Screenshot `07` is retained only as chronological raw evidence;
the report explicitly rejects its initial stale-data interpretation.

## 7. Final disposition

The real product is substantially functional: a user can create the reviewed
Role, build and continue durable research, stop/resume without losing state,
recover exact prior identifiers, and delete the host Instance with clean
resources. The complete acceptance sentence is nevertheless **REJECTED** until
F-01, F-02, F-03, and F-08 are repaired or deliberately re-specified. F-04,
F-05, F-07, and F-09 should follow because they materially affect trust, cost,
and day-to-day operability.
