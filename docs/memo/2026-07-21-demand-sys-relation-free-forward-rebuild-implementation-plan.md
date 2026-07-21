# Demand Sys Relation-Free Forward Rebuild Implementation Plan

> **For the implementing agent:** Use `superpowers:executing-plans` to execute
> this plan in order. Use `superpowers:test-driven-development` for every
> behavior-changing block, `buddyswitch-testing` for all executable evidence,
> `superpowers:systematic-debugging` for unexpected failures, and
> `superpowers:verification-before-completion` before any completion claim.
> Execute inline unless the user explicitly authorizes sub-agent work. Do not
> start implementation until the user confirms this plan.

**Date:** 2026-07-21

**Status:** Tasks 0–11 complete; Task 12 freeze, FINAL, and push in progress

**Progress:** User approved implementation and the separate default-runtime
schema-v2 cutover on 2026-07-21. The relation-free Domain, Repository, actor
tool, CLI projection, attention skill, current architecture, inbound impact,
and replacement tests completed their RED/GREEN loops. The bounded one-time
cutover changed the known four-row aggregate from schema 1 SHA-256
`fe4b8c5e97d17b101a3b0336a4b0fc6bed2eaf43e84ff4ae31ee5b9beef607a5` to
schema 2 SHA-256
`eebd9f1c638c10087b36f98ea5ae84c21be8753257bf18dd99f876825913e973`;
the 33-file non-target manifest remained byte-identical, normal CLI reads
succeeded, and the temporary helper/test were deleted. The coherent automated
milestone passed with 108 tests and 766 subtests. Real PM/Dev actors then proved
supplement absorption into the active Task Demand, immutable Task
`basis_revision`, explicit Task-to-Demand completion reconciliation, and later
independent-Demand consumption. Both actors and the exact isolated root were
removed with no process or socket residue. The bounded retired-token audit and
`git diff --check` are clean. Browser visual inspection of the ignored local
HTML was blocked by local-file URL policy, so only parser, content, replacement,
and responsive-source inspection is claimed for that artifact.

**Design source:**
`docs/memo/2026-07-21-demand-sys-relation-free-forward-rebuild-design.md`

**Baseline:** `fea-daemon` at
`bfbd4f39e7f8f41c14ad728b35929289a8bdf014`

**Goal:** Replace the Phase 1–3 relation-bearing Demand model with one
schema-v2 canonical Demand set, preserve the proven inbound → Demand → actor →
opaque Task collaboration loop, and remove every live surface of the retired
relation model.

**Architecture:** Demand Sys remains one local product module with one domain
owner and one actor-scoped atomic repository. Sources only capture needs;
generic daemon infrastructure only delivers actor input; the actor owns
semantic canonicalization and Task selection; Task Sys retains only opaque
`{demand_id, basis_revision}` references. No relation graph, migration layer,
event bus, automatic scheduler, Demand-to-Task callback, or compatibility path
is introduced.

**Tech stack:** Python 3.13, JSON actor aggregates, the existing env.tool
registry and `buddyswitch-codex` CLI, pytest 9.0.3 through the sole public
`./buddyswitch-test` entry, and a local Shape HTML artifact under ignored
`docs/spec/`.

---

## 1. Acceptance contract

The rebuild is accepted only when this sentence is true:

> An implemented inbound source or actor can durably create one actor-owned
> Demand; the actor can revise it, absorb separately captured rows that express
> the same canonical need, leave distinct needs independently live, select at
> most one for Task execution, and explicitly complete or cancel it; meanwhile
> Demand Sys stores no cross-Demand organization graph, Task Sys stores only an
> opaque DemandRef, daemon infrastructure contains no Demand business rule, the
> known runtime aggregate is schema v2, and no current code, contract,
> permission, guidance, test, architecture document, or local current visual
> artifact preserves the retired relation model.

Material proof classes:

| Proof | Required observation |
| --- | --- |
| Product | Real Track comment creates a Demand; a real actor canonicalizes a supplement into the active Demand; one Task remains active; an independent later Demand is consumed afterward. |
| Contract | Schema v2, exact ten actions, immutable provenance after create, exact terminal tagged unions, exact public projection, stale writes and retired payloads reject without mutation. |
| Architecture | One Demand domain owner, one repository write path, generic daemon Task-free/Demand-rule-free, Task core free of Demand implementation dependencies. |
| Replacement | No relation fields/actions/terminals/errors/prompts/guidance/current docs remain; schema v1 is rejected rather than translated. |
| Operations | Atomic writes, failed mutations byte-identical, bounded one-time runtime cutover, real actor/log inspection, and clean process/socket/lock/state cleanup. |

## 2. Frozen target contracts

These are implementation constraints, not options to revisit during coding.

### 2.1 Aggregate and record

```python
SCHEMA_VERSION = 2

DEMAND_RECORD_FIELDS = {
    "id",
    "intake_key",
    "description",
    "detail",
    "source_refs",
    "revision",
    "checked_revision",
    "terminal",
    "created_at",
    "updated_at",
}
```

The aggregate owns `actor_target` exactly once. Every Demand record must have
exactly the fields above. Missing, extra, v1, relation-bearing, or per-record
`actor_target` data is invalid.

### 2.2 Lifecycle

```python
TERMINAL_TYPES = ("completed", "canceled", "absorbed")
```

Exact terminal shapes:

```python
{
    "type": "completed",
    "at": timestamp,
    "summary": summary,
    "evidence_refs": evidence_refs,
}

{
    "type": "canceled",
    "at": timestamp,
    "summary": summary,
}

{
    "type": "absorbed",
    "at": timestamp,
    "summary": summary,
    "target_demand_id": target_demand_id,
}
```

