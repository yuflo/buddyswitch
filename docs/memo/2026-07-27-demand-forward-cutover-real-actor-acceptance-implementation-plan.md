# Demand Forward Cutover and Real Actor Acceptance Implementation Plan

> **For agentic workers:** Before implementation, read root `AGENTS.md`, this
> plan, and `$buddyswitch-testing` completely. Use
> `$browser:control-in-app-browser` for the WebUI gates.

**Goal:** Remove the last active test that treats a foreign retired Task as
supported input, reset the selected development runtime to one pristine current
truth, and prove the four-action Demand architecture through a deep Dev Actor
run plus Market and Design breadth runs, including daemon-only and App Server
restart recovery.

**Architecture:** Side alone calls `demand_sys.resolve_inbound`; Parent alone
reads and calls `demand_sys.complete`; Goal executes the bound Task;
daemon-service remains a generic trigger/recovery host. Actor build continues
to copy a Git-free runtime surface from an ordinary source directory. Runtime
cutover resets one selected shared root and never translates old state. Product
code changes are allowed only when a real or automated RED proves the planned
test-only cutover insufficient.

**Baseline:** `4b9d29757d20c8bb60406426e7480ef9fe193cf3` on `fea-daemon`.

**Public test entry:** `./buddyswitch-test` only.

## Acceptance sentence

> From a pristine current runtime, fresh Dev, Market, and Design Actors resolve
> multi-Demand conversations only through the unified `buddyswitch-env`
> four-action contract; daemon-only and App Server restart windows converge
> without duplicate mutation or attention; Parent completes a Demand only from
> a completed same-Actor, same-Demand Task and binds at most one next Task; all
> test resources are cleaned.

Stop at the first contradiction. Never patch a live acceptance Actor and count
the continued run as evidence.

## Scope and non-goals

In scope:

- replace one positive retired-record fixture in
  `tests/integration/task_sys/test_goal_binding.py` with a current-schema
  foreign-Actor isolation test;
- reset `/Users/chen/.codex-buddyswitch`, after proving no active owner uses it;
- Gate 1: D2 local research evidence notebook plus recovery windows;
- Gate 2: M2 enterprise AI coding procurement and G1 healthcare appointment
  design;
- correlate wire results, persisted state, Web output, logs, failure effects,
  and cleanup.

Out of scope:

- migration, compatibility reader, fallback, alias, dual schema, or purge API;
- Task storage or `_task_record_belongs_to_actor` changes without a new RED;
- worktree/build changes or any edit under `/Users/chen/Dev/codex`;
- direct runtime JSON edits;
- new lifecycle API, test runner, evidence framework, coordinator, or product
  abstraction;
- finishing every M2/G1 deliverable after first Task terminal plus next binding
  proves orchestration.

Keep these facts separate:

| Concern | Current truth |
|---|---|
| Source | Git commit/diff identifies the candidate; worktree metadata is not runtime input |
| Actor build | Copies a Git-free surface into shared project/Actor workspaces |
| Default shared root | Development state already uses current schemas; reset creates a pristine baseline, not a migration |
| Foreign Actor record | Independently current records are isolated by Actor scope |
| Retired record | Owned, malformed, or unscoped retired records are rejected |

---

## Block A — Remove the positive retired-record contract

**Claim:** Active tests prove current Actor isolation without preserving a
successful retired-record read path.

**Planned source change:** only
`tests/integration/task_sys/test_goal_binding.py`.

### RED

```bash
rg -n \
  'test_actor_scoped_list_ignores_only_foreign_retired_task_records|foreign-retired-task|task-demand-foreign-retired' \
  tests/integration/task_sys/test_goal_binding.py

./buddyswitch-test focused tests/integration/task_sys/test_goal_binding.py
```

- [x] Record the residue and test run id/source/counts/cleanup.
- [x] Treat the positive residue as RED even if the old suite passes.
- [x] Do not weaken the negative retired-schema guards.

Evidence: the exact residue scan found the retired test and hand-written
fixture at lines 251–261. Baseline run
`7fa322ee08794d76b304cad6272759f3` passed 12 tests; its run root was removed.

### Minimal replacement

- [x] Replace the test with
      `test_actor_scoped_list_ignores_foreign_current_schema_task`.
- [x] Create both Actors' Tasks through `task_sys.create`; do not hand-write
      Task JSON.
