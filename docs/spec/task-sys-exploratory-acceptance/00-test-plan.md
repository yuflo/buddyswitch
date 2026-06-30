# Task Sys Exploratory Acceptance Test Plan

Date: 2026-06-30

## Target

Probe the current BuddySwitch Task Sys upgrade waterline through realistic External IM conversations with active actors, then use runtime evidence to identify which behaviors are accepted, borderline, or broken.

This is not a normal unit-test pass. It is an exploratory acceptance run for the current 0-to-1 product loop:

```text
External IM API -> actor wake -> Task Sys task -> side frame or parent frame
  -> source-bound reply / absorbed state -> task_sys.close
  -> External IM event read + explicit ack -> runtime/task status clean
```

The run should make the system behave, not just inspect code. Each case must send an actual External IM message, observe the actor result, inspect daemon / Task Sys state, and record what happened.

## Focused Lifecycle Acceptance Gate

After the Task Sys side-frame lifecycle fix, run one focused case before expanding this matrix:

```text
External IM send -> IM wake -> Task Sys side frame -> fresh side thread -> exact reply/close -> status active_count=0 and no Task Sys side lease remains.
```

This gate must use the Integration External IM API, a test-owned actor when one must be started,
and a single exact-reply message. It passes only when the reply is source-bound, the consumed reply
event is acked, the actor status returns to the recorded Task Sys active-count baseline, and no
test-owned `task_sys.side_frame` lease remains in the side-thread registry.

Do not resume the broader exploratory matrix until this single loop passes with clean resources.

## Scope

In scope:

- Task Sys ingress for External IM-origin work.
- Side-frame resource-boundary behavior.
- Parent handoff behavior when side should not complete a task.
- Explicit Task Sys close behavior after side or parent completion.
- Runtime status and daemon breadcrumbs for Task Sys residue.
- Role differences across `dev`, `market`, and `pm`.
- External IM event read / ack as the test transport boundary.

Out of scope:

- iMessage channel transport behavior.
- Messages.app delivery and sender route state.
- Phone-side UX timing.
- Web Management browser UI interaction.
- Source code fixes during the exploratory run unless the user explicitly switches the task from testing to implementation.

## Current Runtime Assumptions

Known active actors at plan time:

- `dev`: `act-dev-344fa10d0f0b`, active and healthy.
- `market`: `act-market-3d4839c64a96`, active and healthy.
- `pm`: not currently active. Start it only when executing this plan.

PM startup command:

```bash
./buddyswitch-codex instance start --role pm --json
```

Actor discovery command:

```bash
./buddyswitch-codex instance list --json
```

External IM API base URL:

```text
http://127.0.0.1:8765
```

The tester should confirm `/api/health` and `/api/actors` before sending test messages.

## Highlight: Test Resource Lifecycle Gate

**Do not let this exploratory run exhaust host test resources.** Treat every actor service, daemon,
app-server, runtime broker, browser process, socket, marker file, and temporary test helper as an
owned test resource, following `docs/bitter/2026-05-26-test-resource-lifecycle-principles.md`.

Resource lifecycle rules for this run:

- Record the actor/resource baseline before sending test messages: `instance list`, per-actor
  `instance status`, relevant daemon pids, and Task Sys active counts.
- Start only the resources required by the current block. In particular, start `pm` only when the PM
  block is about to run.
- Do not expand from one focused case to the full matrix until the focused case proves both behavior
  and a clean resource/status return path.
- After each role block, check `instance status`, daemon liveness, Task Sys active residue, and
  unacked External IM events before continuing.
- Any actor started solely for this acceptance run, especially `pm`, must be stopped when its cases
  and any required follow-up probes are done, unless the run log records an explicit reason to keep
  it open.
- If residual daemons, brokers, browsers, sockets, or active Task Sys tasks accumulate unexpectedly,
  stop broad testing and record the lifecycle issue before proceeding.
- The final run log must include resource cleanup evidence, not just case verdicts.

## Test Method

Use the Integration External IM API directly, not the Web IM API and not the iMessage channel.

Recommended per-run flow:

1. Create one external connection for the test run:

   ```http
   POST /api/im/connections
   {"display_name":"task-sys-exploratory-acceptance"}
   ```

2. Keep the returned `connection_key` only in the test process memory.

3. Discover reachable actors:

   ```http
   GET /api/im/actors
   Authorization: Bearer <connection_key>
   ```

4. Send each test message:

   ```http
   POST /api/im/messages
   Authorization: Bearer <connection_key>
   {
     "target_identity_id": "<actor_id>",
     "content": "<case message>"
   }
   ```

5. Poll actor replies:

   ```http
   GET /api/im/events?wait_ms=30000&limit=20
   Authorization: Bearer <connection_key>
   ```

6. Fetch each returned reply message:

   ```http
   GET /api/im/messages/<message_id>
   Authorization: Bearer <connection_key>
   ```

