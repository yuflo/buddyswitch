# Tool Layer P0/P1 Architecture Review Memo

Date: 2026-05-21
Workspace: `/Users/chen/Dev/buddyswitch/.worktrees/clean-runtime-env`

## Purpose

This memo records the reviewed P0/P1 task list after the current tool-layer补足 work and the dev buddy runtime log review.

It is meant to survive context reset. A later Codex session should be able to read this file and continue without replaying the discussion.

## Source Inputs

- `docs/bitter/2026-05-18-tool-skill-layering-principles.md`
- `docs/memo/2026-05-20-black-box-tool-runtime-memo.md`
- `docs/spec/2026-05-20-skill-tool-decoupling-alignment.md`
- `docs/memo/2026-05-20-tool-layer-semantic-contract-memo.md`
- `docs/spec/2026-05-21-artifact-context-relation-human-use-scope.md`
- `docs/spec/2026-05-21-artifact-context-relation-human-use-test-plan.md`
- `docs/spec/2026-05-21-artifact-context-relation-human-use-implementation-plan.md`
- dev buddy log for `track-wukong-west-landing`

## Review Verdict

P0 and P1 do not violate `docs/bitter` if implemented with the boundaries below.

They are consistent with the current low-coupling tool-layer architecture:

- tools remain atomic capability surfaces;
- tool contracts remain discoverable through runtime catalog and responses;
- business workflows and role SOP stay in skills, not tools;
- `tool.py` remains the public black-box entrypoint;
- tool implementations access runtime state through `ToolContext` capabilities, not raw workspace object edits;
- no new generic workflow engine, relation object, scheduler, or prompt-side schema mirror is introduced.

The main risk is scope drift. These tasks must stay focused on human/buddy orientation, discovery, feedback, and lightweight traceability.

## Bitter Principles Check

### 1. Fix The Owning Layer

The dev buddy log showed missing or unclear runtime capability:

- `context.summarize` was not enough as an entry surface;
- artifact discovery required knowing an exact artifact id;
- buddybox path rules were found by trial and rejection;
- active-buddy inbox messages could only be scanned by sender, not by simple keyword or bounded count.

`docs/bitter` says not to compensate for weak tool contracts with large prompts. P0/P1 follow that rule because they improve the lower tool contract and runtime feedback surfaces.

### 2. Keep Tools Atomic

Allowed in tool layer:

- `artifact.list` summary discovery;
- `context.summarize` compact candidate ids and attention cues;
- `buddybox.desc` capability and `logical_name` policy;
- `message.list` lightweight inbox discovery filters;
- `request` lifecycle state;
- `artifact.get` read-time derived relation summary.

Not allowed in tool layer:

- A/B collaboration SOP;
- PM/design/dev handoff script;
- long-running supervisor loop;
- workflow engine;
- scheduler/daemon;
- generic relation graph engine;
- role-specific business rules.

Those belong in skills or remain explicit user instructions.

### 3. Preserve Progressive Context Discovery

`context.summarize` should be the first entry surface. It may expose compact rows and ids for:

- candidate tracks;
- candidate requests;
- candidate artifacts;
- open comment threads;
- recent updates;
- compact message cues;
- buddybox descriptor;
- tool affordances.

It must not become `context.get`.

It must not include:

- full artifact bodies;
- full comment threads;
- full message bodies by default;
- full tool catalog schemas;
- full operation semantics;
- large history dumps.

### 4. Keep Skill/Tool Separation

Tool layer owns:

- action names;
- input schema;
- authority and permission boundaries;
- state effects and durability;
- structured success/rejection feedback;
- compact discovery affordances.

Skill layer owns:

- repeated role workflow;
- A/B coordination procedure;
- how PM/design/dev should combine tools;
- product judgment, SOP, and business context;
- when to publish an artifact or ask another buddy.

Do not encode A/B loop behavior inside message, buddybox, request, or context tools.