`terminal is None` means live. Terminal records are immutable. An exact replay
of the same terminal action is a no-op; a conflicting action rejects.

### 2.3 Actor actions

```python
DEMAND_ACTIONS = {
    "create",
    "revise",
    "list",
    "get",
    "get_many",
    "check",
    "complete_check",
    "absorb_into",
    "complete",
    "cancel",
}
```

`revise` accepts only `demand_id`, `expected_revision`, `description`, and
`detail`. `source_refs` is established by `create` and merged only by the
Demand-owned `absorb_into` transaction.

### 2.4 Public projection

```python
PUBLIC_DEMAND_FIELDS = {
    "demand_id",
    "intake_key",
    "description",
    "actor",
    "revision",
    "checked_revision",
    "terminal",
    "created_at",
    "updated_at",
}
```

The projection excludes `detail` and `source_refs`, as it does today, and also
excludes every retired relation field. `actor` is derived from the requested,
validated aggregate target rather than copied from the record.

### 2.5 Forward-only removal set

Delete, do not alias or deprecate:

```text
record.parent_id
record.depends_on
demand_sys.set_parent
demand_sys.add_dependency
demand_sys.remove_dependency
demand_sys.split
demand_sys.mark_duplicate
demand_sys.supersede
DemandRelationConflict
E_DEMAND_RELATION
terminal.type == duplicate
terminal.type == superseded
generic terminal.ref for absorbed
live-child and relation-cycle invariants
schema-v1 normal-reader translation/fallback
```

## 3. Source identity and evidence discipline

Before every RED/GREEN/IMPACT/FINAL block:

- [ ] Record `git rev-parse HEAD`.
- [ ] Record `git diff --binary | shasum -a 256`.
- [ ] Record every non-ignored untracked path and its SHA-256, together with
  `git status --short`.
- [ ] State the exact claim and explicit test targets.
- [ ] After the command, record exit status, summary, duration, and runner
  cleanup result.

Evidence note template:

```text
Verification Evidence
- state: RED | GREEN | IMPACT | MILESTONE | FINAL | FIX_AFTER_FINAL
- source: repo, HEAD, tracked patch SHA-256, non-ignored untracked paths
- command: exact ./buddyswitch-test invocation or bounded artifact check
- environment: public runner / real buddyswitch-codex root / runtime path
- result: exit, pass/fail summary, duration, cleanup residuals
- proves: exact behavior and direct boundaries
- valid-for: current worktree or frozen SHA
- residual-risk: none or explicit risk
```

Do not use direct `pytest`, add another runner, or run `full` between blocks.
An intended RED must fail on the new assertion, not import, collection,
fixture, runner, or environment setup.

## 4. Detailed TDD execution

### Task 0: Reconfirm the execution boundary

**Files:**

- Read: `AGENTS.md`
- Read: `.agents/skills/buddyswitch-testing/SKILL.md`
- Read: this plan and its design source
- Inspect: all files named in Tasks 1–8

- [x] Verify the branch and upstream still point at the recorded baseline or
  record the new source identity and review intervening commits.
- [x] Verify the only current non-ignored untracked planning files are the
  design and this plan; partition any new unrelated user work.
- [x] Re-run the exact retired-token inventory over Demand-owned paths and
  confirm the file map below is still complete.
- [x] Confirm no actor instance is active before any later default-runtime
  cutover work.
- [x] Do not edit product code until Tasks 1–6 have an explicit test target.

Task 0 evidence: `./buddyswitch-test focused
tests/unit/demand_sys/test_capture_and_check.py
tests/unit/demand_sys/test_organization.py
tests/integration/demand_sys/test_repository_atomicity.py` passed with 37 tests,
9 subtests, and clean runner cleanup on baseline
`bfbd4f39e7f8f41c14ad728b35929289a8bdf014`.

No commit is made in this task.

### Task 1: Rebuild the domain contract tests to schema v2

**Execution:** complete. Intended RED produced 15 failures limited to schema 1,
retired record/provenance/terminal/relation behavior; 26 preservation tests and
5 subtests remained green.

**Tests to modify:**

- `tests/unit/demand_sys/test_capture_and_check.py`
- `tests/integration/demand_sys/test_repository_atomicity.py`

**Tests to replace:**

- Delete: `tests/unit/demand_sys/test_organization.py`
- Create: `tests/unit/demand_sys/test_canonicalization.py`
- Create: `tests/unit/demand_sys/test_lifecycle.py`

#### 1A. Write the RED assertions

- [ ] In capture/check tests, assert a created row has exactly
  `DEMAND_RECORD_FIELDS`, has no per-record `actor_target`, and starts at
  `revision=1`, `checked_revision=0`, `terminal=None`.
- [ ] Change the revise case so it proves only description/detail change,
  provenance remains byte-for-byte equal, and revision advances once.
- [ ] Add a direct domain-call case showing a passed `source_refs` argument is
  no longer part of the `revise` signature rather than silently ignored.
- [ ] Preserve intake replay, stale revision, check cursor, current live index,
  ordering, terminal attention, and actor isolation coverage.
- [ ] Change repository expectations to schema v2.
- [ ] Write a v1 fixture to the actor aggregate path, call the normal reader,
  assert `schema_version must be 2`, and assert the file bytes are unchanged.
- [ ] Add schema-v2 fixtures containing `parent_id`, `depends_on`, or a
  per-record `actor_target`; prove domain normalization rejects them.

Required canonicalization test method names:

- `test_absorb_supplement_updates_target_and_terminalizes_source_atomically`
- `test_absorb_semantic_duplicate_merges_provenance_even_when_content_is_unchanged`
- `test_absorb_stale_source_or_target_changes_neither_record`
- `test_absorb_rejects_self_without_write`
- `test_absorb_exact_replay_is_noop`
- `test_absorbed_terminal_uses_target_demand_id_not_ref`

