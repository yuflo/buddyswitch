# Multi-Codex Worktree Guide

This repo can support multiple Codex CLI sessions safely, but only if write isolation is explicit.

## Default Rule

Use one writer session per branch per worktree.

In practice:

- read-only investigation can share the main checkout
- any session that may edit files should get its own branch and its own worktree
- if two sessions will likely touch the same files, do not run them in parallel

## Repo Convention

Use project-local `.worktrees/`.

Why this is the default here:

- the repo already uses `.worktrees/`
- `.worktrees/` is already ignored in `.gitignore`
- project-local paths are easier to inspect and clean up than scattered sibling clones

## Recommended Setup

Keep the main checkout for integration and final review.

Use linked worktrees for active implementation:

```bash
git worktree add .worktrees/<branch-name> -b <branch-name>
```

Examples:

```bash
git worktree add .worktrees/task-market-research -b task-market-research
git worktree add .worktrees/task-dev-runtime-fix -b task-dev-runtime-fix
```

Then run one Codex CLI in each worktree:

```bash
cd .worktrees/task-market-research
codex
```

## When To Use A New Worktree

Create a new worktree when:

- a second Codex session may write code
- two tasks are independent enough to merge later
- you want isolated build output, index state, and uncommitted changes

Do not create a new worktree when:

- the session is only reading, reviewing, or tracing
- the work depends on the unfinished output of another active session
- both sessions are expected to edit the same files or the same branch

## Parallel Work Rules

- one feature or fix per worktree
- one active branch per worktree
- never use the same branch in two worktrees
- keep tasks independent at the file/module level when possible
- keep the main checkout clean so it can merge, test, and compare finished branches

If work is dependent rather than independent, prefer serial handoff:

1. finish the upstream task
2. merge or rebase it
3. start the next task from the updated base

## Runtime Isolation

Git isolation is not enough by itself. Watch for shared runtime state:

- local env files
- ports
- temp/runtime directories
- app data written outside the repo

For parallel app runs, parameterize ports and runtime directories per worktree.

## Cleanup

When a branch is merged or abandoned:

```bash
git worktree remove .worktrees/<branch-name>
git branch -d <branch-name>
git worktree list
```

Do not delete a worktree directory with `rm -rf`. Use `git worktree remove`.

## Practical Recommendation For This Repo

Use this operating model:

- main checkout: review, merge, verify, context panel checks
- one isolated worktree per active writer Codex session
- no parallel writers on the same task unless the task is first split into independent subtasks

This is the simplest setup that stays predictable under multiple Codex CLIs.

## Notes Behind This Guidance

- Git’s official `git worktree` docs position worktrees as multiple working directories on one repo, sharing the Git database while keeping per-worktree `HEAD`, index, and working copy separate.
- The same docs also note that Git refuses to check out the same branch in another worktree unless forced, which is a strong hint that "one branch, one worktree" should be the normal rule.
- Recent agent-oriented writeups and community discussion converge on the same pattern: use separate worktrees for truly independent parallel tasks, keep one session per worktree, and clean them up aggressively when done.

## References

- Git worktree manual: https://git-scm.com/docs/git-worktree.html
- frr.dev, parallel AI-agent workflow with worktrees: https://www.frr.dev/posts/git-worktrees-coding-agents-parallel/
- r/codex discussion on multiple agents and worktrees: https://www.reddit.com/r/codex/comments/1s09f60/multiple_agentsworktrees/
