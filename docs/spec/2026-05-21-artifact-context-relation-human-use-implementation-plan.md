# Artifact Context Relation Human-Use Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Runtime behavior changes must follow `superpowers:test-driven-development`: write the focused failing test, verify the failure, implement the smallest direct change, and rerun the focused test before moving on.

**Goal:** Add simple artifact discovery, a compact human entry surface, and permission-filtered artifact backlinks without adding new material or relation objects.

**Architecture:** Follow the existing black-box env.tool runtime. `artifact.list` is an action on the existing `artifact` tool. `context.summarize` remains a compact read-only orientation surface. `relation_summary` is derived at read time from existing artifacts, tracks, requests, comments, and track updates through host-owned repo/domain access.

**Tech Stack:** Python runtime tools, JSON-backed repos, dataclass `ToolDefinition`/`ActionDefinition`, broker-routed `env.tool`, JSON-compatible schemas, `unittest`/`pytest`, BuddySwitch manifest/skill/projection contract tests.

---

## Source Inputs

Read before implementation:

- `tmp/2026-05-21-tool-layer-human-use-handoff.md`
- `docs/spec/2026-05-21-artifact-context-relation-human-use-scope.md`
- `docs/spec/2026-05-21-artifact-context-relation-human-use-test-plan.md`
- `docs/spec/2026-05-21-request-comment-closure-scope.md`
- `docs/spec/2026-05-21-request-comment-closure-test-plan.md`
- `scripts/env/tool_runtime/definition.py`
- `scripts/env/tool_runtime/context.py`
- `scripts/env/tool_runtime/registry.py`
- `scripts/env/tool_runtime/results.py`
- `scripts/env/tools/artifact/tool.py`
- `scripts/env/tools/artifact/_impl.py`
- `scripts/env/domain/artifact_visibility.py`
- `scripts/env/domain/source_refs.py`
- `scripts/env/tools/context/tool.py`
- `scripts/env/tools/context/_impl.py`
- `scripts/env/repos/artifacts.py`
- `scripts/env/repos/comments.py`
- `scripts/env/repos/requests.py`
- `scripts/env/repos/tracks.py`
- `scripts/runtime_store/projections.py`
- `buddyswitch/skills/shared/artifact-tool/SKILL.md`
- `tests/test_artifact_env_tool.py`
- `tests/test_host_decision_surface_product_mode.py`
- `tests/test_env_tool_semantic_contract.py`
- `tests/test_env_tool_schema_contract.py`
- `tests/test_env_tool_response_contract.py`
- `tests/test_parallel_contracts.py`
- `tests/test_repo_consistency.py`

## Forward Rules

- Do not edit `main`; all work stays in `.worktrees/clean-runtime-env`.
- Do not edit `buddyswitch/objects/**` or `buddyswitch/local/buddybox/**` directly.
- Do not create `artifact.index`, `artifact.search`, `relation`, `insight`, `experiment`,
  `roadmap`, `review`, or `approval` env tools.
- Do not add a relation object directory or relation JSON files.
- Do not add full body search, filter DSLs, saved views, or graph traversal.
- Do not make `source_refs` a required reading path.
- Do not make `context.summarize` include full catalog, schemas, artifact bodies, or full comment
  threads.
- Do not add compatibility adapters or registry business special cases.

## Target Files

Create:

```text
scripts/env/domain/artifact_relations.py
```

Modify:

```text
scripts/env/tool_runtime/context.py
scripts/env/domain/artifact_visibility.py
scripts/env/tools/artifact/tool.py
scripts/env/tools/artifact/_impl.py
scripts/env/tools/context/tool.py
scripts/env/tools/context/_impl.py
buddyswitch/skills/shared/artifact-tool/SKILL.md
tests/test_artifact_env_tool.py
tests/test_host_decision_surface_product_mode.py
tests/test_env_tool_semantic_contract.py
tests/test_env_tool_schema_contract.py
tests/test_env_tool_response_contract.py
tests/test_parallel_contracts.py
tests/test_repo_consistency.py
```

