# Demand Triage Semantic REBUILD Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use
> `superpowers:executing-plans` to execute this plan block by block. Use
> `superpowers:test-driven-development` for each executable change,
> `buddyswitch-testing` for target selection and evidence, and
> `superpowers:verification-before-completion` before any completion claim.
> Steps use checkbox (`- [ ]`) syntax for resumable tracking.

**Status:** implemented; scoped automated verification and full real-Actor
Wave A acceptance passed. Final evidence is recorded in
`2026-07-25-demand-triage-semantic-rebuild-acceptance.md`.

**Goal:** REBUILD isolated Demand triage so every inbound is judged by the one
shared Codex-native `$demand-triage` workflow against sufficient canonical
Message and live/terminal Demand context, while the Demand Sys deterministic
core remains free of model judgment.

**Architecture:** BuddySwitch continues to materialize one shared
`demand-triage` Skill into every Actor workspace. Each isolated Demand side is
a new ephemeral App Server thread in that workspace, explicitly selects the
Skill in its turn, reads existing canonical state through existing read-only
tools, and commits exactly one decision through `demand_triage.resolve`.
Demand Sys validates authority, shape, freshness, idempotency, lifecycle, and
atomic persistence only.

**Tech stack:** Python 3, Codex App Server `thread/start` and native Skills,
Markdown `SKILL.md`, BuddySwitch environment MCP tools, JSON Actor aggregates,
the public `./buddyswitch-test focused` runner, and real WebUI Actors.

**Submission policy:** do not stage or commit this plan separately. During
implementation, keep it with the code, tests, current architecture update, and
acceptance evidence; submit them only after the complete REBUILD passes the
real-Actor acceptance gate. Preserve the two existing untracked Wave A memos.

---

## 1. FRAME

### 1.1 Exact bottleneck

The current isolated side can safely commit a structurally valid Demand
decision, but its semantic classification is unstable:

- D1 split a supplement to the same deliverable into a duplicate Demand;
- G2 merged an explicitly independent deliverable into an existing Demand;
- M1 applied a correction referring to a terminal Demand to an unrelated live
  Demand.

The common cause is one under-specified decision boundary, not three unrelated
runtime defects. The current Skill defines the six effects but does not define
a deterministic judgment sequence, evidence precedence, an independent
acceptance unit, or terminal-reference handling.

### 1.2 Observable acceptance sentence

> From a fresh real Web Actor, an inbound supplement to the same deliverable is
> merged, an independently acceptable deliverable creates a new Demand, and a
> correction to a terminal Demand creates a new correction Demand without
> mutating an unrelated live Demand; the side first receives the shared native
> Skill and sufficient canonical context, commits exactly once, and persisted
> state, tool result, Web-visible outcome, and logs agree.

### 1.3 Current RED evidence

The existing product RED is recorded at source identity
`5a22aeec8a830c1a75f8913c9d725f7487daefbd` in:

- `docs/memo/2026-07-25-real-actor-multi-demand-wave-a-test-report.md`;
- `docs/memo/2026-07-25-real-actor-multi-demand-scenario-test-design.md`.

Do not spend another full real-Actor run reproducing the same RED before
editing. The evidence remains valid until a relevant Skill, prompt, tool
contract, side environment, or model configuration changes.

## 2. TRACE — verified current repository facts

