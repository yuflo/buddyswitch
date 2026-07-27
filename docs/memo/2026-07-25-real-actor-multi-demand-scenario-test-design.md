# Real Actor Multi-Demand Scenario Test Design

Status: review draft

Date: 2026-07-25

Scope: Demand organization and serialized Demand → Task → native Goal operation

## 1. Purpose

This design defines six real Web Actor scenarios across the `market`, `dev`,
and `design` roles. Each scenario uses six to eight natural need-bearing
messages plus ordinary conversational probes. The messages must exercise how
BuddySwitch distinguishes, organizes, mutates, selects, executes, reconciles,
and continues multiple Demands.

The exact acceptance claim is:

> In a fresh Actor, six to eight related, supplemental, changed, independent,
> and withdrawn user inputs produce the intended self-contained canonical
> Demand pool; at most one Task/native Goal is active; native Goal terminal
> state does not automatically terminalize its Demand; an independent parent
> orchestration turn reconciles the latest Demand against durable evidence and
> selects exactly one next Demand from the complete live pool; Web-visible
> behavior, persisted state, tool results, and logs agree.

The immediate goal is product discovery and acceptance evidence. This memo
does not authorize architecture or runtime changes. A defect found during a
scenario stops that scenario at the nearest broken invariant and receives a
separate owner-correct diagnosis before any repair.

## 2. Scope boundaries

### 2.1 In scope

- Real actors created through the current BuddySwitch CLI and Web product.
- Natural multi-turn communication rather than bulk scripted message
  injection.
- The complete current path:

```text
Web inbound Message
  → Demand ingress receipt
  → isolated demand-triage side
  → one triage resolution
  → canonical Demand mutation or no Demand effect
  → Demand pool attention
  → one active Task/native Goal
  → durable result and user-facing delivery
  → Task terminal recording
  → independent parent Demand reconciliation
  → at most one next Task selection
```

- The six current triage decisions:

```text
no_action_needed
handled
create
merge_intake
revise
cancel
```

- Canonical Demand count, content, revision, source provenance, and lifecycle.
- Actor-created independent Demands.
- Active-Task serialization and waiting live Demands.
- Evidence-based Demand completion or deliberate preservation as live.
- A new Demand that follows a completed Demand without reopening or mutating
  the terminal Demand.
- Web-readable Message and Artifact delivery.
- Daemon, App Server, runtime broker, Demand, Task, Goal, side-thread, and
  Message identity correlation.
- Resource cleanup after every scenario.

### 2.2 Explicitly out of scope

- Whether the triage side can accurately describe native Goal progress.
- Quality of progress replies that require Work Goal context.
- Multi-Task or multi-thread parallel execution.
- Daemon outage and replay testing.
- Remote Codex execution.
- Broad role capability or tool permission review.
- Visual polish beyond the concrete scenario acceptance contract.
- Production-scale applications or exhaustive market reports.
- Multiple test drivers sending messages or controlling the same Web session.

Conversational progress questions remain useful realism. In this test they
prove only that ordinary communication does not accidentally create a
long-lived Demand. Their substantive answer quality is not scored.

## 3. Why six bounded scenarios

The selected structure is two scenarios per role:

| Role | Full-loop anchor | Organization-pressure variant |
|---|---|---|
| Market | NVIDIA expansion and open-model strategy | Enterprise AI coding-tool procurement |
| Dev | Local schedule manager | Local research evidence notebook |
| Design | AI research workspace | Healthcare appointment flow |

This is preferable to one long cross-role story because each Actor owns an
independent Demand aggregate and role-specific execution capabilities. A
cross-role saga would confound Demand semantics with collaboration and
permission behavior.

It is also preferable to executing every Demand in every scenario. Five to
eight canonical Demands per scenario would require dozens of expensive native
Goals while providing poor defect locality. Each scenario instead contains
six to eight need-bearing messages expected to converge to approximately
three to five canonical Demands.

## 4. Execution waves

### 4.1 Wave A — complete-loop anchors

Run these first:

1. Market M1 — NVIDIA expansion and open-model strategy.
2. Dev D1 — local schedule manager.
3. Design G2 — AI research workspace.