## Architecture Coupling Check

### Tool Independence

P0/P1 should not require sibling tool imports.

Acceptable:

- `scripts/env/tools/<tool>/tool.py` imports `env.tool_runtime.*` and local private files.
- Private implementation uses `context.repos.*` and `context.rules.*`.
- Shared read-only domain helpers derive facts from existing objects.

Not acceptable:

- `artifact` imports `message` tool package;
- `context` imports another tool implementation;
- `message` calls request/comment/artifact tools internally;
- new central business special cases in the registry;
- shared prose or skills becoming schema mirrors.

### Tool Black-Box Boundary

The public runtime entrypoint remains:

```text
env.tool
  -> registry
  -> env.tools.<tool>.tool.DEFINITION
  -> env.tools.<tool>.tool.invoke(action, args, context)
  -> ToolContext capabilities
  -> ToolResult
```

P0/P1 must not reintroduce old public module surfaces such as `contract.py`, `semantics.py`, `handlers.py`, `service.py`, or `cli.py`.

### Domain Boundary

`artifact_relations.py` is acceptable only as a read-only derived helper.

It must not own publication state, mutate publication state, or become a general relation system.

Preferred fix for the current boundary warning:

- make `artifact_relations.py` rely on `artifact_visibility` for publication relation/currentness;
- avoid duplicating publication ownership logic there;
- keep `source_refs` provenance-only.

Only whitelist `artifact_relations.py` in layer-boundary tests if the helper is explicitly read-only and still delegates publication semantics to existing visibility/publication domains.

## P0 Task List

P0 goal: close current red tests and protect architecture boundaries before adding more capability.

### P0.1 Fix Context Candidate Artifact Noise

Problem:

`context.get.artifact_summaries` and `context.summarize.candidate_artifacts` currently include historical artifacts in at least one existing test path.

Required behavior:

- `context.summarize` should default to low-noise working-surface rows.
- Include current shared material, close proof, and active-buddy-owned drafts.
- When `track_id` is provided, candidate artifacts should stay scoped to that track; owner drafts without track context should not appear in the track-filtered working surface.
- Do not show superseded history as a normal candidate by default.
- Historical readable artifacts remain discoverable through `artifact.list` and traceable through `artifact.get.relation_summary`.

Architecture boundary:

- Do not add a complex `currentness` filter DSL.
- Do not add a new artifact index/search tool.

### P0.2 Update Registry Contract Tests For `request`

Problem:

Some older expected-tool tests still omit `request`.

Required behavior:

- Treat `request` as an official shipped env tool.
- Update expected tool sets and compact affordance assertions accordingly.

Architecture boundary:

- Do not add registry business special cases.
- Runtime discovery must remain generated from `ToolDefinition`.

### P0.3 Fix `request.create` Unknown Field Rejection Order

Problem:

Payload contract tests expect unknown fields to be rejected before missing required fields.

Required behavior:

- `request.create` should report `unsupported payload fields: __unexpected_payload_field__` before checking `track_id` and other required fields.
- State must remain unchanged.

Architecture boundary:

- Keep this as local request tool payload validation.
- Do not add a central validator that duplicates per-tool schemas unless the current runtime already has one and tests require it.

### P0.4 Tighten `artifact_relations.py` Layer Boundary

Problem:

Layer-boundary tests detect publication terms in `artifact_relations.py`.

Preferred behavior:

- Keep `artifact_relations.py` read-only.
- Delegate publication relation/currentness to `artifact_visibility`.
- Avoid duplicating publication logic or direct publication ownership terms.

Architecture boundary:

- Do not create a relation object.
- Do not create relation JSON files.
- Do not build graph traversal or relation workflow engine.

### P0.5 Re-Run Full Verification

Required commands:

```bash
python3 -m pytest -q
```

Completion standard:

- full suite passes;
- any remaining failure is explicitly classified and not ignored;
- focused suites for artifact/context/relation and request/comment still pass.