| Boundary | Current fact | Consequence |
|---|---|---|
| Skill installation | `actor_environment.py` materializes every role's declared Skills into the Actor workspace `.agents/skills`; every role declares `demand-triage` | keep one shared Skill; no side-specific installer or second Skill |
| Side creation | `side_thread_lifecycle.start_side_thread` calls App Server `thread/start(ephemeral=true)` with the Actor workspace | current Demand side is a new isolated thread, not Codex native `/side` / `thread/fork` |
| Skill selection | the side prompt contains `Use $demand-triage`; Codex recognizes the explicit mention and injects the selected `SKILL.md` before first sampling | strengthen and prove the existing native path; do not build a BuddySwitch Skill engine |
| Side context | the side already exposes `demand_sys__list`, `demand_sys__get`, `message__get`, and `message__conversation` | no new context service or Tool is needed |
| Demand history | `demand_sys.list` already accepts `live`, `terminal`, or `all`; compact rows contain id, description, terminal state, and update time | replace live-only Skill guidance with `state="all"` and targeted full reads |
| Conversation | `message.conversation` already accepts a latest-message limit | use a bounded direct-conversation read; do not copy parent or Work transcripts |
| Commit surface | `demand_triage.resolve` is capability-bound, one-shot, source-bound, and atomic through the runtime broker | retain it as the only triage commit surface |
| Deterministic core | `demand_sys.validate_ingress_proposal` and `resolve_ingress` validate exact fields, receipt attempt, live target, opaque revision, idempotency, lifecycle, and atomic mutation | do not add LLM calls, embeddings, keyword classifiers, target selection, or semantic scoring |
| Task/Goal | Task selection and native Goal execution occur after canonical Demand commit | no Task, Goal, orchestration, or Control Thread change belongs in this REBUILD |
| Daemon | generic daemon primitives trigger product handlers but contain no Demand semantics | keep daemon-service unchanged |
| Automated coverage | current tests prove installation, prompt mention, tool wiring, capability use, persistence, and Goal flow; the scripted system model chooses decisions directly | automated tests do not currently prove that the full Skill was model-visible or that a real model follows the semantic SOP |

### 2.1 Important terminology

Use these terms in current code, docs, and reports:

```text
Demand-triage Skill
  semantic judgment workflow followed by the side model

Read-only Demand/Message tools
  canonical fact retrieval

demand_triage.resolve
  one-shot commit operation

Demand Sys deterministic core
  validation, concurrency, idempotency, lifecycle, and atomic persistence
```

Do not use “Demand owner” as a user-facing explanation for the deterministic
core. Internal fields such as `source_context.owner` may retain their exact
machine contract where they mean technical ownership rather than intelligent
judgment.

## 3. Frozen target architecture

```text
validated inbound fact + private ingress receipt
  ↓
new ephemeral Demand side in the same Actor workspace
  ↓
Codex native explicit selection of $demand-triage
  ↓
full shared SKILL.md injected before first model sampling
  ↓
Skill executes one judgment SOP
  ├─ exact inbound fact
  ├─ exact source Message when source is IM
  ├─ bounded direct conversation when source is IM
  ├─ compact live + terminal Demand pool
  └─ full reads for every plausible target and all live candidates before create
  ↓
exactly one semantic decision
  ├─ no_action_needed
  ├─ handled
  ├─ create
  ├─ merge_intake
  ├─ revise
  └─ cancel
  ↓
demand_triage.resolve exactly once
  ↓
Demand Sys deterministic validation + atomic write
  ↓
canonical Demand pool attention
```

This is one live path. There is no fallback prompt, second Skill, parent
judgment, semantic code path, compatibility flag, or `demand-triage-v2`.

### 3.1 Same environment, separate turn context

“Same environment” means:

- the same Actor workspace;
- the same installed Skill package;
- the same project/runtime workspace roots;
- the same canonical Demand and Message state.

It does not mean:

- the same thread history;
- the same model-visible context window;
- the same developer instructions;
- the same model/effort override;
- the same enabled MCP tool set.

The current BuddySwitch Demand side remains `thread/start`, not
`thread/fork`. It must therefore select the already-installed shared Skill in
its own turn. Codex performs the selection and injection natively.

## 4. Frozen semantic SOP

The Skill must teach the following sequence. Tool descriptions continue to
define exact action fields; they must not duplicate this complete SOP.

### 4.1 Step A — determine whether an unmet obligation remains

```text
no continuing obligation and no reply required
  → no_action_needed

one immediate source-local reply fully satisfies the inbound
  → handled

otherwise
  → continue to identify the acceptance unit
```

### 4.2 Step B — resolve the referenced acceptance unit before choosing an effect

Read the current inbound and canonical context first. Determine whether the
user refers to:

- one current live Demand;
- one recently completed or canceled Demand;
- or a genuinely new independently acceptable deliverable.

