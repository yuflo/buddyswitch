# Buddy Run Persist Rebuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild BuddySwitch persistence so one persist commit represents one active buddy run process, not one native SKILL execution result.

**Architecture:** Keep codex-cli native SKILL materialization and execution intact, but remove SKILL ownership from durable state. `prepare` reserves an active-buddy run; codex-cli may use one or many native skills inside that run; `persist` commits a buddy-level process result containing artifacts, state effects, handoff, and contributor audit metadata.

**Tech Stack:** Python runtime scripts, TOML manifest parsing, JSON runtime state, Markdown runtime instructions, `unittest`/`pytest`.

---

## Working Directory

Run all implementation and verification from:

```bash
cd /Users/chen/Dev/buddyswitch/.worktrees/dev0210
```

Do not edit `/Users/chen/Dev/buddyswitch` main checkout for this task.

## Product Goals

The implementation must serve these goals:

- Persist at buddy level: persistence is one active buddy run process commit.
- Persist for buddy collaboration: persisted state must help the next buddy understand what happened, what artifacts to use, and what to do next.
- Project iteration at buddy level: track is the iteration spine, buddy runs are process nodes, artifacts are handoff-ready deliverables, and handoff moves work between buddies.

## Non-Negotiable Constraints

- Do not affect codex-cli native SKILL execution.
- Keep active buddy skill materialization into `.agents/skills/<skill-id>`.
- Keep `buddy.skills` as the list of native skills exposed to codex-cli.
- Remove `persist --skill-id`; do not keep an alias or compatibility path.
- Remove product contract `persist-skill-result`; replace it with buddy-run persist.
- Remove SKILL-level artifact ownership and SKILL-level output slot/schema persistence semantics.
- Do not create wrappers that translate old skill result payloads into buddy run commits.
- Do not leave tests whose purpose is to prove legacy skill-level persist behavior.
- Record SKILL use only as optional contributor audit metadata.
- Do not introduce a workflow engine, transaction system, or multi-entry persist protocol.

## Confirmed Current State

- `scripts/runtime_skills.py` materializes the active buddy's manifest skills into runtime `.agents/skills/<skill-id>`. This is the codex-cli native SKILL execution boundary and must remain.
- `tools/launcher/assets/buddies/*/AGENTS.md` currently instructs each buddy to persist with `scripts/turn_runtime.py persist --skill-id`.
- `scripts/turn_runtime.py` currently validates a selected `skill_id`, resolves selected skill persistence metadata, derives artifact slot from skill `output_slot`, and writes `skill_id` into receipt, artifact, and run audit.
- `scripts/env_manifest.py` currently requires each `[[skills]]` row to define `produces_artifact`, `output_slot`, and `output_schema`.
- `scripts/env_store.py` currently validates artifact objects with `skill_id` and `slot`.
- `framework/contracts/persist-skill-result.json` defines the current product persist contract.
- Existing tests assert skill-level persist identity across receipt, artifact, and run audit.

## Target Model

### Runtime Objects

- `Track`: project iteration spine shared by buddies.
- `Task`: the active buddy's work item on a track or standalone request.
- `BuddyRun`: one active buddy process execution reserved by `prepare` and committed by `persist`.
- `Artifact`: reusable deliverable created by a buddy run.
- `StateEffects`: explicit task/track mutations caused by the buddy run.
- `Handoff`: next buddy, reason, and context for collaboration.
- `Contributors`: optional audit list of native skills or sub-agents used inside the buddy run.

### Handoff Rule

`handoff` is a durable collaboration signal, not an implicit track mutation.

- Required fields when `handoff` is present: non-empty `next_buddy`, non-empty `reason`, non-empty `context`.
- `handoff.next_buddy` must reference a manifest buddy id.
- Empty handoff objects are rejected.
- If both `handoff.next_buddy` and `state_effects.track.next_buddy` are present, they must match.
- `handoff` is saved to receipt and run audit and may drive `next_state`.
- `handoff` does not update the track object unless an explicit `state_effects.track` mutation is also present.

### Run Lifecycle Rule

One prepared context reserves one buddy run id and can be committed exactly once.

