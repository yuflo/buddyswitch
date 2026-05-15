# Runless Buddy Output Rebuild Memo

Date: 2026-05-14
Worktree: `dev2258`
Status: architecture memo and implementation-planning handoff only. No source implementation in this phase.

## Decision

BuddySwitch should stop treating execution runs as durable product state.

The durable system should manage buddy output and collaboration objects:

- `track`
- `task`
- `artifact`
- `handoff`
- `memory`
- `buddybox`

The runtime should only provide execution capability:

- active buddy identity;
- broker/tool routing;
- permission checks;
- atomic writes;
- transient request ids or idempotency keys when needed.

The runtime should not persist run raw files, run reservations, task-bound run lineage, or execution summaries by default. A host turn is disposable unless the buddy explicitly writes something durable through a tool.

Core target:

```text
BuddySwitch does not manage execution history.
BuddySwitch manages buddy outputs, collaboration objects, and reusable knowledge.
```

## Why This Rebuild Is Needed

The current architecture makes a system execution concept do product-management work.

Today the path is effectively:

```text
instance.current_task_id/current_track_id
  -> prepare
  -> run reservation
  -> artifact.source_run_id validation
  -> run.commit audit
  -> task/run association
```

This creates avoidable coupling:

- a single instance binding can accidentally control which task a run may write;
- sub-agents inherit or fight over a parent run context;
- artifact writes depend on `source_run_id`, even though the real product target is a task;
- task records carry run bookkeeping through `run_ids` and `latest_run_id`;
- the host has to persist a run audit even when the meaningful output is already an artifact, handoff, memory, or file.

The recent multi-track sub-agent case exposed this clearly. The problem was not that sub-agents are special. The problem was that durable product writes were routed through an implicit current binding and a task-bound run reservation.

## Non-Negotiable Direction

This rebuild should reject compatibility.

Do not preserve old behavior through aliases, adapters, dual paths, or compatibility flags. BuddySwitch is still at the stage where replacing confusing structure is cheaper than teaching every future agent how to route around it.

Retire these concepts from the canonical path:

- `buddyswitch/content/runs/*.json`
- `buddyswitch/content/runs/reserved/*.json`
- `runs/raw/*` as canonical state
- `run.commit`
- `run.validate_result`
- `source_run_id` as required artifact provenance
- `task.run_ids`
- `task.latest_run_id`
- `instance.current_task_id`
- `instance.current_track_id`
- prepare/persist as a durable turn transaction

If old tests or docs require these fields, update the tests and docs to the new model. Do not keep the old path alive.

## Target Layering

### System Layer

The system layer is execution infrastructure only.

It owns:

- `instance_id`;
- active buddy id;
- workspace/session metadata;
- runtime broker status;
- tool registry and dispatch;
- manifest permission enforcement;
- runtime lock coordination;
- transient request or operation ids when a single tool call needs idempotency.

It does not own:

- current task selection;
- current track selection;
- run history;
- execution summaries;
- task/run linkage;
- artifact/run lineage.

`instance.json` should shrink to execution-container identity:

```json
{
  "instance_id": "inst-example",
  "buddy": "pm",
  "status": "active",
  "workspace_dir": "/path/to/workspace",
  "browser_port": 12345,
  "updated_at": "2026-05-14T00:00:00+08:00"
}
```

No current work fields belong here.

### Product Collaboration Layer

The product layer is explicit buddy-managed state.

It owns:

- tracks as collaboration lanes;
- tasks as buddy-owned work items;
- artifacts as formal deliverables attached to tasks;
- handoffs as explicit cross-buddy transfer records;
- memories as durable reusable knowledge;
- buddybox files as buddy-owned file outputs or working assets.

All product changes should happen through explicit tools.

Examples:

```text
track.join --track-id <track-id>
task.create --track-id <track-id> ...
artifact.create_revision --task-id <task-id> ...
handoff.create --track-id <track-id> ...
memory.write --kind decision ...
buddybox.write --path pm/prototypes/foo.html ...
```

The active buddy's authority comes from the manifest and object ownership rules, not from current instance binding.

## Durable Object Model

### Track

Tracks remain product collaboration lanes.

Keep:

- `id`
- `title`
- `summary`
- `status`
- `current_buddy`
- `next_buddy`
- `task_ids`
- `updated_at`

Track lifecycle authority remains PM-owned unless explicitly redesigned later. Do not use this rebuild to introduce a generic workflow engine or broad track lifecycle ACL system.

### Task

Tasks remain buddy-owned work items and the current artifact parent.

Keep:

- `id`
- `buddy`
- `title`
- `summary`
- `status`
- `track_id`
- `artifact_ids`
- `artifact_slots`
- `created_at`
- `updated_at`

Remove:

- `run_ids`
- `latest_run_id`

Tasks should not know which host turns produced their artifacts. The artifact list and artifact slots are the durable work history that matters for product state.

### Artifact

Artifacts remain formal deliverables attached to tasks.

Keep:

- `id`
- `task_id`
- `buddy`
- `kind`
- `title`
- `summary`
- `content`
- `revision`
- `supersedes_artifact_id`
- `is_current`
- `created_at`
- `updated_at`

Replace required `source_run_id` with object-level provenance:

```json
{
  "created_by": "pm",
  "source_refs": [
    {"type": "artifact", "id": "art-design-handoff-r1"},
    {"type": "memory", "id": "mem-pm-positioning-decision-001"},
    {"type": "buddybox", "path": "pm/prototypes/fireflies.html"},
    {"type": "external", "label": "Fireflies public site", "url": "https://example.com"}
  ]
}
```

`source_refs` should be optional but structured. It records useful provenance without requiring a system run object.

Artifact write authority should be simple:

```text
active buddy may write an artifact to a task it owns,
using a kind allowed by its manifest artifact_kinds.
```

No run reservation should be required.

`artifact.create_revision` should require an explicit `task_id`. It should not fall back to `instance.current_task_id`, because that field no longer exists.

### Handoff

Handoffs remain explicit collaboration objects.

Keep handoff records durable because they are product collaboration state, not execution history.

Handoff records should reference product objects:

- source buddy;
- target buddy;
- track id;
- source task id when relevant;
- artifact ids when relevant;
- memory ids when relevant;
- buddybox paths when relevant;
- reason;
- context;
- status.