Do not modify workspace projection to include permission-sensitive backlinks. `scripts/runtime_store/projections.py`
has no active-buddy scope, so projection tests should guard that no full relation summary is added there. Existing
comment counts in projection remain enough for this task.

## Data Contracts

### `artifact.list` Input

```json
{
  "track_id": "track-example",
  "created_by": "pm",
  "template": "brief",
  "status": "published",
  "q": "signup",
  "limit": 20
}
```

All fields are optional. `limit` defaults to 20.

Allowed enum values:

```text
template: brief, proposal, design, decision, proof, note
status: draft, published, archived
```

### `artifact.list` Success Extra Fields

```json
{
  "artifacts": [],
  "count": 0,
  "filters": {
    "track_id": null,
    "created_by": null,
    "template": null,
    "status": null,
    "q": null,
    "limit": 20
  }
}
```

### Summary Row

```json
{
  "artifact_id": "art-example-r1",
  "title": "Example",
  "summary": "Short summary.",
  "template": "brief",
  "status": "published",
  "currentness": "current",
  "relation": "track_material",
  "created_by": "pm",
  "authors": ["pm"],
  "published_to_track": "track-example",
  "revision": 1,
  "supersedes_artifact_id": null,
  "source_refs_summary": [{"type": "note", "label": "seed"}],
  "open_comment_count": 0,
  "resolved_comment_count": 0,
  "incoming_source_ref_count": 0,
  "target_request_count": 0,
  "result_request_count": 0,
  "track_update_ref_count": 0,
  "comment_count": 0,
  "updated_at": "2026-05-21T00:00:00+08:00"
}
```

Do not include `body`.

### `artifact.get` Relation Summary

Add this field inside the returned `artifact` row:

```json
{
  "relation_summary": {
    "publication": {
      "track_id": "track-example",
      "relation": "track_material",
      "currentness": "current"
    },
    "lineage": {
      "supersedes_artifact_id": null,
      "superseded_by_artifact_ids": ["art-example-r2"]
    },
    "incoming_refs": {
      "source_ref_by_artifacts": [],
      "target_ref_by_requests": [],
      "result_ref_by_requests": [],
      "track_update_refs": [],
      "comment_ids": []
    }
  }
}
```

## Task 0: Baseline Guard

**Files:** none

- [ ] **Step 1: Confirm worktree**

Run:

```bash
pwd
git status --short
```

Expected:

- `pwd` is `/Users/chen/Dev/buddyswitch/.worktrees/clean-runtime-env`;
- existing dirty request/comment files may be present;
- do not switch to or edit `main`.

- [ ] **Step 2: Run current request/comment baseline**

Run:

```bash
python3 -m pytest \
  tests/test_request_env_tool.py \
  tests/test_comment_env_tool.py \
  tests/test_env_tool_semantic_contract.py \
  tests/test_env_tool_schema_contract.py \
  tests/test_env_tool_response_contract.py \
  -q
```

Expected before this task:

- request/comment focused tests pass;
- failures caused by missing `artifact.list` should not appear until new tests are added.

## Task 1: Write Failing Contract Tests

**Files:**

- Modify: `tests/test_env_tool_semantic_contract.py`
- Modify: `tests/test_env_tool_schema_contract.py`
- Modify: `tests/test_env_tool_response_contract.py`
- Modify: `tests/test_repo_consistency.py`

- [ ] **Step 1: Update semantic action expectations**

In `tests/test_env_tool_semantic_contract.py`:

- change artifact expected actions from:

```python
"artifact": {"get", "create_revision", "update_metadata"},
```

to:

```python
"artifact": {"list", "get", "create_revision", "update_metadata"},
```

- add an adjacent-boundary check for `artifact.list` containing snippets:

```python
("artifact", "list", ("summary", "filter", "get")),
```

- add forbidden tool/action assertions that shipped tools do not include:

```text
artifact_index
artifact_search
relation
insight
experiment
roadmap
review
approval
```

- [ ] **Step 2: Add schema assertions**