- `persist_buddy_run()` must fail before writes if `run_envelope.run_id` is missing.
- `persist_buddy_run()` must fail before writes if `buddyswitch/content/runs/<run-id>.json` already exists.
- Successful persist changes the reserved run from `reserved` to committed by writing exactly one run audit and clearing the reservation.
- Reusing the same prepared context after a successful persist must fail without changing state.

### Artifact Kind Rule

Artifacts are keyed by buddy-level `kind`.

- Artifact kinds in one commit must be unique for the current task.
- Creating a new artifact for an existing task/kind creates the next revision and sets `supersedes_artifact_id`.
- Artifact identity is never derived from native skill id.

### Buddy Run Commit Shape

`scripts/turn_runtime.py persist` must accept this top-level result shape:

```json
{
  "execution_summary": "PM wrote the landing page PRD and created the delivery track.",
  "working_notes": [
    "The user asked for PRD plus track creation in one PM run."
  ],
  "artifacts": [
    {
      "kind": "prd",
      "title": "AI Schedule Tool Landing Page PRD",
      "summary": "Defines MVP scope, landing page sections, acceptance criteria, and next handoff.",
      "content": {
        "problem": "Busy professionals need schedule assistance without manual calendar cleanup.",
        "requirements": [],
        "acceptance_criteria": []
      }
    }
  ],
  "state_effects": {
    "track": {
      "action": "create",
      "track_id": "track-ai-schedule-landing-page",
      "title": "AI Schedule Tool Landing Page",
      "status": "active",
      "current_buddy": "pm",
      "next_buddy": "market",
      "summary": "Landing page iteration for an AI schedule tool."
    },
    "task": {
      "status": "done",
      "summary": "PM PRD complete; market/design follow-up needed."
    }
  },
  "handoff": {
    "next_buddy": "market",
    "reason": "Market should validate competitor landing page positioning before design.",
    "context": "Use the PRD artifact and track summary as source context."
  },
  "contributors": {
    "skills": ["write-prd", "track-manager"],
    "agents": []
  }
}
```

### Minimum Valid Commit

Runtime write safety requires:

- `execution_summary`: non-empty string.
- `working_notes`: optional list of strings.
- `artifacts`: optional list; each artifact must include non-empty `kind`, `title`, object `content`, and optional `summary`.
- `state_effects`: optional object with supported `track` and `task` effects.
- `handoff`: optional object with `next_buddy`, `reason`, and `context`.
- `contributors`: optional object; `skills` and `agents` are lists of strings and are audit-only.
- At least one durable collaboration signal: one artifact, one state effect, or one handoff.

## File Map

Modify:

- `buddyswitch/manifest.toml`
- `framework/contracts/persist-buddy-run.json`
- `framework/contracts/market.md`
- `framework/contracts/pm.md`
- `framework/contracts/design.md`
- `framework/contracts/dev.md`
- `framework/contracts/test.md`
- `framework/docs/architecture-overview.md`
- `framework/docs/browser-cockpit.md`
- `framework/docs/track-registry.md`
- `framework/docs/skill-runtime-shared-rules.md`
- `framework/docs/turn-runtime-spec.md`
- `framework/contracts/workspace-projection.json`
- `README.md`
- `scripts/artifact_selection.py`
- `scripts/env_manifest.py`
- `scripts/env_store.py`
- `scripts/runtime_kernel/persist.py`
- `scripts/runtime_store/projections.py`
- `scripts/skill_creator_importer.py`
- `scripts/turn_runtime.py`
- `tools/launcher/assets/buddies/market/AGENTS.md`
- `tools/launcher/assets/buddies/pm/AGENTS.md`
- `tools/launcher/assets/buddies/design/AGENTS.md`
- `tools/launcher/assets/buddies/dev/AGENTS.md`
- `tools/launcher/assets/buddies/test/AGENTS.md`
- `buddyswitch/skills/**/SKILL.md`
- `tests/test_env_manifest_v2.py`
- `tests/test_env_store_v2.py`
- `tests/test_turn_runtime.py`
- `tests/test_turn_integration.py`
- `tests/test_buddyswitch_launcher.py`
- `tests/test_debug_apis.py`
- `tests/test_cleanup_system.py`
- `tests/test_artifact_selection.py`
- `tests/test_console_app_contract.py`
- `tests/test_output_schema_boundaries.py`
- `tests/test_parallel_contracts.py`
- `tests/test_runtime_skills.py`
- `tests/test_repo_consistency.py`
- `tests/test_skill_creator_importer.py`