Each Wave A scenario continues until at least two Tasks have been processed
serially, or until a hard invariant fails. These scenarios cover:

- mutation of a Demand while its existing Task is active;
- latest-Demand reconciliation after Goal terminal state;
- selection from multiple waiting live Demands;
- Actor self-created Demand behavior;
- a new correction Demand after a prior Demand is completed.

### 4.2 Wave B — organization-pressure variants

Run only after Wave A has no unresolved hard failure:

4. Market M2 — enterprise AI coding-tool procurement.
5. Dev D2 — local research evidence notebook.
6. Design G1 — healthcare appointment flow.

Each Wave B scenario continues through:

1. the first Task/Goal terminal result;
2. independent parent Demand reconciliation;
3. creation and binding of one next Task.

The remaining pool may then be inspected and the isolated Actor removed. The
purpose is to broaden semantic judgment samples without paying to finish
every non-essential deliverable.

## 5. Shared real-user execution protocol

### 5.1 Environment isolation

- Use a fresh Actor for every scenario.
- Use a clean isolated BuddySwitch shared root for the acceptance run.
- Start the product through current public CLI entrypoints.
- Use the real Web messaging and Actor console surfaces.
- Do not edit runtime object files directly.
- Record Actor id, main thread id, role, model configuration, shared-root
  identity, Web URL, and source commit before the first message.

### 5.2 Test-driver and Sub-agent ownership

Use a hybrid execution model:

```text
one primary Agent
  → sole WebUI driver and sole test write owner

read-only Sub-agent A
  → CLI and log correlation observer

read-only Sub-agent B
  → Demand / Task / Goal state auditor
```

The WebUI remains the only real consumer entry for scenario actions. Sub-agents
increase observation coverage; they do not become additional users, product
drivers, or mutation owners.

This is an intentional choice between two different test models:

```text
selected
  one WebUI conversation driver
  + parallel read-only CLI/log observers

rejected
  multiple Sub-agents driving the Actor through WebUI or CLI
```

The selected model is more efficient for this acceptance target because the
expensive part is native Goal execution, not observation. Read-only Sub-agents
can correlate logs and canonical state while the primary Agent waits, without
adding another inbound sequence. Multiple driving agents would instead:

- stop simulating one human's continuous conversation;
- introduce competing Message order and timing;
- make Demand merge, revise, cancel, and Task-selection outcomes harder to
  attribute;
- allow a CLI write path to bypass the Web consumer path being accepted;
- risk testing multi-writer concurrency, which is explicitly outside the
  current one-Task scope.

CLI use by a Sub-agent is therefore limited to read-only inspection through
public status/projection commands and attributable log reads. It must not send
messages, create or mutate Demands, create Tasks, control Goals, start or stop
Actors, or perform cleanup. A second WebUI session is not used as another
driver. If later work needs multi-writer or multi-user acceptance, that is a
separate scenario with its own causal and concurrency contract.

| Participant | Owned surface | Allowed actions | Forbidden actions |
|---|---|---|---|
| Primary Agent | WebUI, scenario sequence, final consumer observation | Create the Actor, send every Message, wait, read replies and Artifacts, decide when a checkpoint is satisfied, stop and clean up the scenario | Delegate Web writes to an observer; send the next need before the current checkpoint is understood |
| Sub-agent A — log observer | CLI-visible daemon, App Server, runtime broker, and side-lifecycle logs | Read and correlate actor, Message, source, side thread, turn, Demand, Task, Goal, and broker identities; report new deltas and contradictions | Control the browser, send Messages, invoke mutations, start or stop the Actor, clean runtime state |
| Sub-agent B — state auditor | Public or owner-approved read-only Demand, Task, Goal, Message, and Actor projections | Read checkpoint state, compare expected and observed topology, record revisions and active-slot state | Edit runtime JSON directly; call Demand, Task, Goal, or Message mutations; infer success from state convergence alone |
| Evidence reviewer | Frozen scenario evidence after a stop or checkpoint | Review the collected Web, state, contract, and log evidence for contradictions or missing proof | Continue the scenario, repair state, or manufacture missing evidence |

The primary Agent is the only participant allowed to produce product input.
This preserves one causal sequence:

