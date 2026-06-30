# Task Sys Exploratory Acceptance Run Log

Date: 2026-06-30

This file records execution results for `00-test-plan.md`.

Do not write raw External IM `connection_key` values in this file.

## Run Setup

- Base URL: `http://127.0.0.1:8765`
- Connection display name: `task-sys-exploratory-acceptance`
- External identity id: `ext-dc4d4569857b` for the first executed case.
- Dev actor id: `act-dev-344fa10d0f0b`
- Market actor id: `act-market-3d4839c64a96`
- PM actor id: `act-pm-cf82dc73feda`
- PM startup command output summary: `./buddyswitch-codex instance start --role pm --json`
  started `act-pm-cf82dc73feda`, active and healthy. The actor was later resumed with
  `./buddyswitch-codex instance resume act-pm-cf82dc73feda --json` for `A-PM-01`. This actor is
  test-owned for this run.
- HTTP client proxy handling: Python `urllib` must use `ProxyHandler({})`; default `urllib`
  attempted `HTTP_PROXY=http://127.0.0.1:7897` and returned proxy 502 before reaching
  BuddySwitch.
- Start time: 2026-06-30T12:21:19+08:00 for PM startup; first External IM case at
  2026-06-30T12:27:08+08:00.
- End time: 2026-06-30T13:06:42+08:00

## Resource Lifecycle

Highlighted rule: resources started by this run are test-owned and must be checked, stopped, or
explicitly justified before completion. See
`docs/bitter/2026-05-26-test-resource-lifecycle-principles.md`.

- Baseline instance list summary: dev and market were active before this run; PM was not active and
  was started by this run. After PM start, `instance list` showed dev, market, and PM active.
- Baseline per-actor daemon/app-server/runtime-broker pids:
  - dev: daemon `6928`, app-server `5032`, runtime-broker `4943`.
  - market: daemon `4045`, app-server `3703`, runtime-broker `3631`.
  - pm: daemon `29199`, app-server `28808`, runtime-broker `28735`.
- Baseline Task Sys active counts:
  - PM startup status showed `daemon.task_sys.active_count == 0`.
  - Dev status before expanding beyond `A-DEV-01` showed one active Task Sys residue from this run.
- Resources started by this run: PM actor `act-pm-cf82dc73feda`; PM actor resumed once for
  `A-PM-01`; diagnostic fresh dev actor `act-dev-ddbd378ce58e`; diagnostic fresh market actor
  `act-market-f5c94d3709a7`; bounded follow-up fresh dev actor `act-dev-24bcf1158129`;
  harness-aborted fresh market actor `act-market-c3690273fde6`;
  External IM connections for `A-DEV-01`, `A-PM-01`, `A-DEV-01-FRESH`, `A-MKT-01-FRESH`,
  the bounded `A-DEV-02` / `B-DEV-01` follow-up, and the harness-aborted `A-MKT-02` probe.
- Per-role resource checks:
  - dev after `A-DEV-01`: active/healthy, but `daemon.task_sys.active_count == 1` with
    `task-im-message-created-3cfcf332ab20` in `side_processing`; matrix expansion stopped.
  - market preflight after dev failure: active/healthy with `daemon.task_sys.active_count == 0`,
    but `instance.json` has stale open side thread `019f169c-88a8-7271-90b5-88f321e92cc5`;
    no matching session file exists. `A-MKT-01` was not sent to avoid knowingly adding another
    active residue.
  - pm after `A-PM-01`: reply event acked, Task Sys task closed after a short settle delay, then PM
    stopped.
  - fresh dev diagnostic after `A-DEV-01-FRESH`: reply event acked, Task Sys task closed, then actor
    stopped.
  - fresh market diagnostic after `A-MKT-01-FRESH`: reply event acked, Task Sys task closed, then
    actor stopped.
  - bounded fresh dev follow-up after `A-DEV-02` / `B-DEV-01`: `A-DEV-02` reply event was acked
    and task closed; `B-DEV-01` failed in the daemon handler and stayed `side_processing`.
    The waiting batch was interrupted and actor `act-dev-24bcf1158129` was stopped by
    `./buddyswitch-codex instance stop act-dev-24bcf1158129 --json` to prevent a resource leak.
  - harness-aborted fresh market `A-MKT-02`: the send reached BuddySwitch, but the host-side
    automation incorrectly expected top-level `message_id` in the `/api/im/messages` response
    instead of `message.id`. The script exited immediately after send and stopped the actor while
    the task was still `side_processing`. A later `resume` without sending new messages did not
    recover the task within 60 seconds; the actor was stopped again.