Delete:

- `framework/contracts/persist-skill-result.json`

Create:

- `framework/contracts/persist-buddy-run.json`

Preserve:

- `scripts/runtime_skills.py` behavior except tests may be updated to prove it still materializes native skills unchanged.
- `.agents/skills/<skill-id>` runtime shape.
- `buddy.skills` manifest membership.
- Product-mode prepare context and run reservation semantics.
- Existing task/track/artifact storage directories.

## Implementation Tasks

### Task 1: Replace The Product Persist Contract

**Files:**

- Delete: `framework/contracts/persist-skill-result.json`
- Create: `framework/contracts/persist-buddy-run.json`
- Modify: `framework/docs/turn-runtime-spec.md`
- Modify: `framework/docs/architecture-overview.md`
- Modify: `framework/docs/skill-runtime-shared-rules.md`

- [ ] **Step 1: Create the new contract file**

Create `framework/contracts/persist-buddy-run.json` with this exact contract baseline:

```json
{
  "contract_id": "persist-buddy-run",
  "contract_version": "2026-05-06",
  "request_boundary": "active_buddy + reserved run_id + current task/track context",
  "response_key_order": [
    "ok",
    "receipt",
    "refreshed_context"
  ],
  "commit_required_keys": [
    "execution_summary"
  ],
  "commit_optional_keys": [
    "working_notes",
    "artifacts",
    "state_effects",
    "handoff",
    "contributors"
  ],
  "receipt_required_keys": [
    "ok",
    "buddy_id",
    "task_id",
    "task_title",
    "artifact_ids",
    "run_id",
    "next_state",
    "receipt_paths",
    "related_run_ids"
  ],
  "receipt_optional_keys": [
    "track_id",
    "track_title",
    "track_action",
    "handoff",
    "warnings"
  ]
}
```

- [ ] **Step 2: Remove the old contract file**

Delete `framework/contracts/persist-skill-result.json`. Do not replace it with a redirect file.

- [ ] **Step 3: Update docs from skill-result to buddy-run**

Update `framework/docs/turn-runtime-spec.md`, `framework/docs/architecture-overview.md`, and `framework/docs/skill-runtime-shared-rules.md` to state:

```markdown
Persist commits one active buddy run result. Native skills may contribute to that result, but native skill ids do not own the persist boundary, artifact identity, receipt identity, or write permissions.
```

- [ ] **Step 4: Verify old product contract wording is gone**

Run:

```bash
rg -n "persist-skill-result|persist --skill-id|selected skill_id|same native skill_id|skill result" framework
```

Expected: no product contract references remain. Mentions inside historical whiteboard/spec files are acceptable only if explicitly labeled as retired.

### Task 2: Move Manifest Persistence Metadata From Skill Level To Buddy Level

**Files:**

- Modify: `buddyswitch/manifest.toml`
- Modify: `scripts/env_manifest.py`
- Modify: `tests/test_env_manifest_v2.py`
- Modify: `tests/test_skill_creator_importer.py`

- [ ] **Step 1: Rewrite manifest skill rows**

In `buddyswitch/manifest.toml`, each `[[skills]]` row must contain only:

```toml
[[skills]]
id = "write-prd"
path = "buddyswitch/skills/pm/write-prd"
```

Remove these fields from all skill rows:

```toml
produces_artifact = true
output_slot = "..."
output_schema = "..."
```

- [ ] **Step 2: Add buddy artifact kinds**

Add `artifact_kinds` to each `[[buddies]]` row:

```toml
artifact_kinds = ["prd", "pm-decision", "track-note"]
```

Use these initial values:

- market: `["market-scan", "pmf-report", "customer-discovery", "positioning-brief", "channel-plan", "launch-prep", "market-landing-page-brief"]`
- pm: `["prd", "pm-decision", "track-note"]`
- design: `["design-handoff", "prototype-brief"]`
- dev: `["implementation-report", "skill-import-report"]`
- test: `["smoke-test", "test-report"]`

- [ ] **Step 3: Simplify skill parsing**

In `scripts/env_manifest.py`, remove `_parse_skill_persistence()`. `load_manifest()` must stop requiring `produces_artifact`, `output_slot`, and `output_schema` from skill rows.

Keep validating:

- `schema_version`
- env id/label
- skill id/path
- duplicate skill ids
- buddy id/label/scope
- buddy skills reference declared skill ids
- buddy permissions
- buddy artifact kinds are non-empty strings matching safe id format

- [ ] **Step 4: Update skill importer behavior**

In `scripts/skill_creator_importer.py`, registering an imported skill must:

- create a `[[skills]]` entry with only `id` and `path`;
- add the skill id to the target buddy's `skills`;
- add only a caller-supplied buddy-level `artifact_kind` when explicitly requested;
- do not default artifact kind from `skill_id`;
- stop appending instructions that say `persist --skill-id`.

If the current importer API requires `output_schema`, replace it with an optional `artifact_kind` parameter. The imported native skill id can appear in `contributors.skills`, but it must not become an artifact kind unless the caller intentionally provides a buddy-level artifact kind.

- [ ] **Step 5: Verify manifest parser directly**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_manifest_v2.py tests/test_skill_creator_importer.py -q
```

Expected: tests pass and no test asserts skill persistence metadata.

### Task 3: Rebuild Artifact Storage Around Buddy Artifact Kind

**Files:**

- Modify: `scripts/env_store.py`
- Modify: `scripts/runtime_store/projections.py`
- Modify: `tests/test_env_store_v2.py`
- Modify: `tests/test_debug_apis.py`
- Modify: `tests/test_cleanup_system.py`

- [ ] **Step 1: Replace artifact `skill_id` and `slot` with `kind`**

Artifact objects must be written with:

```json
{
  "id": "art-task-id-prd",
  "title": "AI Schedule Tool Landing Page PRD",
  "task_id": "task-pm-ai-schedule-tool-landing-page",
  "buddy": "pm",
  "kind": "prd",
  "revision": 1,
  "supersedes_artifact_id": null,
  "is_current": true,
  "source_run_id": "run-abc123",
  "summary": "Defines the landing page MVP PRD.",
  "content": {},
  "created_at": "...",
  "updated_at": "..."
}
```

Remove canonical artifact fields:

- `skill_id`
- `slot`

- [ ] **Step 2: Rename task artifact slot semantics to artifact kinds**

Keep the existing task field name `artifact_slots` only if renaming it would create broad unrelated churn. Its keys must now be artifact kinds, not skill output slots.

If the implementation touches all slot helpers anyway, rename helper names from slot language to kind language:

- `_artifact_slot_name()` -> `_artifact_kind_name()`
- `_task_slot_state()` -> `_task_kind_state()`

Do not keep a skill-derived fallback.

- [ ] **Step 3: Change artifact creation API**

Replace `create_artifact(..., skill_id, slot, ...)` with:

```python
create_artifact(
    artifact_id: str | None,
    title: str,
    buddy: str,
    kind: str,
    task_id: str,
    source_run_id: str,
    summary: str = "",
    content: dict[str, Any] | None = None,
    auto_register: bool = True,
) -> dict[str, Any]
```

Validation must require `kind` as a non-empty safe id and must not read `skill_id`.

- [ ] **Step 4: Update projections and debug views**

Any projected artifact summaries must show:

- `id`
- `title`
- `buddy`
- `kind`
- `task_id`
- `source_run_id`
- `summary`

They must not show `skill_id` as the canonical identity.

- [ ] **Step 5: Verify storage tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_store_v2.py tests/test_debug_apis.py tests/test_cleanup_system.py -q
```

Expected: tests pass with artifact kind semantics.

### Task 4: Replace Skill-Level Persist With Buddy Run Commit

**Files:**

- Modify: `scripts/turn_runtime.py`
- Modify: `scripts/runtime_kernel/persist.py`
- Modify: `tests/test_turn_runtime.py`
- Modify: `tests/test_turn_integration.py`

- [ ] **Step 1: Rename public runtime function**

Replace:

```python
persist_skill_result(context, *, skill_id, result, manifest_path=DEFAULT_MANIFEST)
```

with:

```python
persist_buddy_run(context, *, result, manifest_path=DEFAULT_MANIFEST)
```

The function must derive `active_buddy`, `current_task_id`, `current_track_id`, and reserved `run_id` only from the prepared context.

- [ ] **Step 2: Remove CLI `--skill-id`**

Update `scripts/turn_runtime.py persist` parser to accept only:

```bash
scripts/turn_runtime.py persist --context <context.json> --result <result.json>
```

Remove `_derive_cli_persist_skill_id()`.

- [ ] **Step 3: Validate buddy run commit shape**

Replace `_validate_minimum_persist_result()` with `_validate_buddy_run_commit()`:

Rules:

- result is an object;
- `execution_summary` is a non-empty string;
- `working_notes`, if present, is a list of strings;
- `artifacts`, if present, is a list of objects;
- each artifact has non-empty `kind`, non-empty `title`, object `content`, and optional string `summary`;
- each artifact kind belongs to `active_buddy.artifact_kinds`;
- `state_effects`, if present, is an object;
- `handoff`, if present, is an object;
- `contributors`, if present, is an object with optional `skills` and `agents` string lists;
- at least one of `artifacts`, `state_effects`, or `handoff` is present and non-empty.
- `run_envelope.run_id` exists, has a matching reservation, and has not already been committed to `buddyswitch/content/runs/<run-id>.json`.
- artifact kinds are unique within a single commit.
- if `handoff` is present, it has non-empty `next_buddy`, `reason`, and `context`.
- `handoff.next_buddy` references a manifest buddy id.
- if `handoff.next_buddy` and `state_effects.track.next_buddy` are both present, they match.

- [ ] **Step 4: Replace track effect shape**

Retire `state_effects.track_operation`.

Use:

```json
"state_effects": {
  "track": {
    "action": "create",
    "track_id": "track-ai-schedule-landing-page",
    "title": "AI Schedule Tool Landing Page",
    "status": "active",
    "current_buddy": "pm",
    "next_buddy": "market",
    "summary": "Landing page iteration for an AI schedule tool."
  }
}
```

Track effect validation:

- action is `create`, `update`, `advance`, or `archive`;
- requested action is allowed by the active buddy permissions;
- buddy ids in `current_buddy` and `next_buddy` exist;
- status is valid;
- non-create actions require an existing track id;
- explicit current track binding cannot be changed to a different track;
- failures happen before writes.

- [ ] **Step 5: Add task effect shape**

Support:

```json
"state_effects": {
  "task": {
    "status": "done",
    "summary": "PM PRD complete; market research is next."
  }
}
```

Task effect validation:

- status is one of existing task statuses;
- summary, if present, is a string;
- effect applies only to the prepared current task.

- [ ] **Step 6: Persist all artifacts in one buddy run commit**

`persist_buddy_run()` must create zero or more artifacts from `result["artifacts"]`.

For each artifact:

- derive artifact id from `task_id + artifact.kind`;
- reject duplicate artifact kinds inside the same commit before any writes;
- create artifact with `buddy=active_buddy`;
- set `source_run_id=reserved_run_id`;
- attach it to the current task under the artifact kind.
- if an artifact already exists for the current task/kind, create the next revision and set `supersedes_artifact_id`.

- [ ] **Step 7: Save buddy run audit**

Run audit JSON in `buddyswitch/content/runs/<run-id>.json` must include:

```json
{
  "run_id": "run-...",
  "buddy_id": "pm",
  "task_id": "task-...",
  "track_id": "track-...",
  "artifact_ids": ["art-..."],
  "execution_summary": "...",
  "working_notes": [],
  "state_effects": {},
  "handoff": {},
  "contributors": {
    "skills": ["write-prd", "track-manager"],
    "agents": []
  },
  "writes": []
}
```

Do not write `skill_id` into the run audit.

- [ ] **Step 8: Build buddy-level receipt**

Receipt must include:

- `ok`
- `buddy_id`
- `task_id`
- `task_title`
- `artifact_ids`
- `run_id`
- `next_state`
- `receipt_paths`
- `related_run_ids`
- optional `track_id`
- optional `track_title`
- optional `track_action`
- optional `handoff`

Receipt must not include `skill_id`.

`handoff` in receipt must be the validated handoff object. If the run is track-bound, receipt must include `track_id` whenever the prepared context or a track effect resolves one.