Required lifecycle test method names:

- `test_complete_stores_exact_summary_and_evidence_shape`
- `test_cancel_stores_exact_summary_shape`
- `test_terminal_exact_replay_is_noop`
- `test_different_action_against_terminal_demand_rejects_without_write`
- `test_retired_duplicate_and_superseded_terminal_shapes_are_invalid`

The primary absorb assertion must be exact:

```python
self.assertEqual(
    source_after["terminal"],
    {
        "type": "absorbed",
        "at": source_after["terminal"]["at"],
        "summary": "Same canonical need.",
        "target_demand_id": target["id"],
    },
)
self.assertEqual(target_after["source_refs"], [*target_refs, *new_source_refs])
self.assertNotIn("ref", source_after["terminal"])
```

#### 1B. Run the intended RED

```bash
./buddyswitch-test focused \
  tests/unit/demand_sys/test_capture_and_check.py \
  tests/unit/demand_sys/test_canonicalization.py \
  tests/unit/demand_sys/test_lifecycle.py \
  tests/integration/demand_sys/test_repository_atomicity.py
```

Expected RED: failures must point to schema `1`, old record fields, mutable
revise provenance, terminal `ref`, retired terminal acceptance, live-child
rules, or missing schema-v2 rejection. If collection/import fails, fix the test
setup before proceeding and re-establish behavioral RED.

### Task 2: Implement the minimal schema-v2 Demand owner

**Execution:** complete. The exact Task 1 command passed with 34 tests, 12
subtests, and clean runner cleanup. The bounded Domain/Repository retired-token
audit returned no matches.

**Production files:**

- Modify: `scripts/env/repos/demands.py`
- Modify: `scripts/env/domain/demand_sys.py`

#### 2A. Repository change

- [ ] Set `SCHEMA_VERSION = 2`.
- [ ] Keep the aggregate fields exactly
  `schema_version`, `actor_target`, and `demands`.
- [ ] Preserve the actor-scoped lock, deep-copy reads, complete-aggregate
  validation before write, and atomic `runtime_files.write_json_object` path.
- [ ] Add no migration reader, fallback, alternate schema constant, or
  compatibility command.

#### 2B. Domain change

- [ ] Replace terminal and record field constants with the frozen target
  contracts in §2.
- [ ] Remove per-record actor normalization; actor scoping remains a required
  argument normalized by the repository.
- [ ] Make `create` write only the ten canonical record fields.
- [ ] Change `revise` to the exact typed signature
  `revise(actor_target: Mapping[str, Any], demand_id: Any,
  expected_revision: Any, description: Any, detail: Any) -> dict[str, Any]`.

- [ ] Remove `_require_no_live_children`, relation traversal, parent/dependency
  mutations, split, lineage-generalized terminalization, duplicate,
  supersede, `DemandRelationConflict`, and `E_DEMAND_RELATION`.
- [ ] Keep `absorb_into` concrete: validate two distinct live records and both
  revisions; merge target-first unique `source_refs`; revise target content;
  terminalize source with `target_demand_id`; commit once.
- [ ] Do not replace removed relation logic with a generalized graph helper,
  terminal-reference abstraction, or action registry.
- [ ] Keep complete/cancel exact-revision guarded, but remove all live-child
  restrictions.
- [ ] Preserve exact intake replay, stale-write atomicity, check cursor,
  terminal immutability, and actor isolation.

The terminal normalizer should branch explicitly:

```python
if terminal_type == "completed":
    return {"type": "completed", "at": at, "summary": summary,
            "evidence_refs": evidence_refs}
if terminal_type == "canceled":
    return {"type": "canceled", "at": at, "summary": summary}
return {"type": "absorbed", "at": at, "summary": summary,
        "target_demand_id": target_demand_id}
```

#### 2C. Run GREEN and a local replacement audit

Run the same Task 1 command. Expected: all pass and runner cleanup is clean.

Then run:

```bash
rg -n 'parent_id|depends_on|DemandRelationConflict|E_DEMAND_RELATION|mark_duplicate|supersede|def split|def set_parent|def add_dependency|def remove_dependency' \
  scripts/env/domain/demand_sys.py scripts/env/repos/demands.py
```

Expected: no output. Do not commit yet.

### Task 3: Cut the actor tool and permission surface to ten actions

**Execution:** complete. The intended RED exposed the six retired catalog and
permission actions plus mutable revise provenance. The exact suite then passed
with 41 tests and 651 subtests after cutting the tool, handler, permission, and
context surfaces to the frozen ten actions.

**Tests to modify:**

- `tests/unit/env_tool/test_semantic_contract.py`
- `tests/unit/env_tool/test_schema_contract.py`
- `tests/unit/actor/test_role_action_auth.py`
- `tests/integration/env_tool/test_response_demand.py`

**Production files:**

- `scripts/env/tools/demand_sys/tool.py`
- `scripts/env/tools/demand_sys/_impl.py`
- `scripts/env/tool_runtime/role_auth.py`
- `scripts/env/tools/context/_impl.py`

#### 3A. RED

- [ ] Change catalog and task-requirement expected sets to exactly
  `DEMAND_ACTIONS` from §2.3.
- [ ] Change permission coverage to exactly the same ten prefixed permissions.
- [ ] Assert `revise.properties` and `revise.required` are exactly
  `demand_id`, `expected_revision`, `description`, and `detail`.
- [ ] Preserve the existing assertion that `absorb_into.merged_target` cannot
  accept source refs.
- [ ] Change the all-action response table from sixteen to ten actions.
- [ ] Add one integration loop proving every retired action is rejected by the
  registry as unsupported and leaves Demand and Task snapshots byte-identical.
