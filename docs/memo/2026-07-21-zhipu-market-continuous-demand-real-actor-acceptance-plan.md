# Zhipu Market Continuous-Demand Real-Actor Acceptance Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:executing-plans` to execute this plan task-by-task. Delegation is
> not authorized for this run. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove, with two real Codex actors, that evolving PM requests about one
Zhipu market study are organized as Demands and consumed by serial Market Tasks
into an adaptive, evidence-backed research result.

**Architecture:** All runtime state is isolated under one fixed temporary
`BUDDYSWITCH_SHARED_ROOT`. A real PM actor uses `message.send`; normal IM,
daemon, Demand, actor, Task, browser, artifact, and Track owners handle the rest.
The controller observes supported CLI surfaces and owned logs, chooses one later
correction from the actual artifact, and never writes product state directly.

**Tech Stack:** BuddySwitch public CLI, installed Codex App Server runtime,
native actor env tools, Central IM, daemon service, Demand Sys, Task Sys, Chrome
DevTools cockpit, Artifact/Track Sys, JSON/JQ, owned app-server/daemon logs.

**Design:**
`docs/memo/2026-07-21-zhipu-market-continuous-demand-real-actor-acceptance-design.md`

**Fixed run root:**
`/private/tmp/buddyswitch-zhipu-market-1784566044/.codex-buddyswitch`

**Commit policy:** This is runtime acceptance of the existing Phase 4 candidate.
Do not create a plan-only or evidence-only commit. Keep both documents with the
pending coherent Phase 4 change set until the user explicitly authorizes commit.

---

## 0. Execution contract

Every public command shown later uses the same explicit prefix:

```bash
env BUDDYSWITCH_SHARED_ROOT=/private/tmp/buddyswitch-zhipu-market-1784566044/.codex-buddyswitch \
  ./buddyswitch-codex
```

Do not export the run root globally. An omitted environment prefix must fail
review rather than accidentally targeting the default live root.

Acceptance evidence is written after the run to:

```text
docs/memo/2026-07-21-zhipu-market-continuous-demand-real-actor-acceptance-record.md
```

The record contains ids, timestamps, observed state, artifact findings, failure
signals, and teardown evidence. It does not mirror current architecture rules.

## 1. Runtime paths and observation surfaces

No production/test source file is expected to change. The only planned new file
after this plan is the execution record above.

Allowed observation surfaces:

- `instance start/list/status/input/stop/delete`;
- `demand list/get`, `task list/get`, and `track list/get`;
- PM/Market native `track.open` and `artifact.get` calls;
- IM delivery output, instance-owned daemon log, and app-server thread reads;
- process/socket/path absence checks during teardown.

Raw runtime projection files may be read only if a supported projection or owned
log cannot expose an exact acceptance fact. They are never written, moved,
renamed, or used as a mutation interface.

## 2. Task 1 — Freeze baseline and start exact actors

- [x] **Step 1: Prove isolation before creation**

Run:

```bash
test ! -e /private/tmp/buddyswitch-zhipu-market-1784566044/.codex-buddyswitch
./buddyswitch-codex instance list
git rev-parse HEAD
git diff --binary | shasum -a 256
/Users/chen/.npm-global/bin/codex --version
```

Expected: isolated root absent, default instance list unchanged, repository
identity recorded, and installed Codex—not a fake executable—reported.

- [x] **Step 2: Start PM and Market actors**

Run the two commands separately and record each JSON response:

```bash
env BUDDYSWITCH_SHARED_ROOT=/private/tmp/buddyswitch-zhipu-market-1784566044/.codex-buddyswitch \
  ./buddyswitch-codex instance start --role pm

env BUDDYSWITCH_SHARED_ROOT=/private/tmp/buddyswitch-zhipu-market-1784566044/.codex-buddyswitch \
  ./buddyswitch-codex instance start --role market
```

Expected: two distinct actor ids, recorded real Codex identity, healthy app
server/runtime broker/daemon, and idle bootstrap threads.

- [x] **Step 3: Verify exact isolated inventory**

Run `instance list`, `instance status`, and `instance capabilities ... get` for
both ids using the fixed environment prefix. Expected: exactly two instances in
the isolated root and no mutation to the default instance list.

## 3. Task 2 — Create one shared research Track

- [x] **Step 1: Direct the PM to create the Track**

Submit this exact control prompt to the PM actor:

```text
Create one Track for the research engagement titled “智谱公司市场竞争力持续调研”.
Set its requirements to: maintain a decision-grade, evidence-backed, versioned
analysis of Zhipu AI; publish Market research as Track material; preserve source
dates, URLs, uncertainty, and explicit revisions after feedback. Do not perform
the market research yourself. Return the exact track_id and stop.
```