- [ ] **Step 9: Verify turn runtime tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_turn_runtime.py tests/test_turn_integration.py -q
```

Expected: tests pass and no test calls `persist` with `skill_id`.

### Task 5: Update Buddy Instructions And Native Skill Instructions

**Files:**

- Modify: `tools/launcher/assets/buddies/market/AGENTS.md`
- Modify: `tools/launcher/assets/buddies/pm/AGENTS.md`
- Modify: `tools/launcher/assets/buddies/design/AGENTS.md`
- Modify: `tools/launcher/assets/buddies/dev/AGENTS.md`
- Modify: `tools/launcher/assets/buddies/test/AGENTS.md`
- Modify: `buddyswitch/skills/**/SKILL.md`
- Modify: `framework/contracts/market.md`
- Modify: `framework/contracts/pm.md`
- Modify: `framework/contracts/design.md`
- Modify: `framework/contracts/dev.md`
- Modify: `framework/contracts/test.md`

- [ ] **Step 1: Rewrite buddy canonical loop**

Each buddy `AGENTS.md` canonical loop must say:

```markdown
1. Prepare context with `scripts/turn_runtime.py prepare "<ordinary request>"`.
2. Let Codex CLI use the native skills exposed in `.agents/skills`.
3. Execute any needed native skills inside this locked buddy session.
4. Build one buddy run commit with artifacts, state effects, handoff, and contributor audit metadata.
5. Persist with `scripts/turn_runtime.py persist --context <context> --result <result>`.
6. If another turn is needed, derive a new request from `receipt.next_state` or `receipt.handoff`.
```

- [ ] **Step 2: Rewrite receipt instructions**

Receipt rendering must show:

- `Persisted: ok|failed`
- `Buddy: <buddy_id>`
- `Task: <task_title> [<task_id>]`
- `Track: <track_title> [<track_id>]` only when available
- `Artifacts: <artifact_id_1>, <artifact_id_2>|none`
- `Run: <run_id>`
- `Handoff: <next_buddy>|none`

No receipt instruction may mention `skill_id`.

- [ ] **Step 3: Rewrite native skill shared rules**

Every `SKILL.md` must stop saying the skill persists with its native skill id.

Use this replacement:

```markdown
This native skill contributes content to the current buddy run. Do not call persist from the skill perspective. The locked buddy session persists one buddy run commit after all needed native skill work is integrated.
```

- [ ] **Step 4: Update buddy contract docs**

Each `framework/contracts/<buddy>.md` must describe buddy-level artifact kinds and handoff expectations, not skill-level result persistence.

- [ ] **Step 5: Verify instruction cleanup**

Run:

```bash
rg -n "persist --skill-id|persist-skill-result|same native skill_id|reporting the Codex skill name|chosen skill id" tools/launcher/assets/buddies buddyswitch/skills framework/contracts framework/docs
```

Expected: no active instruction remains.

### Task 6: Preserve And Prove Native SKILL Execution

**Files:**

- Modify: `tests/test_runtime_skills.py`
- Modify: `tests/test_buddyswitch_launcher.py`
- Modify: `tests/test_repo_consistency.py`

- [ ] **Step 1: Keep materialization behavior unchanged**

Tests must prove:

- active buddy skills are installed into `.agents/skills/<skill-id>`;
- inactive buddy skills are not installed;
- package contents remain copied as native Codex skill packages;
- launcher still starts with runtime `.agents/skills`.

- [ ] **Step 2: Add no-persist-coupling assertion**

Add a repo consistency test that fails if `scripts/runtime_skills.py` imports `turn_runtime`, `env_store`, or persist contract files.

Reason: native skill exposure must not depend on buddy-run persistence.

- [ ] **Step 3: Verify launcher/runtime skills tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_runtime_skills.py tests/test_buddyswitch_launcher.py tests/test_repo_consistency.py -q
```

Expected: materialization tests pass without any skill-level persist assumptions.

### Task 7: Add PM To Market Collaboration Scenario Tests

**Files:**

- Modify: `tests/test_turn_integration.py`
- Modify: `tests/test_turn_runtime.py`

- [ ] **Step 1: Add PM buddy run scenario**

Test functional input:

```text
给一款AI日程工具做一个简单的landing page，写一份PRD，然后创建绑定一个track
```

Expected PM buddy run commit:

- creates or binds a PM task;
- creates a track;
- writes one `prd` artifact;
- records contributors `["write-prd", "track-manager"]`;
- writes handoff to `market` or `design`;
- run audit has `buddy_id="pm"` and no `skill_id`.

- [ ] **Step 2: Add Market buddy run scenario on same track**

