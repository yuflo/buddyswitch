# Artifact Context Relation Human-Use Scope

Date: 2026-05-21

Source handoff: `tmp/2026-05-21-tool-layer-human-use-handoff.md`

## Goal

Complete the remaining human-use tool-layer work after `request` and PM-only `comment.resolve`:

1. add `artifact.list` so a human or buddy can discover readable materials without already knowing an artifact id;
2. improve `context.summarize` so entering env or switching track gives a compact working surface;
3. add derived `relation_summary` / backlinks so an artifact can explain why it matters without adding a relation object.

This is a forward implementation target. Do not build transition adapters, compatibility aliases,
complex search systems, generic relationship engines, workflow engines, or new material object
types.

## Current Bottleneck

The current runtime can store and read artifacts, create cross-buddy requests, and resolve PM-reviewed
comment threads. The remaining human-use bottleneck is orientation and traceability:

- a user cannot ask the tool layer for a simple list of readable artifacts;
- `context.summarize` is not yet a complete first working surface for materials, comments, and recent updates;
- `artifact.get` reads content but does not show incoming request/comment/update/lineage references.

The product question is:

> If a person enters the BuddySwitch env, can they quickly understand what materials exist, what needs attention, and why a material matters?

## Forward Confirmation

The implementation must be direct and final for this iteration:

- add `artifact.list` under the existing `artifact` tool;
- extend existing `context.summarize`;
- derive relation/backlink data from existing runtime objects;
- keep `artifact` as the universal material carrier;
- keep `source_refs` provenance-only;
- keep list and context payloads compact.

Do not add temporary or transitional surfaces:

- no `artifact.index`;
- no `artifact.search`;
- no `relation` tool;
- no relation object files;
- no `insight`, `experiment`, `roadmap`, `review`, or `approval` env tool objects;
- no message/request bridge;
- no compatibility alias for old artifact discovery;
- no full-text body search;
- no AND/OR filter DSL;
- no saved views.

## Tool Architecture Requirements

The existing tool architecture remains the source of truth:

- public tool contracts live in `scripts/env/tools/<tool>/tool.py` as `ToolDefinition` and
  `ActionDefinition`;
- behavior lives in the same package's `_impl.py`;
- runtime access goes through `ToolContext` repos/domains;
- tool responses use `scripts/env/tool_runtime/results.py`;
- runtime discovery is projected by `scripts/env/tool_runtime/registry.py`;
- tests own the executable contract.

Do not add a central schema catalog, registry business special cases, or sibling-tool imports.

## Task 2: `artifact.list`

### Purpose

`artifact.list` is a read-only discovery action for readable artifact summaries.

It answers:

> What materials can I see, and which artifact id should I open?

It must not answer:

> What is the full artifact content?

Full content remains `artifact.get`.

### Filters

V1 filters are intentionally simple:

```text
track_id
created_by
template
status
q
limit
```

Filter rules:

- `track_id`: restrict to readable artifacts connected to that track.
- `created_by`: restrict by artifact creator buddy id.
- `template`: one of `brief`, `proposal`, `design`, `decision`, `proof`, `note`.
- `status`: one of `draft`, `published`, `archived`.
- `q`: case-insensitive substring match over `title` and `summary` only.
- `limit`: positive integer, default 20.

All filters apply after artifact read visibility. A private draft owned by another buddy must never
appear because a filter matched it.

Do not support `relation` or `currentness` filters in v1. Return those as fields first.

### Summary Row