This direct input is control-plane setup and must create no PM or Market Demand.

- [x] **Step 2: Discover and verify the Track through public reads**

After the PM thread returns idle, assign the exact start-response ids to shell
variables `PM_ACTOR_ID` and `MARKET_ACTOR_ID`, then use
`track list --owner "$PM_ACTOR_ID"`. Assign its sole result to `TRACK_ID` and use
`track get "$TRACK_ID"`. Expected: exactly one active Track with the requested
title/requirements and no material yet.

## 4. Task 3 — Send initial Demand C and catch its active Task

- [x] **Step 1: Send the initial request through the real PM actor**

Tell the PM actor to call `message.send` once to the exact Market identity with
the exact content below, substituting only the already observed Track id:

```text
请对智谱AI（北京智谱华章及其当前公开商业品牌）开展一份面向战略决策的市场竞争力深度调研，并把版本化 brief artifact 发布到本消息给出的研究 Track。

研究必须覆盖：模型与产品矩阵、技术差异化及局限、API/模型经济性、开发者生态、企业客户与商业化、合作伙伴、融资/上市或其他业务质量信号、监管与地缘风险、可持续壁垒，以及未来12个月情景。至少比较 DeepSeek、阿里Qwen、字节豆包、百度文心、Moonshot/Kimi、MiniMax；全球厂商只在相关处加入。

必须使用当前网页证据而不是模型记忆。以至少12项一手/官方材料和6项可靠独立材料为研究深度下限；每个关键当前事实保留URL、来源日期、访问日期。明确区分事实、公司主张、推断、不确定性，不得把benchmark直接等同于可持续商业优势。

先完成当前证据可支持的第一版，不要假定这是最终需求。Track id: $TRACK_ID。
```

Build the submitted `--text` argument in double-quoted shell text so `$TRACK_ID`
expands to the literal observed id before the PM turn starts.

- [x] **Step 2: Prove inbound capture before Task assertions**

Poll Market `demand list` until one new live Demand appears. Record its Demand id,
intake key, revision, checked revision, description, and source summary. Expected:
IM-derived C exists before any claim about Task creation.

- [x] **Step 3: Catch and record the active Task**

Poll Market `task list --actor "$MARKET_ACTOR_ID"` and
`instance status "$MARKET_ACTOR_ID"` at short intervals. Stop polling when a
Demand-backed Task for C is active. Record
Task id, exact DemandRef, lifecycle status, thread/turn state, and active count.
Expected: active count is exactly one.

If no Task becomes active, retain Demand/daemon/turn evidence and diagnose rather
than sending another initial request.

## 5. Task 4 — Inject in-flight same-need supplement D

- [x] **Step 1: Send D while C's Task is still active**

Immediately tell the PM actor to call `message.send` once to the Market actor with:

```text
补充到正在进行的智谱竞争力调研：请强化融资/上市进展、企业客户与商业收入信号、API与模型推理成本、渠道/合作伙伴质量，并给所有关键证据标注“公司主张 / 独立佐证 / 推断”级别。重点检查漂亮benchmark或融资估值是否被误当成可持续市场壁垒。这是原研究交付的补充，不是另一份独立报告。
```

- [x] **Step 2: Observe organization without dictating the action**

Poll Demand state until D is checked. Read plausible C/D candidates with public
`demand get`. Expected semantic outcome: D is terminal with `absorbed_into=C`, C
contains the added scope at a newer revision, and final observed revisions are
acknowledged. Record any different actor judgment and its resulting state.

- [x] **Step 3: Prove the single-active gate during revision change**

Sample Task projection throughout D capture and organization. Expected: the
original Task remains the only active Task; there is never a second concurrent
Task. Record the original Task's C basis revision and C's newer live revision.

## 6. Task 5 — Inspect the first artifact and send adaptive correction E

- [x] **Step 1: Wait for a readable first artifact**

Poll Task/Track state without interrupting work. When the first relevant Task is
terminal and the Track has current material, direct the PM to call `track.open`
and `artifact.get` for the exact current material id. Capture the full body from
the PM app-server thread record. Confirm source ledger, dates, competitor
coverage, findings, and explicit uncertainty.

- [x] **Step 2: Select the correction deterministically from actual content**

Evaluate material weaknesses in this priority order and select the first one
present:

1. material current claim with no retrievable source;
2. company claim stated as independently verified fact;
3. outdated product/pricing/financing fact;
4. benchmark treated as commercial moat;
5. competitor or customer segment collapsed too broadly;
6. contradiction present but not reconciled.

