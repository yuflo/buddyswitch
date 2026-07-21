# Dev Landing Page Multi-Demand Real-Actor Acceptance Execution Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:executing-plans` to execute this plan task-by-task. Delegation is
> not authorized for this run. Steps use Markdown checkboxes for tracking.

**Goal:** Use formal BuddySwitch CLI and real PM/Dev actors in the default
environment to determine whether immutable terminal Demands plus fresh live
roots work effectively across an in-flight supplement, a post-completion
correction, and a post-completion independent landing-page extension.

**Architecture:** PM supplies normal IM inbound messages; Dev owns Demand checks,
Task selection, source changes, verification, and reports. The controller never
names a Demand action in business messages and observes public projections,
rendered product behavior, and owned logs. Runtime data remains in the default
environment for review; only exact actor/process resources are cleaned up.

**Tech Stack:** `./buddyswitch-codex`, installed Codex App Server, Central IM,
daemon service, Demand Sys, Task Sys, launcher-owned `projects/app`, Dev-selected
frontend stack, local browser rendering, JSON/JQ, Git source identity.

**Design:**
`docs/memo/2026-07-21-dev-landing-page-multi-demand-real-actor-acceptance-design.md`

**Default shared root:** `/Users/chen/.codex-buddyswitch` — do not set a temporary
`BUDDYSWITCH_SHARED_ROOT` prefix for this run.

**Commit policy:** Runtime acceptance and its memos remain with the current
Phase 4 worktree. Do not create a plan-only/evidence-only commit and do not
commit or push without explicit user authorization.

---

## 0. Execution invariants

- Every actor lifecycle and interaction mutation uses formal public
  `./buddyswitch-codex` commands.
- Every business request reaches Dev through PM `message.send`, not Dev direct
  input, controller-written Demand state, or a pre-created Task.
- Direct PM input is dispatch-only control and must not perform product work.
- Do not tell Dev to absorb, revise, reopen, supersede, set a parent, add a
  dependency, or choose a Task.
- Do not edit `/Users/chen/.codex-buddyswitch/**` runtime objects directly.
- Source edits are made only by Dev inside its runtime-authorized
  `projects/app` mount.
- The controller may run the app's documented verification/preview commands and
  use supported browser inspection as external product evidence.
- Do not run `env reset`, `data cleanup`, or delete the shared project workspace.

Execution evidence is written to:

```text
docs/memo/2026-07-21-dev-landing-page-multi-demand-real-actor-acceptance-record.md
```

## 1. Freeze the real baseline

- [x] **Step 1: Record repository and runtime identity**

Run:

```bash
git rev-parse HEAD
git diff --binary | shasum -a 256
git ls-files --others --exclude-standard -z | xargs -0 shasum -a 256
git status --short
/Users/chen/.npm-global/bin/codex --version
./buddyswitch-codex env status
./buddyswitch-codex instance list
```

Expected: installed Codex is reported, default `instance list` is empty, browser
is inactive, and the complete dirty-worktree identity is retained.

- [x] **Step 2: Confirm project seed boundary before actor creation**

Run:

```bash
test ! -e /Users/chen/.codex-buddyswitch/project/workspace/projects/app
find projects/app -maxdepth 2 -type f | sort
```

Expected: the default shared project does not yet exist and repository
`projects/app` contains only the mount README. If the shared project already
exists, inspect it and stop rather than overwrite unknown user work.

## 2. Start exact real actors

- [x] **Step 1: Create PM and Dev through the default CLI**

Run separately:

```bash
./buddyswitch-codex instance start --role pm
./buddyswitch-codex instance start --role dev
```

Record both exact actor ids, thread ids, app-server PIDs/sockets, daemon PIDs,
runtime-broker PIDs/sockets, and installed Codex identities.

- [x] **Step 2: Set low-latency model depth**

Substitute only the observed ids:

```bash
./buddyswitch-codex instance capabilities "$PM_ACTOR_ID" set --parent fast --side fast
./buddyswitch-codex instance capabilities "$DEV_ACTOR_ID" set --parent balanced --side fast
```

Read both capability records back. Expected: PM is `fast/fast`, Dev is
`balanced/fast`.

- [x] **Step 3: Verify real inventory and seeded project**

Run `instance list` and `instance status` for both exact ids. Confirm:

- exactly two active real actors;
- healthy app server, daemon, and runtime broker;
- idle bootstrap threads;
- `/Users/chen/.codex-buddyswitch/project/workspace/projects/app/README.md`
  exists as the launcher-created shared source seed.

## 3. Stage A — initial runnable landing page

- [x] **Step 1: Dispatch A through PM → Dev IM**

Use one PM control turn that calls `message.send` exactly once to the observed
Dev identity with this business content:

```text
请在当前允许写入的 projects/app 中，从现有空白/README-only 状态创建一个新的、可本地运行的响应式单页 landing page，产品名为 FluxOps AI。

FluxOps AI 是面向数据平台团队的 AI 数据运维工具：发现数据管道异常，聚合同一事故的症状，解释可能根因，并引导安全恢复。页面必须清楚呈现用户问题、产品机制、核心工作流、可信边界和一个明确主 CTA；桌面和移动端都必须可用。

请选择当前范围所需的最小前端方案，不要为了未来扩展引入后端、账号系统、数据库或通用框架。完成后运行真实验证并检查实际渲染页面，记录启动命令、验证结果和改动文件。这是一个全新 app，允许在 README-only source root 中进行必要 scaffold。
```

The PM control prompt itself must say: dispatch only, create no PM Demand/Task,
do not implement, and return only the IM message id.

- [x] **Step 2: Prove inbound Demand before Task claims**

Poll:

```bash
./buddyswitch-codex demand list --actor "$DEV_ACTOR_ID"
```

Record A's IM id, Demand id, intake key, description, revision, checked revision,
parent, dependencies, and terminal state. Confirm its intake key references the
real IM message.

- [x] **Step 3: Catch A's active Task**

Poll once per second until a Demand-backed active Task appears:

```bash
./buddyswitch-codex task list --actor "$DEV_ACTOR_ID"
./buddyswitch-codex instance status "$DEV_ACTOR_ID"
```

Record the exact Task id, DemandRef/basis revision, lifecycle state, and active
count. Immediately proceed to Stage B while this Task is still active.

If A completes before the active interval is observed, record Stage B as not
proven and do not mislabel a later message as in-flight.

## 4. Stage B — in-flight same-deliverable supplement

- [x] **Step 1: Send B while A's Task is active**

PM sends exactly one new IM message to Dev:

```text
补充到正在开发的同一个 FluxOps AI landing page：不要使用图库式 AI 插画、发光渐变球或抽象机器人作为主视觉。请用页面内真实可读的 pipeline incident timeline、状态变化和 root-cause investigation flow，把“异常发现 → 症状聚合 → 根因解释 → 安全恢复”讲具体。它属于当前同一页面交付，不需要第二个页面或独立报告；同时保持移动端可读。
```

Do not mention A's Demand id, Task id, or any organization action.

- [x] **Step 2: Observe B's actor-owned organization**

Poll until B is checked. Read A and B with public `demand get`. Record:

- whether B remains live, is absorbed, becomes duplicate, or receives a
  parent/dependency;
- whether A's description/detail/revision changes;
- the actor's explanation from its Demand Check turn;
- any failed/recovered action and its state effect.

- [x] **Step 3: Prove Task seriality during B**

Sample `task list` throughout capture and organization. Expected product safety:
active Task count never exceeds one. Do not require a second Task merely because
A's Demand revision changes; record the actor's actual reconciliation behavior.

## 5. Stage A/B product boundary

- [x] **Step 1: Wait for terminal Demand/Task and inspect source**

Wait until no Dev Task is active and A/B are acknowledged. Record the terminal
receipt(s). Inspect, without editing:

```bash
find /Users/chen/.codex-buddyswitch/project/workspace/projects/app -maxdepth 3 -type f | sort
```

Read the app README/package scripts and changed source. Determine exact install,
verification, and preview commands from current files rather than assuming a
framework.

- [x] **Step 2: Re-run the app's exact verification**

Run the documented non-destructive verification commands in the shared project
source. Expected: exit 0 with no test/build/typecheck error. Record command,
toolchain identity, duration, and output summary.

- [x] **Step 3: Render desktop and mobile A/B state**

Start the documented local preview server, open the actual page, and capture:

- desktop viewport around 1440×1000;
- mobile viewport around 390×844;
- console/runtime errors;
- visible presence of the requested incident timeline/root-cause mechanism;
- source identity corresponding to the render.

Leave the preview server running only while required for inspection.

## 6. Stage C — adaptive post-completion correction

- [x] **Step 1: Select one correction from rendered evidence**

Choose the first observed material problem in this order:

1. runtime failure, broken layout, overflow, or inaccessible interaction;
2. unreadable contrast or hierarchy;
3. missing/unclear requested product mechanism;
4. broken CTA or navigation behavior;
5. unsupported material claim.

Record the screenshot/DOM evidence and exact affected text or component. If none
is present, use the narrow fallback: request one concrete mobile accessibility
improvement based on computed/visible evidence. Do not invent a defect.

- [x] **Step 2: Dispatch C as concrete page feedback**

PM sends one message naming only the observed problem, evidence, and expected
visible correction. It must state that the delivered FluxOps page needs this
correction, but must not mention Demand lifecycle, reopening, supersession, or
relation actions.

- [x] **Step 3: Observe C's Demand/Task behavior**

Record C's capture, check, matching candidates, actor judgment, organization,
Task selection, and exact DemandRef. Specifically prove whether A stays terminal,
whether C is a fresh root, and whether any current action links them.

- [x] **Step 4: Verify and render the corrected page**

After C completes, rerun the same applicable verification and render the same
desktop/mobile viewports. Confirm the selected defect materially changed and no
new runtime error appeared.