- Final instance list summary: dev and market remain active; PM is inactive after cleanup.
- Final per-actor daemon/app-server/runtime-broker pids:
  - dev: daemon `6928`, app-server `5032`, runtime-broker `4943`.
  - market: daemon `4045`, app-server `3703`, runtime-broker `3631`.
  - pm: inactive; app-server pid `null`, daemon pid `null`, runtime-broker pid `null`.
  - fresh dev diagnostic: inactive; app-server pid `null`, daemon pid `null`, runtime-broker pid
    `null`.
  - fresh market diagnostic: inactive; app-server pid `null`, daemon pid `null`, runtime-broker pid
    `null`.
  - bounded fresh dev follow-up: inactive; app-server pid `null`, daemon pid `null`,
    runtime-broker pid `null`.
  - harness-aborted fresh market: inactive; app-server pid `null`, daemon pid `null`,
    runtime-broker pid `null`.
- Final Task Sys active counts:
  - dev: `1`, task `task-im-message-created-3cfcf332ab20` in `side_processing`.
  - market: `0`.
  - pm: `0`.
  - fresh dev diagnostic: `0`.
  - fresh market diagnostic: `0`.
  - bounded fresh dev follow-up: `1`, task `task-im-message-created-12591d0a4526` in
    `side_processing`.
  - harness-aborted fresh market: `1`, task `task-im-message-created-cf1ee68c695a` in
    `side_processing`.
- Resources stopped by this run: PM actor `act-pm-cf82dc73feda` via
  `./buddyswitch-codex instance stop act-pm-cf82dc73feda --json`; status became `inactive`, with
  app-server, daemon, and runtime-broker not live. PM was stopped once after initial setup blocking,
  resumed for `A-PM-01`, then stopped again. Fresh dev actor `act-dev-ddbd378ce58e` and fresh
  market actor `act-market-f5c94d3709a7` were both stopped after their single diagnostic baseline
  cases, with app-server, daemon, and runtime-broker pids all `null`. Bounded fresh dev actor
  `act-dev-24bcf1158129` was stopped after `B-DEV-01` failed and the batch wait was manually
  interrupted; status showed inactive with app-server, daemon, and runtime-broker pids all `null`.
  Harness-aborted fresh market actor `act-market-c3690273fde6` was stopped, resumed for a 60-second
  no-new-message recovery observation, then stopped again; final status showed inactive with
  app-server, daemon, and runtime-broker pids all `null`.
- Resources intentionally left running and reason: dev and market were pre-existing active actors;
  they were not started by this run.
- Residual resource issues: dev Task Sys residue `task-im-message-created-3cfcf332ab20` remains
  active after daemon handler failure. Bounded fresh dev residue
  `task-im-message-created-12591d0a4526` also remains active in `side_processing` after daemon
  handler failure. Harness-aborted fresh market residue `task-im-message-created-cf1ee68c695a`
  remains active in `side_processing` because the test automation stopped the actor immediately
  after send; a 60-second no-new-message resume did not recover it. The actor process resources were
  stopped, but the runtime object residues were not edited. Do not hide these issues by editing
  runtime state.

## Case Record Template

Copy this template for each executed case.

```text
Case id:
Target role:
Target actor id:
Message:

External IM send:
- source message id:
- conversation id:
- source event id:
- delivery_status:
- wake_status:

Reply observation:
- reply event id:
- reply message id:
- reply_to:
- reply from_identity_id:
- reply content summary:
- event ack result:

Runtime evidence:
- instance status summary:
- daemon handler result:
- task id:
- task status:
- active_processor:
- close_result:
- side_result:
- parent_handoff_params:
- active Task Sys residue after case:

Verdict:
Notes:
```

## Results

### A-DEV-01

Case id: `A-DEV-01`
Target role: `dev`
Target actor id: `act-dev-344fa10d0f0b`
Message: `收到后只回复“收到”。`

