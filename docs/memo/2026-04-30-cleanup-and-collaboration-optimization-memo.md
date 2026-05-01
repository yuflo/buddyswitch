# Cleanup And Collaboration Optimization Memo

Date: 2026-04-30
Worktree: `dev2230`

## Target

Move BuddySwitch toward collaborative product development:

- `data cleanup --buddy <buddy>` should only block when that buddy still has active execution state.
- Product work should be shared across buddies instead of trapped inside one instance workspace.

## Confirmed Optimization Items

### 1. Make `--buddy` Cleanup Scope-Aware

Current behavior:

- Cleanup checks active launcher and browser state before parsing the cleanup target.
- Any active launcher or browser blocks `data cleanup --buddy <buddy>`, even when the active work belongs to a different buddy.

Required behavior:

- Parse the cleanup target before active-session checks.
- For `--buddy <buddy>`, block only active launcher or browser state attributed to that buddy.
- Keep broad blocking for cleanup modes that touch all instance-local runtime data.

Why this matters:

- Buddy-scoped cleanup should not stop unrelated active work.
- The cleanup safety rule should match the cleanup target.

### 2. Redesign Project Collaboration Around Shared Product Work

Current behavior:

- Each product-mode instance gets its own execution worktree.
- `projects/app` source exists inside that instance workspace.
- This makes project edits instance-bound instead of collaboration-bound.

Product problem:

- BuddySwitch is a collaborative development product.
- PM, dev, design, market, and test should operate around the same product work surface.
- A project change should not live only inside the instance that produced it.

Recommended direction:

- Treat the project workspace as the shared product work surface.
- Treat each instance as execution context only: buddy binding, browser profile, Codex home, raw dumps, and runtime scratch.
- Route durable product edits through the shared project work surface selected by the active track or task.

Implementation question to settle before coding:

- Should BuddySwitch keep one shared project worktree per shared root, or one shared project worktree per active track?

Recommendation:

- Start with one shared project worktree per shared root.
- Add track-level separation only when a real workflow needs simultaneous divergent product branches.

## No-Change Items

### Keep Instance Delete Separate From Shared State Cleanup

Decision:

- `instance delete <instance-id>` remains an instance-local operation.
- Shared BuddySwitch state stays under the cleanup command path.

### Keep Run Audit Projection Model

Decision:


- `buddyswitch/content/runs/` remains durable run audit state.
- `runs/raw/` remains instance-local runtime output.

## Proposed Next Step

Implement in two tight passes:

1. Fix cleanup semantics for `--buddy`: scope-aware active checks.
2. Define the shared project work surface and update launcher behavior so product edits are collaboration-bound, not instance-bound.

Stop condition:

- Targeted cleanup tests prove unrelated active buddies no longer block `--buddy`.
- A launcher design note or test names the shared project work surface contract before changing project workspace behavior.