Remove run dependency from handoff source fields. Handoff provenance should be object-based, not run-based.

### Memory

Memory is durable reusable buddy knowledge.

Use memory when a conclusion should influence later work but is not itself a formal task artifact.

Examples:

- PM decision rationale;
- positioning facts;
- repeated user preference;
- product constraints;
- architecture boundary;
- lessons learned from a failed attempt;
- reusable context summary.

Suggested memory record:

```json
{
  "id": "mem-pm-fireflies-locks-001",
  "buddy": "pm",
  "kind": "decision",
  "title": "Fireflies landing page lock gaps",
  "summary": "Fireflies is blocked until CTA, proof, pricing, hero visual, and security claims are locked.",
  "content": {
    "body": "..."
  },
  "source_refs": [
    {"type": "artifact", "id": "art-task-pm-fireflies-prd-r1"}
  ],
  "created_at": "2026-05-14T00:00:00+08:00",
  "updated_at": "2026-05-14T00:00:00+08:00"
}
```

Memory should not become an automatic transcript sink. The buddy must choose to write memory when the content is reusable.

### Buddybox

Buddybox is a buddy-owned file domain for outputs that are better represented as files than JSON object content.

Examples:

- PM HTML prototype;
- design sketch export;
- market CSV scratch data;
- generated screenshots;
- dev patch notes or local reports;
- test evidence assets.

Suggested root:

```text
buddyswitch/content/buddybox/<buddy>/
```

Example:

```text
buddyswitch/content/buddybox/pm/prototypes/fireflies-lock.html
```

Buddybox files are durable when intentionally written. They are not run raw. They should be referenced from artifacts, handoffs, or memory when they matter.

Buddybox tools should be explicit:

- `buddybox.write`
- `buddybox.read`
- `buddybox.list`
- `buddybox.delete`

Write permissions are buddy-scoped by path. A PM buddy can write under `buddybox/pm/`, not under `buddybox/dev/`.

## Execution Model

There is no durable run lifecycle.

The host may still have an internal request id or operation id for:

- idempotency on a single broker request;
- log correlation while debugging;
- retrying a single tool call;
- timeout handling.

That id is not product state and should not be referenced by task, track, artifact, handoff, memory, or buddybox records.

The default turn lifecycle becomes:

```text
1. Host receives request.
2. Host reads context through env tools.
3. Host or sub-agents call explicit product tools.
4. Durable state is written immediately by those tools.
5. Host final response summarizes what was written.
```

No final `persist` step is required.

If a buddy wants the execution summary to persist, it must write one of:

- artifact;
- memory;
- handoff;
- buddybox file.

This is intentional. Durable state should be chosen, not automatic.

## Sub-Agent Model

Sub-agents should not receive run contexts.

They should receive:

- active buddy identity through the same instance/session;
- explicit target ids such as `track_id`, `task_id`, `artifact_id`;
- tool permissions inherited from the active buddy;
- optional buddybox path or memory purpose when needed.

Read-only sub-agent:

```text
Read track/task/artifact context and return findings to parent.
No durable state required.
```

Artifact-writing sub-agent:

```text
Given task_id=task-pm-fireflies
Call artifact.create_revision with explicit task_id.
No source_run_id.
No run commit.
```

File-output sub-agent:

```text
Given buddybox path pm/prototypes/fireflies.html
Call buddybox.write.
Optionally create artifact or memory that references that file.
```

Multiple sub-agents can work under one buddy without competing over a current task. Runtime locking still serializes actual writes where needed, but the lock protects storage integrity only. It does not define work ownership.

## Tool Surface After Rebuild

Keep and simplify:

- `track.list`
- `track.get`
- `track.join`
- `track.create`
- `track.update`
- `track.advance`
- `track.archive`
- `task.list`
- `task.get`
- `task.create`
- `task.update`
- `task.archive`
- `artifact.list`
- `artifact.get`
- `artifact.create_revision`
- `artifact.update_metadata`
- `handoff.list`
- `handoff.validate`
- `handoff.create`
- `context.get`
- `context.summarize`
- `context.list_sources`

Add:

- `memory.list`
- `memory.get`
- `memory.write`
- `memory.update`
- `memory.archive`
- `buddybox.list`
- `buddybox.read`
- `buddybox.write`
- `buddybox.delete`

Remove from the canonical surface:

- `run.commit`
- `run.validate_result`
- `run.get_receipt`
- `run.get_raw`
- `binding.get`
- `binding.set_task`
- `binding.set_track`
- `binding.clear`
- run-scoped browser evidence issuance.

Browser evidence, if still needed for market-quality gates, should attach to the artifact or memory being written. It should not require a run token.

## Prepare And Context

`prepare` should stop creating durable reservations.

It may remain as a context read helper if useful, but its output should be equivalent to calling context and tool discovery APIs:

```text
active buddy
instance identity
available tools
tool semantics
relevant tracks/tasks/handoffs/artifacts
warnings
```

It should not return:

- run id;
- context revision tied to a run;
- persist command hint;
- current task id;
- current track id;
- task-bound reservation.

If this makes `turn_runtime.py` too misleading, rename or split it during implementation. Do not preserve old `prepare/persist` semantics for compatibility.

## Rejected Designs

### Keep Run As A System-Layer Audit Object

Rejected.

This is cleaner than task-bound runs, but it still makes every host turn look like durable state. BuddySwitch should persist outputs, collaboration, and reusable knowledge, not every execution transaction.

### Add Work Scope

Rejected.

`work scope` would be another abstraction for agents to learn. The real targets are already visible: track, task, artifact, memory, buddybox, handoff.

### Keep Current Binding As A Compatibility Layer

Rejected.

Current binding is the source of accidental coupling. If a UI later needs selection state, add a separate `selection` concept that cannot authorize writes and is not used by prepare, artifact writes, or task management.

### Keep Run Reservation Only For Artifact Writes

Rejected.

Artifact write authority should come from the active buddy, manifest permissions, artifact kind policy, and task ownership. A run reservation adds indirection without product value.

### Move Run Raw Into Memory Automatically

Rejected.

Memory must be chosen, curated, and reusable. Automatically storing every execution summary in memory would recreate run raw under a more confusing name.

## Implementation Roadmap