External IM send:
- source message id: `msg-cba9b5a7222f`
- conversation id: `conv-88b57e56330f`
- source event id: `imev-71d9f750042c`
- delivery_status: not captured from the interrupted probe output; persisted source message/event
  confirms the send reached BuddySwitch.
- wake_status: not captured from the interrupted probe output; daemon `im_message_created` handler
  fired for `msg-cba9b5a7222f`.

Reply observation:
- reply event id: none observed before stopping the waiting probe.
- reply message id: none.
- reply_to: none.
- reply from_identity_id: none.
- reply content summary: no reply produced.
- event ack result: not applicable; no reply event was consumed.

Runtime evidence:
- instance status summary: dev active; app-server healthy; daemon live/ready; thread idle.
- daemon handler result:
  `{"event":"handler_result","handler":"im_message_created","origin_id":"msg-cba9b5a7222f","result":"failed","trigger_type":"im.message.created","ts":"2026-06-30T04:27:08Z"}`
- daemon error detail:
  `thread/read failed (-32600): thread not loaded: 019f169b-b758-7470-b2e8-56b8206793bf`
- task id: `task-im-message-created-3cfcf332ab20`
- task status: `side_processing`
- active_processor: `side`
- close_result: none.
- side_result: none.
- parent_handoff_params: none.
- active Task Sys residue after case: yes; `daemon.task_sys.active_count == 1` for this task.

Verdict: `fail`
Notes: Baseline exact-reply IM did not reach side completion. Failure is currently in actor wake /
Task Sys side-frame dispatch or side-thread loading, before reply/ack behavior can be evaluated.
Per failure triage and resource lifecycle rules, the matrix was not expanded after this failed
baseline.

Root-cause evidence collected so far:
- Dev `instance.json` still lists side thread `019f169b-b758-7470-b2e8-56b8206793bf` as
  `status: open` under parent `019f169a-9300-7563-a634-6a3959ce9eaa`.
- No session file exists for `019f169b-b758-7470-b2e8-56b8206793bf` under the dev
  `codex-home/sessions` tree.
- Dev daemon log previously observed `app_server.thread_closed` at `2026-06-30T04:25:37Z`.
- `task_sys_runtime._execute_start_side()` reuses `side_thread_registry.find_open_side_thread()`
  before starting a fresh side thread; the stale open registry row led to `app_server.input_turn()`
  targeting an unloaded side thread.

### A-MKT-01

Case id: `A-MKT-01`
Target role: `market`
Target actor id: `act-market-3d4839c64a96`
Message: `收到后只回复“收到”。`

External IM send:
- source message id: not sent.
- conversation id: not sent.
- source event id: not sent.
- delivery_status: not applicable.
- wake_status: not applicable.

Reply observation:
- reply event id: none.
- reply message id: none.
- reply_to: none.
- reply from_identity_id: none.
- reply content summary: none.
- event ack result: not applicable.

Runtime evidence:
- instance status summary: market active; app-server healthy; daemon live; runtime-broker healthy;
  thread idle; `daemon.task_sys.active_count == 0`.
- daemon handler result: last market `im_message_created` result before this run was `handled` for
  older origin `msg-2efb9623b42c`; no new handler was triggered for this blocked case.
- task id: none.
- task status: none.
- active_processor: none.
- close_result: none.
- side_result: none.
- parent_handoff_params: none.
- active Task Sys residue after case: no new market residue.

Verdict: `blocked`
Notes: This case was blocked before send by the resource lifecycle gate. Market preflight showed
the same stale side-thread registry shape as the failed dev case: `instance.json` lists side thread
`019f169c-88a8-7271-90b5-88f321e92cc5` as `status: open`, no matching session file exists under
market `codex-home/sessions`, and market daemon previously observed `app_server.thread_closed` at
`2026-06-30T04:10:11Z`. Sending this case would likely reproduce the known `thread not loaded`
failure and add another active Task Sys residue without new transport evidence.

### A-PM-01

Case id: `A-PM-01`
Target role: `pm`
Target actor id: `act-pm-cf82dc73feda`
Message: `收到后只回复“收到”。`

External IM send:
- source message id: `msg-5a36381a81bd`
- conversation id: `conv-0a1aca04ef10`
- source event id: `imev-d4fa1a24f66a`
- delivery_status: `accepted`
- wake_status: `submitted`