- [x] Assert the scoped list contains only the selected Actor's Task and the
      unscoped list contains both valid current Tasks.
- [x] Keep
      `test_retired_task_record_is_rejected_without_translation` and
      `test_actor_scoped_list_rejects_owned_retired_task_record`.
- [x] Make no production change if this current-schema proof passes.

### GREEN and residue

```bash
./buddyswitch-test focused \
  tests/integration/task_sys/test_goal_binding.py \
  tests/unit/architecture/test_demand_sys_boundaries.py

rg -n \
  'ignores_only_foreign_retired|foreign-retired-task|task-demand-foreign-retired' \
  tests scripts tools buddyswitch/skills docs/arch
git diff --check
```

Expected: no positive retired-coexistence test. Retired names remain only in
scoped rejection/absence guards.

Evidence: GREEN run `e39c5150de8c4ce9b6b028b8c3f46531` passed 20 tests
through the public runner. The exact positive-residue scan returned no match,
`git diff --check` passed, and the run root was removed. Production code is
unchanged.

---

## Block B — Reset the selected development runtime

**Claim:** Acceptance starts with one pristine current truth, without copy,
translation, or a hidden old root.

### Preflight

```bash
export DEMAND_CUTOVER_ROOT=/Users/chen/.codex-buddyswitch
test "$DEMAND_CUTOVER_ROOT" = /Users/chen/.codex-buddyswitch
export BUDDYSWITCH_SHARED_ROOT="$DEMAND_CUTOVER_ROOT"
export BUDDYSWITCH_STATE_ROOT="$DEMAND_CUTOVER_ROOT/state"

./buddyswitch-codex env status
./buddyswitch-codex instance list
./buddyswitch-codex env browser status
```

- [x] Freeze the exact source/diff identity.
- [x] Stop if an App Server, daemon, broker, Browser, Web listener, or held lock
      owns the root. Use its lifecycle owner; do not kill an unverified PID.

Evidence: HEAD was `4b9d29757d20c8bb60406426e7480ef9fe193cf3`
plus the Block A test diff and this untracked plan. Public status reported zero
instances and inactive Browser; process, socket, and `lsof` probes found no
owner.

### Minimal cutover

```bash
./buddyswitch-codex env reset --yes
```

- [x] Copy no Demand, Task, Artifact, IM, identity, registry, lock, or private
      workspace record into the rebuilt environment.
- [x] Add no code for this reset.

Evidence: the exact non-symlink root passed canonical-path validation and
`env reset --yes` returned `removed=true`. No state was copied or translated.

### GREEN and residue

- [x] Prove the exact root, attributable processes, sockets, listeners, and
      held files are absent.
- [x] An unheld lock path is still unacceptable here because the whole root
      was reset.
- [x] Start no acceptance Actor in this default root; every real gate uses a
      separate isolated root.

Evidence: `/Users/chen/.codex-buddyswitch` is absent; no attributable process,
socket, port `9222` listener, held file, or lock path remains.

---

## Common real-Actor protocol

For each gate, allocate a fresh isolated root and port, then start WebUI only
through:

```bash
BUDDYSWITCH_SHARED_ROOT="<isolated-root>" \
BUDDYSWITCH_STATE_ROOT="<isolated-root>/state" \
./buddyswitch-codex web --host 127.0.0.1 --port <free-port>
```

Create a fresh Actor in WebUI. WebUI is the only scenario writer; CLI,
filesystem reads, logs, and Web console are observers. Send one message at a
time and wait for settled receipt plus Side cleanup.

Correlate:

```text
Web Message → source/attempt → Side Thread/lease → Skill/tools
→ env.tool request/result → receipt/Demand revision → orchestration
→ Task/Goal → Web-visible reply/artifact → cleanup
```

Every run must prove:

- Side sees `list/get/resolve_inbound`, not `complete`;
- Parent sees `list/get/complete`, not `resolve_inbound`;
- Goal sees no Demand mutation;
- direct `create/revise/cancel`, dedicated triage MCP, and special broker method
  are absent;
- each accepted inbound settles once; rejection/interruption has no partial
  write;
- at most one Task is active;
- Demand completion cites a completed same-Actor, same-Demand Task;
- the promised result is readable in WebUI.

On failure, preserve evidence, clean the Actor/root, return to the nearest
automated RED, and repeat with a new Actor.

---

## Block C — Gate 1: D2 plus recovery matrix