This is a major refactor. It should be done in small verified slices, but without compatibility paths.

## Deletion Review Inventory

This section is the implementation guardrail against leftovers. Before starting code changes, use this inventory to make sure the rebuild removes every old dependency path, not only the obvious `run` service.

Deletion scope rules:

- This is not a one-to-one path replacement. `persist`, run audit files, run raw files, and instance binding are removed because durable writes move directly to explicit product tools.
- The replacement for "persist one run" is "write the intended durable object at the moment it matters": artifact, handoff, memory, or buddybox.
- `runs/raw` is not renamed to buddybox. Disposable scratch stops being canonical BuddySwitch state; buddybox is only for intentional durable buddy-owned file outputs.
- When this inventory names a file, remove only the listed old run/current-binding behavior unless the bullet explicitly says to delete the file or service.
- Keep runtime infrastructure that still serves execution: broker framing, active buddy identity, manifest permissions, workspace identity, locks, and generic tool dispatch.
- Keep product collaboration infrastructure: track, task, artifact, handoff services and useful skills remain, but lose run/current-binding coupling.
- Do not replace deleted run state with a hidden equivalent under another name.

Intended whole-file or whole-service deletes are limited to:

- `scripts/runtime_kernel/persist.py`
- `scripts/env/services/runs.py`
- `scripts/env/services/bindings.py`
- `buddyswitch/skills/shared/run-tool/SKILL.md`
- `framework/contracts/persist-buddy-run.json`, unless it is replaced by direct product-tool contracts with no run boundary.
- generated/canonical runtime state under `buddyswitch/content/runs/` and `runs/raw/`.

Everything else in this inventory is rewrite/removal of specific run/current-binding behavior, not a blanket file deletion.

### Runtime Transaction Path

Remove or rewrite these run-centric entrypoints:

- `scripts/turn_runtime.py`
  - Remove run id generation.
  - Remove context revision derived from run id.
  - Remove run envelope construction and validation.
  - Remove run reservation save/load/clear helpers.
  - Remove persist command hints.
  - Remove `persist` CLI command.
  - Replace `prepare` with a context/tool discovery command, or rename the file if the old name becomes misleading.
- `scripts/runtime_kernel/resolve.py`
  - Stop returning prepared run envelopes.
  - Replace with context discovery or remove if `prepare` disappears.
- `scripts/runtime_kernel/persist.py`
  - Delete. There is no run persist boundary.
- `scripts/runtime_kernel/client.py`
  - Remove persist idempotency helpers based on `context.run_envelope.turn_identity.run_id`.
  - Keep only generic broker request helpers.
- `scripts/runtime_kernel/dispatcher.py`
  - Remove broker methods `prepare` and `persist` as run transaction methods.
  - Keep `env.tool`, `ping`, and `status`.
  - Remove persist-specific idempotency hydration.
- `scripts/runtime_kernel/broker.py`
  - Keep the broker as execution infrastructure.
  - Remove CLI/method assumptions that `prepare` and `persist` are canonical lifecycle operations.
  - Keep active buddy and workspace identity validation.
- `scripts/runtime_kernel/server.py`
  - Keep framing, capacity, timeout, and structured error handling.
  - Ensure tests no longer require prepare/persist method routing.
- `scripts/runtime_kernel/protocol.py`
  - Keep generic request/response framing.
  - Remove protocol wording or examples that make run transactions canonical.
- `scripts/runtime_kernel/lifecycle.py`
  - Keep broker process lifecycle if still useful.
  - Ensure lifecycle docs do not describe run reservation health as the main-path check.
- `scripts/runtime_kernel/coordinator.py`
  - Remove special lock handling for `prepare` and `persist`.
  - Keep read/write lock derivation from actual env tool mutability.
- `scripts/env/services/runs.py`
  - Delete the service.
  - No replacement service should appear under another name.

### Run Content And Reservation Storage

Remove canonical run storage:

- `buddyswitch/content/runs/*.json`
- `buddyswitch/content/runs/reserved/*.json`
- `runs/raw/*` as BuddySwitch canonical or recommended scratch state.

Remove code paths that create, scan, clean, project, or display those paths:

- `scripts/env_store.py`
  - `RUN_CONTENT_DIR`
  - `run_content_path`
  - `save_run_content`
- `scripts/env_cleanup.py`
  - run content discovery;
  - run raw discovery;
  - `run_ids` cleanup plan fields.
- `scripts/runtime_store/projections.py`
  - run audit projections;
  - `current_task_id` or `current_track_id` projections from instance payload;
  - `related_run_ids`.
- `scripts/workspace_data.py`
  - remove `scan_run_audits`;
  - stop exporting run audit data to console-facing helpers.
- `framework/console/app.js`
  - run audit cards;
  - latest run fields;
  - source run display;
  - task run history display.
- `framework/contracts/workspace-projection.json`
  - remove `run_audits`;
  - remove task `run_ids` and `latest_run_id`;
  - remove artifact `source_run_id`;
  - add memory and buddybox projection shapes.
- `tools/launcher/workspace.sh`
  - remove only workspace creation and git ignore rules for `buddyswitch/content/runs` and `runs/raw`.
  - keep workspace bootstrap, source checkout setup, runtime broker setup, and other non-run behavior.

### Instance Current Binding

Remove current-work state from instance records and tools:

- `tools/launcher/env.sh`
  - stop writing `current_task_id`;
  - stop writing `current_track_id`.
- `tools/launcher/instance.sh`
  - remove current task/track columns and field readers.
- `scripts/env/services/bindings.py`
  - delete the service.
- `scripts/env/client.py`
  - remove `binding` CLI resource.
  - remove `task get-current`.
  - remove `task set-current`.
  - remove `track get-current`.
- `scripts/env/tools/dispatch.py`
  - remove `binding` handler registration.
  - remove imports of `bindings`.
- `scripts/env/tools/contracts.py`
  - remove `binding` tool contract.
  - remove `current_binding` returns from all contracts.
  - remove mutability labels that mention instance binding.
- `scripts/env/tools/semantics.py`
  - remove binding action semantics.
  - remove text saying actions write or depend on `current_task_id/current_track_id`.
- `scripts/env/services/tasks.py`
  - remove `get_current_task`.
  - remove `set_current_task`.
  - remove current-binding returns and help text.