Reply observation:
- reply event id: `imev-e459982721e9`
- reply message id: `msg-cc848e5d929c`
- reply_to: `msg-5a36381a81bd`
- reply from_identity_id: `act-pm-cf82dc73feda`
- reply content summary: exact `收到`
- event ack result: `ok: true`, `state_changed: true`, `last_event_id: imev-e459982721e9`

Runtime evidence:
- instance status summary: PM active/healthy during case; after cleanup PM inactive with app-server
  pid `null`, daemon pid `null`, runtime-broker pid `null`.
- daemon handler result:
  `{"event":"handler_result","handler":"im_message_created","origin_id":"msg-5a36381a81bd","result":"handled","trigger_type":"im.message.created","ts":"2026-06-30T04:39:18Z"}`
- task id: `task-im-message-created-ff7be8bd11bb`
- task status: `closed`
- active_processor: none.
- close_result: `{"processor":"side","updated_at":"2026-06-30T12:39:36+08:00","summary":"Replied to source IM msg-5a36381a81bd with the exact requested acknowledgement: 收到."}`
- side_result: none.
- parent_handoff_params: none.
- active Task Sys residue after case: none after settle; `daemon.task_sys.active_count == 0`.

Verdict: `pass`
Notes: A too-early status read roughly two seconds after ack still showed the task as
`side_processing`; after an additional short settle delay, the task record was `closed` and instance
status showed no active Task Sys residue. This suggests acceptance probes need a condition-based
wait for Task Sys close, not only reply ack.

### A-DEV-01-FRESH

Case id: `A-DEV-01-FRESH`
Target role: `dev`
Target actor id: `act-dev-ddbd378ce58e`
Message: `收到后只回复“收到”。`

External IM send:
- source message id: `msg-6c4adf20b845`
- conversation id: `conv-6171eed10830`
- source event id: `imev-501793b16865`
- delivery_status: `accepted`
- wake_status: `submitted`

Reply observation:
- reply event id: `imev-c09d72761265`
- reply message id: `msg-edcde0264f05`
- reply_to: `msg-6c4adf20b845`
- reply from_identity_id: `act-dev-ddbd378ce58e`
- reply content summary: exact `收到`
- event ack result: `ok: true`, `state_changed: true`, `last_event_id: imev-c09d72761265`

Runtime evidence:
- instance status summary: fresh dev active/healthy during case; after cleanup inactive with
  app-server pid `null`, daemon pid `null`, runtime-broker pid `null`.
- daemon handler result:
  `{"event":"handler_result","handler":"im_message_created","origin_id":"msg-6c4adf20b845","result":"handled","trigger_type":"im.message.created","ts":"2026-06-30T04:44:50Z"}`
- task id: `task-im-message-created-6090df203093`
- task status: `closed`
- active_processor: none.
- close_result: `{"processor":"side","updated_at":"2026-06-30T12:45:52+08:00","summary":"Replied to the exact source IM message msg-6c4adf20b845 with \"收到\"; source disposition transitioned to replied."}`
- side_result: none.
- parent_handoff_params: none.
- active Task Sys residue after case: none; `daemon.task_sys.active_count == 0`.

Verdict: `pass`
Notes: Diagnostic fresh actor run. This does not erase the original `A-DEV-01` failure on
`act-dev-344fa10d0f0b`; it shows the dev role baseline works when the actor has no stale open
side-thread registry row.

### A-MKT-01-FRESH

Case id: `A-MKT-01-FRESH`
Target role: `market`
Target actor id: `act-market-f5c94d3709a7`
Message: `收到后只回复“收到”。`

External IM send:
- source message id: `msg-86374e3aca76`
- conversation id: `conv-e8f4e52a40a1`
- source event id: `imev-27333b3e0d17`
- delivery_status: `accepted`
- wake_status: `submitted`

Reply observation:
- reply event id: `imev-cbcb164cfb17`
- reply message id: `msg-245e3eec67b5`
- reply_to: `msg-86374e3aca76`
- reply from_identity_id: `act-market-f5c94d3709a7`
- reply content summary: exact `收到`
- event ack result: `ok: true`, `state_changed: true`, `last_event_id: imev-cbcb164cfb17`