**Claim:** One fresh Dev Actor proves semantic depth, daemon-offline commit,
interrupted-Side retry, and terminal Goal recovery across App Server restart.

### Automated baseline

```bash
export DEMAND_RUNTIME_PYTHON="$(command -v python)"
test -x "$DEMAND_RUNTIME_PYTHON"
"$DEMAND_RUNTIME_PYTHON" -c 'import tomllib'

./buddyswitch-test focused \
  tests/integration/demand_sys/test_side_triage_flow.py \
  tests/integration/goal_mode/test_task_goal_reconciliation.py \
  tests/system/goal_mode/test_product_flow.py
```

- [x] Do not start the Actor until this is GREEN with a clean run root.

Evidence: public focused run `29ae6ea057054c42ba80eebcc7c88bad`
passed 26 tests and 15 subtests in 201.80 seconds; its run root and processes
were removed.

### D2 conversation

| Step | WebUI message | Expected effect |
|---|---|---|
| D2-1 | 开发一个本地研究证据库，可以新建资料条目，保存标题、摘要、来源URL和获取日期，并在浏览器中查看。 | create A |
| D2-2 | 同一个基础功能再加入来源类型和可信度备注，刷新后仍能读取。 | merge A |
| D2-3 | 另外单独做全文搜索，能搜标题、摘要和来源。 | create B |
| D2-4 | 搜索再补充来源类型和日期范围过滤。 | merge B |
| D2-5 | 另做一个导出功能，把当前资料导出成 Markdown。 | create C |
| D2-6 | 导出范围改成同时支持 Markdown 和 JSON。 | revise C |
| D2-7 | 另外做一个全文搜索，可以搜标题、摘要和来源。 | no new Demand |
| D2-8 | 搜索这轮先取消，基础资料和导出保留。 | cancel B |

Expected topology: A live/completed; B canceled; C live/revised; no duplicate
Search Demand.

### Recovery window 1 — daemon offline during Side commit

- [x] Wait for one inbound receipt at `resolving` with its exact Side lease.
- [x] Prove App Server and broker healthy, then stop only the daemon:

```bash
"$DEMAND_RUNTIME_PYTHON" tools/launcher/instance_daemon.py stop \
  --instance-json "<isolated-root>/instances/<actor-id>/instance.json"
```

- [x] Let Side call unified `resolve_inbound`; prove receipt and canonical
      Demand settle while daemon is offline and agree with the tool result.
- [x] Recover only through:

```bash
BUDDYSWITCH_SHARED_ROOT="<isolated-root>" \
BUDDYSWITCH_STATE_ROOT="<isolated-root>/state" \
./buddyswitch-codex instance resume <actor-id>
```

- [x] Prove lease cleanup and at most one effective Parent attention; any
      sequential replay is a no-op after rereading current truth.

### Recovery window 2 — App Server interrupted before resolver

- [x] On another inbound, wait for `resolving` plus Side lease, then stop App
      Server before resolver commit:

```bash
"$DEMAND_RUNTIME_PYTHON" tools/launcher/app_server.py stop \
  --socket "<socket-from-instance-record>" \
  --pid-file "<instance-root>/runtime/app-server.pid" \
  --marker-file "<instance-root>/runtime/app-server.socket" \
  --log-file "<instance-root>/runtime/app-server.log"
```

- [x] Prove no partial Demand write and no false settled receipt.
- [x] Run public `instance resume`; prove one replacement Side attempt settles
      once and the old lease/process/socket disappears.

### Recovery window 3 — Goal recovery after daemon and App Server stop

- [x] With Task/Goal active, stop only daemon.
- [x] Let native Goal become complete with App Server alive; Task/Demand must
      not falsely complete while daemon is absent.
- [x] Stop App Server through its owner, then run public `instance resume`.
- [x] Prove the same Thread/Goal terminal truth is recovered, Task completes
      once, Parent runs once effectively, and at most one current non-canceled
      next Demand binds.

### Gate 1 GREEN and cleanup

- [x] Exercise the delivered notebook in the Actor Browser and verify promised
      behavior/evidence in WebUI.
- [x] Stop/delete Actor through WebUI; stop WebUI; release Browser.
- [x] Run `env reset --yes` against the exact isolated root.
- [x] Prove ports, root, App Server, daemon, broker, Side leases, sockets, held
      locks, and attributable processes are absent.