- `scripts/env/services/tracks.py`
  - remove `get_current_track`.
  - keep `track.join`, but remove the side effect that writes instance binding.
- `scripts/env/services/context.py`
  - remove current binding validation and mismatch checks.
  - remove active context sections that are just current task/track projections.

### Task And Artifact Run Fields

Remove run bookkeeping from product objects:

- `scripts/env_store.py`
  - remove `task.run_ids` validation.
  - remove `task.latest_run_id` validation.
  - remove `initial_run_id` from `create_task`.
  - remove `add_run_to_task`.
  - remove required `artifact.source_run_id`.
  - remove required `handoff.source_run_id`.
  - add artifact `created_by` and `source_refs`.
- `scripts/env/services/artifacts.py`
  - remove `_validate_source_run`.
  - remove `source_run_id` from create/validate/update payload fields.
  - require explicit `task_id`; do not fall back to instance binding.
  - remove `source_run` and `source_run_id` summary fields.
  - update metadata should not require a provenance field when title/summary changes.
- `scripts/env/services/handoffs.py`
  - remove required `source_run_id`.
  - remove run-audit handoff discovery.
  - let handoff source references be artifact ids, memory ids, buddybox paths, and optional source task id.
- `scripts/env/services/track_relations.py`
  - remove artifact summary source run fields.
  - keep source buddy/task/currentness relation fields.
- `scripts/env/services/context.py`
  - remove run scan helpers.
  - remove recent run summaries.
  - remove source-of-truth text pointing to `buddyswitch/content/runs/<run_id>.json`.
  - add memory and buddybox summaries instead.
- `scripts/artifact_selection.py`
  - remove unused current-task argument and any run/source-run assumptions.

### Evidence And Browser Quality Gates

Market/browser evidence must not remain run-token based.

Review these files. Rewrite by default; remove only the parts whose sole purpose is run-token issuance or run-audit storage:

- `scripts/env/services/evidence.py`
  - replace prepared-run validation with target artifact or memory validation.
  - remove run-scoped evidence token root.
  - keep evidence integrity checks if browser evidence remains.
  - if evidence remains, attach evidence to artifact or memory writes.
- `scripts/browser_evidence.py`
  - remove assumptions that evidence is issued for a prepared run.
- `framework/docs/browser-cockpit.md`
  - remove per-run evidence contract and run audit token storage.

### Tool Registry And CLI Surface

The canonical tool surface must not expose old run or binding concepts.

Remove or rewrite:

- `scripts/env/tools/contracts.py`
  - remove `run` tool.
  - remove `binding` tool.
  - remove `source_run_id` payload fields.
  - add `memory` and `buddybox`.
- `scripts/env/tools/semantics.py`
  - remove all `run.*` action semantics.
  - remove all `binding.*` action semantics.
  - remove `source_run_id` explanations.
  - add complete semantic descriptions for `memory.*` and `buddybox.*`.
- `scripts/env/tools/dispatch.py`
  - remove `run` and `binding` handlers.
  - add `memory` and `buddybox` handlers.
- `scripts/env/client.py`
  - remove `run` resource commands.
  - remove `binding` resource commands.
  - add `memory` and `buddybox` resource commands.
- `buddyswitch/manifest.toml`
  - remove `run-tool` skill.
  - add memory/buddybox permissions only if the implementation keeps permission names explicit.
- `buddyswitch/env-profiles/*.json`
  - replace `scratch.root = runs/raw/<buddy>`.
  - add buddybox writable roots if the sandbox/profile model needs explicit writable paths.
- `scripts/env_profiles.py`
  - remove validation that expects `runs/raw/<buddy>`.
  - validate buddybox root rules instead if profiles keep writable path metadata.
- `scripts/skill_creator_importer.py`
  - remove generated guidance saying native skills contribute to a current buddy run.
  - remove generated guidance saying one locked session persists a buddy run commit.

### Docs, Skills, And Guidance

All guidance must teach the new durable-output model.

Important distinction:

- Do not delete buddy AGENTS files wholesale.
- Do not delete useful buddy-specific skills wholesale.
- Delete only the shared `run-tool` skill because the run tool itself is removed.
- Keep the shared `artifact-tool`, `task-tool`, `track-tool`, and `handoff-tool` skills, but rewrite their old run/current-binding rules.
- Rewrite AGENTS and remaining skills so they no longer teach prepare/persist, current binding, run receipts, run raw, or buddy-run commits.

Rewrite these docs and skills unless the bullet explicitly says delete:

- `README.md`
  - remove prepare/persist product loop.
  - remove run content and `runs/raw` as state locations.
- root `AGENTS.md`
  - replace runtime state list with track/task/artifact/handoff/memory/buddybox.
- `tools/launcher/assets/buddies/*/AGENTS.md`
  - keep these files.
  - remove mandatory prepare first.
  - remove mandatory persist after execution.
  - remove receipt/run-id language.
  - replace `runs/raw/<buddy>` scratch guidance with buddybox guidance where durable files are intended.
- `buddyswitch/skills/shared/run-tool/SKILL.md`
  - delete and remove from manifest.
- `buddyswitch/skills/shared/artifact-tool/SKILL.md`
  - remove reserved source run rules.
  - update payload to use explicit `task_id` and optional `source_refs`.
- `buddyswitch/skills/shared/task-tool/SKILL.md`
  - remove current binding workflow.
- `buddyswitch/skills/shared/track-tool/SKILL.md`
  - remove current binding and buddy-run commit language.
- `buddyswitch/skills/shared/handoff-tool/SKILL.md`
  - remove `source_run_id` as required.
- buddy-specific skills under `buddyswitch/skills/{pm,design,dev,market,test}/**/SKILL.md`
  - keep useful skills.
  - replace "contribute to one buddy-run commit" with "write durable outputs explicitly".
  - replace "before persist" with direct product tool writes.
- `framework/docs/*`
  - update relevant active docs: architecture overview, turn runtime spec, skill shared rules, browser cockpit, artifact/run policy, track registry, runtime broker runbook, interface spec, and console docs.
  - do not mass-delete framework docs just because the path is broad.
- `docs/spec/*` and older active planning docs
  - archive as historical or rewrite if they are still used as implementation guidance.
  - Do not let old task/artifact/run upgrade plans remain as active instructions.