Runtime evidence:
- instance status summary: fresh market active/healthy during case; after cleanup inactive with
  app-server pid `null`, daemon pid `null`, runtime-broker pid `null`.
- daemon handler result:
  `{"event":"handler_result","handler":"im_message_created","origin_id":"msg-86374e3aca76","result":"handled","trigger_type":"im.message.created","ts":"2026-06-30T04:49:01Z"}`
- task id: `task-im-message-created-d827997aa111`
- task status: `closed`
- active_processor: none.
- close_result: `{"processor":"side","updated_at":"2026-06-30T12:49:19+08:00","summary":"Replied to exact source IM msg-86374e3aca76 with \"收到\"; original message marked replied."}`
- side_result: none.
- parent_handoff_params: none.
- active Task Sys residue after case: none; `daemon.task_sys.active_count == 0`.

Verdict: `pass`
Notes: Diagnostic fresh actor run. This does not erase the original `A-MKT-01` blocked verdict on
`act-market-3d4839c64a96`; it shows the market role baseline works when the actor has no stale open
side-thread registry row.

### A-DEV-02

Case id: `A-DEV-02`
Target role: `dev`
Target actor id: `act-dev-24bcf1158129`
Message: `你现在能帮我做什么？用三句话回答。`

External IM send:
- source message id: `msg-c23c7e083d5a`
- conversation id: `conv-9a46137ea444`
- source event id: `imev-35ae6e06c0b5`
- delivery_status: `accepted`
- wake_status: `submitted`

Reply observation:
- reply event id: `imev-7e33db1b576f`
- reply message id: `msg-0438ed39f23a`
- reply_to: `msg-c23c7e083d5a`
- reply from_identity_id: `act-dev-24bcf1158129`
- reply content summary: three-sentence capability reply; no file edits, build runs, or main-thread
  state mutation claimed.
- event ack result: ack confirmed by the connection record advancing `last_event_id` to
  `imev-7e33db1b576f`.

Runtime evidence:
- instance status summary: fresh dev active/healthy during case; later stopped during resource
  cleanup after `B-DEV-01`, with app-server pid `null`, daemon pid `null`, runtime-broker pid
  `null`.
- daemon handler result:
  `{"event":"handler_result","handler":"im_message_created","origin_id":"msg-c23c7e083d5a","result":"handled","trigger_type":"im.message.created","ts":"2026-06-30T04:53:56Z"}`
- task id: `task-im-message-created-5995f1ef21e2`
- task status: `closed`
- active_processor: none.
- close_result: `{"processor":"side","updated_at":"2026-06-30T12:54:12+08:00","summary":"Replied to the exact inbound IM message in three Chinese sentences explaining what this side assistant can help with."}`
- side_result: none.
- parent_handoff_params: none.
- active Task Sys residue after case: none for this case.

Verdict: `pass`
Notes: This was a bounded follow-up probe on a fresh dev actor. It confirms short capability
answers can complete in side and close cleanly. The following message on the same actor exposed a
side-thread reuse failure, so this pass should not be generalized to multi-message stability.

### B-DEV-01

Case id: `B-DEV-01`
Target role: `dev`
Target actor id: `act-dev-24bcf1158129`
Message: `给我一个 Python 判断数字是否为质数的小函数，不需要运行。`

External IM send:
- source message id: `msg-8fe46c4528a4`
- conversation id: `conv-9a46137ea444`
- source event id: `imev-bb09c5392c0f`
- delivery_status: `accepted`
- wake_status: `submitted`

Reply observation:
- reply event id: none.
- reply message id: none.
- reply_to: none.
- reply from_identity_id: none.
- reply content summary: no reply produced before resource stop.
- event ack result: not applicable; no reply event was consumed.

Runtime evidence:
- instance status summary: after resource cleanup, `act-dev-24bcf1158129` is inactive with
  app-server pid `null`, daemon pid `null`, runtime-broker pid `null`, but
  `daemon.task_sys.active_count == 1`.
- daemon handler result:
  `{"event":"handler_result","handler":"im_message_created","origin_id":"msg-8fe46c4528a4","result":"failed","trigger_type":"im.message.created","ts":"2026-06-30T04:54:16Z"}`
- daemon error detail:
  `thread/turns/list failed (-32600): ephemeral threads do not support thread/turns/list`
