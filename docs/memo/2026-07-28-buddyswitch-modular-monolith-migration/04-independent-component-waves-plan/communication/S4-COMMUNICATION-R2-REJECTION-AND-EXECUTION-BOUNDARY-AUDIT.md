# S4 Communication R2 Rejection And Cleanup Execution-Boundary Audit

> Audit state: `COMPLETE`
> Reviewed packet: `BS-MM-S4-COMMUNICATION-R2-20260803-01`
> Disposition: `REJECTED — FIX_AFTER_FINAL REQUIRED`
> Date: 2026-08-03

## 1. Decision

R2 correctly repaired Communication-owned recursive Message discovery, role
selection, retired-state cleanup, index projection and stable leaf-symlink
handling. Its returned source/runtime identities and passing replacement FINAL
were valid.

Acceptance is nevertheless blocked because the generic destructive effect
owner does not enforce the safety and result-truth invariants that R2 claimed.
Planner validation is stale information, not authority to delete.

## 2. Root cause and responsibility

The primary delivery failure was coordinating-side proof design. R2 stated that
the generic boundary must reject symlinked parents, but its required proof did
not explicitly mutate the filesystem between `build_cleanup_plan` and
`execute_cleanup_plan`. The executor proved planner rejection for an already
present symlink and reasonably treated that as satisfying the ambiguous
boundary statement. Its secondary review failure was claiming terminal safety
without tracing the actual delete helper.

The code-level root cause predates R2:

```text
discover/validate -> raw path plan -> execute without revalidation -> unlink/rmtree
```

Safety is owned by the planner while the irreversible effect is owned by the
executor. That violates one semantic owner and terminal-truth rules.

## 3. Read-only audit evidence

The hub reproduced the returned R2 identity and installed runtime, then used
isolated temporary roots only. No product source, user state or runtime state
was changed.

| Boundary | Phase change | Observed R2 effect | Required effect |
|---|---|---|---|
| state-relative path | replace a regular parent with a symlink after plan | external child deleted; path reported deleted | external child preserved; path skipped and warned |
| instance-private external path | replace `private/notes` with an external symlink after plan | actor-private owner rejection fell back to raw absolute deletion; external child deleted | no fallback after owner rejection; external child preserved |
| missing path | remove the selected file after plan | no filesystem effect, but `deleted_paths` and `deleted_count` reported deletion | absent from actual deletion result; warning records stale plan |
| selected parent and child | planner order places parent before child | parent recursively removes both; executor then reports a no-op child deletion | execute deepest-first or otherwise prove every reported effect |

The stable leaf-link scenario remains valid: deleting the link entry without
following its target is required. The defect is trusting a raw planned path at
effect time, not permitting leaf-link unlink itself.

## 4. Complete affected execution surface

The execution owner has four coupled responsibilities that must be corrected
together:

1. validate state and shared roots immediately before destructive effects;
2. guard every relative and instance-private external path at effect time;
3. never turn an actor-private owner rejection into raw absolute deletion;
4. project only effects that the current cleanup execution actually caused.

Communication Private remains the single owner of Message discovery. No
Communication Public, Web, Daemon, Tool, schema, command or composition design
changes are required.

## 5. Chosen design

Keep the current preview/execute split and current plan/result shapes. At
execution time, the generic cleanup owner derives each target from its trusted
boundary root, rejects a symlinked root or parent and permits only the final
leaf symlink to be unlinked. Instance-private paths are re-derived beneath the
current shared root and regular files continue through the actor-private
repository boundary; a rejection never falls back to unguarded absolute
deletion.

Execute nested paths deepest-first so child and parent entries have real,
attributable effects. Missing or newly unsafe entries are skipped, warned and
excluded from `deleted_paths`, `deleted_count` and index IDs. Unexpected I/O
errors continue to fail rather than being converted into success.

This is execution-time revalidation, not a claim of hostile-concurrency atomic
filesystem security. The runtime lock and active-instance gate remain the
coordination boundary. Introducing platform-specific `openat`/directory-fd
infrastructure is outside this repair.

## 6. Quality ratchet

The repository testing review rule now requires any destructive two-phase
boundary to change the relevant state between planning and execution and prove
both the external effect and the reported result. Planner-only rejection is no
longer acceptable evidence for executor safety.