- `framework/contracts/prepare-turn-context.json`
  - remove `binding_snapshot`, `current_task_id`, `current_track_id`, `run_envelope`, `persist_command_hint`, and run-shaped context sections.
- `framework/contracts/persist-buddy-run.json`
  - delete or replace with direct product-tool contracts.
  - Do not leave a renamed persist contract with the same run boundary.
- `framework/contracts/{pm,design,dev,market,test}.md`
  - remove "every run contributes to one persist-buddy-run commit".
  - replace `runs/raw/<buddy>` scratch roots with buddybox guidance only for durable file outputs.
  - remove "task effects are limited to the current prepared task".
- `framework/agent-registry.md`
  - remove canonical prepare/persist flow and `buddyswitch/content/runs` state language.
- `framework/docs/artifacts-runs-git-policy.md`
  - rewrite as product-output storage policy or delete if its only purpose is run/raw placement.
- `framework/docs/skill-runtime-shared-rules.md`
  - remove one-run-per-turn persist guidance.
  - replace with explicit artifact/memory/handoff/buddybox write guidance.
- `framework/docs/skill-architecture-best-practices.md`
  - remove prepared context and persist boundary claims from native skill architecture.
- `scripts/runtime_agents.py`
  - update template validation away from mandatory prepare/persist commands.
  - validate new active-buddy/tool-output rules instead.

### Tests And Fixtures

The test suite must be treated as part of the architecture, not as compatibility pressure.

Replace tests that assert old behavior:

- run env tool tests;
- turn runtime prepare/persist tests;
- runtime broker persist tests;
- artifact source run tests;
- handoff source run tests;
- binding env tool tests;
- context binding tests;
- launcher instance current binding tests;
- console/projection tests that expect run audits;
- cleanup tests for run raw/content;
- response contract tests that expect `run.*`, `binding.*`, `source_run_id`, `current_binding`, `run_ids`, or `latest_run_id`.
- env profile tests that expect `runs/raw/<buddy>`.
- buddy sandbox tests that grant writes to `runs/raw/<buddy>`.
- runtime AGENTS validation tests that require prepare/persist commands.
- runtime skill installation tests that expect `run-tool` to be shared by every buddy.
- repo consistency tests that assert buddy-run commit wording, run audit paths, or persist contracts.
- output schema boundary tests that preserve buddy-run commit result shape.
- framework contract tests for `prepare-turn-context`, `persist-buddy-run`, and workspace projection run audits.

Add regression tests that fail if the old architecture returns:

- `run_envelope`;
- `context_revision` tied to a run;
- `persist_command_hint`;
- `source_run_id`;
- `current_task_id`;
- `current_track_id`;
- `run_ids`;
- `latest_run_id`;
- `run` tool;
- `binding` tool.

## Addition Review Inventory

This section prevents the new memory and buddybox work from being under-specified.

First implementation stance:

- Use local files and directories only.
- Do not introduce a database, vector store, background indexer, search service, or sync service.
- Keep memory as JSON files under `buddyswitch/objects/memories/`.
- Keep buddybox as ordinary files under `buddyswitch/content/buddybox/<buddy>/`.
- Add atomic writes and path validation before adding richer storage behavior.

Permission enforcement stance:

- Permissions must be enforced by tool/service functions, launcher sandbox rules, manifest/env-profile checks, and structured tool responses.
- AGENTS files, skills, docs, and prompt wording may explain how to use tools, but must not be the permission source.
- Rejections must return machine-readable structured fields such as `ok=false`, `error.code`, `permission_boundary`, `why_blocked`, `impact`, `retryable`, `retry_guidance`, `allowed_next_actions`, and where useful `allowed_next_action_options`.
- Success responses must return machine-readable state signals such as `state_changed`, `durability`, `created_ids`, `updated_ids`, `read_scope`, and follow-up affordances where useful.
- Tool contracts and operation semantics are discovery surfaces. The service implementation remains authoritative for dynamic permission checks.
- Memory and buddybox must not ship with prompt-only permission rules. Owner scope, cross-buddy read/write behavior, path validation, and archive/delete authority must be checked in code.

Semantic contract stance:

- New and changed env tools must satisfy `docs/memo/2026-05-14-env-tool-semantic-contract-memo.md`.
- Runtime-visible tool metadata must be sufficient for the host to choose a capability, understand inputs, predict side effects, interpret success, and recover from rejection without reading `scripts/env/services/*.py`.
- Each capability must expose `title`, `plain_description`, `use_when`, `do_not_use_when`, and `capability_boundary`.
- Each action must expose `title`, `plain_description`, `inputs_explained`, `side_effects`, `risk_hints`, `success_means`, and `common_failures`.
- Every payload field must have a plain-language explanation. Empty text, generic "use this tool" language, or docs-only explanation should fail tests.
- `side_effects` must say what the action may write, what it does not write, durability, and idempotency.
- `risk_hints` should at least cover read-only vs write, destructive behavior, idempotency, open-world input, external effects, and human approval if relevant.
- Result semantics must be part of tool responses, not left to log inspection or docs.
- The semantic layer is guidance and interpretation, not authorization. Enforcement remains in service/broker/launcher code.

### Memory Storage

Add memory as a first-class object type:

- directory: `buddyswitch/objects/memories/`;
- object id pattern: `mem-<buddy>-<slug>-<shortid>`;
- service module: `scripts/env/services/memories.py`;
- optional helper module if needed: `scripts/env/services/memory_relations.py`.

Local file implementation:

- one memory record per JSON file;
- file path: `buddyswitch/objects/memories/<memory_id>.json`;
- write through temp-file-plus-rename, matching existing object write patterns;
- list by scanning JSON files and filtering in memory;
- no full-text search in the first implementation.

Required memory fields:

- `id`;
- `buddy`;
- `kind`;
- `title`;
- `summary`;
- `content`;
- `source_refs`;
- `status`;
- `created_at`;
- `updated_at`.

Initial memory statuses:

- `active`;
- `archived`.

Initial memory kinds should stay small and concrete:

- `decision`;
- `fact`;
- `preference`;
- `constraint`;
- `lesson`;
- `context-summary`.

Memory permissions, if explicit permission strings are kept:

- `memory.read`;
- `memory.write`;
- `memory.update`;
- `memory.archive`.