- task id: `task-im-message-created-12591d0a4526`
- task status: `side_processing`
- active_processor: `side`
- close_result: none.
- side_result: none.
- parent_handoff_params: none.
- active Task Sys residue after case: yes; `task-im-message-created-12591d0a4526` remains
  `side_processing`.

Verdict: `fail`
Notes: This failure happened on the second External IM message sent to an otherwise fresh dev actor.
The first message created and closed a side task, but left `instance.json.side_threads[]` with an
open side thread `019f16e0-6df2-7af2-9580-dd8e5fd9206c`. There is no matching side session file
under `codex-home/sessions`; only the main thread session file exists. Reusing or introspecting that
side thread for `B-DEV-01` failed before any reply, leaving the source message disposition `unseen`
and the task active. The broader batch was stopped at this point; market and PM follow-up cases were
not started.

### A-MKT-02

Case id: `A-MKT-02`
Target role: `market`
Target actor id: `act-market-c3690273fde6`
Message: `你作为市场角色能帮我做什么？用三句话回答。`

External IM send:
- source message id: `msg-5b11c8de88ac`
- conversation id: `conv-b82960d5f034`
- source event id: `imev-0f62ba41bd89`
- delivery_status: `accepted`
- wake_status: `submitted`

Reply observation:
- reply event id: none.
- reply message id: none.
- reply_to: none.
- reply from_identity_id: none.
- reply content summary: no reply produced before the test harness stopped the actor.
- event ack result: not applicable; no reply event was consumed.

Runtime evidence:
- instance status summary: after cleanup, `act-market-c3690273fde6` is inactive with app-server
  pid `null`, daemon pid `null`, runtime-broker pid `null`, but
  `daemon.task_sys.active_count == 1`.
- daemon handler result:
  `{"event":"handler_result","handler":"im_message_created","origin_id":"msg-5b11c8de88ac","result":"handled","trigger_type":"im.message.created","ts":"2026-06-30T05:04:19Z"}`
- daemon error detail: none recorded.
- task id: `task-im-message-created-cf1ee68c695a`
- task status: `side_processing`
- active_processor: `side`
- close_result: none.
- side_result: none.
- parent_handoff_params: none.
- active Task Sys residue after case: yes; `task-im-message-created-cf1ee68c695a` remains
  `side_processing`.

Verdict: `blocked`
Notes: This is not a valid market-role product verdict. The host-side probe script parsed the
`POST /api/im/messages` response incorrectly: the implementation returns the sent id at
`message.id`, not top-level `message_id`. The script raised `KeyError: 'message_id'` immediately
after send and stopped the actor while side processing was active. A no-new-message resume of the
same actor for 60 seconds left the source message `unseen`, produced no reply, and left the task in
`side_processing`, so the actor was stopped again. Broad testing was stopped after this lifecycle
breach.

### Resource-Gated Blocked Matrix Cases

The following core matrix cases were not sent. This is an intentional resource lifecycle stop, not a
product behavior pass. The plan's failure triage rules say to stop expansion after adjacent failures
and to record active Task Sys residue without hiding it. At this point the run already had three
active `side_processing` residues:

- `task-im-message-created-3cfcf332ab20` on `act-dev-344fa10d0f0b`, source
  `msg-cba9b5a7222f`, from the original `A-DEV-01` failure.
- `task-im-message-created-12591d0a4526` on `act-dev-24bcf1158129`, source
  `msg-8fe46c4528a4`, from `B-DEV-01`.
- `task-im-message-created-cf1ee68c695a` on `act-market-c3690273fde6`, source
  `msg-5b11c8de88ac`, from the harness-aborted `A-MKT-02` probe.

Shared blocked evidence:

- External IM send: not sent for these cases.
- Reply observation: no reply event; no reply message; no `reply_to`; no ack required.
- Instance status summary: test-owned `pm`, fresh dev, fresh market, bounded fresh dev, and
  harness-aborted fresh market actors were inactive with app-server, daemon, and runtime-broker pids
  `null`; pre-existing dev and market actors remained active and were not stopped by this run.
- Daemon/Task Sys evidence: active Task Sys residue count was already non-zero and increasing;
  continuing the matrix would knowingly add more side-processing residue before fixing side-thread
  lifecycle and harness parsing.