Gate 2 is blocked until Gate 1 is fully GREEN.

### Gate 1 successful run

- Root/port/Actor/Thread:
  `/private/tmp/buddyswitch-demand-d2-retry-019fa2d7/.codex-buddyswitch`,
  `61357`, `act-dev-1ecd1c1bf7dd`,
  `019fa2e5-5c3f-7cf3-991f-f02bb9c80735`.
- D2-1 `msg-c78cb33b6b9b` created
  `demand-ae2d12209dc4`. The first fault-injection attempt landed after Side
  settlement, so it was recorded only as a normal create and not credited as a
  recovery window.
- Window 1 used D2-2 `msg-096b056d593b`, Side Thread
  `019fa2e7-d28e-7203-96e8-7c02d8ca8072`, attempt
  `attempt-1f64deae9ac9`. With App Server and broker healthy, daemon stopped
  while receipt was `resolving`; the same attempt settled offline as
  `merge_intake`, same Demand revision 2/pool revision 2. Public resume cleaned
  the lease and retained exactly one revision-1 active Task.
- Window 2 used D2-3 `msg-f6b8e15ad81b`, initial Side Thread
  `019fa2e9-48f2-7e10-9054-b733a7864f34`, attempt
  `attempt-51270459de47`. App Server stopped with pool revision 2, one Demand,
  receipt still `resolving`, and no outcome. Public resume created replacement
  attempt `attempt-88ff3df75708`, which settled exactly once as create of
  `demand-e692f25c27f8`; pool revision became 3 and all Side leases cleared.
- Window 3 stopped daemon while Task `task-demand-88eb42a70153` and its native
  Goal were active. The Goal completed at `goal_updated_at=1785144851` with
  64,432 tokens/278 seconds while Task remained active and both Demands
  remained non-terminal. After App Server owner stop and public resume, the
  Task recovered that exact terminal snapshot once and only
  `task-demand-ed6c2c67485d` bound to the same Demand at basis revision 2.
- D2-4 `msg-1aacd66e22e6` merged Search to revision 2; D2-5
  `msg-3aeba799b1da` created Export `demand-1502b4a4d256`; D2-6
  `msg-5069b7e2ff72` revised Export to Markdown plus JSON; D2-7
  `msg-4360fb8c03c2` merged into the existing Search rather than creating a
  fourth Demand; D2-8 `msg-1f2e4fbac5ae` canceled only Search. Final accepted
  topology was three Demands: base completed, Search canceled, Export revision
  2 live; Side leases were empty and no Task-slot contradiction occurred.
- Real logs contained nine Side attempts/calls to unified
  `demand_sys__resolve_inbound`, zero Side `complete`, zero main-thread
  `resolve_inbound`, and one main-thread `complete`; that `complete` shared the
  exact submission id of an independent Parent orchestration turn. No direct
  create/revise/cancel tool call or dedicated triage MCP appeared.
- The Dev Actor opened Browser port `9222` and published readable WebUI replies
  and Artifacts `art-3eb01d3420`, `art-13d3272d8d`, and
  `art-0f3480e77e`. An independent Browser check started the delivered app,
  created a six-field record, refreshed, and found every field exactly once.
- Cleanup stopped and deleted the Actor through WebUI, stopped the temporary app
  and WebUI, ran public `env reset --yes`, and removed the empty parent. Root,
  ports `61357`/`4173`/`9222`, processes, sockets, locks, and leases were absent.

### Gate 1 attempt 1 — RED and restart point

The first fresh Dev Actor exposed a current-schema lifecycle contradiction, so
the run stopped before D2-4 and is not acceptance evidence.

- Root/port/Actor/Thread:
  `/private/tmp/buddyswitch-demand-d2.JNgV4l`, `61356`,
  `act-dev-0d14edb4ecf7`, `019fa2cd-bd15-7bd1-a9fd-d83982195ea4`.
- Recovery window 1 passed: `msg-d1ca6798870f` settled through Side Thread
  `019fa2ce-c5b5-7aa1-bf85-306d3ea6275c` while only daemon was offline;
  Demand `demand-561736d3c427` revision 1 bound exactly one Task
  `task-demand-6406009d69e0` after public resume.
- Recovery window 2 passed: `msg-a047d1e04eef` attempt
  `attempt-7d2f6671fe2e` was interrupted before mutation; public resume created
  replacement attempt `attempt-f9575aa1c765`, which merged the same Demand to
  revision 2 exactly once.