Memory tool actions:

- `memory.list`;
- `memory.get`;
- `memory.write`;
- `memory.update`;
- `memory.archive`.

Initial memory payloads:

- `memory.list`: optional `buddy`, `kind`, `status`, `source_ref`, `limit`.
- `memory.get`: required `memory_id`.
- `memory.write`: required `kind`, `title`, `summary`, `content`; optional `source_refs`.
- `memory.update`: required `memory_id`; optional `kind`, `title`, `summary`, `content`, `source_refs`, `status`.
- `memory.archive`: required `memory_id`.

Memory tool wiring must include:

- `scripts/env/tools/contracts.py`;
- `scripts/env/tools/semantics.py`;
- `scripts/env/tools/dispatch.py`;
- `scripts/env/client.py`;
- `buddyswitch/manifest.toml` permission and skill/capability metadata if explicit permissions remain;
- focused tests for service behavior, CLI routing, response contract, and registry presence.

Memory access rule:

```text
active buddy can write its own memory;
PM can read cross-buddy memory summaries where useful;
full cross-buddy reads require an explicit relation rule or stay owner-only for the first implementation.
```

Do not overbuild memory search. Start with list/get and simple filters by buddy, kind, status, and source ref.

Memory semantic requirements:

- Capability `use_when`: record durable reusable knowledge, decisions, constraints, preferences, lessons, and context summaries that should influence later work.
- Capability `do_not_use_when`: do not use memory for formal deliverables, cross-buddy handoff records, raw execution transcripts, or arbitrary file assets.
- `memory.list` is read-only; success means matching memory summaries were returned, not that memory content was fully consumed.
- `memory.get` is read-only; success means the caller received the full readable memory record within permission scope.
- `memory.write` writes one memory JSON file; success must return the created memory id and source ref form.
- `memory.update` mutates an existing memory record; success must state which fields changed.
- `memory.archive` changes status to `archived`; it is not physical deletion.
- Common failures must include invalid kind/status, missing required fields, unreadable internal source refs when summarized, cross-buddy full-read denial, owner-scope write denial, and malformed content.
- `risk_hints`: list/get are read-only and idempotent; write is durable and non-idempotent unless caller supplies a stable idempotency key later; update/archive are durable mutations and conditionally idempotent.

### Buddybox Storage

Add buddybox as a buddy-owned file domain:

- root: `buddyswitch/content/buddybox/`;
- per-buddy root: `buddyswitch/content/buddybox/<buddy>/`;
- service module: `scripts/env/services/buddybox.py`.

Local directory implementation:

- store ordinary files directly under `buddyswitch/content/buddybox/<buddy>/...`;
- no database metadata table in the first implementation;
- derive `size_bytes`, `updated_at`, and rough `content_type` from the filesystem;
- write through temp-file-plus-rename inside the same directory;
- create parent directories on write after path validation.

Buddybox path rules:

- path must be relative;
- path must not contain `..`;
- path must not be absolute;
- write path must stay inside the active buddy root;
- delete path must stay inside the active buddy root;
- read path must either be owned by active buddy or pass an explicit cross-buddy read rule;
- writes should be atomic.

Buddybox tool actions:

- `buddybox.list`;
- `buddybox.read`;
- `buddybox.write`;
- `buddybox.delete`.

Initial buddybox payloads:

- `buddybox.list`: optional `path`, `recursive`, `limit`.
- `buddybox.read`: required `path`; optional `encoding`.
- `buddybox.write`: required `path`; one of `content` or `content_base64`; optional `content_type`.
- `buddybox.delete`: required `path`.

`buddybox.read` should return UTF-8 text for text files and base64 for binary files. `buddybox.write` should accept base64 so screenshots and other generated assets are not excluded by the first local-file implementation.

Buddybox tool wiring must include:

- `scripts/env/tools/contracts.py`;
- `scripts/env/tools/semantics.py`;
- `scripts/env/tools/dispatch.py`;
- `scripts/env/client.py`;
- `buddyswitch/manifest.toml` permission and capability metadata if explicit permissions remain;
- launcher profile/sandbox writable-root updates;
- focused tests for path traversal rejection, owner write scope, cross-buddy write rejection, list/read/write/delete, binary payload handling, CLI routing, and registry presence.

Buddybox permissions, if explicit permission strings are kept:

- `buddybox.read`;
- `buddybox.write`;
- `buddybox.delete`.

Buddybox response payloads should include:

- `path`;
- `buddy`;
- `size_bytes`;
- `updated_at`;
- `content_type` when obvious;
- `source_ref` form usable by artifacts, memory, and handoffs.

Buddybox should not become generic scratch by default. Durable buddybox files are intentional outputs. Temporary local scratch can stay outside canonical BuddySwitch state unless a buddy explicitly promotes it through `buddybox.write`.

Buddybox semantic requirements:

- Capability `use_when`: create, read, list, or delete intentional buddy-owned file outputs such as prototypes, screenshots, exports, local reports, and generated evidence assets.
- Capability `do_not_use_when`: do not use buddybox for formal artifact body content that belongs in an artifact, reusable knowledge that belongs in memory, disposable scratch, or source-code edits under `projects/app/`.
- `buddybox.list` is read-only; success means file summaries were returned, not file bodies.
- `buddybox.read` is read-only; success must explain whether content is UTF-8 text or base64 binary and include read scope.
- `buddybox.write` writes or replaces one file under the active buddy root; success must return path, size, content type, and source ref form.
- `buddybox.delete` removes one file under the active buddy root; success must state whether a file was deleted.
- Common failures must include path traversal, absolute path, foreign buddy write/delete attempt, missing file, unsupported encoding, invalid base64, directory/file conflict, and sandbox denial.
- `risk_hints`: list/read are read-only; write is durable and may overwrite; delete is destructive; buddybox has no open-world effect by itself but may store open-world content obtained elsewhere.

### Env Profiles And Sandbox

Update buddy execution profiles so the writable durable file domain is buddybox, not run raw.

Meaning:

- Env profile means the per-buddy capability JSON under `buddyswitch/env-profiles/*.json`.
- Sandbox means the launcher-generated Codex filesystem permission profile that decides which local paths the active buddy process can write.
- Today this profile grants each buddy a writable `runs/raw/<buddy>` scratch root.
- After the rebuild, if a buddy needs a durable writable file root, that root should be its own buddybox directory.