7. Ack each consumed reply event:

   ```http
   POST /api/im/events/ack
   Authorization: Bearer <connection_key>
   {"event_id":"<event_id>"}
   ```

8. Inspect actor runtime state:

   ```bash
   ./buddyswitch-codex instance status <actor_id> --json
   ```

9. Inspect relevant daemon log and Task Sys records. Runtime object reads are allowed for this host-side test audit, but product-mode actors must not edit runtime object files directly.

Do not use `tmp/im_reply_console.py` for this plan. That helper uses `/api/web/im/*` and the Web Management server-owned web identity, which is useful for manual chat but is not the cleanest External IM boundary probe.

## Evidence To Record For Every Case

For each case, record the following in `01-run-log.md`:

- Case id.
- Target role and actor id.
- Sent message id, conversation id, and event id.
- Reply event id and reply message id, if any.
- Reply `reply_to` value.
- Reply summary or exact short excerpt.
- Ack result.
- Actor instance status after completion.
- Task Sys task id.
- Task Sys task status.
- Task Sys close result or parent handoff params.
- Daemon handler result line.
- Final verdict: `pass`, `borderline`, `fail`, or `blocked`.
- Notes on whether observed behavior matches this plan's expectation.

Do not record raw `connection_key`.

## Acceptance Vocabulary

Use these verdicts consistently:

- `pass`: observed behavior matches expectation and runtime state is clean.
- `borderline`: product behavior is usable but exposes an unclear policy boundary or weak observability.
- `fail`: observed behavior contradicts expected Task Sys semantics.
- `blocked`: the case could not be completed because setup, actor availability, or transport failed.

Runtime state is clean when:

- The reply event is acked if one was consumed.
- The source message is either replied or intentionally absorbed.
- The Task Sys task is `closed`, or is active only when the case expects parent work still in progress.
- `instance status` does not show unexpected active Task Sys residue.
- Daemon handler status reflects trigger dispatch, not external phone delivery.

## Core Test Matrix

### Group A: Side-Eligible IM Closure

These cases should complete in side because they only require the current IM source, a short exact reply or absorbed disposition, and `task_sys.close`.

| Case | Role | Message | Expected Result | Probe Point |
|---|---|---|---|---|
| A-DEV-01 | dev | `收到后只回复“收到”。` | side sends exact reply and closes task | Baseline IM exact reply |
| A-MKT-01 | market | `收到后只回复“收到”。` | side sends exact reply and closes task | Market role baseline |
| A-PM-01 | pm | `收到后只回复“收到”。` | side sends exact reply and closes task | PM role baseline |
| A-DEV-02 | dev | `你现在能帮我做什么？用三句话回答。` | side answers briefly and closes task | Capability short reply |
| A-MKT-02 | market | `你作为市场角色能帮我做什么？用三句话回答。` | side answers briefly and closes task | Role-specific capability |
| A-PM-02 | pm | `你作为 PM 角色能帮我做什么？用三句话回答。` | side answers briefly and closes task | Role-specific capability |

Expected evidence:

- Reply message has `reply_to` equal to the source message id.
- Task status is `closed`.
- `close_result.processor` is `side`.
- No `parent_handoff_params`.
- No active Task Sys residue after completion.

### Group B: Borderline Lightweight Content

These cases intentionally sit near the side/parent boundary. They help determine whether the current prompt policy is too permissive.

| Case | Role | Message | Expected Result | Probe Point |
|---|---|---|---|---|
| B-DEV-01 | dev | `给我一个 Python 判断数字是否为质数的小函数，不需要运行。` | side may answer and close | Code snippet without workspace or verification |
| B-MKT-01 | market | `给我 3 个常见用户访谈问题，不需要调研。` | side may answer and close | Generic market advice without research |
| B-PM-01 | pm | `给我 3 条写验收标准的通用建议，不要创建 track。` | side may answer and close | Generic PM advice without shared-state writes |

Expected evidence:

- If side closes, the reply must avoid claiming external verification, research, or product-state mutation.
- If parent handoff happens, it is acceptable only if the handoff reason is concrete and resource-based.
- Mark as `borderline` if side completes with claims that imply unperformed verification, research, or state mutation.

### Group C: Must Escalate To Parent

These cases require resources that side is not supposed to use. They should produce `task_sys.need_parent` and then parent work, or at minimum an active parent-processing task.

| Case | Role | Message | Expected Result | Probe Point |
|---|---|---|---|---|
| C-DEV-01 | dev | `请在当前项目里找到 iMessage 相关测试并跑一遍，告诉我结果。` | side calls `task_sys.need_parent`; parent handles workspace/test work | Workspace and tests |
| C-DEV-02 | dev | `帮我修改 BuddySwitch 代码，让复杂计算请求必须交给 parent。` | parent required | Source edits and implementation |
| C-DEV-03 | dev | `请写程序并实际验证 1e9 以内质数数量和最大质数。` | parent required | Computation and verification |
| C-MKT-01 | market | `查一下今天 OpenAI 最新模型消息，给我结论。` | parent required | Web/research/evidence |
| C-MKT-02 | market | `调研一下 BuddySwitch 的潜在用户画像，并给出证据。` | parent required | Research and evidence |
| C-PM-01 | pm | `创建一个 track 来推进 Task Sys 验收，并写入初始需求。` | parent required | Shared product-state write |
| C-PM-02 | pm | `把这次测试结论写成正式 artifact/report。` | parent required | Durable deliverable |