Classify the result without changing code:

- correction invalidated A's original acceptance evidence;
- or A was valid and C is a later quality improvement.

## 7. Stage D — independent related capability

- [x] **Step 1: Dispatch D after C is terminal**

PM sends one new Dev message:

```text
在已经完成并纠正过的 FluxOps AI landing page 上，新增一个独立可交付的互动转化能力：incident-cost estimator。用户输入每月事故次数、每次平均工程师投入小时和团队综合小时成本，页面计算月度事故人工成本；再提供一个由用户自行调整的可恢复比例，显示对应的可恢复机会。所有结果都必须明确标为场景估算，不得承诺真实节省。

它应融入现有页面并复用当前视觉系统，但这是一个新的互动能力，不是对前面页面缺陷的修正，也不要整体重写页面。完成后验证输入、计算、边界值和移动端交互。
```

- [x] **Step 2: Observe D's Demand/Task behavior**

Record the same Demand/Task fields as C. Prove whether D is a fresh root and
whether any terminal A/C Demand is visible or linkable during Demand Check.
Compare the actor's reasoning for D with C rather than treating both as one
generic “related” case.

- [x] **Step 3: Verify estimator semantics and render D**

Run the app's exact verification. Exercise at least:

- zero incidents;
- ordinary positive values;
- an edited recoverable percentage;
- invalid or boundary input behavior;
- mobile interaction.

Check the displayed formula against the inputs and confirm the UI labels results
as scenario estimates. Capture final desktop/mobile evidence.

## 8. Final actor and state audit

- [x] **Step 1: Ask Dev for a read-only implementation recap**

Use one Dev direct control turn only after all Demand work is terminal. Tell Dev
not to create Demand/Task or modify source; ask it to summarize current files,
verification, A/B/C/D context continuity, repeated work, and residual risk from
the current workspace. Capture the exact tool calls to ensure the turn remained
read-only.

- [x] **Step 2: Audit explicit runtime requirements**

Build the execution record with pass/fail/partial/incomplete evidence for:

- formal CLI and real Codex identity;
- PM → Dev IM capture for A/B/C/D;
- B captured during A's active Task;
- Demand checks and final revision acknowledgements;
- maximum active Task count;
- A/B/C/D rendered outcomes;
- C completion validity versus escaped-defect interpretation;
- D independent-deliverable interpretation;
- context reconstruction with no cross-terminal relation;
- daemon and browser errors/recovery;
- cleanup and remaining default state.

- [x] **Step 3: Return to the relation design question**

Evaluate H1–H4 separately for C and D. The final analysis must state:

- where fresh-root execution worked;
- where stored Demand organization failed to explain the work;
- whether the pain came from premature completion or missing lineage;
- what relation capability appears valuable;
- what remains unproven in a single-actor/single-active-Task run.

Do not implement a Demand relation change in this execution.

## 9. Exact non-destructive cleanup

- [x] **Step 1: Stop preview/browser resources**

Stop only the preview process started for this run. Release Dev browser ownership
through:

```bash
./buddyswitch-codex env browser release --instance "$DEV_ACTOR_ID"
```

Confirm no preview PID, owned browser PID, or browser schedule remains.

- [x] **Step 2: Stop and delete exact actors**

Run only for the two observed ids:

```bash
./buddyswitch-codex instance stop "$DEV_ACTOR_ID"
./buddyswitch-codex instance delete "$DEV_ACTOR_ID" --yes
./buddyswitch-codex instance stop "$PM_ACTOR_ID"
./buddyswitch-codex instance delete "$PM_ACTOR_ID" --yes
./buddyswitch-codex instance list
```

Expected: default instance list is empty. Do not run `env reset` or remove the
shared project workspace.

- [x] **Step 3: Prove process cleanup and retained evidence**

Verify no process/socket matches the two actor identities. Confirm:

- the generated FluxOps source remains under the default shared project;
- Demand/Task runtime projections remain available for analysis;
- repository `projects/app` and unrelated dirty worktree files were not changed
  by Dev;
- the execution record states exactly what remains in the default environment.

## 10. Artifact verification

- [x] **Step 1: Verify memo and worktree integrity**

Run:

```bash
git diff --check
rg -n 'T''BD|T''ODO|impl''ement later|fi''ll in' \
  docs/memo/2026-07-21-dev-landing-page-multi-demand-real-actor-acceptance-design.md \
  docs/memo/2026-07-21-dev-landing-page-multi-demand-real-actor-acceptance-plan.md \
  docs/memo/2026-07-21-dev-landing-page-multi-demand-real-actor-acceptance-record.md
git status --short
```

Expected: clean formatting, no placeholder, all execution checkboxes resolved,
and no unexpected repository source change from the default runtime project.

This is a runtime MILESTONE acceptance, not repository FINAL. Do not run the
full BuddySwitch test suite merely because the experiment completed; executable
BuddySwitch source is not changed by this plan.