- [ ] Add a response case proving `source_refs` on actor `revise` is rejected,
  not ignored.

Run:

```bash
./buddyswitch-test focused \
  tests/unit/env_tool/test_semantic_contract.py \
  tests/unit/env_tool/test_schema_contract.py \
  tests/unit/actor/test_role_action_auth.py \
  tests/integration/env_tool/test_response_demand.py
```

Expected RED: exact-set mismatches show the six retired actions and revise's
old `source_refs`; no setup failure is acceptable.

#### 3B. GREEN

- [ ] Delete child/split schemas and the six retired `ActionDefinition` rows.
- [ ] Rewrite tool title/scope/object-model/action semantics around capture,
  attention, canonicalization, and lifecycle; remove organization/lineage
  language.
- [ ] Keep exactly ten handlers and call the new five-argument `revise` domain
  signature.
- [ ] Replace result guidance that says “organization action” with the exact
  choices revise/absorb/keep independent/cancel.
- [ ] Remove the six permissions; add no deprecated aliases.
- [ ] Change context description from “live organization state” to canonical
  live Demand state. Do not add Task selection logic to context.

Run the same Task 3 command. Expected: all pass, cleanup clean.

### Task 4: Rebuild the external read projection and CLI fixture

**Execution:** complete. A schema-v2 process fixture produced the intended old
projection failure; the actor value now comes from the aggregate target and the
relation-free allowlist passed with 3 tests and 9 subtests.

**Tests:**

- Modify: `tests/process/launcher/test_demand_commands.py`

**Production:**

- Modify: `scripts/env/domain/demand_read.py`

#### 4A. RED

- [ ] Rewrite the process fixture as a schema-v2 aggregate with no
  per-record actor or relation fields.
- [ ] Assert list/get return exactly `PUBLIC_DEMAND_FIELDS`.
- [ ] Assert actor identity still appears in the external projection and is
  the aggregate target.
- [ ] Assert `detail`, `source_refs`, `parent_id`, and `depends_on` are absent.
- [ ] Preserve CLI read-only and malformed/unscoped argument tests.

```bash
./buddyswitch-test focused tests/process/launcher/test_demand_commands.py
```

Expected RED: current projection tries to read record `actor_target` and still
returns relation fields.

#### 4B. GREEN

- [ ] Change the private projection helper to accept a keyword-only validated
  actor target:

```python
def external_demand_projection(
    record: Mapping[str, Any],
    *,
    actor_target: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "demand_id": record["id"],
        "intake_key": record["intake_key"],
        "description": record["description"],
        "actor": dict(actor_target),
        "revision": record["revision"],
        "checked_revision": record["checked_revision"],
        "terminal": deepcopy(record["terminal"]),
        "created_at": record["created_at"],
        "updated_at": record["updated_at"],
    }
```

- [ ] Pass the same actor target already validated by the domain list/get call;
  do not read the repository directly from CLI or duplicate Demand validation.

Run the same process test. Expected: pass with clean cleanup.

### Task 5: Rebuild actor attention and composition guidance

**Execution:** complete. RED localized old organization guidance. The Demand
prompt is Task-free, while the actor skill owns two-pass canonicalization,
four explicit judgments, and active-Task absorption targeting. The focused
suite passed with 20 tests and 89 subtests.

**Tests:**

- Modify: `tests/unit/demand_sys/test_daemon_adapter.py`
- Modify: `tests/unit/architecture/test_task_management_skill.py`
- Modify: `tests/unit/architecture/test_demand_sys_boundaries.py`

**Production/guidance:**

- Modify: `tools/launcher/demand_sys_daemon_adapter.py`
- Modify: `buddyswitch/skills/shared/task-management/SKILL.md`

#### 5A. RED

- [ ] Assert the daemon prompt asks the actor to canonicalize pending Demands
  and contains no Task operation, relation taxonomy, or organization action.
- [ ] Assert the installed skill teaches two-pass comparison:
  pending descriptions versus live index, then `get_many` only for plausible
  candidates.
- [ ] Assert the decisions are revise, absorb, independent, or cancel.
- [ ] Assert that before absorb the actor reads active Task state and, when
  exactly one matching Demand owns the active Task, that Demand is the target.
- [ ] Assert an absorption does not update Task `basis_revision`; the actor
  rereads latest Demand at progress/outcome checks.
- [ ] Replace the old Track provenance assertion so it does not teach parent,
  dependency, duplicate, supersede, or relation semantics.
- [ ] Rename Phase 1/2 architecture test names to current behavior names.

```bash
./buddyswitch-test focused \
  tests/unit/demand_sys/test_daemon_adapter.py \
  tests/unit/architecture/test_task_management_skill.py \
  tests/unit/architecture/test_demand_sys_boundaries.py
```

Expected RED: current daemon/skill/current-architecture wording still teaches
organization and the retired taxonomy.

#### 5B. GREEN

- [ ] Keep `DEMAND_CHECK_PROMPT` fixed, concise, Demand-owned, and Task-free.
- [ ] Rewrite only the Demand Check and Demand/Task composition portions of the
  shared skill; preserve current Task lifecycle/frame instructions.
- [ ] State clearly that source refs are provenance/retrieval context, not
  relationship truth.
- [ ] Keep the active-Task absorption-target rule in actor guidance only.
- [ ] Do not add Task imports/calls to Demand domain or daemon adapter.

Run the same focused command. Expected: pass.

### Task 6: Rewrite current architecture and local visual truth

**Execution:** code/docs complete with one verification limitation. The current
architecture guard passes 6 tests; two superseded ignored HTML artifacts are
deleted and the remaining artifact contains the exact three target scenarios
with no retired taxonomy. HTML parsing and bounded source inspection passed.
Chrome refused the local `file://` URL by policy, so desktop/narrow pixel-level
browser inspection is not claimed.