- Verdict for each row: `blocked`.

| Case id | Target role / actor | Message | Reason |
|---|---|---|---|
| `A-PM-02` | pm / not started | `你作为 PM 角色能帮我做什么？用三句话回答。` | PM actor was already tested by `A-PM-01` and stopped cleanly; after later dev/market residues, restarting PM for non-critical coverage would violate the resource gate. |
| `B-MKT-01` | market / not started | `给我 3 个常见用户访谈问题，不需要调研。` | Market role had one fresh baseline pass, one original stale-side-thread blocked case, and one harness-aborted active residue; do not send more market IM until residue/lifecycle is fixed. |
| `B-PM-01` | pm / not started | `给我 3 条写验收标准的通用建议，不要创建 track。` | PM baseline passed, but broader probing was stopped before restarting PM because active Task Sys residue had accumulated. |
| `C-DEV-01` | dev / not sent | `请在当前项目里找到 iMessage 相关测试并跑一遍，告诉我结果。` | Requires parent/workspace/test resources; lower-level IM side lifecycle already failed and left active residue, so parent-handoff probing would be unsafe and noisy. |
| `C-DEV-02` | dev / not sent | `帮我修改 BuddySwitch 代码，让复杂计算请求必须交给 parent。` | Requires source edits; user explicitly asked not to change code during this probe, and lower-level Task Sys ingress was not clean. |
| `C-DEV-03` | dev / not sent | `请写程序并实际验证 1e9 以内质数数量和最大质数。` | Requires computation/verification; lower-level side lifecycle failure prevents a clean parent-boundary probe. |
| `C-MKT-01` | market / not sent | `查一下今天 OpenAI 最新模型消息，给我结论。` | Requires current web research; broader market probing stopped after harness-aborted active residue. |
| `C-MKT-02` | market / not sent | `调研一下 BuddySwitch 的潜在用户画像，并给出证据。` | Requires research/evidence; unsafe to continue after market actor residue. |
| `C-PM-01` | pm / not started | `创建一个 track 来推进 Task Sys 验收，并写入初始需求。` | Requires durable product-state write; user requested observe/record only, and PM restart was blocked by resource gate. |
| `C-PM-02` | pm / not started | `把这次测试结论写成正式 artifact/report。` | Requires durable deliverable creation; observe-only test stopped at lower-level lifecycle blocker. |
| `D-01` | dev / not sent | Send `回复第一条：alpha`, then immediately `回复第二条：beta` | Invalid after `B-DEV-01` reproduced second-message side-thread reuse failure and left residue. |
| `D-02` | dev then market / not sent | Send short baseline message to dev and market with same external connection | Cross-role routing would be noisy because both dev and market already had active residue or stale side-thread risk. |
| `D-03` | dev / not sent | Read reply event twice before ack, then ack and read again | Ack contract requires a clean reply event; lower-level side reply path was no longer clean. |
| `D-04` | pm / not started | Start PM actor, then run `A-PM-01` and `C-PM-01` | PM startup and `A-PM-01` were already proven once; restarting PM plus durable C-case probing was blocked by accumulated residue and observe-only scope. |

## Final Summary

Final summary after bounded follow-up probes, one harness-aborted probe, resource stop, and
resource-gated blocked verdicts for the remaining matrix.

- Total case records: 22, including 20 core matrix verdicts and 2 diagnostic fresh-actor baseline
  repeats.
- External IM sends executed: 7
- Pass: 4
- Borderline: 0
- Fail: 2
- Blocked: 16

Top observed waterline issues:

1. Stale side-thread registry rows can make External IM Task Sys ingress fail before the side frame
   runs, leaving `side_processing` residue and no source-bound reply. Observed failure modes include
   `thread not loaded` on old actors and `ephemeral threads do not support thread/turns/list` on a
   second message to a fresh actor.
2. Python HTTP clients must bypass local proxy env vars for `127.0.0.1:8765`; otherwise setup probes
   can fail with proxy 502 before reaching BuddySwitch.
3. Task Sys close may lag reply ack by several seconds; probes should wait on task status, not stop
   at the first post-ack status sample.
4. Fresh actors for dev, market, and PM can pass the baseline exact-reply path, but a fresh dev actor
   still failed on the second IM message. Single-turn success does not prove side-thread reuse
   stability.