- Recovery window 3 passed: the revision-1 Goal completed while daemon was
  offline without falsely completing Task/Demand; after App Server stop and
  public resume, Task `task-demand-6406009d69e0` recovered its exact terminal
  snapshot once and exactly one revision-2 Task
  `task-demand-74225e68f4c4` was bound.
- RED: D2-3 `msg-c040119ad491` / attempt
  `attempt-21d6064cb434` created Demand `demand-ee1f936e00f3`, but its settled
  Side Thread `019fa2d7-93b4-7890-9996-486a15fa9df2` remained open and
  capability-consumed for more than 180 seconds.
- Root cause: `run_daemon` reconciles handlers at startup or after a 15-second
  notification timeout. Continuous Goal/App Server notifications prevent that
  timeout, starving generic reconciliation and delaying settled lease cleanup
  until the stream becomes idle.
- Automated RED: public run `a1cc7bba76794e51b97cba289c7e709b`
  proved only the startup reconcile occurred while two notifications crossed
  the maintenance interval; the run root was removed.
- Minimal fix: `daemon_core.run_daemon` now carries one generic monotonic
  maintenance deadline. A timeout resets the deadline; a busy notification
  stream performs handler reconciliation and heartbeat when the same deadline
  expires. There is no Demand branch or lifecycle shortcut.
- GREEN: exact regression run `444931f948a64650b9a747fc66e17d0f`
  passed 1 test. Affected-boundary run
  `50ae4283419d451baecd93af8ce5eb56` passed 50 tests and 15 subtests,
  including daemon core, Side triage, Goal reconciliation, and the product
  flow; both run roots were removed.
- Restart point: restart D2-1 with a fresh Actor and a reset-compatible isolated
  root.
- Cleanup: the failed Actor was stopped and deleted through WebUI. Because the
  first root name did not satisfy the existing `.codex-buddyswitch` reset guard,
  the inactive owned root was moved under an explicit temporary parent as
  `.codex-buddyswitch`, removed through public `env reset --yes`, and the empty
  parent removed. Ports `61356`/`9222`, processes, sockets, and both paths are
  absent.

---

## Block D — Gate 2 semantic breadth

**Claim:** The same four actions generalize to Market and Design judgment
without role-specific code or a second Demand path.

Use a fresh isolated root and Actor per scenario.

### M2 — Market Actor

1. 为50人研发团队比较 GitHub Copilot、OpenAI Codex 和 Cursor，关注成本、代码代理能力、管理控制和数据政策，输出采购短名单。
2. 在同一份比较中加入50席的月度与年度成本估算，所有价格写明检索日期和适用套餐。
3. 另外单独整理一份采购前的数据治理与安全核查清单。
4. 短名单范围改成只比较 Copilot Enterprise 和 Codex 企业方案，不再评估 Cursor。
5. 再单独设计一个两周试点方案，包含参与人、任务样本和每天记录的数据。
6. 试点方案里补充成功指标、退出条件和预算上限。
7. 安全核查清单由法务另做，取消这项。

Expected: A revised to exclude Cursor; B canceled; C live/merged.

- [x] Price claims show retrieval date and applicable plan.
- [x] Canceled B is never selected.
- [x] Continue through first terminal Task, Demand reconciliation, and one
      grounded next-Task binding.
- [x] At least one actual research result is readable in WebUI.
- [x] Fully clean Actor/root before G1.

#### M2 evidence

- Fresh root/port/Actor/Thread:
  `/private/tmp/buddyswitch-demand-m2-019fa2f5/.codex-buddyswitch`,
  `61358`, `act-market-39e3a4b1e707`,
  `019fa2f9-3fc1-7023-8de6-741d1d79007a`.
- The seven WebUI messages settled as three current-schema Demands:
  A `demand-85a9dbef47d3` revision 3 live, B
  `demand-6083aca3553d` revision 2 canceled, and C
  `demand-1ab8823fbb2f` revision 2 live. There was no fourth Demand.
- B was never selected. A reached terminal Task
  `task-demand-9fdf081a1bf1`, reconciled, and was rebound from current
  revision 3 as `task-demand-b7bc043fc460`; the subsequent grounded binding
  selected C. This proves the requested first terminal, reconciliation, and
  next-selection boundary without requiring all deliverables to finish.