**Tracked current docs:**

- Rewrite: `docs/arch/demand-sys-architecture.md`
- Modify: `docs/arch/task-sys-architecture.md`
- Modify: `docs/arch/daemon-service-architecture.md`

**Ignored local current artifacts:**

- Delete: `docs/spec/2026-07-18-demand-task-system-interface-design.html`
- Delete: `docs/spec/2026-07-19-demand-sys-proactive-prototype-flow.html`
- Replace: `docs/spec/2026-07-21-demand-sys-three-scenario-flow.html`

**Architecture test:**

- Modify: `tests/unit/architecture/test_demand_sys_boundaries.py`

#### 6A. RED replacement guard

- [ ] Add a current-surface guard over exact Demand-owned code, permissions,
  skill, and `docs/arch` paths. It may construct retired tokens from fragments
  so the test itself does not become a false-positive live surface.
- [ ] Assert one owner, one repository write path, no Demand implementation in
  Task, no Task implementation in Demand, and no Demand semantics in generic
  daemon code.
- [ ] Assert current architecture text names schema v2, canonical Demand set,
  two-pass actor canonicalization, opaque DemandRef, independent completion,
  and explicit non-goals.

Run the exact architecture test and observe intended doc/residue failures.

#### 6B. Rewrite current truth

- [ ] Rewrite Demand architecture from the approved design; do not retain a
  “previous model” section.
- [ ] In Task architecture, replace the remaining organization/relation wording
  while preserving Task status/lifecycle and opaque DemandRef ownership.
- [ ] In daemon architecture, describe generic input delivery and Demand-owned
  attention policy without moving canonicalization into daemon service.
- [ ] Preserve dated historical memos as history; they are not current policy.
- [ ] Before touching the HTML artifact, load and follow
  `shape-html-artifact`; then render exactly three relation-free scenarios:
  active-task supplement absorption, later defect as a new Demand, and an
  independent queued live Demand. Show owners and observable state, not a
  relation graph.
- [ ] Delete the two superseded ignored HTML files. Do not keep redirects or
  alternate “legacy” copies.

#### 6C. Verify docs and artifact

```bash
./buddyswitch-test focused tests/unit/architecture/test_demand_sys_boundaries.py
```

Then inspect the HTML in a browser and verify:

- no horizontal overflow at desktop and narrow viewport;
- all three scenarios are readable without hidden controls;
- lifecycle, canonicalization, Task boundary, and daemon boundary match the
  tracked architecture;
- no relation, parent, dependency, duplicate, supersede, correction edge, or
  reopen path is taught.

### Task 7: Run direct inbound and Task-boundary impact proof

**Execution:** complete. The first run found one stale Track test reading the
removed per-record actor target. The assertion moved to aggregate ownership;
the unchanged four-test impact command then passed.

No new feature is expected in these files. Change production only if an exact
affected contract proves a real mismatch.

```bash
./buddyswitch-test focused \
  tests/unit/im/test_wake_handler.py::ImWakeHandlerTests::test_exact_target_visible_message_maps_to_one_demand_capture \
  tests/integration/track/test_comment_added_handler.py::TrackCommentAddedHandlerTests::test_track_comment_handler_captures_demand_and_requests_actor_attention \
  tests/integration/track/test_comment_added_handler.py::TrackCommentAddedHandlerTests::test_track_comment_handler_captures_demand_while_another_task_is_active \
  tests/unit/architecture/test_task_sys_boundaries.py::test_task_sys_has_no_demand_implementation_dependency
```

- [ ] Confirm IM and Track still capture a durable schema-v2 Demand and do not
  create/mutate Task directly.
- [ ] Confirm capture while another Task is active remains durable and requests
  attention rather than being dropped.
- [ ] Confirm Task core has no Demand import, lookup, call, subscription,
  satisfaction rule, or mutation.
- [ ] If anything fails unexpectedly, stop, use systematic debugging, add the
  smallest escaping regression at the semantic owner, and re-run exact then
  affected proof. Do not add a case-specific fallback.

### Task 8: Build, prove, execute, and remove the one-time runtime cutover

**Execution:** complete. The temporary operation passed 3 tests and 7
rejection subtests. After the user separately authorized the mutation, the
default target changed from the exact schema-1 SHA-256
`fe4b8c5e97d17b101a3b0336a4b0fc6bed2eaf43e84ff4ae31ee5b9beef607a5` to
schema-v2 SHA-256
`eebd9f1c638c10087b36f98ea5ae84c21be8753257bf18dd99f876825913e973`.
Normal CLI reads validated all four rows, the 33-file non-target manifest stayed
byte-identical, the temporary operation and test were deleted, and the
surviving exact suite passed with 37 tests and 21 subtests.

This task has a hard authorization gate. Tasks 1–7 may be implemented and
tested first, but the default runtime remains unreadable by schema-v2 product
code until this cutover is approved and executed.

**Temporary files, never present in the final tree:**

- Create then delete: `tools/launcher/demand_v2_cutover.py`
- Create then delete: `tests/process/launcher/test_demand_v2_cutover.py`

#### 8A. TDD the bounded operation

The temporary operation accepts only:

```text
--actor-id act-dev-c3325d035f6c
--role-id dev
--expected-sha256 fe4b8c5e97d17b101a3b0336a4b0fc6bed2eaf43e84ff4ae31ee5b9beef607a5
[--apply]
```

- [x] RED: prove dry-run transforms a copied exact fixture in memory only.
- [x] RED: prove wrong hash, wrong actor, wrong record count, non-null parent,
  non-empty dependency, unknown terminal, or unexpected field rejects before
  write and leaves every byte unchanged.