Never select the “closest” live Demand merely because the actual referent is
terminal.

### 4.3 Step C — apply evidence precedence

1. Explicit current user relationship language outranks an inferred boundary
   written earlier by the model.
2. “Same deliverable”, “supplement”, “continue”, or equivalent language is
   evidence of one acceptance unit, not an automatic lexical rule.
3. “Independent deliverable”, “separate acceptance”, or equivalent language is
   evidence of a new acceptance unit, not an automatic lexical rule.
4. The user's current result/delivery grouping defines the acceptance unit.
   Technical separability alone is not product independence: an addition being
   implementable, testable, scheduled, canceled, or delivered in a separate
   step does not create a new Demand when the user groups it into the same
   deliverable.
5. An earlier Actor-proposed future improvement governs that proposal; it does
   not reclassify a later explicit user supplement to the same deliverable.
6. Create only when the current user requests a distinct standalone result or
   delivery that is not grouped into an existing result.
7. A terminal Demand is immutable. A new correction, defect, or follow-up that
   remains unmet becomes a new Demand whose canonical text names the prior
   result being corrected; it does not create a lifecycle dependency edge.

### 4.4 Step D — choose exactly one effect

```text
create
  a new independently acceptable unmet result

merge_intake
  compatible evidence, detail, or constraint added to the same intended result

revise
  the same result remains the acceptance unit, but its outcome, boundary,
  binding constraint, delivery, or satisfaction meaning changes

cancel
  the user explicitly withdraws or invalidates one live Demand
```

Before `create`, reread every live Demand in full to prevent duplicate
acceptance units. Before `merge_intake`, `revise`, or `cancel`, reread the exact
live target in full. For a terminal reference, reread that terminal Demand in
full before creating the correction Demand.

### 4.5 Step E — submit once

The `reason` must cite the observed relationship and acceptance-unit evidence,
not merely repeat the chosen enum. Construct post-resolution canonical
`description` and `detail`, then call `demand_triage.resolve` exactly once.
Follow stale-reference feedback; do not call ordinary Demand mutations.

## 5. Scope

### 5.1 In scope

- replace the current thin shared `demand-triage` Skill in place;
- replace its live-only context rule with the existing all-state Demand read
  and bounded source conversation read;
- keep explicit Codex-native `$demand-triage` selection;
- prove the full selected Skill is present at the real App Server model
  boundary before the first tool call;
- align the minimal handler prompt and resolver descriptions with the one
  semantic source;
- update current Demand architecture documentation;
- preserve exact deterministic mutation behavior;
- add focused architecture, integration, system, and replacement proof;
- rerun Wave A with real Market, Dev, and Design Actors through WebUI;
- record and clean all runtime resources.

### 5.2 Explicit non-goals

- changing the Demand side from `thread/start` to `thread/fork`;
- inheriting or copying the parent transcript;
- adding a Control Main or Work Thread;
- adding a context projection service;
- adding a Demand graph, dependency, supersedes, duplicate, or correction edge;
- adding a new Actor-facing Demand action or triage action;
- adding pagination, search, or ranking to `demand_sys.list`;
- changing Task selection, Task schema, native Goal, or Demand orchestration;
- changing daemon-service core;
- adding LLM, embedding, semantic similarity, or keyword classification to
  Python code;
- using a scripted test model to claim real semantic quality;
- migrating historical runtime data or preserving a compatibility path.

## 6. REPLACE and residue rules

The replacement is incomplete while any current surface teaches the retired
live-only/free-judgment path.

Remove or replace:

- `complete current live Demand pool` in the Skill description;
- `demand_sys__list(state="live")` as the complete triage candidate set;
- optional source-conversation guidance when source is an IM Message;
- handler wording that restricts triage to “current canonical live Demands”;
- resolver wording that describes `reason` only against the live pool;
- user-facing “Demand owner” wording for the deterministic core;
- tests that treat `$demand-triage` text presence alone as proof of Skill
  execution;
- current architecture prose that omits the shared native Skill and the
  live/terminal context rule.

Do not create:

- compatibility aliases;
- `demand-triage-v2`;
- a fallback long prompt copying the Skill;
- a second semantic decision table in Python or tool schema;
- a hidden semantic validator in Demand Sys;
- a second test runner or model-evaluation framework.

Historical memos retain their recorded facts. They are not active policy and
are not rewritten to pretend the old run had the new behavior.

## 7. File map

### 7.1 Modify

- `buddyswitch/skills/shared/demand-triage/SKILL.md`
  — the only complete inbound-to-Demand semantic SOP.
- `tools/launcher/demand_triage_handler.py`
  — minimal Skill selection prompt and terminology only; no copied SOP.
- `tools/launcher/demand_triage_mcp_server.py`
  — precise decision/commit descriptions and deterministic-core terminology;
  no semantic algorithm.
- `docs/arch/demand-sys-architecture.md`
  — current thread, Skill, context, decision, and deterministic-core truth.
- `tests/unit/architecture/test_task_management_skill.py`
  — active semantic ownership and retired-guidance absence.
- `tests/integration/demand_sys/test_side_triage_flow.py`
  — handler prompt, tool availability, single commit surface, and no duplicated
  policy.
- `tests/unit/demand_sys/test_triage_mcp_server.py`
  — exact resolver catalog wording and schema boundary.
- `tests/system/goal_mode/test_product_flow.py`
  — inspect the real Codex model request for native Skill injection; continue
  to treat scripted decisions as plumbing proof only.

### 7.2 Verify unchanged

- `scripts/env/domain/demand_sys.py`
  — no intelligent behavior; existing deterministic tests stay green.
- `scripts/env/tools/demand_sys/tool.py`
  — existing `list(state=all)` and six-action Actor surface remain sufficient.
- `scripts/env/tools/message/tool.py`
  — existing exact Message and bounded conversation reads remain sufficient.
- `tools/launcher/side_thread_lifecycle.py`
  — side remains a new ephemeral `thread/start`.
- `tools/launcher/app_server.py`
  — native Skill discovery/injection remains Codex-owned.
- `tools/launcher/daemon_*.py`
  — no Demand semantic change.
- `buddyswitch/manifest.toml`
  — one shared `demand-triage` remains installed for every role.

### 7.3 Do not create or delete product files

No new Skill, Tool, domain module, context service, compatibility file, or
daemon handler is required. The only possible new file during implementation
is the final acceptance report:

`docs/memo/2026-07-25-demand-triage-semantic-rebuild-acceptance.md`.

## 8. Test-driven implementation

### Task 1: Establish exact automated RED at the model-visible and active-policy boundaries

**Files:**

- Modify:
  `tests/unit/architecture/test_task_management_skill.py`
- Modify:
  `tests/integration/demand_sys/test_side_triage_flow.py`
- Modify:
  `tests/unit/demand_sys/test_triage_mcp_server.py`
- Modify:
  `tests/system/goal_mode/test_product_flow.py`

- [x] **Step 1: Replace the thin Skill string check with a scoped architecture contract**

Rename
`test_triage_skill_is_side_only_and_has_no_parent_or_task_selection_branch` to
`test_triage_skill_owns_one_complete_relationship_sop`.

The test must prove only active-policy and replacement facts:

```python
def test_triage_skill_owns_one_complete_relationship_sop() -> None:
    text = TRIAGE.read_text(encoding="utf-8")
    normalized = " ".join(text.lower().split())

    required = (
        'demand_sys__list(state="all")',
        "acceptance unit",
        "explicit current user",
        "independently",
        "terminal demand",
        "correction demand",
        "merge_intake",
        "revise",
        "demand_triage.resolve",
    )
    for phrase in required:
        assert phrase in normalized

    assert 'demand_sys__list(state="live")' not in normalized
    assert "needs_parent_judgment" not in normalized
    assert "task_sys" not in normalized
    assert "message__send" not in normalized
```

This test does not claim that a model made the right decision. It proves that
one current Skill owns the required SOP and that the retired live-only teaching
is absent.

- [x] **Step 2: Make the handler integration test reject the retired prompt**

Keep the existing exact tool list and one-shot capability assertions. Add:

```python
self.assertIn("Use $demand-triage", start["text"])
self.assertNotIn("canonical live Demands", start["text"])
self.assertNotIn("acceptance unit", start["text"])
self.assertNotIn("state=\"all\"", start["text"])
```

The final two assertions preserve one owner: the handler selects the Skill but
does not copy its reusable policy.

- [x] **Step 3: Add a real App Server model-request Skill-injection assertion**

In `ProductFlowController`, add a helper that flattens the provider request's
model-visible input without interpreting model output:

```python
@staticmethod
def _model_visible_input(request_record: dict[str, Any]) -> str:
    body = request_record.get("body")
    if not isinstance(body, dict):
        return ""
    return json.dumps(body.get("input"), ensure_ascii=False, sort_keys=True)
```

Before the scripted controller returns the first triage `resolve` call, assert:

```python
visible = self._model_visible_input(request_record)
if (
    "<name>demand-triage</name>" not in visible
    or "acceptance unit" not in visible.lower()
    or "demand_triage.resolve" not in visible
):
    raise AssertionError(
        "selected demand-triage Skill was not injected before triage sampling"
    )
```

Keep the scripted `decision="create"` response. Document beside it:

```python
# This controller authors a deterministic decision to prove the product
# plumbing. It does not prove real-model semantic classification.
```

- [x] **Step 4: Update the resolver catalog test**

Require the resolver description to say `Demand Sys` rather than
`Demand owner`, and require `reason` to describe the relationship to canonical
Demand context rather than only the live pool. Do not add fields or semantic
validation.

- [x] **Step 5: Run exact RED**

Run:

```bash
./buddyswitch-test focused \
  tests/unit/architecture/test_task_management_skill.py::test_triage_skill_owns_one_complete_relationship_sop \
  tests/integration/demand_sys/test_side_triage_flow.py::DemandSideTriageFlowTests::test_handler_starts_resolver_side_without_output_schema \
  tests/unit/demand_sys/test_triage_mcp_server.py::DemandTriageMcpServerTests::test_resolve_catalog_exposes_one_shot_contract_and_described_arguments
```

Expected: FAIL because the current Skill still says `state="live"`, lacks the
acceptance-unit SOP, and the prompt/resolver still use retired wording. Setup,
import, or runner failures are not valid RED.

Run the exclusive system target separately:

```bash
./buddyswitch-test focused \
  tests/system/goal_mode/test_product_flow.py::NativeGoalProductFlowSystemTests::test_web_actor_delivers_then_goal_and_demand_complete
```

Expected: FAIL at the new Skill-content assertion, before the scripted model
commits triage. Record source identity and cleanup state.

### Task 2: Replace the thin Skill and live-only current guidance

**Files:**

- Modify:
  `buddyswitch/skills/shared/demand-triage/SKILL.md`
- Modify:
  `tools/launcher/demand_triage_handler.py`
- Modify:
  `tools/launcher/demand_triage_mcp_server.py`
- Modify:
  `docs/arch/demand-sys-architecture.md`

- [x] **Step 1: Rewrite the existing Skill in place**

Keep the frontmatter name `demand-triage`. Change its description to:

```yaml
description: Resolve one raw inbound fact against the Actor's complete canonical Demand context in an isolated triage side.
```

The body must implement Sections 4.1–4.5 of this plan in imperative form and
must explicitly require:

```text
1. Read the exact inbound fact.
2. For an IM source, read the exact source Message.
3. For an IM source, read the latest direct conversation with a fixed limit of 20.
4. Call demand_sys__list(state="all").
5. Resolve the referenced acceptance unit before choosing an effect.
6. Reread every live Demand before create and every plausible target in full.
7. Apply the evidence precedence and decision definitions.
8. Call demand_triage.resolve exactly once.
```

Include three short generalized counterexamples:

```text
Same-deliverable supplement
  Adding a compatible field to one existing deliverable is merge_intake, not
  create merely because the field could be implemented later.

Independent deliverable
  A separately accepted and canceled library/report/tool is create, not
  merge_intake merely because it is related to the same project.

Terminal correction
  A defect or change to a terminal result creates a correction Demand naming
  that result; it never revises an unrelated live Demand.
```

