# Runtime Layering Sweep Memo

Date: 2026-05-19
Status: audit memo only; no code changes implemented here.

## Product Summary

The PM landing-page incident is not only a PM behavior problem.

It exposed a broader runtime layering problem: some real execution contracts, context discovery
signals, tool responses, and skill/prompt guidance do not line up cleanly enough for every buddy to
choose the correct surface.

The repair should follow `docs/bitter/2026-05-18-tool-skill-layering-principles.md`: fix the layer
that owns the broken contract. Do not compensate with larger prompts, phrase triggers, SOUL-style
identity documents, or long AGENTS manuals.

## Core Diagnosis

BuddySwitch currently has several distinct contract layers:

1. Profile contract layer: declares each buddy's source access and runtime capabilities.
2. Workspace / filesystem enforcement layer: makes source workspace reads and writes actually obey
   the profile contract.
3. Env tool service / state-transition layer: mutates runtime objects and enforces object lifecycle
   rules.
4. Tool semantics layer: describes atomic capabilities, inputs, authorities, side effects, and
   failures.
5. Tool response layer: reports the actual effect of one call.
6. Context discovery layer: gives the host compact first-pass runtime facts and affordances.
7. Skill / AGENTS / prompt layer: gives short role boundaries and repeated workflow judgment.

The earlier label "P0: bottom-layer permission mismatch" was too broad. The P0 issues belong to two
different architecture layers and should be fixed separately.

## Priority Scope

### P0-A: Workspace / Filesystem Enforcement Mismatch

Layer: workspace / filesystem enforcement.

Problem:

- Env profiles declare `projects/app` as writable only for `dev`.
- PM, Design, Test, and Market declare `project.access=read-only`.
- Launcher/product-mode tests currently still expect PM relative writes into the shared
  `projects/app` workspace to succeed.

Why this matters:

- If non-Dev buddies can physically write source, no amount of AGENTS text or context hints can make
  the product contract reliable.
- This is not a tool description problem. It is real filesystem behavior.

Expected contract:

- `dev`: can write `projects/app`.
- `pm`, `design`, `test`, `market`: can read `projects/app`, cannot write it.

Recommended fix direction:

- Enforce the profile matrix in launcher/workspace projection.
- Add product-mode matrix tests proving Dev writes succeed and non-Dev writes fail.

### P0-B: Artifact State-Transition Contract Violation

Layer: env tool service / object state-transition.

Problem:

- `artifact.update_metadata` currently accepts `body`.
- That allows an active-buddy-owned artifact body to be rewritten in place.
- This may bypass the intended draft-first publication path:

```text
artifact.create_revision -> track.add_material / track.add_proof -> artifact.get
```

Why this matters:

- Published product-readable artifact content should move through revision/publication semantics,
  not silent in-place body mutation.
- This affects every buddy that writes artifacts, not only PM.

Expected contract:

- `artifact.update_metadata` should not be a hidden body rewrite path.
- Body changes should go through `artifact.create_revision`.
- Shared visibility should remain owned by `track.add_material` and `track.add_proof`.

Recommended fix direction:

- Either remove `body` from `artifact.update_metadata`, or restrict it to a clearly defined draft-only
  path with explicit response fields.
- Add tests proving published artifact bodies cannot be rewritten through metadata update.

### P1: Context Discovery Decision Surface Is Too Thin

Layer: context discovery.

Problem:

- `context.summarize` gives counts, candidate tracks, buddybox description, and generic tool
  affordances.
- It does not clearly surface enough first-pass runtime facts for each buddy.

This is not prompt guidance. It should be richer structured context: facts, permissions, visibility,
and atomic route summaries.

Missing first-pass facts:

- `active_buddy`.
- `projects/app` path and current buddy access.
- Whether the current buddy can write product source.
- Buddybox private boundary: active-buddy private, not product-readable, not cross-buddy-readable.
- Shared deliverable route:

```text
draft body:        artifact.create_revision
publish material: track.add_material
publish proof:    track.add_proof
read full body:   artifact.get
```

