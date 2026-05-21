# Request And PM Comment Resolution Scope

Date: 2026-05-21

## Goal

Add the smallest runtime-backed collaboration closure needed for a lean five-buddy product iteration:

- a durable `request` object/module with one `request` env tool for cross-buddy work requests;
- one PM-only `comment.resolve` operation for reviewed discussion closure.

This is a forward implementation target. Do not build transition adapters, compatibility paths,
legacy `handoff` surfaces, a workflow engine, an approval system, a review object, or `comment.reopen`.

## Terminology

BuddySwitch uses these layers:

```text
object/module -> tool -> action/operation
```

`request` is the object/module and also the env tool name. Its actions are operations under that
tool, matching the existing `track.create`, `artifact.create_revision`, and `comment.add` pattern.

Examples:

```text
request.create
request.list
request.get
request.accept
request.block
request.complete
request.cancel
```

These action names are `ActionDefinition.name` values inside `scripts/env/tools/request/tool.py`.
They are not separate architectural layers.

## Current Code Findings

The current tool architecture is black-box and definition-driven:

- `scripts/env/tools/<tool>/tool.py` is the only public tool entrypoint.
- `ToolDefinition` and `ActionDefinition` in `scripts/env/tool_runtime/definition.py` are the
  public contract source.
- `scripts/env/tool_runtime/registry.py` discovers tool packages and projects catalog semantics
  from `ToolDefinition`.
- Tool implementations route through `ToolContext`; tool packages must not directly own runtime
  state roots or import sibling tools.
- Canonical success/rejection response shape is owned by `scripts/env/tool_runtime/results.py`.

Existing related surfaces:

- `task` is active-buddy private work state. It is not a cross-buddy request.
- `message` is immutable direct inbox text. Its repo explicitly rejects status/read/track/artifact
  fields, so it should not be stretched into structured work requests.
- `comment` already persists `status=open|resolved`, but the tool only exposes `add` and `list`.
- `context.get`, `context.summarize`, workspace projection, manifest permissions, shared skills,
  and role guidance must be updated if `request` becomes a real runtime object.

## Object Targets

### `request`

Purpose: represent one explicit cross-buddy request for work, review, validation, or response on a
track. It carries the minimum structured state needed to know whether the recipient accepted,
blocked, completed, or the requester canceled the request.

The object is product-readable runtime state, not private task state.

Minimum fields:

```json
{
  "id": "req-example",
  "track_id": "track-example",
  "from_buddy": "pm",
  "to_buddy": "dev",
  "title": "Implement approved scope",
  "summary": "Build the scoped flow from the current design artifact.",
  "target_refs": [{"type": "artifact", "id": "art-design-r1"}],
  "status": "open",
  "blocker": null,
  "result_refs": [],
  "created_at": "2026-05-21T00:00:00+08:00",
  "updated_at": "2026-05-21T00:00:00+08:00",
  "accepted_at": null,
  "blocked_at": null,
  "completed_at": null,
  "canceled_at": null
}
```

Allowed statuses:

```text
open
accepted
blocked
done
canceled
```

Allowed transitions:

```text
open -> accepted
open -> canceled
accepted -> blocked
accepted -> done
accepted -> canceled
blocked -> accepted
blocked -> done
blocked -> canceled
```

No assignment queue, WIP engine, SLA, priority system, or multi-recipient broadcast is included.

### `comment.resolve`

Purpose: PM review closure for an existing comment thread.

Rules:

- Only active buddy `pm` can resolve.
- Resolving means PM reviewed the thread and decided the feedback is addressed, accepted as a
  non-blocker, or no longer relevant to the current iteration.
- Non-PM buddies can add comments with evidence or responses; they cannot close discussion.
- Resolving one `comment_id` resolves the entire thread containing that comment.
- There is no `comment.reopen` in this task. If a problem remains, a buddy adds a new comment.

Resolution fields added to each resolved comment row:

```json
{
  "status": "resolved",
  "resolved_by": "pm",
  "resolved_at": "2026-05-21T00:00:00+08:00",
  "resolution_summary": "Reviewed by PM; addressed in art-dev-r1."
}
```

## Required Runtime Surfaces

Implementing this task must update:

- request repo/domain/tool package;
- comment repo/domain/tool package for PM-only resolution;
- `ToolContext` repo/domain access;
- runtime file roots and directory creation;
- manifest permission validation and buddy permissions;
- shared `request-tool` skill and existing `comment-tool` skill;
- role contracts and runtime buddy guidance;
- `context.get`, `context.summarize`, and `context.list_sources`;
- workspace projection contract and projection builder;
- architecture, schema, semantic, response, integration, manifest, profile, skill, and projection tests.

## Non-Goals

- No `handoff` object or compatibility alias.
- No `review` object.
- No `approval` object.
- No `comment.reopen`.
- No message status/read receipts.
- No task visibility changes.
- No workflow engine.
- No generic permission language.
- No central schema catalog.
- No registry per-tool business special cases.

## Definition Of Done

- `request` appears in runtime discovery, CLI, context, manifest permissions, skills, role guidance,
  and workspace projection.
- `request` create/list/get/accept/block/complete/cancel behavior is covered by functional tests.
- `comment.resolve` is discoverable, PM-only, thread-scoped, durable, and covered by functional tests.
- Existing message, task, comment add/list, track/artifact publication, context, and clean-runtime
  tests remain green.
- Static checks reject legacy `handoff`, compatibility adapters, and old public tool files.