Do not include runtime payload schemas, Python field tables, tool-result shapes,
Task selection, parent escalation, or Goal instructions.

- [x] **Step 2: Keep the handler prompt minimal**

Replace:

```text
Use $demand-triage to resolve this one inbound fact against the Actor's current
canonical live Demands.
```

with:

```text
Use $demand-triage to resolve this one inbound fact against the Actor's current
canonical Demand context.
```

Do not copy the SOP into `TRIAGE_PROMPT`.

- [x] **Step 3: Align the resolver's visible descriptions**

Keep the exact six decisions and existing flat schema. Apply only these
semantic clarifications:

```text
reason:
  Grounded explanation of this inbound's relationship to the Actor's
  canonical Demand context and why this resolution effect is correct.

resolve:
  ... Demand Sys atomically settles the receipt and applies any authorized
  Demand change ...
```

`demand_ref` remains a current live target for `merge_intake`, `revise`, and
`cancel`. A terminal correction uses `create` with `demand_ref=null`; no
terminal mutation or relationship field is added.

- [x] **Step 4: Update the current Demand architecture**

In `docs/arch/demand-sys-architecture.md`, make these current facts explicit:

- the isolated side is a new ephemeral thread in the same Actor workspace, not
  a fork of the parent transcript;
- every role shares one installed `demand-triage` Skill;
- the side explicitly selects that native Skill in its turn;
- triage reads bounded Message context and the compact all-state Demand pool;
- the Skill owns semantic judgment;
- Demand Sys is a deterministic core and contains no model judgment;
- `demand_triage.resolve` remains the single commit path;
- Task/Goal and daemon boundaries remain unchanged.

Replace ambiguous user-facing “Demand owner” terminology where it refers to
the deterministic core. Keep exact architecture-law ownership statements where
they describe code dependency ownership.

- [x] **Step 5: Run the same exact targets GREEN**

Run the two commands from Task 1 unchanged.

Expected:

- all exact tests PASS;
- system controller observes the full selected Skill before its first triage
  response;
- the real broker/tool path still commits exactly once;
- test cleanup reports no process, socket, or temporary-root residue.

### Task 3: Prove direct boundaries and absence of semantic creep

**Files:** verification only unless a focused failure identifies an owning
defect.

- [x] **Step 1: Prove shared Skill installation and isolated thread identity**

Run:

```bash
./buddyswitch-test focused \
  tests/unit/actor/test_runtime_skills.py::RuntimeSkillsTests::test_each_role_keeps_shared_runtime_tools_without_handoff \
  tests/integration/actor/test_side_thread_lifecycle.py::SideThreadLifecycleContractTests::test_start_side_thread_passes_model_and_effort_to_isolated_thread_without_registry_persistence \
  tests/integration/app_server/test_client.py::AppServerClientTests::test_thread_start_sends_isolated_side_runtime_options
```

Expected: PASS, proving one shared Skill catalog and the retained
`thread/start` side architecture.

- [x] **Step 2: Prove Demand Sys stayed deterministic**

Run:

```bash
./buddyswitch-test focused \
  tests/unit/demand_sys/test_ingress_resolution.py \
  tests/integration/demand_sys/test_side_triage_flow.py \
  tests/unit/architecture/test_demand_sys_boundaries.py
```

Expected: PASS with unchanged schema, authority, lifecycle, revision,
idempotency, atomicity, single write path, and daemon neutrality.

Do not weaken these tests to accommodate a semantic shortcut. If implementation
requires importing model, App Server, embeddings, Task, or daemon semantics
into `scripts/env/domain/demand_sys.py`, stop: the design has been violated.

- [x] **Step 3: Inspect replacement residue**

Run:

```bash
rg -n \
  'canonical live Demands|list\\(state="live"\\)|Demand owner|demand-triage-v2|needs_parent_judgment' \
  buddyswitch/skills/shared/demand-triage \
  tools/launcher/demand_triage_handler.py \
  tools/launcher/demand_triage_mcp_server.py \
  docs/arch/demand-sys-architecture.md \
  tests/unit/architecture/test_task_management_skill.py \
  tests/integration/demand_sys/test_side_triage_flow.py \
  tests/unit/demand_sys/test_triage_mcp_server.py
```

Expected:

- no retired live-only instruction;
- no duplicate/new Skill;
- no parent branch;
- no ambiguous user-facing deterministic-core terminology.

Any intentional negative assertion that names a retired term must be
recognizable as an absence proof.

## 9. Real Actor acceptance

Automated GREEN proves Skill delivery, available context, one-shot commit, and
deterministic state effects. It does not prove that a real model applies the
semantic SOP. Real Web Actors are therefore mandatory before acceptance.

### 9.1 Test ownership

Use the execution model already frozen in the scenario design:

```text
one primary Agent
  → sole WebUI writer and sole scenario driver

read-only observer
  → CLI/log correlation only

read-only state auditor
  → Demand/Task/Goal projection only
```

Observers must not send Messages, mutate Demand/Task state, control Goals,
start/stop Actors, or perform cleanup.

### 9.2 Environment preflight

- [x] Record repository HEAD and complete dirty/untracked identity.
- [x] Create one isolated BuddySwitch shared root.
- [x] Start WebUI through the current public BuddySwitch CLI.
- [x] Record Web URL, shared root, Actor role, Actor id, main thread id, parent
  and side capability model configuration.
- [x] Confirm every Actor workspace contains exactly one installed
  `.agents/skills/demand-triage/SKILL.md`.
- [x] Confirm no previous Actor, Demand, Task, Goal, side lease, socket, or
  test process exists in the isolated root.

### 9.3 Wave A regression order

Run the scenarios sequentially in the order D1, G2, M1. Send one Web Message,
wait for the receipt, side, Demand state, reply, and logs to settle, then send
the next Message. When one scenario's named regression checkpoint passes,
complete that scenario's remaining Wave A messages before deleting its Actor
and starting the next role. Do not keep three live Actors for a later replay.

#### Gate A — D1 same-deliverable supplement

1. Create a Dev Actor.
2. Send D1-1 from the scenario design to create the base schedule tool Demand.
3. Wait until Demand A is canonical and any active Task is observable.
4. Send D1-2 exactly:

```text
同一个基础工具补充每周重复日程和本地时区显示。
```

Required result:

- `merge_intake A`;
- A revision/source refs advance exactly once;
- no duplicate Demand is created;
- at most one active Task remains;
- tool feedback, receipt, persisted state, and logs agree.

On failure, stop the entire acceptance run and do not hide it with a retry.

#### Gate B — G2 independent deliverable

1. Create a fresh Design Actor.
2. Execute G2-1 through G2-4 exactly as specified in the scenario design.
3. Send G2-5 exactly:

```text
另外单独整理加载、空数据、来源失效和生成失败的状态库。
```

Required result:

- `create C`;
- A and B retain their existing canonical meaning;
- C is independently completable, acceptable, cancelable, and deliverable;
- no `merge_intake A`;
- at most one active Task remains.

On failure, stop the entire acceptance run.

#### Gate C — M1 terminal correction

1. Create a fresh Market Actor.
2. Execute M1-1 through M1-5 exactly as specified in the scenario design.
3. Wait until acquisition-brief Demand A is terminal and unrelated Demands B/C
   remain identifiable.
4. Send M1-6 exactly:

```text
第一份收购简报范围改一下：只看过去12个月，并且删除无法由公司或监管文件确认的传闻。
```

Required result:

- the side reads all-state Demand summaries and the relevant terminal A;
- it creates one new correction Demand D;
- D's canonical text names the prior acquisition brief and the remaining
  correction;
- terminal A is unchanged;
- unrelated live B/C are unchanged;
- no unrelated `revise`;
- at most one active Task remains.

On failure, stop the entire acceptance run.

### 9.4 Complete each Wave A scenario after its regression checkpoint

After D1-2, G2-5, or M1-6 passes, continue that same Actor through the
scenario's remaining Wave A messages from:

`docs/memo/2026-07-25-real-actor-multi-demand-scenario-test-design.md`.

Verify:

- same-deliverable additions continue to merge;
- outcome/boundary changes revise rather than merge;
- independent acceptance units create;
- terminal follow-ups create new unmet Demands without terminal mutation;
- simple progress questions or acknowledgements do not become Demands;
- one active Task/native Goal is preserved;
- Task completion remains evidence rather than automatic Demand completion;
- the next live Demand is selected only after the current Task terminal
  reconciliation;
- user-visible replies and Artifacts are readable in WebUI.

Wave A passes only after all three complete scenarios pass. Wave B remains
forbidden until that full Wave A hard gate passes.

### 9.5 Required evidence

For every inbound record:

- Web Message id and exact text;
- side thread id, turn id, selected Skill evidence, model/effort;
- ordered read-tool calls and arguments;
- `demand_triage.resolve` arguments and final tool result;
- receipt state and attempt id;
- Demand ids, revisions, terminal state, and source refs before/after;
- active/terminal Task and native Goal identity when applicable;
- Web-visible reply or Artifact;
- broker/daemon errors or contradictions;
- capability-consumed-to-lease-cleanup latency.

Persist the final result in:

`docs/memo/2026-07-25-demand-triage-semantic-rebuild-acceptance.md`.

Do not overwrite the earlier failed Wave A report.

### 9.6 Cleanup

- [x] Delete every created Actor through the real WebUI/public product path.
- [x] Confirm public instance list is empty.
- [x] Stop WebUI through its owning process/session.
- [x] Run public `env reset --yes` against the exact isolated shared root.
- [x] Confirm the Web port is closed.
- [x] Confirm no attributable Actor, daemon, App Server, runtime broker,
  browser, socket, lock, side lease, or temporary root remains.
- [x] Record cleanup result in the acceptance memo.

## 10. Acceptance matrix

| Proof class | Required exit condition |
|---|---|
| Product | D1 merges the same deliverable, G2 creates the independent deliverable, M1 creates a terminal correction; full Wave A then passes |
| Contract | native Skill is model-visible before triage sampling; one resolve result, receipt, persisted effect, Web status, and logs agree |
| Architecture | one shared Skill owns semantic judgment; existing read tools supply facts; Demand Sys is deterministic; Task/Goal and daemon are unchanged |
| Replacement | no live-only guidance, duplicate SOP, second Skill, fallback prompt, parent branch, or intelligent Python path remains |
| Operations | Actors, leases, processes, sockets, ports, locks, and isolated state cleanly disappear |

The REBUILD is not complete if automated tests pass but any real Actor semantic
gate fails.

## 11. Verification breadth and submission

Use exact and affected focused tests during implementation. Do not run
`./buddyswitch-test full` merely because the plan is complete. Run full only
after the candidate is frozen for merge/release, when the user explicitly asks
for repository-wide acceptance, or when an unresolved affected boundary
requires that breadth.

Before submission:

- [x] Run `git status --short` and partition all task-related files from
  unrelated user work.
- [x] Record HEAD, tracked patch identity, and every non-ignored untracked file.
- [x] Confirm the two pre-existing Wave A memos remain intact.
- [x] Confirm this plan was not submitted as a plan-only commit.
- [x] Confirm code, tests, current architecture, this plan, and the acceptance
  report form one coherent final change.
- [x] Run final diff review against the acceptance sentence and every proof
  class.
- [ ] Request explicit user acceptance before any broader architecture phase.

## 12. Stop conditions

Stop implementation and return for review if any of the following becomes
necessary:

- changing `thread/start` to `thread/fork`;
- adding a Tool or first-class context object;
- adding semantic logic to Demand Sys or daemon-service;
- adding a Demand relationship graph or terminal dependency edge;
- changing Task/Goal/orchestration behavior;
- weakening one-shot, capability, receipt, revision, lifecycle, or atomicity
  assertions;
- accepting state convergence while the tool/Web result reports failure;
- continuing Wave B after a Wave A hard failure.

These are scope changes, not implementation details.