In `tests/test_env_tool_schema_contract.py`, load:

```python
artifact_list = catalog.get_action_definition("artifact", "list").input_schema
```

Assert:

- `required == []`;
- properties are exactly `track_id`, `created_by`, `template`, `status`, `q`, `limit`;
- `template.enum == ["brief", "proposal", "design", "decision", "proof", "note"]`;
- `status.enum == ["draft", "published", "archived"]`;
- `limit.type == "integer"` and `limit.minimum == 1`.

- [ ] **Step 3: Extend compact response contract**

In `tests/test_env_tool_response_contract.py`, update `test_context_get_and_summarize_catalog_scope` so `summary` must:

- include `candidate_artifacts`;
- include `open_comment_threads`;
- include `recent_updates`;
- not include `tool_catalog`;
- not include `operation_semantics`;
- not include JSON Schema keys such as `properties`, `required`, or `additionalProperties`;
- not include any artifact `body`.

- [ ] **Step 4: Add forbidden surface scan**

In `tests/test_repo_consistency.py`, add checks that no shipped tool package or registry expected
set contains forbidden tool names:

```text
artifact_index, artifact_search, relation, insight, experiment, roadmap, review, approval
```

Do not fail on those words inside `docs/spec` or skill body prose; fail only on shipped runtime tool
packages, registry contracts, or object directories.

- [ ] **Step 5: Verify failures**

Run:

```bash
python3 -m pytest \
  tests/test_env_tool_semantic_contract.py \
  tests/test_env_tool_schema_contract.py \
  tests/test_env_tool_response_contract.py \
  tests/test_repo_consistency.py \
  -q
```

Expected:

- failures for missing `artifact.list`;
- failures for missing compact context fields;
- no unrelated request/comment regression should be introduced by test edits.

## Task 2: Write Failing `artifact.list` Functional Tests

**Files:**

- Modify: `tests/test_artifact_env_tool.py`

- [ ] **Step 1: Add owner draft discovery test**

Add `test_list_returns_owner_draft_summaries_without_body`.

Seed:

- PM draft `art-list-pm-brief`;
- PM draft `art-list-pm-note`;
- Dev draft `art-list-dev-private`.

Dispatch as PM:

```python
artifact.list {}
```

Assert:

- PM rows include the two PM drafts;
- PM rows do not include `art-list-dev-private`;
- each returned row lacks `body`;
- PM draft rows have `status=draft`, `currentness=draft`, `relation=owner`;
- response is read-only: `state_changed=False`, `durability="none"`.

- [ ] **Step 2: Add published material/proof/history test**

Add `test_list_returns_published_material_proof_and_history_summaries`.

Seed:

- track `track-art-list-published`;
- publish `art-list-brief-r1` as material;
- publish `art-list-proof-r1` as close proof;
- create `art-list-brief-r2` superseding r1 and publish r2 as current material.

Dispatch:

```python
artifact.list {"track_id": "track-art-list-published"}
```

Assert:

- r2 row has `relation=track_material`, `currentness=current`;
- proof row has `relation=track_proof`, `currentness=proof`;
- r1 row has `relation=track_history`, `currentness=superseded` if the existing track history read boundary allows it;
- no row has `body`.

- [ ] **Step 3: Add simple filter test**

Add `test_list_filters_are_simple_and_title_summary_only`.

Seed:

- title/summary match rows;
- one artifact whose `body` contains the query but title/summary do not.

Assert:

- `q` matches title/summary only;
- `created_by`, `template`, `status`, and `track_id` filters narrow rows;
- `limit=1` returns one row;
- default limit does not exceed 20.

- [ ] **Step 4: Add invalid filter test**

Add `test_list_rejects_invalid_filters_without_state_change`.

Cases:

```python
{"unsupported": "x"}
{"template": "prd"}
{"status": "live"}
{"created_by": "unknown"}
{"q": 123}
{"limit": 0}
{"limit": "1"}
{"track_id": "track-missing"}
```

Assert each rejection has:

- `ok=false`;
- `state_changed=false`;
- `durability=none`;
- meaningful `permission_boundary`, `why_blocked`, and `correctable_fields` where applicable.

- [ ] **Step 5: Verify failures**

Run:

```bash
python3 -m pytest tests/test_artifact_env_tool.py -q
```

Expected:

- failures for unsupported `artifact.list`.

## Task 3: Write Failing Context And Relation Tests

**Files:**

- Modify: `tests/test_host_decision_surface_product_mode.py`
- Modify: `tests/test_artifact_env_tool.py`
- Modify: `tests/test_parallel_contracts.py`

- [ ] **Step 1: Add context entry surface test**

In `tests/test_host_decision_surface_product_mode.py`, extend or add a test that seeds:

- active track;
- current artifact;
- proof artifact;
- visible request;
- unresolved artifact comment;
- track update referencing the artifact.

Assert `context.summarize {}` includes:

- `candidate_artifacts`;
- `candidate_requests`;
- `open_comment_threads`;
- `recent_updates`;
- `current_context_summary.artifacts`;
- `current_context_summary.open_comment_threads`;
- `current_context_summary.recent_updates`;
- no artifact body or full comment content.

- [ ] **Step 2: Add context track filter test**

Seed two tracks with separate artifacts, requests, comments, and updates.

Dispatch:

```python
context.summarize {"track_id": "track-a"}
```

Assert all candidate arrays only refer to `track-a`.

- [ ] **Step 3: Add relation summary publication and lineage test**

In `tests/test_artifact_env_tool.py`, add `test_get_relation_summary_includes_publication_and_lineage`.

Seed r1/r2 revisions and publish through track tools.

Assert `artifact.get` for r1 includes:

- `relation_summary.publication`;
- `relation_summary.lineage.supersedes_artifact_id`;
- visible `superseded_by_artifact_ids`;
- no unreadable private draft superseded-by ids.

- [ ] **Step 4: Add relation incoming refs test**

Add `test_get_relation_summary_includes_permission_filtered_incoming_refs`.

Seed:

- visible source-ref artifact;
- private source-ref artifact by another buddy;
- request target ref;
- request result ref;
- track update ref;
- artifact and artifact_section comments.

Assert:

- visible source-ref artifact appears;
- private source-ref artifact is omitted;
- target/result requests appear in separate buckets;
- update ref appears with track/update metadata only;
- comment ids appear without comment content.

- [ ] **Step 5: Add projection guard test**

In `tests/test_parallel_contracts.py`, assert workspace projection does not expose full
`relation_summary` because it has no active-buddy permission scope.

Existing comment counts on artifact projection should remain intact.

- [ ] **Step 6: Verify failures**

Run:

```bash
python3 -m pytest \
  tests/test_artifact_env_tool.py \
  tests/test_host_decision_surface_product_mode.py \
  tests/test_parallel_contracts.py \
  -q
```

Expected:

- failures for missing `artifact.list`, missing context arrays, and missing relation summary.

## Task 4: Add Read-Only Artifact Relation Domain

**Files:**

- Create: `scripts/env/domain/artifact_relations.py`
- Modify: `scripts/env/tool_runtime/context.py`

- [ ] **Step 1: Create `artifact_relations.py`**

Implement pure read helpers that scan existing repos and return permission-filtered lightweight
rows.

Required functions:

```python
def comment_counts_for_artifact(artifact_id: str) -> dict[str, int]:
    ...

def relation_counts_for_artifact(*, artifact_id: str, active_buddy: str) -> dict[str, int]:
    ...

def relation_summary_for_artifact(*, artifact: dict[str, Any], active_buddy: str) -> dict[str, Any]:
    ...
```

Rules:

- use `artifact_visibility.artifact_read_decision` before exposing artifact refs;
- use request domain visibility before exposing request refs;
- omit archived track update refs;
- include artifact and artifact_section comment ids for readable artifact targets;
- return lightweight rows only;
- do not mutate repos;
- do not import tool packages.

- [ ] **Step 2: Register domain access**