```text
Primary sends one Web Message
  → Sub-agent A observes the attributable log chain
  → Sub-agent B observes the attributable state transition
  → Primary confirms the Web-visible result
  → Primary sends the next Message
```

Sub-agent observations are read-only and checkpoint-bound:

1. receive the exact Actor id, main thread id, Message id, and expected
   checkpoint from the primary Agent;
2. report only new state or log deltas attributable to those identities;
3. distinguish “not yet observed” from “failed”;
4. notify the primary Agent immediately when contract result and persisted
   effect disagree;
5. do not retry, mutate, or advance the scenario independently.

Do not run multiple scenarios in parallel during Wave A. Shared browser focus,
runtime resources, and interleaved logs would weaken failure attribution. Wave
B also remains serial unless Wave A has proved that the environment provides
clean scenario isolation and a later review explicitly authorizes parallel
execution.

If any observer accidentally sends a Message, invokes a mutation, controls the
Web session, or changes runtime state, the current scenario evidence is
invalid. Stop, clean up, and restart that scenario with a fresh Actor. Do not
explain away observer interference as product concurrency.

### 5.3 Message pacing

Do not send all scenario inputs back-to-back. After each need-bearing input:

1. confirm the Web Message persisted and record `message_id`;
2. locate `source_key=im.message.created:<message_id>`;
3. observe the ingress receipt reach `settled`;
4. record the final triage decision;
5. read the affected Demand and record id, canonical content, lifecycle,
   revision, and source refs;
6. confirm the side lease is eventually removed;
7. confirm that an existing active Task id did not change and no second active
   Task appeared;
8. only then send the next ordinary conversational or need-bearing message.

One scenario may intentionally send two supplements close together to exercise
stale-reference recovery, but that concurrency must be named before sending
the second message. It must not become the default pacing pattern.

### 5.4 State-based waiting

Use state transitions, not arbitrary sleeps, as the completion signal:

| Boundary | Observation cadence | Diagnostic threshold |
|---|---:|---:|
| Message → settled triage receipt | 5–10 seconds | inspect after 90 seconds without settlement |
| Goal execution | 30–60 seconds | inspect when expected activity or logs stop advancing |
| Goal terminal → Task terminal | 5–10 seconds | inspect after 60 seconds |
| Task terminal → parent reconciliation | 5–10 seconds | inspect after 60 seconds |
| Parent reconciliation → next Task binding | 5–10 seconds | inspect after 60 seconds |

A threshold is not permission to declare failure or blindly retry. It is the
point to correlate logs, leases, receipts, Task state, and App Server state.

### 5.5 Human-style conversation

Insert two or three natural messages per scenario, for example:

- “收到，你继续。”
- “你现在主要在核对哪些来源？”
- “先不用展开，只确认刚才的范围是否已经更新。”

Expected core behavior:

- acknowledgements with no requested work produce `no_action_needed`;
- an immediately answerable question may produce `handled`;
- neither form creates or mutates a canonical Demand unless the message also
  changes an actual obligation.

The substantive accuracy of Work-progress replies is excluded from this
acceptance run.

## 6. Scenario M1 — NVIDIA expansion and open-model strategy

### 6.1 Product brief

Create one Market Actor. Ask for a concise current report instead of an
open-ended investment thesis. Limit the primary report to 900 Chinese
characters plus one compact table.

Real-source starting points:

- [NVIDIA author profile noting the Gretel acquisition](https://developer.nvidia.com/blog/author/johnmyers/)
- [NVIDIA Nemotron 3 official technical overview](https://developer.nvidia.com/blog/building-nvidia-nemotron-3-agents-for-reasoning-multimodal-rag-voice-and-safety/)

The Actor must discover and verify current sources itself. Factual answers and
prices are not frozen test fixtures.

### 6.2 Need-bearing messages

| Step | Timing | User message | Expected Demand effect |
|---|---|---|---|
| M1-1 | Actor idle | “调研英伟达过去18个月公开披露的收购动作，区分已完成、已宣布和传闻；分析每笔动作的战略意图，输出一份不超过900字的中文简报并回复我。” | `create A`; A enters Task/Goal |
| M1-2 | A Goal active | “在同一份收购简报里，再加一列：每笔交易补足了数据、软件、网络还是人才能力，并标注官方来源日期。” | `merge_intake A` |
| M1-3 | A Goal active | “另外单独调研英伟达最近对开放权重或开源模型的公开表态，给我一条带出处的时间线。” | `create B`; B waits |
| M1-4 | A Goal active | “开放模型那项再补充 Nemotron 3 已开放的权重、数据、训练配方和许可证，只写官方材料能确认的内容。” | `merge_intake B` |
| M1-5 | A Goal active | “再单独给我一页判断：这些动作对企业采购 AI 基础设施意味着什么，分机会、风险和待观察。” | `create C`; C waits |
| M1-6 | A Goal active | “第一份收购简报范围改一下：只看过去12个月，并且删除无法由公司或监管文件确认的传闻。” | `revise A` |
| M1-7 | A Goal active | “采购影响那一页先不用了，撤回。” | `cancel C` |

Conversational probes:

- “收到，你继续查。” → no Demand effect.
- “你有没有把合作和收购分开？只确认一下。” → no Demand;
  reply quality excluded.

### 6.3 Expected topology

```text
A: live, revised, multiple source refs
B: live, merged, multiple source refs
C: terminal:canceled
active Tasks: at most one
```

When A's original Goal becomes terminal:

- if the durable result and delivery satisfy A's latest revision, complete A
  and select B;
- if they satisfy only the older A meaning, keep A live and compare its
  remaining work against B;
- never complete A merely because its bound Goal is complete.

Hard failure: the old Task result omits the revised twelve-month,
official-confirmation boundary but parent reconciliation completes the latest
A anyway.

## 7. Scenario M2 — enterprise AI coding-tool procurement

### 7.1 Product brief

Create one Market Actor. Compare only official current materials and stamp
pricing claims with the retrieval date.

Real-source starting points:

- [GitHub Copilot plans](https://github.com/features/copilot/plans)
- [GitHub Copilot organization and enterprise billing](https://docs.github.com/en/copilot/concepts/billing/organizations-and-enterprises)
- [OpenAI Codex Security](https://help.openai.com/en/articles/20001107)

### 7.2 Need-bearing messages

| Step | User message | Expected Demand effect |
|---|---|---|
| M2-1 | “为50人研发团队比较 GitHub Copilot、OpenAI Codex 和 Cursor，关注成本、代码代理能力、管理控制和数据政策，输出采购短名单。” | `create A` |
| M2-2 | “在同一份比较中加入50席的月度与年度成本估算，所有价格写明检索日期和适用套餐。” | `merge_intake A` |
| M2-3 | “另外单独整理一份采购前的数据治理与安全核查清单。” | `create B` |
| M2-4 | “短名单范围改成只比较 Copilot Enterprise 和 Codex 企业方案，不再评估 Cursor。” | `revise A` |
| M2-5 | “再单独设计一个两周试点方案，包含参与人、任务样本和每天记录的数据。” | `create C` |
| M2-6 | “试点方案里补充成功指标、退出条件和预算上限。” | `merge_intake C` |
| M2-7 | “安全核查清单由法务另做，取消这项。” | `cancel B` |

### 7.3 Expected topology and acceptance

```text
A: live or completed after first Task, revised to exclude Cursor
B: terminal:canceled
C: live, merged, waiting until the slot is empty
```

- A's canonical content must not retain Cursor as an evaluated candidate.
- C cannot produce a second active Task while A is active.
- B cannot be selected after cancellation.
- Once A is reconciled, parent must read C in full before creating its Task.
- “It is next in the list” is not a grounded selection reason.

## 8. Scenario D1 — local schedule manager

### 8.1 Product brief

Create one Dev Actor. Keep the implementation local and small:

- no login;
- no server;
- simple HTML, CSS, and JavaScript are sufficient;
- actual browser interaction is required;
- source files or screenshots alone are not completion evidence.

### 8.2 Need-bearing messages

| Step | User message | Expected Demand effect |
|---|---|---|
| D1-1 | “开发一个简易本地日程管理工具：创建、编辑、查看和删除日程，刷新后数据保留。完成基础版时，请自行识别一个不阻塞交付但值得后续做的独立改进，并用 Demand 明确提出，不要塞进当前任务。” | `create A`; Goal should later create independent self-Demand S |
| D1-2 | “同一个基础工具补充每周重复日程和本地时区显示。” | `merge_intake A` |
| D1-3 | “另外单独增加日历导出功能，先按 CSV 设计。” | `create B` |
| D1-4 | “导出需求改一下：不要 CSV，改成标准 ICS 文件。” | `revise B` |
| D1-5 | “再单独增加日程冲突检测，不要阻止保存，只在重叠时警告。” | `create C` |
| D1-6 | “冲突检测也要识别重复日程展开后的冲突。” | `merge_intake C` |
| D1-7 | “冲突检测这轮先不做，取消。” | `cancel C` |
| D1-8 | “基础工具的删除方式改掉：不要不可撤销的 confirm，改成移入回收站并提供短时间撤销。” | `revise A` |

### 8.3 Expected topology

```text
A: live/revised; original Task may reference an older A revision
B: live/revised; waiting
C: terminal:canceled
S: live, created directly by the Actor, no ingress receipt
```

### 8.4 Acceptance

- S must describe a genuinely independent later improvement. It must not
  rename unfinished A work.
- S source provenance must be Actor thread/turn provenance, not an ingress
  receipt.
- Creation of S while A is active cannot create another active Task.
- Parent reconciliation must exercise the real browser result against latest
  A.
- If the delivered application still uses irreversible browser confirmation,
  A remains live.
- The browser's delete confirmation dialog is application behavior, not
  BuddySwitch Demand completion evidence.
- When B and S wait together, the next selection reason must compare grounded
  facts rather than hidden priority.

## 9. Scenario D2 — local research evidence notebook

### 9.1 Product brief

Create one Dev Actor. Build a local single-user evidence notebook. Exclude
authentication, collaboration, cloud synchronization, and production
deployment.

### 9.2 Need-bearing messages

| Step | User message | Expected Demand effect |
|---|---|---|
| D2-1 | “开发一个本地研究证据库，可以新建资料条目，保存标题、摘要、来源URL和获取日期，并在浏览器中查看。” | `create A` |
| D2-2 | “同一个基础功能再加入来源类型和可信度备注，刷新后仍能读取。” | `merge_intake A` |
| D2-3 | “另外单独做全文搜索，能搜标题、摘要和来源。” | `create B` |
| D2-4 | “搜索再补充来源类型和日期范围过滤。” | `merge_intake B` |
| D2-5 | “另做一个导出功能，把当前资料导出成 Markdown。” | `create C` |
| D2-6 | “导出范围改成同时支持 Markdown 和 JSON。” | `revise C` |
| D2-7 | “另外做一个全文搜索，可以搜标题、摘要和来源。” | No new Demand; at most merge provenance or report existing meaning |
| D2-8 | “搜索这轮先取消，基础资料和导出保留。” | `cancel B` |

### 9.3 Expected topology and acceptance

```text
A: live or completed
B: terminal:canceled
C: live/revised
no fourth duplicate Search Demand
```

- D2-7 cannot create a duplicate Demand merely because it has a new
  `message_id`.
- B cannot be selected after cancellation.
- After A is reconciled, C is the only valid next selection.
- If C delivers Markdown but not JSON, Task/Goal completion does not justify
  Demand completion.

## 10. Scenario G1 — healthcare appointment flow

### 10.1 Product brief

Create one Design Actor. Produce a mobile-first patient flow with four to six
key screens and a readable design Artifact.

Real-source starting points:

- [GOV.UK check-answers pattern](https://design-system.service.gov.uk/patterns/check-answers/)
- [GOV.UK validation-error pattern](https://design-system.service.gov.uk/patterns/validation/)
- [W3C accessible forms tutorial](https://www.w3.org/WAI/tutorials/forms/)

These sources provide evidence and interaction guidance, not a visual style to
copy.

### 10.2 Need-bearing messages

| Step | User message | Expected Demand effect |
|---|---|---|
| G1-1 | “设计一个患者预约门诊的移动端流程：选择科室、日期、时段、填写联系方式、确认并看到成功结果。” | `create A` |
| G1-2 | “同一流程补充空状态、无可用时段、输入错误、键盘操作和屏幕阅读器说明。” | `merge_intake A` |
| G1-3 | “另外单独设计预约成功后的改期和取消流程。” | `create B` |
| G1-4 | “改期和取消中补充确认、撤销或恢复机制，避免误操作。” | `merge_intake B` |
| G1-5 | “再单独设计医护人员维护可预约时段的后台。” | `create C` |
| G1-6 | “患者预约流程范围改成访客模式，不要求先注册；提交前用短信验证码确认联系方式。” | `revise A` |
| G1-7 | “医护人员后台本轮不做，取消。” | `cancel C` |
| G1-8 | “另外给患者流程设计一份5人可用性测试脚本和观察表。” | `create D` |

### 10.3 Expected topology and acceptance

```text
A: live/revised
B: live/merged
C: terminal:canceled
D: live, independent deliverable
```

- Accessibility and error behavior are satisfaction conditions of A, not a
  separate Demand.
- B is an independently satisfiable post-booking journey.
- D is an independent deliverable and must not be merged into A.
- C cannot be selected.
- A's Artifact must reflect guest booking and SMS verification.
- Artifact content must be readable from the actual product surface, not only
  visible as metadata.

## 11. Scenario G2 — AI research workspace

### 11.1 Product brief

Create one Design Actor. Design a bounded desktop Web research workspace:

- information architecture;
- key workspace screen;
- evidence-card behavior;
- major system states;
- no complete design system or production implementation.

### 11.2 Need-bearing messages

| Step | Timing | User message | Expected Demand effect |
|---|---|---|---|
| G2-1 | Actor idle | “设计一个 AI 调研工作台：左侧研究问题，中间资料和笔记，右侧结论草稿；能区分待验证与已确认信息。” | `create A` |
| G2-2 | A active | “同一工作台补充证据卡片，显示来源、获取时间、引用片段和可信状态。” | `merge_intake A` |
| G2-3 | A active | “另外单独设计一个移动端快速审核模式，只用于查看和批准结论。” | `create B` |
| G2-4 | A active | “审核模式范围改成平板横屏，不再做手机。” | `revise B` |
| G2-5 | A active | “另外单独整理加载、空数据、来源失效和生成失败的状态库。” | `create C` |
| G2-6 | A active | “状态库补充可访问提示文案和恢复动作。” | `merge_intake C` |
| G2-7 | A active | “平板审核模式取消，这轮不做。” | `cancel B` |
| G2-8 | A terminal completed | “刚完成的工作台有个问题：同一研究问题的补充资料被显示成另一项独立研究。请重新设计合并提示和证据归属，并交付修正版。” | `create D`; never revise terminal A |

### 11.3 Terminal follow-up probe

G2-8 directly evaluates the distinction between behavioral dependency and
historical context.

Hard baseline:

- A remains terminal and immutable.
- D is a new live Demand.
- D's `description` and `detail` restate the defect, desired correction,
  delivery, and satisfaction evidence sufficiently to execute D without
  reading A.
- D includes the new feedback Message source.

Exploratory reference observation:

- determine whether D also persists a reference to A, A's terminal Task, or
  the original design Artifact;
- if no such reference exists, record a cross-terminal Demand context
  traceability gap;
- do not infer that this requires restoring a Demand dependency graph.

## 12. Evidence record

Create one row for every inbound and every terminal transition:

```text
scenario
step
timestamp
actor_id
main_thread_id
message_id
source_key
side_thread_id
expected_decision
observed_decision
demand_id_before
demand_id_after
demand_revision_before
demand_revision_after
demand_pool_revision
active_task_id
task_status
goal_status
reply_message_id
artifact_id
handler_result
broker_result
verdict
notes
```

Do not manually create a second runtime evidence ledger. This is a test-run
report or table derived from current public/read-only product projections and
logs.

## 13. Required identity and log chain

For each need-bearing input, correlate:

```text
IM Message accepted
  → Demand ingress scheduled
  → receipt claimed
  → side lease created
  → demand_triage.resolve called
  → broker success or failure envelope
  → receipt settled
  → atomic Demand effect
  → Demand pool attention
  → orchestration deferred or parent turn submitted
  → Task selected and persisted
  → native Goal bound
  → durable delivery and verification
  → native Goal terminal
  → Task terminal recorded
  → independent parent reconciliation
  → Demand completed/revised/left live
  → at most one next Task selected
```

Required observations:

- a successful `demand_triage.resolve` has a real top-level `ok: true` broker
  result;
- a successful persisted mutation cannot be reported as tool failure;
- `create`, `merge_intake`, `revise`, `complete`, and `cancel` increment the
  private pool revision;
- `handled` and `no_action_needed` do not mutate the Demand pool;
- `handled` has an exact durable reply to its source Message even though this
  run does not score the quality of Work-progress content;
- a settled side lease is cleaned;
- Task/Goal status does not itself mutate Demand lifecycle;
- every completed IM-origin Demand cites both terminal Task evidence and the
  exact durable reply evidence;
- actor, role, message, source, Demand, Task, Goal, thread, turn, and Artifact
  identities remain attributable across the path.

## 14. Verdict model

Do not collapse acceptance into a weighted score. Record hard failures and
product-quality findings separately.

### 14.1 Hard failures

- A supplement creates a duplicate Demand.
- An independent obligation is merged into an unrelated Demand.
- A revision leaves retired meaning as canonical truth.
- A canceled Demand is selected or revived.
- More than one Task is active for an Actor.
- Goal completion automatically completes an unsatisfied latest Demand.
- Parent selection does not read the full live pool.
- Persisted effect, broker envelope, tool interpretation, Web status, or logs
  contradict each other.
- A failure produces an undeclared canonical effect.
- A delivered result exists only as metadata and cannot be read by the user.
- A side lease, process, socket, schedule, or isolated state root remains after
  cleanup.

### 14.2 Product judgment findings

- Selection reason does not compare grounded facts.
- Demand canonical content is not self-contained.
- A merge loses material source meaning or constraints.
- A terminal follow-up Demand cannot preserve useful reference to the original
  delivery.
- An Actor self-demand is merely unfinished current Task work under another
  name.
- The parent completes a Demand with status-only rather than durable evidence.

### 14.3 Observations excluded from pass/fail

- Progress reply specificity.
- Side awareness of live native Goal context.
- Non-material writing or visual-style preferences.
- High token or elapsed-time cost that does not break the product path.

Cost remains recorded because it informs later product optimization, but it
does not replace semantic acceptance.

## 15. Stop conditions

Stop the current scenario and diagnose before sending more messages when:

- two active Tasks appear;
- a second Web or CLI test driver produces product input;
- a read-only observer mutates Demand, Task, Goal, Message, Actor, or runtime
  state;
- a persisted effect and broker result disagree;
- a receipt remains resolving beyond the diagnostic threshold;
- parent reconciliation repeatedly writes the same terminal effect;
- a canceled or terminal Demand is revived;
- Web, Message, Demand, Task, and thread identities cannot be correlated;
- a core invariant is already broken and later steps would only add noise.

Do not keep executing the scenario merely to accumulate more failures.

## 16. Cleanup acceptance

For each scenario:

1. capture the final Actor console, Demand pool, Task projection, Goal state,
   Message delivery, relevant Artifact ids, and logs;
2. stop the Actor through the current public product operation;
3. remove the isolated scenario Actor and state through the approved cleanup
   path;
4. verify no owned process, socket, side lease, pending schedule, or temporary
   root remains;
5. record cleanup result alongside the scenario verdict.

Manual Web observation supplements the durable record. It does not replace
repeatable state and log evidence.

## 17. Review gate

This design requires review before real Actor execution. Review should confirm:

- six scenarios are sufficient and none is unnecessarily complex;
- every message has an unambiguous expected Demand effect;
- Wave A covers the most important current risks;
- the G2 terminal follow-up probe represents the intended reference-versus-
  dependency distinction;
- the execution budget and stopping rules are acceptable;
- one primary Web driver plus read-only CLI/log Sub-agents provides clear
  ownership and failure attribution;
- no excluded side-progress problem has leaked back into the acceptance claim.

After approval, prepare a separate execution checklist and test-run report
template. Do not change product code before a real scenario exposes a
reproducible owner-level defect.