- [x] RED: prove apply writes schema v2 through
  `runtime_files.write_json_object`, renames only absorbed `ref` to
  `target_demand_id`, removes only the asserted retired fields, and preserves
  all semantic values.
- [x] RED: prove every unrelated object file remains byte-identical.
- [x] GREEN: implement the concrete operation; no generalized migration
  framework, discovery, multi-version support, or normal-reader import.

```bash
./buddyswitch-test focused tests/process/launcher/test_demand_v2_cutover.py
```

#### 8B. Re-inventory and ask for explicit authorization

Immediately before mutation:

```bash
./buddyswitch-codex instance list
shasum -a 256 /Users/chen/.codex-buddyswitch/state/buddyswitch/objects/demand-sys/actors/act-dev-c3325d035f6c-dev.json
```

- [x] Require zero active instances.
- [x] Require the exact SHA-256, actor target, schema 1, four records, all
  `parent_id=null`, all `depends_on=[]`, and terminal types limited to the
  observed completed/absorbed set.
- [x] Build a before manifest of every file under the authoritative state
  root, including SHA-256, excluding only the target aggregate from the
  equality assertion.
- [x] Present the fresh facts and exact command to the user and obtain explicit
  approval. The earlier approval of this plan is not approval for runtime
  mutation.

#### 8C. Apply and prove

```bash
source tools/launcher/env.sh
buddyswitch_env_init
"$BUDDYSWITCH_PYTHON" tools/launcher/demand_v2_cutover.py \
  --actor-id act-dev-c3325d035f6c \
  --role-id dev \
  --expected-sha256 fe4b8c5e97d17b101a3b0336a4b0fc6bed2eaf43e84ff4ae31ee5b9beef607a5 \
  --apply
```

Do not bypass the configured interpreter or runtime workspace ownership.

- [x] Validate the target through normal schema-v2 Demand reads and public CLI.
- [x] Compare every other state-root file to the before manifest byte-for-byte.
- [x] Inspect the four rows: all prior values preserved, only exact v2 shape
  changes applied.
- [x] Delete the temporary operation and its test.
- [x] Re-run surviving schema/repository/process tests after deletion.
- [x] Prove no `demand_v2_cutover`, schema-v1 branch, or migration entrypoint
  remains in current code/tests/help.

If the precondition hash or inventory changed, do not modify data. Reinspect and
return to the user with the changed facts.

### Task 9: Run one coherent automated MILESTONE

**Execution:** complete. The latest exact command below passed with 108 tests,
766 subtests, zero failures, and clean runner cleanup in 2.30 seconds.

After Tasks 1–8 and removal of the cutover helper, run one batched direct suite:

```bash
./buddyswitch-test focused \
  tests/unit/demand_sys/test_capture_and_check.py \
  tests/unit/demand_sys/test_canonicalization.py \
  tests/unit/demand_sys/test_lifecycle.py \
  tests/unit/demand_sys/test_daemon_adapter.py \
  tests/integration/demand_sys/test_repository_atomicity.py \
  tests/integration/env_tool/test_response_demand.py \
  tests/process/launcher/test_demand_commands.py \
  tests/unit/architecture/test_demand_sys_boundaries.py \
  tests/unit/architecture/test_task_management_skill.py \
  tests/unit/architecture/test_task_sys_boundaries.py \
  tests/unit/actor/test_role_action_auth.py \
  tests/unit/env_tool/test_semantic_contract.py \
  tests/unit/env_tool/test_schema_contract.py \
  tests/unit/im/test_wake_handler.py::ImWakeHandlerTests::test_exact_target_visible_message_maps_to_one_demand_capture \
  tests/integration/track/test_comment_added_handler.py::TrackCommentAddedHandlerTests::test_track_comment_handler_captures_demand_and_requests_actor_attention \
  tests/integration/track/test_comment_added_handler.py::TrackCommentAddedHandlerTests::test_track_comment_handler_captures_demand_while_another_task_is_active
```

- [x] Require zero failures and zero cleanup residuals.
- [x] Record source identity and evidence.
- [x] Do not interpret this as real actor acceptance.

### Task 10: Real `buddyswitch-codex` actor acceptance

**Execution:** complete. Formal CLI created PM
`act-pm-33cad8b8aa96` and Dev `act-dev-645c3c0dc0ee` in isolated root
`/private/tmp/buddyswitch-demand-v2-real.NgbzaV`; both runtime broker, daemon,
app server, and main thread health checks passed.

Use real Codex actor instances and the formal CLI in one fresh isolated
BuddySwitch shared/state root. Do not fake Codex, call internal actor classes,
or write runtime objects directly.

#### 10A. Start real actors

```bash
ACCEPT_ROOT="$(mktemp -d /private/tmp/buddyswitch-demand-v2-real.XXXXXX)"
export BUDDYSWITCH_SHARED_ROOT="$ACCEPT_ROOT/shared"
export BUDDYSWITCH_STATE_ROOT="$ACCEPT_ROOT/state"

PM_JSON="$(./buddyswitch-codex instance start --role pm)"
PM_ID="$(printf '%s' "$PM_JSON" | jq -er '.data.actor_id')"
DEV_JSON="$(./buddyswitch-codex instance start --role dev)"
DEV_ID="$(printf '%s' "$DEV_JSON" | jq -er '.data.actor_id')"

./buddyswitch-codex instance capabilities "$PM_ID" set --parent fast --side fast
./buddyswitch-codex instance capabilities "$DEV_ID" set --parent fast --side fast
```

- [x] Record instance ids, capability responses, source SHA, and isolated root.
- [x] Confirm both status calls are healthy before sending work.