- WebUI displayed the revised procurement result and Artifact
  `art-787929050e`: only Copilot Enterprise and Codex Enterprise were compared;
  Copilot was labeled `US$39/user/month (retrieved 2026-07-27)` with 50-seat
  monthly and annual calculations; Codex Enterprise was correctly labeled
  contact-sales with no invented fixed seat price and with Business pricing
  explicitly rejected as a substitute.
- Runtime logs correlated seven Side attempts with seven unified
  `demand_sys.resolve_inbound` calls, zero Side `complete` calls, zero Parent
  `resolve_inbound` calls, and zero retired action calls. Side leases and
  `last_failure` were empty at the proof boundary.
- The Actor was stopped and deleted in WebUI, the Web process was stopped,
  public `env reset --yes` returned `removed:true`, and the root was removed.
  Ports `61358` and `9222` had no listeners; no attributable actor, daemon,
  broker, App Server, socket, or lock remained before G1.

### G1 — Design Actor

1. 设计一个患者预约门诊的移动端流程：选择科室、日期、时段、填写联系方式、确认并看到成功结果。
2. 同一流程补充空状态、无可用时段、输入错误、键盘操作和屏幕阅读器说明。
3. 另外单独设计预约成功后的改期和取消流程。
4. 改期和取消中补充确认、撤销或恢复机制，避免误操作。
5. 再单独设计医护人员维护可预约时段的后台。
6. 患者预约流程范围改成访客模式，不要求先注册；提交前用短信验证码确认联系方式。
7. 医护人员后台本轮不做，取消。
8. 另外给患者流程设计一份5人可用性测试脚本和观察表。

Expected: A revised to guest/SMS flow; B live/merged; C canceled; D independent.

- [x] Accessibility/error states remain conditions of A.
- [x] B and D remain independent; canceled C is never selected.
- [x] Continue through first terminal Task, Demand reconciliation, and one
      grounded next-Task binding.
- [x] Actual design Artifact is readable in WebUI.
- [x] Fully clean Actor/root.

#### G1 evidence

- The first two attempts exposed invalid operator sequencing rather than a
  product defect: one waited for terminal work before sending the revision,
  and one queued all eight messages concurrently. Both Actors and roots were
  fully removed. The next correctly serialized attempt produced a real RED:
  the separately requested usability-test script/observation sheet was merged
  into A instead of becoming independent D.
- Public RED run `31109150cdd4463ba309911cb36908e6` failed the exact structural
  owner test. The minimal change added one rule to the existing shared
  `demand-triage` skill: an additionally requested testing/research deliverable
  is an independent acceptance unit unless the user explicitly groups it with
  the evaluated product/design. No new action, schema, adapter, compatibility
  path, or daemon Demand branch was added. Exact GREEN run
  `43ca34106fea464e9c3af3894c463714` passed.
- Fresh GREEN root/port/Actor/Thread:
  `/private/tmp/buddyswitch-demand-g1-green-019fa31a/.codex-buddyswitch`,
  `61359`, `act-design-5448181975c4`,
  `019fa31d-64d9-7bd3-b7f6-b584193dfbb4`.
- Eight sequential WebUI messages settled through eight unique Side attempts
  into four current-schema Demands: A `demand-70b9edbef829` revision 3 live,
  B `demand-070b185ead2b` revision 2 live, C
  `demand-579ae4dc2829` revision 2 canceled, and D
  `demand-19326f74fe13` revision 1 live. The persisted decisions were four
  creates, two merges, one revision, and one cancellation, with no failed or
  outstanding receipt.
- A retained empty/no-slot/input/SMS error handling plus keyboard and screen
  reader conditions while its current revision required guest mode and SMS
  verification. B remained the independent reschedule/cancel flow with
  confirmation and undo/recovery. D remained the independent five-person
  usability-test script and observation table. C was never selected.
- A completed Tasks `task-demand-4bc64dd1eab2` and
  `task-demand-5771e7d8fb1c`, then reconciled and rebound from current revision
  3 as active Task `task-demand-1c9e08acfbb7`; no Task selected canceled C.
  The main rollout contained six unified `demand_sys.get`, three
  `demand_sys.list`, three `task_sys.create`, five `task_sys.get`, and three
  `task_sys.list` calls, with zero Parent `resolve_inbound` or `complete`
  calls. Parent configuration did not expose `resolve_inbound`.