Review:

- `buddyswitch/env-profiles/*.json`;
- `scripts/env_profiles.py`;
- `tests/test_buddy_env_profiles.py`;
- `tests/test_buddy_env_sandbox.py`.

Profile rules:

- remove `scratch.root = runs/raw/<buddy>`;
- add `buddybox.root = buddyswitch/content/buddybox/<buddy>` only if the launcher profile needs to expose writable durable roots;
- keep source checkout and `projects/app/` write rules separate from buddybox;
- keep cross-buddy buddybox writes blocked by default.

This is a policy change, not a path rename. `runs/raw` was disposable run scratch. `buddybox` is explicit buddy-owned durable output space.

### Source References

Introduce one shared `source_refs` schema for artifacts, memory, and handoffs.

Allowed initial ref types:

- `artifact`: requires `id`;
- `memory`: requires `id`;
- `buddybox`: requires `path`;
- `track`: requires `id`;
- `task`: requires `id`;
- `handoff`: requires `id`;
- `external`: requires `label`, optional `url`;
- `note`: requires `label`.

Validation rules:

- reject unknown ref types;
- reject missing required keys;
- validate ids with the existing id pattern;
- validate buddybox paths with buddybox path rules;
- do not require every source ref target to be readable by the active buddy on write, but do require the writer to have permission to read any full content it claims to summarize when the ref is an internal object.

Source reference semantic requirements:

- Every action that accepts `source_refs` must explain the field in `inputs_explained`.
- The explanation must say `source_refs` records useful provenance and context. It is not authorization and does not replace owner/permission checks.
- Success responses should return normalized `source_refs` or a `source_ref_summary` when useful, so the host can see what provenance was actually attached.
- Rejections should use stable boundaries such as `source_refs.type`, `source_refs.required_fields`, `source_refs.buddybox_path`, or `source_refs.read_scope`.
- Common failures must include unknown ref type, missing required key, invalid id, invalid buddybox path, and claiming to summarize unreadable internal content.
- Artifact, memory, and handoff semantics must each explain how `source_refs` affects downstream discovery without implying that referenced content was automatically copied into the object body.

### Shared Tool Wiring Checklist

Do not treat memory and buddybox as service-only additions. The first implementation must wire every visible surface that agents use.

Storage helpers:

- add memory object helpers in `scripts/env_store.py` or keep them fully contained in `scripts/env/services/memories.py`;
- add buddybox path helpers in `scripts/env/services/buddybox.py`;
- keep path validation and atomic writes close to the service that performs writes.

Env tool surface:

- add `memory` and `buddybox` to `scripts/env/tools/contracts.py`;
- add operation semantics to `scripts/env/tools/semantics.py`;
- add handler registration in `scripts/env/tools/dispatch.py`;
- add CLI commands in `scripts/env/client.py`;
- add manifest permissions/capability metadata only if explicit permission names remain part of the model.
- ensure all memory/buddybox permission denials flow through `env.tools.responses.rejection`, not through prompt warnings.
- ensure `context.get` or its replacement projects the capability/action semantics for memory and buddybox, including payload field explanations and risk hints.

Context and display:

- add memory and buddybox summaries to `scripts/env/services/context.py`;
- add memory and buddybox projection rows to `scripts/runtime_store/projections.py`;
- update `scripts/workspace_data.py` exports;
- update `framework/console/app.js` to render memory and buddybox summaries.
- ensure projection schemas describe output fields enough for the console and host to interpret memory/buddybox summaries without reading projection code.

Lifecycle support:

- update env profiles and launcher sandbox writable roots for buddybox;
- update cleanup logic for memory and buddybox;
- update workspace/git policy for `buddyswitch/objects/memories/` and `buddyswitch/content/buddybox/`.

Tests:

- service tests for memory and buddybox;
- CLI routing tests;
- env tool response contract tests;
- registry/semantics tests;
- tests that every memory/buddybox action explains every payload field and includes `side_effects`, `risk_hints`, `success_means`, and `common_failures`;
- tests that reject empty or generic semantic descriptions;
- tests that `source_refs` payload semantics exist for every action that accepts it;
- tests that `context.get`, `context.summarize`, and `context.list_sources` remain read-only and explain output meaning, read scope, and common failure modes;
- context projection tests;
- console projection tests;
- sandbox/profile tests;
- cleanup/workspace policy tests;
- rejection tests that assert `permission_boundary`, `why_blocked`, `retry_guidance`, and `allowed_next_actions` are returned for forbidden memory/buddybox operations;
- guidance tests that AGENTS/skills state they are context/help only, not permission sources;
- regression tests that `run` and `binding` tools are absent.

### Context And Discovery

`context.get` and `context.summarize` should become product-state discovery helpers.

Meaning:

- Context discovery is the read-only orientation payload a buddy receives to understand available product state and tools.
- It is not a selected current task and not a prepared run envelope.
- It should help the buddy discover explicit ids to use in later tool calls.

They should include:

- active buddy identity;
- tool catalog;
- relevant tracks;
- relevant tasks;
- artifact summaries;
- handoff summaries;
- memory summaries;
- buddybox summaries.

They should not include:

- run envelopes;
- current binding;
- persist hints;
- run audit summaries;
- source run fields.

Context semantic requirements:

- Capability `use_when`: orient the active buddy before choosing explicit product tools, inspect readable product-state summaries, and discover ids for later calls.
- Capability `do_not_use_when`: do not use context as write authority, task selection state, artifact full-body read substitute, or run preparation.
- `context.get` is read-only; success means full allowed context sections were returned with `state_changed=false`, `durability=none`, and a clear `read_scope`.
- `context.summarize` is read-only; success means compact summaries and candidate next actions were returned, not that a task/track was selected.
- `context.list_sources` is read-only; success means source descriptors were returned, including what each section contains and where its source of truth lives.
- Common failures must include invalid context filter payload, insufficient read scope, stale referenced object, and malformed stored object.
- `risk_hints`: all context actions are read-only, idempotent, non-destructive, and do not authorize later writes.
- Context output should include capability/action semantics or point to their runtime-visible location; it must not force the host to infer tool choice from docs or service code.

### Console And Projections

