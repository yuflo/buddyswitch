---
name: finish-dev-change
description: Use when Dev has implemented and verified a change and must present valid completion paths for the current repo state.
---

# Finish Dev Change

## Purpose
- Close out a verified change without crossing workspace ownership or git safety boundaries.

## Use when
- Implementation and verification are complete and Dev needs to present the valid next steps.

## Do not use when
- Fresh verification has not been run yet.

## Inputs
- Repo state, branch or worktree state, changed files, fresh verification evidence, risks, and durable report status.
- Runtime contract references: `context.get.tool_catalog`, `"$BUDDYSWITCH_PYTHON" scripts/turn_runtime.py status`.

## Steps
1. Re-run fresh verification before presenting completion options.
2. Detect whether the checkout is a normal branch, linked worktree, or detached HEAD.
3. Summarize changed files, verification, risks, and durable reports.
4. Offer only valid next paths for the current state: pull request, keep the branch/worktree, merge when safe and explicitly chosen, or discard with explicit confirmation.
5. If the workspace is launcher-owned or externally managed, stop at reporting and do not delete launcher-owned workspace content.
6. Do not merge into main without explicit user choice.

## Outputs
- Completion summary with repo state, valid finish options, verification, and risks.

## Guardrails
- Do not clean or delete workspace content automatically.
- Do not present merge as the default when the branch state is unclear.
- Do not hide residual risk behind a completion summary.

## Stop Conditions
- Fresh verification is blocked or repo state cannot be identified safely.

## Verification
- Completion note includes fresh verification, repo state, valid options, and residual risk.

## Examples
- In a linked worktree, present pull request and keep as normal options, plus discard only with explicit confirmation.

## Counterexamples
- Merge into main immediately or delete the worktree without an explicit decision.