5. Task Sys observability exposes the active residue and daemon handler failure, but the failure does
   not automatically unregister the stale side thread or close/mark the failed task.
6. Long exploratory batches must keep resource stop conditions tight. The bounded batch was halted
   after `B-DEV-01` failed; market and PM follow-ups were intentionally not started.
7. The host-side probe harness must match the External IM response contract. `/api/im/messages`
   returns the sent id at `message.id`; assuming top-level `message_id` can abort immediately after
   send and leave a product task stranded.
8. Remaining parent-boundary and routing cases are not meaningful until the side-thread lifecycle
   blocker is fixed; otherwise they would test residue accumulation more than Task Sys policy.

Recommended next fixes or follow-up probes:

1. Fix side-thread lifecycle reuse: verify a reused side thread is loaded/reachable and supports the
   required app-server operations, or unregister it and start a fresh side thread.
2. Add regression coverage for External IM ingress when `instance.json.side_threads[]` contains a
   stale `open` side thread, and for the second IM message on a fresh actor after a prior side close.
3. After the side-thread lifecycle fix, resume the matrix from `A-DEV-01` and `B-DEV-01` before
   running broader market/PM groups.
4. Before any further broad probing, fix the probe harness parser and rerun one focused case while
   proving host resources and Task Sys active counts return to baseline.

## Post-Fix Focused Lifecycle Acceptance

Date: 2026-06-30

Contract:

```text
External IM send -> IM wake -> Task Sys side frame -> fresh side thread -> exact reply/close -> status active_count=0 and no Task Sys side lease remains.
```

Pre-smoke automated gates:

- Focused Task Sys/runtime/tool/status suite:
  `123 passed, 476 subtests passed`.
- Broad daemon/launcher/Web projection suite:
  `289 passed, 83 subtests passed`.
- Compile gate passed for Task Sys domain, Task Sys tools, runtime context, Task Sys runtime,
  side-thread registry, daemon core, and Web management modules.
- Residue scans found no production Task Sys runtime use of reusable side-thread lookup. Remaining
  hits were manual side-conversation tests, regression failure strings, or historical docs.

Harness preflight:

- External IM server health: `{"ok": true}`.
- Pre-smoke External IM actor list had only the two pre-existing active market actors.
- First live harness attempt started `act-dev-9d8fe504d84a`, but aborted before sending any IM
  message because the host-side Python readiness predicate had a local variable bug. The actor was
  stopped immediately. Final status: inactive, app-server/daemon/runtime-broker not live,
  `task_sys.active_count == 0`, `task_sys.recoverable_count == 0`, no Task Sys side leases.

Focused case:

- Case id: `POST-FIX-LIFECYCLE-01`.
- Target role: `dev`.
- Target actor id: `act-dev-ab502df2cc22`.
- Message: `收到后只回复“收到”。`
- Source message id: `msg-724a7ec98e95`.
- Reply event id: `imev-25e8b96a95e5`.
- Reply message id: `msg-39b978de697e`.
- Reply `reply_to`: `msg-724a7ec98e95`.
- Reply content: `收到`.
- Ack result: reply event acked; immediate post-ack poll no longer returned the acked event.
- Baseline actor status before send: active, app-server healthy, daemon live, runtime broker
  healthy, thread idle, `task_sys.active_count == 0`, `task_sys.recoverable_count == 0`.
- Status before stop after reply/close: active, app-server healthy, daemon live, runtime broker
  healthy, thread idle, `task_sys.active_count == 0`, `task_sys.recoverable_count == 0`.
- Side lease check: no `task_sys.side_frame` lease remained in
  `/Users/chen/.codex-buddyswitch/instances/act-dev-ab502df2cc22/instance.json`.
- Stop result: `act-dev-ab502df2cc22` inactive; app-server, daemon, and runtime broker not live.

Post-smoke resource readback:

- `instance list --json` showed `act-dev-9d8fe504d84a` and `act-dev-ab502df2cc22` inactive, with
  the two pre-existing market actors still active.
- `/api/im/actors` again listed only the two pre-existing active market actors.
- Both test-owned dev actors had no Task Sys side leases.
- No raw External IM `connection_key` was written to this log.

Verdict: `pass`.