`artifact.list` returns rows under `artifacts`. Each row is summary-only:

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
  "updated_at": "2026-05-21T00:00:00+08:00"
}
```

Forbidden in list rows:

- `body`;
- full comment thread content;
- full relation graph traversal;
- private buddybox content.

## Task 3: `context.summarize` Human Entry Surface

### Purpose

`context.summarize` is the compact orientation tool used at the beginning of a product-mode turn:

- after entering an instance;
- after switching active buddy;
- after selecting or filtering to a track;
- before deciding whether to open artifacts, requests, comments, or track details.

It answers:

> Where am I, what needs attention, what materials exist, and what should I open next?

It is not a deep-read tool. `context.get`, `artifact.get`, `request.get`, `comment.list`, and
`track.open` remain the detailed follow-up tools.

### Compact Return

`context.summarize` should return:

- `current_context_summary`: counts and readiness booleans;
- `candidate_tracks`: compact track rows;
- `candidate_requests`: compact visible request rows;
- `candidate_artifacts`: summary-only artifact rows, no body;
- `open_comment_threads`: unresolved thread summaries, not full threads;
- `recent_updates`: compact track update rows;
- `buddybox_desc`: existing private workspace descriptor;
- `tool_affordances`: compact runtime affordances, no full schemas;
- `decision_surface`: compact readiness and role information.

The existing dirty worktree already has `candidate_requests`. This task finishes the rest of the
human entry surface.

### Compact Comment Thread Row

`open_comment_threads` rows should be thread-level:

```json
{
  "thread_id": "comment-root",
  "target_type": "artifact",
  "target_id": "art-example-r1",
  "latest_comment_id": "comment-reply",
  "latest_by_buddy": "test",
  "open_comment_count": 2,
  "updated_at": "2026-05-21T00:00:00+08:00"
}
```

Do not include full comment content in `context.summarize`. Use `comment.list` for the thread body.

### Recent Update Row

`recent_updates` rows should be small:

```json
{
  "track_id": "track-example",
  "update_id": "upd-example",
  "kind": "progress",
  "summary": "Implemented main path.",
  "by_buddy": "dev",
  "ref_count": 1,
  "created_at": "2026-05-21T00:00:00+08:00"
}
```

Keep only the latest rows within `limit`.

## Task 4: Derived `relation_summary` / Backlinks

### Purpose

`relation_summary` explains artifact context without adding a new relationship system.

It answers:

> Where is this artifact published, what supersedes it, and which existing requests, comments, source refs, or track updates point to it?

### Surface

Add `relation_summary` to `artifact.get` responses.

Add lightweight relation counts to `artifact.list` rows only if they remain cheap and simple:

```json
{
  "incoming_source_ref_count": 1,
  "target_request_count": 1,
  "result_request_count": 1,
  "track_update_ref_count": 1,
  "comment_count": 2
}
```

Do not add full incoming row lists to `artifact.list`.

### Relation Summary Shape

`artifact.get` should include:

```json
{
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
    "source_ref_by_artifacts": [
      {"artifact_id": "art-research-r1", "title": "Research", "created_by": "market"}
    ],
    "target_ref_by_requests": [
      {"request_id": "req-design", "track_id": "track-example", "status": "open"}
    ],
    "result_ref_by_requests": [
      {"request_id": "req-dev", "track_id": "track-example", "status": "done"}
    ],
    "track_update_refs": [
      {"track_id": "track-example", "update_id": "upd-abc", "kind": "progress"}
    ],
    "comment_ids": ["comment-root", "comment-reply"]
  }
}
```

Every incoming row must be permission-filtered. If the active buddy cannot read the referencing
object, that row is omitted.

### Ref Semantics Boundary

Keep existing ref semantics separate:

- `artifact.source_refs`: provenance-only metadata;
- `request.target_refs`: what the request asks the recipient to act on;
- `request.result_refs`: what completion produced;
- `track.update.refs`: evidence/material refs attached to timeline updates.

Do not turn `source_refs` into a dependency graph or required reading path.

## Definition Of Done

- `artifact.list` is discoverable through runtime registry, schemas, `context.get`, and compact
  affordances.
- `artifact.list` returns readable summary rows only, with simple filters and no `body`.
- `context.summarize` includes candidate artifacts, candidate requests, open comment threads, recent
  updates, and compact next-action affordances.
- `artifact.get` includes permission-filtered derived `relation_summary`.
- No new material or relation objects are introduced.
- Existing request/comment behavior remains green.
- Focused and broader relevant tests pass.