Expected evidence:

- Side does not directly complete the requested work.
- Task has `side_result.outcome == "need_parent"` at some point.
- `parent_handoff_params` explain the resource need.
- Parent frame either completes source-bound work and calls `task_sys.close`, or the task remains visibly active in `parent_processing`.
- Mark as `fail` if side directly claims it ran tests, edited files, researched the web, created product state, or produced artifacts.

### Group D: Routing, Isolation, And Reuse

These cases test cross-message, cross-role, and event-consumption integrity.

| Case | Target | Message Pattern | Expected Result | Probe Point |
|---|---|---|---|---|
| D-01 | dev | Send `回复第一条：alpha`, then immediately `回复第二条：beta` | Two source-bound replies, each with correct `reply_to` | Side-thread reuse and source isolation |
| D-02 | dev then market | Send short baseline message to dev and market with same external connection | Replies come from correct actors | Actor routing isolation |
| D-03 | dev | Read reply event twice before ack, then ack and read again | Same event repeats before ack; disappears after ack | External IM explicit ack contract |
| D-04 | pm | Start PM actor, then run A-PM-01 and C-PM-01 | PM is reachable and Task Sys policy holds | Newly started actor behavior |

Expected evidence:

- No reply is attributed to the wrong actor.
- No reply uses the wrong source `reply_to`.
- External IM event ack advances only after explicit ack.
- PM startup produces a healthy active actor before PM cases run.

## Role-Specific Waterline Expectations

### Dev

Side may:

- Acknowledge short messages.
- Provide brief generic explanations or small snippets when no workspace or verification is requested.

Parent should handle:

- Reading or editing source files.
- Running tests, builds, formatters, app servers, or scripts.
- Verifying computational claims.
- Creating durable implementation evidence.

### Market

Side may:

- Answer short role-capability questions.
- Provide generic non-researched brainstorming if the user explicitly does not ask for research or evidence.

Parent should handle:

- Web search.
- Evidence collection.
- Market research synthesis.
- Competitive analysis.
- Durable reports or artifacts.

### PM

Side may:

- Answer short role-capability questions.
- Provide generic advice that does not mutate product state.

Parent should handle:

- Track creation or updates.
- Requirements/material/proof publication.
- Product decisions that should become durable state.
- Artifact/report creation.

## Completion Criteria

The exploratory test task is complete when:

1. PM actor has either been started and tested, or PM startup is explicitly marked blocked with reason.
2. All Group A cases have a recorded verdict.
3. At least one Group B case per role has a recorded verdict.
4. All Group C cases have a recorded verdict.
5. All Group D cases have a recorded verdict, unless a lower-level blocker makes later isolation tests invalid.
6. Every consumed External IM reply event has been acked or explicitly recorded as unacked because the case is testing pre-ack repeat behavior.
7. `01-run-log.md` contains a final summary with counts by verdict.
8. The final summary lists the top observed waterline issues, ordered by product impact.
9. No raw `connection_key` is written to docs, logs, shell history snippets, or committed files.
10. Resource lifecycle is verified: resources started by this run are stopped or explicitly justified,
    and the run log records final actor/service/Task Sys residue status.

## Failure Triage Rules

When a case fails:

- Do not immediately patch code.
- Record the exact observed runtime path first.
- Identify whether the failure is in External IM transport, actor wake, Task Sys side decision, parent handoff, close semantics, status projection, or observability.
- If the failure reproduces in two adjacent cases, stop expanding the matrix and focus on root-cause investigation.
- If a case leaves active Task Sys residue unexpectedly, record the task id and do not hide it by manually editing runtime state.

## Execution Notes

This plan intentionally allows non-trivial runtime and token cost. The goal is to simulate realistic human-to-actor usage deeply enough to expose policy gaps and product waterline issues.

Use a small automation script or inline Python HTTP client for execution so the `connection_key`
stays in process memory. Avoid shell commands that expose the key in argv, terminal history, or
copied logs. The client must bypass local proxy environment variables for `127.0.0.1:8765`, for
example by using `urllib.request.ProxyHandler({})` or `curl --noproxy '*'`, otherwise localhost
requests may be sent through `HTTP_PROXY`/`HTTPS_PROXY` and fail before reaching BuddySwitch.

After each role block, run:

```bash
./buddyswitch-codex instance status <actor_id> --json
```

and record whether `daemon.task_sys.active_count` is expected for that point in the run.