Test functional input:

```text
对于 track-id 这样一款产品的landing page，我们想了解这类产品在营销上应该怎么表达和展现，以及目前相关竞品的情况和它们的landing page
```

Expected market buddy run commit:

- uses the PM-created track id as current track context;
- writes one `market-landing-page-brief` artifact;
- records contributors such as `["research-scan", "positioning-copy"]`;
- does not create a new track;
- writes handoff to `design`;
- run audit has `buddy_id="market"` and no `skill_id`.

- [ ] **Step 3: Assert collaboration context**

After both runs:

- track contains task ids for the PM and market work;
- track artifact index exposes both `prd` and `market-landing-page-brief`;
- related runs expose previous run ids for continuity;
- no downstream consumer needs skill ids to understand the collaboration state.

- [ ] **Step 4: Verify integration tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_turn_integration.py -q
```

Expected: PM-to-market collaboration passes through buddy run commits.

### Task 8: Remove Historical Skill-Level Persist Residue

**Files:**

- Modify: all active product/runtime/doc/test surfaces returned by the search commands below.
- Exclude historical planning notes under `docs/spec` and `docs/whiteboard` unless they are active implementation guidance for this task.

- [ ] **Step 1: Search for old runtime API names**

Run:

```bash
rg -n "persist_skill_result|_persist_skill_result|_persist_artifact_skill|persist_skill_result_request|_derive_cli_persist_skill_id|skill_id is required|persist requires a single skill_id" buddyswitch scripts tools framework tests README.md
```

Expected: no active runtime code or tests contain these names.

- [ ] **Step 2: Search for old product contract language**

Run:

```bash
rg -n "persist-skill-result|persist --skill-id|same native skill_id|selected skill_id|output_slot|output_schema|produces_artifact" buddyswitch scripts tools framework tests README.md
```

Expected:

- no active runtime, docs, skill instructions, or tests use old persist semantics;
- `output_schema` may remain only in framework schema validation tests if those schemas are still used as authoring references outside runtime.

- [ ] **Step 3: Search for canonical artifact skill ownership**

Run:

```bash
rg -n "\"skill_id\"|artifact\\.skill_id|receipt\\[\"skill_id\"\\]|run_payload\\.get\\(\"skill_id\"\\)" scripts tests framework tools buddyswitch README.md
```

Expected:

- no canonical artifact, receipt, or run audit requires `skill_id`;
- optional contributor audit may use `contributors.skills`.

### Task 9: Final Verification

**Files:**

- No direct edits.

- [ ] **Step 1: Compile changed Python files**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile scripts/env_manifest.py scripts/env_store.py scripts/runtime_kernel/persist.py scripts/runtime_store/projections.py scripts/skill_creator_importer.py scripts/turn_runtime.py scripts/runtime_skills.py
```

Expected: no compile errors.

- [ ] **Step 2: Run focused test suite**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_manifest_v2.py tests/test_env_store_v2.py tests/test_turn_runtime.py tests/test_turn_integration.py tests/test_runtime_skills.py tests/test_buddyswitch_launcher.py tests/test_repo_consistency.py tests/test_skill_creator_importer.py tests/test_artifact_selection.py tests/test_output_schema_boundaries.py tests/test_parallel_contracts.py tests/test_console_app_contract.py -q
```

Expected: all selected tests pass.

- [ ] **Step 3: Run cleanup/debug regression tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_debug_apis.py tests/test_cleanup_system.py -q
```

Expected: tests pass with buddy-run artifact/run fields.

- [ ] **Step 4: Confirm main checkout is not polluted**

Run:

```bash
git -C /Users/chen/Dev/buddyswitch status --short docs/spec
git -C /Users/chen/Dev/buddyswitch/.worktrees/dev0210 status --short docs/spec
```

Expected: new plan files are visible only in `dev0210`.

## Definition Of Done

- `persist --skill-id` no longer exists.
- `persist-skill-result` contract no longer exists.
- Artifact, receipt, and run audit are buddy-run centered and do not use `skill_id` as canonical state.
- `contributors.skills` exists only as optional audit metadata.
- Native skill materialization and codex-cli execution exposure remain unchanged.
- PM-to-market collaboration on one track is covered by functional tests.
- Old skill-level persist tests and docs are removed, not preserved as compatibility.