Quote the exact affected claim and cite the exact evidence gap in the execution
record. If none applies, challenge the report's single most important moat claim
with an explicit falsification request; this is the complete fallback rule.

- [x] **Step 3: Send E as one concrete PM message**

The PM sends one message naming the quoted claim, the observed evidence gap, and
the exact correction requested. State that it revises the same research
deliverable. Do not mention Demand ids, relation actions, or Task tools to the
Market actor.

- [x] **Step 4: Prove material revision**

Observe E's Demand capture/organization and the next serial Task. After the new
artifact revision appears, use PM `artifact.get` to compare the affected section.
Expected: the analysis changes materially rather than appending a generic caveat;
source/revision lineage remains clear.

## 7. Task 6 — Add related child Demand F

- [x] **Step 1: Send the distinct decision question**

The PM sends this exact Market message:

```text
基于已经完成并纠偏过的智谱竞争力研究，请再回答一个相关但有独立交付结果的问题：未来12个月，智谱在中国企业大模型市场最可能赢得和失去哪些细分场景？请形成 win/loss segment map、关键竞争者对位、三种情景，以及能够证伪每项判断的可观察信号。它属于主研究之下的决策分支，不要把主报告整体重写成这个问题。
```

- [x] **Step 2: Observe child organization and serial selection**

Expected semantic outcome: F remains live with `parent_id=C` and is not absorbed.
No dependency is required. If another Task is active, F waits; after the gate is
clear it may receive one Task with its own exact DemandRef.

- [x] **Step 3: Read the child result and final synthesis**

After F's Task is terminal, use Track/artifact reads through the PM actor to
capture the segment map and scenario watchlist. Ask the PM for one final review
of whether C's current artifact plus F's output answer the evolving engagement.

## 8. Task 7 — Acceptance audit

- [x] **Step 1: Audit every explicit requirement**

Build a requirement/evidence table in the execution record covering:

- real actors and real Codex identity;
- one initial plus D/E/F IM messages;
- one supplement captured during an active Task;
- C/D/E organization and F child structure;
- every final revision acknowledged;
- sampled active Task count never above one;
- old Task snapshot did not terminalize a newer Demand revision;
- adaptive artifact correction and final research coverage;
- IM/daemon/turn/Task/artifact causality;
- clean isolated teardown.

Mark evidence as pass, fail, incomplete, or contradicted. Absence of an obvious
error is not a pass.

- [x] **Step 2: Record defects without bypassing them**

For any failure, capture exact command, response, ids, log excerpt, canonical
state effect, and root-cause boundary. Do not modify source or state during the
run. If the goal cannot continue safely, retain the isolated root and stop before
cleanup only long enough to preserve supported diagnostics.

## 9. Task 8 — Exact teardown

- [x] **Step 1: Stop and delete only the two exact actors**

Use isolated-root-prefixed `instance stop` and `instance delete --yes` for Market
and PM. Release any Market browser resource before stop if status still reports
one. Expected: both exact actors absent from isolated `instance list`.

- [x] **Step 2: Reset only the isolated environment**

After actor processes stop:

```bash
env BUDDYSWITCH_SHARED_ROOT=/private/tmp/buddyswitch-zhipu-market-1784566044/.codex-buddyswitch \
  ./buddyswitch-codex env reset --yes
rmdir /private/tmp/buddyswitch-zhipu-market-1784566044
```

Never run `data cleanup --role` or `--all-data`.

- [x] **Step 3: Prove zero residue and default-state preservation**

Expected checks:

```bash
test ! -e /private/tmp/buddyswitch-zhipu-market-1784566044
./buddyswitch-codex instance list
ps -axo pid=,command=
```

Filter process output by the two exact actor ids and run-root marker. Expected:
no match. Confirm the default instance list equals its pre-run snapshot and no
repository runtime projection was created.

- [x] **Step 4: Verify execution artifacts**

Run:

```bash
git diff --check
rg -n 'T''BD|T''ODO|impl''ement later|fi''ll in' \
  docs/memo/2026-07-21-zhipu-market-continuous-demand-real-actor-acceptance-design.md \
  docs/memo/2026-07-21-zhipu-market-continuous-demand-real-actor-acceptance-plan.md \
  docs/memo/2026-07-21-zhipu-market-continuous-demand-real-actor-acceptance-record.md
git status --short
```

Expected: clean diff formatting, no placeholder, and only the pre-existing Phase
4 scope plus these acceptance documents. Do not commit or push without explicit
authorization.