In `scripts/env/tool_runtime/context.py`:

- import `env.domain.artifact_relations as _artifact_relations_domain`;
- add `artifact_relations` to `DomainAccess`;
- update `RuntimeObjectAccess.runtime_sources()["artifacts"]` from `artifact.get` to
  `artifact.list / artifact.get`.

- [ ] **Step 3: Run focused relation helper import check**

Run:

```bash
python3 -m pytest tests/test_env_tool_response_contract.py::EnvToolResponseContractTests::test_context_get_and_summarize_catalog_scope -q
```

Expected:

- may still fail for missing context fields, but must not fail due to import errors.

## Task 5: Implement Summary-Only Artifact Rows

**Files:**

- Modify: `scripts/env/domain/artifact_visibility.py`

- [ ] **Step 1: Add summary-only row helper**

Add a helper separate from existing `artifact_summary_row` because `artifact_summary_row` currently
includes `body` for `artifact.get`.

Suggested signature:

```python
def artifact_list_row(
    artifact: dict[str, Any],
    active_buddy: str,
    *,
    comment_counts: dict[str, int] | None = None,
    relation_counts: dict[str, int] | None = None,
) -> dict[str, Any]:
    ...
```

Required output:

- all fields from the scope summary row;
- `source_refs_summary` from `source_refs.source_ref_summary`;
- comment counts defaulting to 0;
- relation counts defaulting to 0;
- no `body`.

- [ ] **Step 2: Preserve full body get behavior**

Do not remove `body` from `artifact_summary_row`; `artifact.get` still needs full body.

- [ ] **Step 3: Run artifact tests**

Run:

```bash
python3 -m pytest tests/test_artifact_env_tool.py -q
```

Expected:

- still fails for missing `artifact.list` action or relation summary, but existing artifact get/create/update tests should not newly fail because of helper extraction.

## Task 6: Implement `artifact.list`

**Files:**

- Modify: `scripts/env/tools/artifact/tool.py`
- Modify: `scripts/env/tools/artifact/_impl.py`
- Modify: `buddyswitch/skills/shared/artifact-tool/SKILL.md`

- [ ] **Step 1: Add `ActionDefinition(name="list")`**

In `scripts/env/tools/artifact/tool.py`, add a read action before `get`.

Input schema:

- `additionalProperties=False`;
- `required=[]`;
- properties `track_id`, `created_by`, `template`, `status`, `q`, `limit`;
- `template` enum from current artifact template values;
- `status` enum from current artifact status values;
- `limit` integer minimum 1.

Semantic text must clearly say:

- use for summary discovery;
- use `artifact.get` for full body;
- no full-text body search.

- [ ] **Step 2: Add payload normalization**

In `scripts/env/tools/artifact/_impl.py`, add:

```python
def _normalize_list_filters(args: dict[str, Any], active_buddy: str, context: ArtifactServiceContext) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    ...
```

Return either normalized filters or a canonical rejection.

Validate:

- unsupported fields through existing `_require_allowed_fields`;
- `track_id` non-empty and readable/non-archived if provided;
- `created_by` one of manifest buddy ids;
- `template` in `context.repos.artifact.VALID_ARTIFACT_TEMPLATES`;
- `status` in `context.repos.artifact.VALID_ARTIFACT_STATUS`;
- `q` string if provided;
- `limit` positive integer, default 20.

- [ ] **Step 3: Add list handler**

Implement:

```python
def list_artifacts_for_active_buddy(*, args: dict[str, Any], context: ArtifactServiceContext) -> dict[str, Any]:
    ...
```

Algorithm:

1. normalize filters;
2. iterate `context.repos.artifact.list_artifacts()`;
3. call `artifact_read_decision` and skip unreadable artifacts;
4. apply simple filters;
5. build summary-only rows with `artifact_list_row`;
6. sort deterministically by `updated_at` then `artifact_id` descending;
7. apply `limit`;
8. return `tool_results.success` with `artifacts`, `count`, and `filters`.

- [ ] **Step 4: Register handler**

Add:

```python
"list": list_artifacts_for_active_buddy,
```

to `_ACTION_HANDLERS`.

- [ ] **Step 5: Update shared artifact skill**

In `buddyswitch/skills/shared/artifact-tool/SKILL.md`:

- mention `list` as the summary discovery action;
- keep `get` as full body read;
- keep runtime response as authoritative.

- [ ] **Step 6: Verify focused artifact list tests**

Run:

```bash
python3 -m pytest \
  tests/test_artifact_env_tool.py \
  tests/test_env_tool_semantic_contract.py \
  tests/test_env_tool_schema_contract.py \
  -q
```

Expected:

- `artifact.list` tests pass;
- relation/context tests may still fail until later tasks.

## Task 7: Implement `context.summarize` Human Entry Surface

**Files:**

- Modify: `scripts/env/tools/context/tool.py`
- Modify: `scripts/env/tools/context/_impl.py`

- [ ] **Step 1: Update context definition text**

In `scripts/env/tools/context/tool.py`, update `context.summarize` `returns`, `use_when`, and
description so they mention:

- candidate artifacts;
- candidate requests;
- open comment threads;
- recent updates;
- compact orientation only.

No schema fields need to be added; existing `track_id`, `task_id`, and `limit` remain enough.

- [ ] **Step 2: Add candidate artifact rows**

In `scripts/env/tools/context/_impl.py`, replace the current material-only internal summary with
summary-only artifact rows:

- scan visible artifacts through the same visibility rules as `artifact.list`;
- if `track_id` is provided, restrict to that track;
- include own drafts when no `track_id` filter is provided;
- never include `body`;
- respect `limit`.

Do not import `env.tools.artifact`; use domain/repo helpers through `ToolContext`.

- [ ] **Step 3: Add open comment thread rows**

Add a helper:

```python
def _open_comment_thread_rows(... ) -> list[dict[str, Any]]:
    ...
```

Rules:

- consider comments on visible tracks and candidate artifacts;
- group by `thread_id`;
- include only threads with at least one `status=open` comment;
- row fields: `thread_id`, `target_type`, `target_id`, `latest_comment_id`, `latest_by_buddy`,
  `open_comment_count`, `updated_at`;
- no `content`.

- [ ] **Step 4: Add recent update rows**

Add a helper:

```python
def _recent_update_rows(... ) -> list[dict[str, Any]]:
    ...
```

Rules:

- scan visible tracks only;
- sort by `created_at` descending then update id;
- row fields: `track_id`, `update_id`, `kind`, `summary`, `by_buddy`, `ref_count`, `created_at`;
- respect `limit`.

- [ ] **Step 5: Update summary payload**

`summarize_context` must include:

```python
"candidate_artifacts": sections["candidate_artifacts"],
"open_comment_threads": sections["open_comment_threads"],
"recent_updates": sections["recent_updates"],
```

Update `current_context_summary` and `decision_surface.context_readiness` with artifact/comment/update
signals.

- [ ] **Step 6: Update context source descriptors**

In `context_sources_desc()`:

- set artifact source of truth to `artifact.list / artifact.get`;
- keep request source as `request.list / request.get`;
- keep comments as `comment.list`.

- [ ] **Step 7: Verify focused context tests**

Run:

```bash
python3 -m pytest \
  tests/test_host_decision_surface_product_mode.py \
  tests/test_env_tool_response_contract.py \
  -q
```

Expected:

- context compactness and human entry tests pass;
- relation summary tests may still fail.

## Task 8: Add `relation_summary` To `artifact.get`

**Files:**

- Modify: `scripts/env/tools/artifact/_impl.py`
- Modify: `scripts/env/domain/artifact_relations.py`

- [ ] **Step 1: Extend get response row**

In `get_artifact_for_active_buddy`, after read visibility passes:

- build existing full artifact row;
- attach:

```python
row["relation_summary"] = context.rules.artifact_relations.relation_summary_for_artifact(
    artifact=artifact,
    active_buddy=active_buddy,
)
```