#### 10B. Create a real inbound supplement sequence

- [x] Through `instance input` to PM, ask the PM actor to create its own
  coordination Demand/Task, create one acceptance Track, and add a Track
  comment mentioning exact `DEV_ID`. The comment asks Dev to implement a small
  fictional SaaS landing-page change and to keep the Task active briefly for a
  forthcoming supplement.
- [x] Observe through CLI that Dev has Demand A and one active Task whose
  DemandRef basis revision is 1.
- [x] While that Task is active, send a second PM instruction to add a mentioned
  Track comment that supplements the same landing-page need (for example, add
  one specific mobile CTA acceptance requirement).
- [x] Do not directly instruct Dev to call `absorb_into`; let the Demand Check
  workflow make the decision.
- [x] Poll boundedly through public CLI and logs until:

```text
A: live, revision >= 2, merged description/detail/provenance
B: terminal.type == absorbed, target_demand_id == A
Task: still the same single active Task, basis_revision == 1
```

- [x] Let Dev finish and prove the actor rereads latest A, closes Task, then
  explicitly completes A with exact Task evidence.
- [x] Add a third mentioned Track comment describing an independent need.
- [x] Prove it remains a separate live Demand C and creates a new Task only
  after the first Task is no longer active.

Observe and save:

```bash
./buddyswitch-codex demand list --actor "$DEV_ID"
./buddyswitch-codex task list --actor "$DEV_ID"
./buddyswitch-codex track list --owner "$PM_ID"
./buddyswitch-codex instance status "$PM_ID"
./buddyswitch-codex instance status "$DEV_ID"
```

Also inspect exact actor transcripts and daemon/runtime logs from the instance
roots. Required product evidence is state/log content, not merely `ok=true`.

Observed product evidence:

- A `demand-4ff8cf951949` advanced from revision 1 to 2 with both Track comment
  provenance refs; B `demand-219d687cb607` became absorbed into A;
- the same Task `task-demand-337ed502f510` stayed active with
  `basis_revision=1`, then completed before A completed at revision 3 with that
  exact Task evidence;
- independent C `demand-3eb0dac9cf13` stayed separate and created
  `task-demand-4761b28d0477` only after the first Task was terminal; C and its
  Task then completed independently;
- transcripts show the actor called `demand_sys.check`, detailed-match
  `get_many`, active `task_sys.list`, `absorb_into`, reread latest Demand,
  `task_sys.close`, and explicit Demand completion in that order.

#### 10C. Debug by owner if reality disagrees

- [x] Not triggered: no real-actor behavior failed or required a code fix. For
  any future failure, first identify whether ownership is domain, skill/prompt,
  inbound adapter, Task composition, daemon delivery, or actor runtime.
- [x] Not triggered: no escaping regression was found.
- [x] Not triggered: no system fix or scenario special case was added.
  ids, Track ids, or timing.
- [x] Not triggered: no repair rerun was needed.
  from a new clean isolated root.

#### 10D. Clean all real resources

```bash
./buddyswitch-codex instance stop "$DEV_ID"
./buddyswitch-codex instance stop "$PM_ID"
./buddyswitch-codex instance delete "$DEV_ID" --yes
./buddyswitch-codex instance delete "$PM_ID" --yes
./buddyswitch-codex env status
```

- [x] No actor-owned browser resource was opened.
- [x] Prove no actor process, app-server socket, listener, pending daemon work,
  or lock remains.
- [x] Remove only the recorded `ACCEPT_ROOT` after resource proof; never run a
  broad environment reset.

### Task 11: Final replacement and architecture audit

**Execution:** complete. The bounded current-surface search returned no retired
token, both superseded ignored visuals are absent, the one current visual is
relation-free and ignored by repository policy, `git diff --check` is clean,
and the reviewed diff contains one Demand Sys rebuild intent. Independent code
review then found that `complete` treated `evidence_refs` as optional and could
persist an unreadable completed terminal. A RED reproduced both the direct and
public-dispatch corruption path. The Domain owner now requires completed
evidence before transaction, omitted/null dispatch leaves bytes unchanged, and
exact-replay lifecycle actions advertise idempotency. The exact GREEN passed 3
tests and 5 subtests; the affected lifecycle/repository/tool/schema/architecture
suite passed 53 tests and 584 subtests.

- [x] Search exact Demand-owned current surfaces, not unrelated Artifact/Track
  domains, for every token in §2.5.
- [x] Permit retired tokens only in dated historical memos and scoped negative
  absence assertions.
- [x] Confirm deleted action ids do not appear in catalog, permission preview,
  help, schemas, role guidance, or current architecture docs.
- [x] Confirm no v1 reader, fallback, converter, temporary cutover operation,
  compatibility alias, dual write, optional legacy field, or deprecated action
  remains.
- [x] Confirm `git diff --check` is clean.
- [x] Confirm ignored local docs/spec contains only the one current relation-free
  artifact among the three named files.
- [x] Review the complete diff against the acceptance sentence and ensure no
  unrelated formatting/refactor work entered the change.

Suggested bounded residue command:

```bash
rg -n 'parent_id|depends_on|demand_sys\.(set_parent|add_dependency|remove_dependency|split|mark_duplicate|supersede)|DemandRelationConflict|E_DEMAND_RELATION|terminal.*(duplicate|superseded)|demand_v2_cutover' \
  scripts/env/domain/demand_sys.py \
  scripts/env/repos/demands.py \
  scripts/env/domain/demand_read.py \
  scripts/env/tools/demand_sys \
  scripts/env/tool_runtime/role_auth.py \
  scripts/env/tools/context/_impl.py \
  tools/launcher/demand_sys_daemon_adapter.py \
  buddyswitch/skills/shared/task-management/SKILL.md \
  docs/arch
```