- PM-only track lifecycle authority for create/archive.
- Market search/evidence boundaries.
- Close-proof visibility, not only current shared material visibility.

Recommended fix direction:

- Add a compact `decision_surface` to `context.summarize`.
- Keep full schemas in `context.get` and `turn_runtime.py status`.
- Do not add phrase-routing or task-specific business rules.

### P2: Tool Semantics And Response Signals Need Cleanup

Layer: tool semantics and tool response.

Problems found:

- Task success responses say `artifact.create_revision` can "draft or publish shared artifacts",
  which contradicts the single publication path.
- `track.update_now` appends a progress update row but the success response does not clearly report
  the appended `update_id` or second state change.
- Comment rejection guidance references `track.get`, but the registered read action is `track.open`.
- Comment catalog/semantics understate real supported scope such as `artifact_section`, `anchor`,
  `mentions`, `artifact_revision_id`, and list `status`.
- Evidence catalog says readable artifact target, while service enforcement is authorship/owner
  scope.

Recommended fix direction:

- Correct tool semantics and success/rejection responses.
- Add tests that inspect state impact, persisted JSON, readability, rejection feedback, and allowed
  next actions.

### P3: Skill / Prompt Deduplication And Slimming

Layer: skill / AGENTS / prompt.

Problem:

- AGENTS files are mostly short and aligned, but some lines still act like mini tool routers.
- Shared `*-tool` skills function partly as shadow tool manuals.
- Market skills repeat browser/evidence runtime rules across multiple skills.
- Repeated runtime blocks risk drifting from the actual tool catalog and responses.

What should remain in skills:

- Workflow judgment.
- Skill-specific output quality bars.
- Domain-specific evidence standards.
- Examples and counterexamples that clarify skill scope without phrase-trigger routing.

What should move down:

- Atomic tool operations.
- Payload and return details.
- Visibility, durability, ownership, and permission semantics.
- Search/evidence backend boundaries.
- Response-field interpretation.

AGENTS position:

- Keep AGENTS short.
- Do not turn AGENTS into SOUL.md, a long PM SOP, a tool manual, or a phrase-to-tool router.
- AGENTS should keep only role orientation, startup command, non-bypassable boundaries, and
  verification/safety rules.

## Explicit Non-Goals

- Do not add landing-page phrase routing.
- Do not add rules like "if the user asks for a landing page, always use X".
- Do not encode task-specific business constraints in AGENTS or tool semantics.
- Do not create SOUL.md-style identity/personality guidance.
- Do not explain artifact publication semantics through more prompt text.
- Do not use prompt bulk to hide runtime contract gaps.

## Recommended First Repair Batch

First batch should stay narrow:

1. Fix P0-A workspace/filesystem enforcement and tests.
2. Fix P0-B artifact state-transition contract and tests.
3. Add the minimal P1 `context.summarize` decision surface and tests.

P2 and P3 can follow after the real behavior and first-pass context are correct. This preserves the
`docs/bitter` rule: repair real execution and runtime-visible contracts first, then remove prompt and
skill duplication instead of adding more of it.

## Verification Targets

Recommended tests for the first batch:

- Product-mode launcher matrix:
  - Dev relative writes to `projects/app` succeed.
  - PM, Design, Test, and Market relative writes to `projects/app` fail.
- Artifact state transition:
  - A published artifact body cannot be changed through `artifact.update_metadata`.
  - A body change requires `artifact.create_revision`.
  - Track publication remains visible through `track.open`.
  - Full artifact body remains readable through `artifact.get`.
- Context discovery:
  - `context.summarize` exposes `active_buddy`, `project.access`, source write capability, buddybox
    privacy, shared artifact/track route, PM-only track lifecycle authority, and Market search/evidence
    boundaries.
  - Proof artifacts are discoverable as shared proof context, not only material context.

## Decision

Treat the PM incident as a symptom of runtime layering drift, not as a reason to add PM prompt rules.

The architecture-safe path is:

```text
real enforcement -> state-transition contract -> context discovery -> tool semantics/response -> skill slimming
```

Prompt text is the last resort, not the repair mechanism.
