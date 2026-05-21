# Tool Layer P0/P1 Forward Scope

Date: 2026-05-21

Source memo: `docs/memo/2026-05-21-tool-layer-p0-p1-architecture-review.md`

## Goal

Complete the reviewed P0/P1 tool-layer work in `clean-runtime-env` without polluting `main`.

The work has two phases:

1. P0: close current runtime/test red points and protect the architecture boundary.
2. P1: add small human-use discovery improvements exposed by the dev buddy log.

This is a complete task. Do not implement only a subset of P0 or only a subset of P1 unless a real product-semantics blocker is raised to the user first.

## Current Bottleneck

The tool layer now has request/comment closure, artifact listing, context candidate artifacts, and derived artifact relation summaries. The remaining bottleneck is not missing large workflow capability. It is the quality of small runtime contracts:

- full-suite tests are not green;
- `context.summarize` / `context.get` expose too much artifact history in the working surface;
- some registry contract tests still reflect old tool sets or old router behavior;
- `request.create` does not reject unknown fields before required-field validation;
- `artifact_relations.py` touches publication vocabulary in a way that trips the layer-boundary guard;
- `context.summarize`, `buddybox.desc`, and `message.list` still need small discovery improvements for a human or buddy entering env.

## Forward Confirmation

Use the forward path:

- make direct code/test changes in the current runtime;
- remove or replace stale expectations;
- keep one runtime contract path;
- keep tests as the executable boundary.

Do not build transition or compatibility paths:

- no old/new tool registry bridge;
- no message/request/comment bridge object;
- no alias action for compatibility unless existing router normalization already defines it;
- no hidden fallback search system;
- no prompt-side schema mirror.

## Architecture Boundary

The implementation must preserve:

- `env.tool -> registry -> env.tools.<tool>.tool.DEFINITION -> invoke(action, args, context) -> ToolContext -> ToolResult`;
- public `tool.py` files import only `env.tool_runtime.*` and local private files;
- tool private implementations do not import sibling tool packages;
- tool contracts are projected from `ToolDefinition`;
- runtime state is accessed through `ToolContext` capabilities and repos/rules behind it;
- skills own business workflow and role SOP.

Do not introduce:

- scheduler;
- daemon;
- workflow engine;
- generic relation graph engine;
- relation object;
- insight/experiment/roadmap/review/approval tool objects;
- complex filter DSL;
- full-text artifact body search;
- message ownership bindings to track/artifact/request.

## P0 Scope

### P0.1 Context Candidate Artifact Noise

`context.summarize` and `context.get.artifact_summaries` should show the active working surface, not all readable artifact history.

Required behavior:

- include current shared track material;
- include current close proof;
- include active-buddy-owned drafts when no `track_id` filter is provided;
- exclude superseded/history rows from context candidate surfaces by default;
- exclude archived-track artifacts;
- when `track_id` is provided, keep candidate artifacts scoped to that track and do not include owner drafts without track context;
- keep historical readable artifacts discoverable through `artifact.list` and traceable through `artifact.get.relation_summary`.

### P0.2 Registry Contracts For `request`

`request` is now an official shipped env tool.

Required behavior:

- expected tool sets include `request`;
- compact affordances include `request`;
- registry projection does not require central business special cases;
- dynamic tool package discovery still works.

### P0.3 `request.create` Unknown Field Order

Required behavior:

- `request.create` rejects unsupported payload fields before it checks required fields such as `track_id`;
- the rejection contains the unsupported field name;
- state remains unchanged.

### P0.4 `artifact_relations.py` Layer Boundary

Required behavior:

- keep `artifact_relations.py` read-only;
- do not mutate publication state there;
- delegate publication relation/currentness to `artifact_visibility`;
- avoid duplicating publication ownership logic;
- keep `source_refs` provenance-only.

If a test whitelist is still required, it must describe `artifact_relations.py` as a read-only derived helper and must not weaken the publication write-boundary guard.

### P0.5 Full Verification

Required behavior:

- focused suites pass;
- full `python3 -m pytest -q` passes;
- no failure is ignored or classified away without user confirmation.

## P1 Scope

### P1.1 `context.summarize` Message Cues

Add compact message cues for the active-buddy inbox.

Required behavior:

- expose recent inbox count;
- expose latest message ids;
- expose sender buddy;
- expose reply linkage when present;
- do not include full message bodies by default;
- do not include sent messages unless they are also in the active buddy's inbox;
- do not encode A/B workflow semantics.

### P1.2 `buddybox.desc` `logical_name` Policy

Make buddybox path rules visible without prescribing business directory SOP.

Required behavior:

- `buddybox.desc` exposes `logical_name_policy`;
- the policy states that names are relative to active-buddy private root;
- the policy states that absolute paths are invalid;
- the policy states that `..` traversal is invalid;
- the policy states that buddy-prefix names such as `dev/...`, `pm/...`, or another manifest buddy prefix are invalid;
- the policy gives generic valid examples only, such as `notes/todo.md`;
- the policy does not recommend role workflow directories such as `coordination/` or `execution/`;
- rejection feedback remains structured and includes why a logical name was blocked.

### P1.3 `message.list` Inbox Discovery

Keep `message` as direct buddy-to-buddy inbox communication.

Required behavior:

- `message.list` still returns only active-buddy inbox messages;
- keep existing `buddy` sender filter;
- add `q` keyword filter over visible active-buddy inbox message text;
- add `limit` positive integer filter;
- apply visibility before `q` and `limit`;
- do not add `track_id`, `artifact_id`, `request_id`, `refs`, `status`, `read_at`, `recipients`, or `broadcast` to message storage;
- do not add message thread/workflow/inbox engine.

## Explicit Non-Goals

Do not implement:

- `artifact.index`;
- `artifact.search`;
- relation tool/object;
- insight/experiment/roadmap/review/approval tool objects;
- scheduler/daemon/workflow engine;
- prompt-side schema mirror;
- skill-side payload/action tables;
- message/request/comment bridge object;
- message binding to product objects;
- complex filter DSL;
- full-text body search.

## Definition Of Done

The task is complete only when:

- P0 and P1 required behaviors are implemented;
- architecture boundary tests pass;
- compact surfaces do not leak full bodies or schemas;
- message remains direct inbox communication;
- buddybox remains active-buddy-private;
- full relevant verification passes, including `python3 -m pytest -q`;
- final review finds no violation of `docs/bitter`, black-box tool runtime, or skill/tool decoupling.
