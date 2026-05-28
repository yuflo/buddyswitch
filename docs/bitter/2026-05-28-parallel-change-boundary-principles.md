# Parallel Change Boundary Principles

Date: 2026-05-28
Status: distilled principle note from merge-conflict architecture research and BuddySwitch parallel development needs.

## Core Lesson

Frequent merge conflicts are usually not a Git problem.

They are architecture feedback.

If many developers repeatedly need to edit the same router, registry, schema, prompt, runtime file,
global store, type file, changelog, or service, the project has concentrated change in the wrong
place.

Do not solve that first with more merge process. Move the change boundary.

## What Goes Wrong

Parallel work becomes slow when product changes are forced through shared choke points:

- one central registry where every feature adds an entry;
- one large service where unrelated object behavior accumulates;
- one global type or constants file that becomes the default landing zone;
- one route, prompt, manifest, or tool catalog file edited by every capability;
- one generated or lock-like file manually edited by several branches;
- one technical-layer folder where every feature crosses the same files;
- one broad refactor mixed into normal feature work.

The visible symptom is a merge conflict.

The deeper failure is that unrelated product work is no longer structurally independent.

## Non-Negotiable Rule

High-churn shared files are architecture debt.

When a file is frequently edited by unrelated changes, first ask:

```text
Why do these changes need to meet here?
```

If the answer is only "because this is the central list", "because this is the shared util", or
"because all actions go through this file", the design is probably wrong.

Prefer splitting the change surface over teaching contributors to rebase more carefully.

## Boundary Design Rules

### Prefer Product Slices Over Technical Layers

Routine work should usually land inside one owning product slice or runtime object boundary.

For BuddySwitch, that means changes should normally stay inside boundaries such as:

- `artifact`;
- `track`;
- `task`;
- `message`;
- `comment`;
- `buddybox`;
- one specific buddy or shared skill;
- one specific tool package.

Do not split ordinary feature work as "one person changes storage, one changes service, one changes
tool schema, one changes tests" unless the work is truly infrastructure-wide. That creates artificial
coordination.

### Turn Central Lists Into Local Fragments

Manual central lists become conflict factories.

Prefer:

```text
per-module manifest + generated index
per-feature route file + generated route table
per-change changelog fragment + release-time changelog generation
per-tool action definition + registry discovery
per-object test fixture + shared helper only when repeated need is real
```

Do not preserve a shared file merely because it feels simpler today. If every contributor must touch
it, it is not simple operationally.

### Keep Public Contracts Small And Stable

A module boundary is real only when consumers can use it without importing internals.

Each owning module should expose a small public contract and keep high-churn implementation details
private. Cross-module imports into sibling internals are a boundary leak, even if the directory names
look modular.

For BuddySwitch runtime work:

- tool callers should consume tool catalog and response semantics, not private `_impl.py` details;
- sibling object repos should not import or mutate each other;
- cross-object rules should live in explicit domain operations;
- skills should not copy runtime payload schemas or dispatch internals.

### Shrink The Shared Zone

Files named `utils`, `types`, `context`, `runtime`, `registry`, `manager`, or `service` deserve
skepticism when they grow.

They often hide missing ownership.

Before adding to a shared file, check whether the code belongs in the module that owns the product
behavior. Shared code should be earned by repeated stable use, not used as the default place to put
code that does not yet have a clear home.

### Serialize Mechanical Global Changes

Formatting, renames, moves, import rewrites, generated-file changes, and broad mechanical migrations
should not be mixed with feature PRs.

Do them as separate short-lived changes:

1. announce the touched boundary;
2. apply the mechanical change with a script or deterministic command;
3. verify behavior did not change;
4. merge quickly;
5. have feature branches rebase onto the new structure.

Parallelizing a global rename is fake speed. It moves cost into every other branch.

## Process Rules That Support The Architecture

### Reserve Known Hotspots

Some files are legitimately shared: external schemas, public contracts, launcher entrypoints, runtime
discovery, and core storage boundaries.

When a task must touch one of them, make that explicit before implementation. Serialize the hotspot
or split the work so only one change modifies the shared contract while the rest happens behind local
boundaries.

### Keep One Intent Per Change Set

Do not mix:

- feature behavior;
- broad rename or move;
- formatting;
- unrelated cleanup;
- public contract changes;
- test harness restructuring.

Mixed-intent changes increase both text conflicts and semantic conflicts. They also make rollback and
review harder.

### Measure Conflict Hotspots

When collaboration slows down, inspect the files, not only the people.

Useful signals:

- files most often touched by PRs;
- files touched by the most different contributors;
- files repeatedly involved in merge conflicts;
- files that require frequent rebase after unrelated work lands;
- files where review delays cluster;
- files where tests often break after text-clean merges.

Repeated hotspots should produce architecture work: split, generate, move ownership, narrow contracts,
or delete stale central paths.

## Warning Signs

Stop and inspect boundaries if these appear:

- "Every feature needs to add one more case to this switch."
- "Just add it to the shared registry."
- "Put the type in the global types file for now."
- "This utility is used by everything."
- "This PR is mostly feature work but also moves many files."
- "The conflict is only in the index file again."
- "Two unrelated features both need to edit the same service."
- "The tests pass alone, but branches keep breaking when combined."

These are not normal collaboration friction. They are signs that product change has been routed
through a shared choke point.

## BuddySwitch Implication

BuddySwitch should keep moving toward independently changeable runtime object and tool boundaries.

The preferred shape remains:

```text
SKILL -> Tool Contract -> Service -> Domain Ops -> Object Repo -> JSON / Files
```

This layering only helps if each layer keeps its ownership:

- skills own workflow judgment, not runtime schemas;
- tool contracts own action semantics, not object storage;
- services adapt requests and responses, not sibling object rules;
- domain ops own cross-object rules;
- repos own one object family only.

When a new change repeatedly crosses these boundaries, do not add compatibility wrappers first.
Re-check whether the boundary is placed correctly.

## General Principle

The best merge-conflict reduction strategy is not asking developers to coordinate more often.

It is designing the code so ordinary product changes do not need to coordinate at all, while real
shared contracts are small, explicit, owned, and verified.

Conflict frequency is a product architecture metric.
