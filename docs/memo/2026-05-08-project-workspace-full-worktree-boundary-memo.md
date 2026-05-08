# Project Workspace Full Worktree Boundary Memo

Date: 2026-05-08
Status: Direction memo for launcher workspace cleanup

## Problem

Product mode creates a shared project source directory at:

```text
${BUDDYSWITCH_SHARED_ROOT}/project/workspace
```

The intended product-mode contract is narrower:

```text
runtime workspace/projects/app -> ${BUDDYSWITCH_SHARED_ROOT}/project/workspace/projects/app
```

However, the current launcher implementation materializes
`${BUDDYSWITCH_SHARED_ROOT}/project/workspace` as a full repository worktree.
As a result, the project workspace contains not only `projects/app`, but also
BuddySwitch framework files and directories such as:

- `buddyswitch/`
- `tools/`
- `scripts/`
- `tests/`
- `framework/`
- `docs/`
- `AGENTS.md`
- `README.md`
- `buddyswitch-codex`

This makes the shared product source area look like a second BuddySwitch source
checkout. That is misleading because buddy instances are supposed to treat
`projects/app` as the product source mount point, not treat
`project/workspace` as another framework workspace.

## Confirmed Cause

This is not a file copy operation.

The launcher creates the project workspace with a Git worktree command:

```bash
git -C "${repo_root}" worktree add --detach "${project_workspace}" HEAD
```

That command checks out the whole BuddySwitch repository at
`${BUDDYSWITCH_SHARED_ROOT}/project/workspace`. The full directory tree is
there because Git materialized a complete worktree, not because launcher logic
explicitly copied framework files into the project source area.

The runtime then repairs the instance-local projection by replacing:

```text
${BUDDYSWITCH_SHARED_ROOT}/instances/<instance-id>/workspace/projects/app
```

with a symlink to:

```text
${BUDDYSWITCH_SHARED_ROOT}/project/workspace/projects/app
```

So the only path needed by buddy-facing product work is `projects/app`.

## Current Contract

The useful contract is:

- Product instances run from an instance runtime worktree under
  `${BUDDYSWITCH_SHARED_ROOT}/instances/<instance-id>/workspace`.
- Buddy-facing product source is addressed as relative `projects/app`.
- `projects/app` resolves to shared product source so multiple buddy instances
  can read or write the same product files according to their role boundaries.
- Shared BuddySwitch runtime state lives under
  `${BUDDYSWITCH_SHARED_ROOT}/state` and is separately projected into instance
  workspaces.

The current contract does not require buddy-facing access to a full framework
checkout under `project/workspace`.

## Why The Current Shape Is Harmful

The full worktree is operationally convenient, but it weakens the mental model.

Concrete harms:

- It blurs the boundary between BuddySwitch framework source and product source.
- It makes `project/workspace` look like a second launcher/dev checkout.
- It exposes framework directories in a location named as product workspace.
- It increases the chance that future code, docs, or agents depend on the wrong
  root.
- It conflicts with the intended instruction that sessions should use
  `projects/app`, not `${BUDDYSWITCH_PROJECT_WORKSPACE_DIR}` as a buddy input
  path.

This is a clarity problem first, not a storage problem. The current behavior may
work, but it communicates the wrong boundary.

## Optimization Goal

Make `${BUDDYSWITCH_SHARED_ROOT}/project/workspace` express only shared product
source, not the whole BuddySwitch framework checkout.

The target shape should be:

```text
${BUDDYSWITCH_SHARED_ROOT}/project/workspace/
└── projects/
    └── app/
```

Additional files should exist only if they are required for real product-source
operation, build tooling, or Git safety. Framework implementation directories
such as `buddyswitch/`, `tools/`, `scripts/`, `tests/`, and `framework/` should
not appear there by default.

## Preferred Direction

Keep the benefits of Git-managed product source, but narrow the checkout.

The likely simplest clean path is:

1. Continue using a Git worktree for `${BUDDYSWITCH_SHARED_ROOT}/project/workspace`
   so source edits remain Git-tracked and safe.
2. Configure that worktree as sparse checkout.
3. Include `projects/app/` as the primary sparse path.
4. Include only minimal extra root files if product tooling proves they are
   required.
5. Keep runtime instance workspaces unchanged from the buddy perspective:
   `projects/app` remains the only product source path they need.

This preserves the validated shared-product-source behavior while removing the
misleading full-framework checkout from the product workspace.

## Non-Goals

- Do not remove the `projects/app` product-source contract.
- Do not make each instance own a separate product source copy.
- Do not move canonical BuddySwitch state into `project/workspace`.
- Do not expose `${BUDDYSWITCH_PROJECT_WORKSPACE_DIR}` as a required buddy input
  path.
- Do not solve this by adding more prompt guidance. The filesystem shape should
  communicate the boundary directly.

## Verification Criteria

A correct cleanup should prove:

- `./buddyswitch-codex instance start --buddy <buddy>` still creates a usable
  product-mode instance.
- Instance cwd remains
  `${BUDDYSWITCH_SHARED_ROOT}/instances/<instance-id>/workspace`.
- Instance `projects/app` resolves to the shared project source.
- Cross-buddy writes to `projects/app` still land in the same shared source.
- `${BUDDYSWITCH_SHARED_ROOT}/project/workspace` no longer contains framework
  directories by default.
- Existing cleanup commands still preserve shared product source and still
  target runtime state separately.
- Tests assert the boundary in terms of `projects/app` projection and shared
  source behavior, not the presence of a full repository checkout.

## Final Decision Direction

The current full `project/workspace` checkout is an implementation artifact, not
a product requirement.

The optimization target is a narrow, Git-managed shared product workspace whose
visible surface is `projects/app` plus only proven product-source necessities.
This is the clearest filesystem model for product-mode buddy instances and
matches the documented runtime contract.