- [ ] **Step 2: Ensure relation summary respects read boundaries**

In `artifact_relations.py`:

- when scanning artifacts, include only rows passing `artifact_read_decision(...).allowed`;
- when scanning requests, include only rows passing `request.ensure_visible`;
- when scanning tracks, skip archived tracks;
- when scanning comments, include comments only when the artifact itself is readable.

- [ ] **Step 3: Keep rows lightweight**

Returned incoming rows must not include:

- artifact `body`;
- comment `content`;
- private buddybox content;
- full request `summary` unless tests explicitly require it.

- [ ] **Step 4: Verify relation tests**

Run:

```bash
python3 -m pytest tests/test_artifact_env_tool.py -q
```

Expected:

- artifact relation tests pass;
- all previous artifact tests remain green.

## Task 9: Projection And Static Guards

**Files:**

- Modify: `tests/test_parallel_contracts.py`
- Modify: `tests/test_repo_consistency.py`

- [ ] **Step 1: Keep projection active-buddy neutral**

Ensure tests assert:

- workspace projection still has top-level artifacts and comment counts;
- workspace projection does not expose full `relation_summary`;
- no permission-sensitive backlink arrays are added to projection.

Do not modify `framework/contracts/workspace-projection.json` unless an existing test requires a
contract key-order update for a deliberately added lightweight count. The preferred path is no
projection shape change.

- [ ] **Step 2: Static forbidden surface scan**

Ensure `tests/test_repo_consistency.py` rejects shipped runtime tool packages or object dirs for:

```text
relation
artifact_index
artifact_search
insight
experiment
roadmap
review
approval
```

Allow these words in docs/spec and skill prose.

- [ ] **Step 3: Verify guards**

Run:

```bash
python3 -m pytest \
  tests/test_parallel_contracts.py \
  tests/test_repo_consistency.py \
  -q
```

Expected:

- guards pass;
- no projection relation leak is introduced.

## Task 10: Final Focused Verification

**Files:** no edits unless verification finds failures.

- [ ] **Step 1: Run artifact/context/relation loop**

Run:

```bash
python3 -m pytest \
  tests/test_artifact_env_tool.py \
  tests/test_host_decision_surface_product_mode.py \
  tests/test_env_tool_semantic_contract.py \
  tests/test_env_tool_schema_contract.py \
  tests/test_env_tool_response_contract.py \
  tests/test_repo_consistency.py \
  -q
```

Expected:

- all pass.

- [ ] **Step 2: Run request/comment baseline**

Run:

```bash
python3 -m pytest \
  tests/test_request_env_tool.py \
  tests/test_comment_env_tool.py \
  tests/test_env_layer_end_to_end.py \
  -q
```

Expected:

- all pass.

- [ ] **Step 3: Run projection/runtime skill checks**

Run:

```bash
python3 -m pytest \
  tests/test_parallel_contracts.py \
  tests/test_black_box_tool_runtime.py \
  tests/test_runtime_skills.py \
  -q
```

Expected:

- all pass.

- [ ] **Step 4: Run broader relevant suite**

Run:

```bash
python3 -m pytest \
  tests/test_artifact_env_tool.py \
  tests/test_track_env_tool.py \
  tests/test_comment_env_tool.py \
  tests/test_request_env_tool.py \
  tests/test_host_decision_surface_product_mode.py \
  tests/test_env_tool_semantic_contract.py \
  tests/test_env_tool_schema_contract.py \
  tests/test_env_tool_response_contract.py \
  tests/test_parallel_contracts.py \
  tests/test_black_box_tool_runtime.py \
  tests/test_repo_consistency.py \
  -q
```

Expected:

- all pass.

## Completion Checklist

- `artifact.list` exists and is discoverable.
- `artifact.list` filters are flat and simple.
- `artifact.list` never returns `body`.
- `context.summarize` is a compact human entry surface.
- `artifact.get` returns permission-filtered `relation_summary`.
- No new material objects or relation objects exist.
- Request/comment baseline remains green.
- Final response states verification commands and any remaining risk.