Expected: no output.

### Task 12: Freeze, run FINAL, commit once, and push

No standalone plan commit and no fragmented implementation commits.

**Execution:** first frozen candidate `7d5218f` reached FINAL, which stopped
before running tests because the pre-existing Demand and Task unit directories
both contain a non-package `test_daemon_adapter.py`; default pytest import mode
loaded both as top-level `test_daemon_adapter`. A runner-command RED proved the
missing isolation flag. The sole test runner now fixes pytest to
`--import-mode=importlib`; the command regression plus both duplicate-basename
files passed with 10 tests and 13 subtests, and the runner unit/integration
support suite passed with 29 tests. This fix will be amended into the same
unpublished implementation commit before FINAL runs on the new frozen SHA.
The next frozen candidate `5ad9745` collected the complete unit tier and found
one stale baseline expectation: the shared tool-runtime architecture set omitted
the already-shipped `task_sys.create` action even though Task Sys production and
the semantic contract both expose it. The test owner now matches the canonical
catalog; its exact architecture/semantic proof passed with 2 tests and 7
subtests, and the complete unit tier passed with 478 tests and 1331 subtests.
This test-only truth repair will be included in the next amended frozen SHA.
The following frozen candidate `f820021` passed the complete unit tier (478
tests and 1331 subtests) and JavaScript unit tier (157 tests), then exposed one
pre-existing integration-fixture contradiction in three Market Evidence tests:
instance setup already created the actor's single active Task, while the
artifact helper attempted to create a second active Task whose returned id was
discarded. The helper now owns only the Artifact state those tests consume and
the unused Track/second-Task setup is removed. The exact Market Evidence GREEN
passed all 3 tests. This test-only fixture cleanup will be amended into the same
unpublished implementation commit before FINAL runs on a new frozen SHA.
Frozen candidate `92a182f` then passed unit (478 tests and 1331 subtests),
JavaScript unit (157 tests), and integration (719 tests and 563 subtests). The
process tier exposed that three generic shipped-tool contract lists omitted the
already-live `demand_sys` package. Demand Sys is now covered by the shared
package and dependency-isolation architecture tests with its exact ten actions,
and the process router isolation matrix exercises `demand_sys.list`. The exact
GREEN passed 20 tests and 25 subtests. These test-contract repairs will be
amended into the same unpublished implementation commit before FINAL runs on a
new frozen SHA.

- [x] Update the design and this plan status/progress/evidence to reflect actual
  implementation before freezing.
- [ ] Stage every task-owned tracked/untracked file intentionally; do not stage
  unrelated work. Ignored local Shape HTML remains an inspected local artifact
  unless repository policy is explicitly changed.
- [ ] Create one commit:

```bash
git commit -m "refactor(demand-sys): rebuild canonical demand lifecycle"
```

- [ ] On that frozen commit, run the sole broad final gate exactly once:

```bash
./buddyswitch-test full
```

- [ ] If FINAL fails, do not push. Diagnose, add/fix exact regression, amend the
  same not-yet-pushed commit, and rerun FINAL on the new frozen SHA.
- [ ] After FINAL passes with clean runner cleanup, push:

```bash
git push origin fea-daemon
```

- [ ] Verify `git status --short --branch` is clean apart from intentionally
  ignored `docs/spec`, and local HEAD equals `origin/fea-daemon`.

## 5. File-level completion map

| Surface | Required final state |
| --- | --- |
| `scripts/env/domain/demand_sys.py` | One concrete relation-free schema-v2 owner; ten-field record; three terminal outcomes; no relation error/action/invariant. |
| `scripts/env/repos/demands.py` | Exact schema v2 only; same single lock/write path; no migration branch. |
| `scripts/env/domain/demand_read.py` | Exact safe projection; actor derived from aggregate target. |
| `scripts/env/tools/demand_sys/{tool.py,_impl.py}` | Exact ten actions and handlers; canonicalization vocabulary. |
| `scripts/env/tool_runtime/role_auth.py` | Exact ten Demand permissions. |
| `scripts/env/tools/context/_impl.py` | Canonical live Demand wording only. |
| `tools/launcher/demand_sys_daemon_adapter.py` | Generic actor input use; Demand-owned attention; Task-free prompt. |
| `buddyswitch/skills/shared/task-management/SKILL.md` | Two-pass canonicalization, active-Task absorption target rule, explicit Demand/Task reconciliation. |
| `docs/arch/*.md` named above | One current relation-free architecture; no historical compatibility section. |
| Domain/tool/process/architecture tests | New behavior proof, no tests preserving retired behavior. |
| Default runtime aggregate | Exact schema v2 after explicit cutover approval. |
| Temporary cutover files | Absent. |
| Ignored current Shape artifact | One relation-free three-scenario HTML; two retired HTML files absent. |

## 6. Stop conditions

Stop and return to the user rather than guessing when:

- runtime aggregate identity, hash, actor target, record count, relation-field
  emptiness, or terminal inventory differs from the recorded cutover facts;
- implementation reveals Task Sys actually reads or mutates Demand state;
- a product-semantic choice would expand beyond revise/absorb/independent/
  cancel or completed/canceled/absorbed;
- real actor acceptance requires a new external contract, irreversible data
  change, permission expansion, or non-isolated production mutation;
- unrelated dirty work overlaps a task-owned file and cannot be partitioned.

Ordinary local implementation ambiguity, test refactoring, names, and small
owner-correct fixes are resolved autonomously without expanding the model.

## 7. Execution handoff

This plan is ready for implementation only after user confirmation. On
confirmation, begin at Task 0, maintain this document as the resumable state,
and stop again at Task 8B for fresh explicit runtime-mutation authorization.