- WebUI displayed the readable main-flow Artifact `art-a437e6569a`, the
  accessibility supplement `art-4a5c2ba46c`, and the guest/SMS supplement
  `art-68fe577888`, correlated to their source messages.
- The Actor was stopped and deleted in WebUI, the Web process was stopped,
  public `env reset --yes` returned `removed:true`, and the empty parent root
  was removed. Ports `61359` and `9222` had no listeners; no attributable
  Actor, process, socket, or lock remained.

### Final GREEN and residue

```bash
./buddyswitch-test focused \
  tests/integration/daemon/test_core_runtime.py \
  tests/integration/task_sys/test_goal_binding.py \
  tests/integration/demand_sys/test_side_triage_flow.py \
  tests/integration/goal_mode/test_task_goal_reconciliation.py \
  tests/integration/env_tool/test_response_demand.py \
  tests/process/cli/test_env_native_mcp_projection.py \
  tests/unit/architecture/test_demand_sys_boundaries.py \
  tests/unit/architecture/test_task_management_skill.py \
  tests/system/goal_mode/test_product_flow.py

rg -n \
  'demand_triage\.resolve|buddyswitch-demand-triage|demand\.ingress\.resolve|demand_sys__(create|revise|cancel)|actor_creation_receipts|ignores_only_foreign_retired' \
  scripts tools buddyswitch/skills docs/arch tests
git diff --check
```

Expected: retired terms occur only in scoped negative guards. Do not run
`./buddyswitch-test full` unless the candidate is explicitly frozen for
merge/release or the user requests repository-wide acceptance.

## Evidence and ACCEPT

For each automated run and Actor, record source/diff identity, public command
and run id, Actor/Thread/port/root identities, Message-to-Goal correlation,
stop/resume timestamps, expected versus observed effects, Web-visible result,
cleanup, omitted checks, and risk.

Accept only when Product, Contract, Architecture, Replacement, and Operations
proofs agree. Real Actor evidence is mandatory.

### Final ACCEPT evidence

- Candidate identity remained baseline
  `4b9d29757d20c8bb60406426e7480ef9fe193cf3` plus the exact local diff;
  nothing was committed or pushed during implementation.
- Final public focused run `41b10edb9ab44db9a265299db03910f8`
  passed 92 tests and 65 subtests in 202.82 seconds across daemon runtime,
  Task/Demand integration, Goal reconciliation, env-tool wire projection,
  architecture boundaries, triage-skill ownership, and the system product
  flow. Its `/private/tmp/bs-test-41b10edb-s9vcq_0h` root was absent after the
  run.
- The retired-term scan returned only scoped negative guards: current-schema
  validation rejects `actor_creation_receipts`; Side configuration forbids the
  dedicated triage MCP; Parent/Goal surfaces forbid direct create/revise/cancel;
  and the runtime broker proves the special ingress method unsupported and
  absent from dispatcher source. No live code, skill, current architecture
  guide, or positive test preserves a retired path.
- `git diff --check` passed. Final G1 ports `61359`/`9222`, root, Actor,
  attributable processes, sockets, locks, and the public test root were absent.
- Product, Contract, Architecture, Replacement, and Operations proofs agree:
  D2 proved recovery and terminal convergence, M2/G1 proved semantic breadth,
  automated runs fixed and covered the two observed REDs, and all three GREEN
  Actors were cleaned.
- Omitted by design: `./buddyswitch-test full` was not run because this local
  candidate was not declared frozen for merge/release and repository-wide
  acceptance was not requested. Remaining risk is limited to qualitative model
  judgment beyond the exercised conversations; no known runtime, schema,
  compatibility, or cleanup contradiction remains.

## Simplicity review

- The planned Task fixture replacement remains test-only. The one new real RED
  added one daemon regression and one product-neutral run-loop deadline; it
  added no Demand branch, helper layer, schema, or lifecycle API.
- One cutover operation: existing `env reset --yes`; no migration or cleanup
  feature.
- Existing lifecycle owners perform fault injection and public
  `instance resume` performs recovery; no test backdoor.
- Three Actors only: D2 supplies depth/recovery; M2 and G1 supply breadth.
- M2/G1 stop after first terminal Task plus next binding.
- Reuse one identity chain; no second evidence ledger or architecture mirror.

Reject any proposed product module, schema, compatibility branch, cleanup
command, worktree coupling, or second orchestration path unless a new
observable RED proves this plan insufficient.