Update workspace projections and console UI around durable output objects:

Meaning:

- Projection means the read-only JSON snapshot built for the local context panel/console.
- Today `scripts/runtime_store/projections.py` and `scripts/workspace_data.py` build a snapshot that includes `run_audits`.
- After the rebuild, the snapshot should expose durable objects directly: tracks, tasks, artifacts, handoffs, memory summaries, and buddybox file summaries.
- Console means `framework/console/app.js`, which should render those durable objects instead of execution runs.

- show tracks and tasks with current artifacts;
- show memory summaries;
- show buddybox file summaries;
- show handoffs;
- remove latest run panels;
- remove run audit detail pages;
- remove source run labels.

The console should answer:

```text
What outputs and collaboration state exist?
```

It should not answer:

```text
What execution turns happened?
```

### Cleanup And Workspace Policy

Update cleanup around the new durable object set:

- memory objects;
- buddybox files;
- artifacts;
- tasks;
- tracks;
- handoffs.

Remove cleanup concepts:

- run raw;
- run content;
- run ids;
- reserved runs.

Update workspace/git policy to ignore or track the right directories intentionally. If `buddybox` is canonical runtime state, it should follow the same policy as artifact content: generated in runtime workspace, not casually edited in source checkout.

### New Review Gates

After implementation, these searches should return no canonical code or active guidance hits except historical memo files:

```bash
rg -n "run\\.commit|run\\.validate_result|run\\.get_receipt|run\\.get_raw|binding\\." scripts buddyswitch tools framework README.md AGENTS.md
rg -n "source_run_id|run_ids|latest_run_id|current_task_id|current_track_id" scripts buddyswitch tools framework README.md AGENTS.md
rg -n "run_envelope|persist_command_hint|prepare-context|buddyswitch/content/runs|runs/raw" scripts buddyswitch tools framework README.md AGENTS.md
```

Allowed remaining hits:

- migration memos under `docs/memo/`;
- old changelog text explicitly marked as historical;
- tests that assert old paths are absent.

### Slice 1: Lock The New Contract With Failing Tests

Add tests that prove:

- `instance.json` contains no current task or current track fields.
- context preparation creates no run reservation file.
- artifact creation requires explicit `task_id`.
- artifact creation does not accept or require `source_run_id`.
- task objects contain no `run_ids` or `latest_run_id`.
- run env tools are absent from the runtime tool registry.
- binding env tools are absent from the runtime tool registry.
- no canonical state is written under `buddyswitch/content/runs/`.

### Slice 2: Simplify Instance And Context Preparation

Change launcher instance creation and validation so `instance.json` is execution identity only.

Remove current binding reads from:

- launcher instance setup;
- runtime context building;
- context service;
- tests and buddy guidance.

`context.get` should provide discoverable product state without pretending there is a selected current task.

### Slice 3: Remove Run Reservation And Commit Services

Delete or retire the run persistence path:

- reservation creation;
- reservation validation;
- reservation clearing;
- run audit writing;
- run receipt loading;
- idempotent run commit behavior;
- `run` env service actions.

Do not leave compatibility aliases.

### Slice 4: Remove Run Fields From Task And Artifact

Update object schemas:

- remove `task.run_ids`;
- remove `task.latest_run_id`;
- remove required `artifact.source_run_id`;
- add artifact `created_by`;
- add artifact `source_refs`.

Update all object creation, validation, fixtures, and tests accordingly.

### Slice 5: Make Product Writes Fully Explicit

Update tools so product writes do not depend on implicit current binding:

- `artifact.create_revision` requires `task_id`.
- `artifact.update_metadata` operates by `artifact_id` and active-buddy ownership.
- `task.create` can optionally accept `track_id` or route through `track.join`, depending on the simplest existing service boundary.
- `track.join` may create or reuse an active-buddy task, but it must not update instance binding.

### Slice 6: Add Memory

Add memory object storage and tools:

- write memory;
- read memory;
- list memory;
- update memory metadata/content;
- archive memory.

Keep memory buddy-scoped and explicit. Do not auto-ingest host execution summaries.

### Slice 7: Add Buddybox

Add buddybox file tools:

- list;
- read;
- write;
- delete.

Enforce buddy path scope. Return paths that artifacts, memory, and handoffs can reference.

### Slice 8: Rebuild Semantics, Skills, And Guidance

Update:

- env tool contracts;
- operation semantics;
- shared skills;
- buddy AGENTS files;
- README/runtime docs;
- memo references that explain old prepare/persist behavior.

The new visible rule should be:

```text
Use tools to write durable product state.
If it matters later, write artifact, memory, handoff, or buddybox.
Otherwise the execution turn is disposable.
```

### Slice 9: End-To-End Verification

Prove these main paths:

- PM creates three track notes for three tasks without run reservations.
- PM dispatches multiple sub-agents that write artifacts to different PM tasks without current binding.
- Design reads PM artifacts and writes design handoff artifact.
- Dev reads PM/design artifacts and writes implementation report.
- Test reads implementation report and writes test report.
- A buddy writes an HTML prototype to buddybox and references it from an artifact.
- A reusable decision is written to memory and later read in context.
- No run raw or run content files are produced.

## Migration Policy

This rebuild should not migrate historical run raw.

Existing development runtime state can be discarded or regenerated. If a useful old run contains durable product knowledge, extract it manually into memory, artifact, handoff, or buddybox before the refactor lands.

No automated compatibility migration should be built unless a real production data constraint appears.

## Acceptance Criteria

The refactor is complete when:

1. Durable state consists of track, task, artifact, handoff, memory, and buddybox records/files.
2. The runtime no longer writes canonical run raw, run reservations, or run audit files.
3. Instances no longer contain current task or current track fields.
4. Artifact writes require explicit product targets and do not require run ids.
5. Task records no longer contain run bookkeeping.
6. Sub-agents can independently write different task artifacts under one buddy without switching instance binding.
7. Important execution conclusions are durable only when explicitly written to artifact, memory, handoff, or buddybox.
8. Tests fail if old run, binding, or source-run paths return to the canonical tool surface.

## One-Line Version

BuddySwitch should persist buddy-managed outputs and collaboration state, not execution turns; runtime enables tools, while artifacts, memory, buddybox, tasks, tracks, and handoffs carry durable product meaning.