## P1 Task List

P1 goal: fold selected dev buddy log findings into the human-use tool layer without adding orchestration complexity.

### P1.1 Add Compact Message Cues To `context.summarize`

Problem from log:

The dev buddy ran `context.summarize`, then still needed `context.get` and large output to orient.

Required behavior:

- Add compact message cues for the active-buddy inbox, such as recent inbox count, latest message ids, sender buddy, and reply linkage when present.
- Keep candidate rows compact.
- Include exact follow-up tool hints through existing `tool_affordances`.

Architecture boundary:

- Do not include full message bodies by default.
- Do not include full catalog or operation schemas.
- Do not turn `context.summarize` into a report generator.
- Do not encode A/B coordination or business workflow semantics in message cues.

### P1.2 Expose Buddybox `logical_name` Policy

Problem from log:

`dev/` prefix was rejected, and the agent had to discover by trial that `execution/` was usable.

Required behavior:

- `buddybox.desc` should expose clear `logical_name` policy:
  - active-buddy private scope;
  - valid logical-name shape;
  - forbidden/reserved prefixes if they exist;
  - structured reason for path rejections.

Architecture boundary:

- Do not create a shared file system.
- Do not make buddybox product-readable.
- Do not bypass artifact publication for cross-buddy materials.
- Do not prescribe business directory SOP in the tool contract.

### P1.3 Add Lightweight Inbox Discovery To Messages

Problem from log:

The dev buddy needed to inspect relevant inbox messages while orienting, but `message.list` only supports active-buddy inbox reads with an optional sender filter.

Required behavior:

- Keep `message` as direct buddy-to-buddy inbox communication.
- `message.list` supports simple filters:
  - existing `buddy` sender filter;
  - `q` keyword search over visible active-buddy inbox message text;
  - `limit`.
- Message responses include ids and existing direct-message metadata sufficient for follow-up.

Architecture boundary:

- Do not add thread/workflow/inbox engine.
- Do not bind messages to track/artifact/request ownership.
- Do not make message the durable task/request system.
- Use `request` for explicit durable cross-buddy ask/accept/block/done state.
- Use `comment` for target-scoped discussion.

### P1.4 Boundary: No Long-Running Runtime Guarantees

Problem from log:

The requested A/B supervisor loop could not be guaranteed by prompt and subagent sleep alone.

Required behavior:

- Keep tool-layer surfaces sufficient for recovery when a skill or user prompt chooses to use them:
  - request state;
  - searchable active-buddy inbox messages;
  - active-buddy private buddybox files;
  - artifact publication and backlinks.

Architecture boundary:

- Do not build a scheduler.
- Do not build a daemon.
- Do not build a workflow engine.
- Do not claim the tool layer guarantees long-running subagents.

The A/B coordination SOP belongs in skills or explicit user prompts.

## Explicit Non-Goals

Do not implement in P0/P1:

- `artifact.index`;
- `artifact.search`;
- relation tool/object;
- insight/experiment/roadmap/review/approval tool objects;
- scheduler/daemon/workflow engine;
- prompt-side schema mirror;
- skill-side payload/action tables;
- direct edits to `buddyswitch/objects/**`;
- direct edits to `buddyswitch/local/buddybox/**`;
- message/request/comment bridge object;
- complex filter DSL;
- full-text body search.

## Execution Recommendation

1. Finish P0 before P1.
2. Keep each task test-first where behavior changes.
3. After P0, run the full suite once before starting P1.
4. For P1, add focused tests around human-visible behavior:
   - `context.summarize` compactness;
   - buddybox `logical_name` policy fields;
   - message inbox `q` and `limit` behavior;
   - no full bodies or schema mirrors in compact surfaces.
5. End with full verification.

## One-Line Constraint

Improve orientation, discovery, and recoverability in the tool layer; keep business SOP and long-running coordination strategy in skills or explicit prompts.
