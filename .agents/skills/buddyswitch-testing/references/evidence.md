# Verification Evidence

Evidence is reusable only when it still proves the current claim on an equivalent
source state, command, and material environment.

## Record

```text
Verification Evidence
- state: <RED | GREEN | IMPACT | MILESTONE | FINAL | FIX_AFTER_FINAL>
- source: <repo root, HEAD, tracked patch identity, non-ignored untracked identity>
- command: <canonical command and explicit targets>
- environment: <material runner and toolchain identity>
- result: <exit status, summary, duration, cleanup/residual state>
- proves: <exact claim and direct boundaries>
- valid-for: <current worktree or frozen SHA>
- residual-risk: <none or explicit risk>
```

Claim scope and source identity are different. A task may exclude unrelated dirty
changes from its claim, but the command still ran in the complete worktree state.

## Source Identity

- For a frozen commit, record repository root and commit SHA.
- For a dirty worktree, record HEAD, tracked patch identity, and every non-ignored
  untracked file visible to the command.
- Within one uninterrupted turn, direct comparison showing no intervening change is
  sufficient.
- For cross-turn or cross-agent reuse, attach identity strong enough for the next
  actor to establish equivalence. If equivalence cannot be established, rerun the
  narrowest required proof rather than a broad suite.

## Reuse Matrix

| Current condition | Decision |
|---|---|
| Read-only review; repository state unchanged | Reuse |
| Same source, command, environment, clean result, and claim breadth | Reuse |
| New claim is broader than recorded proof | Run only the missing scope |
| Relevant source/test/fixture/contract changed | Invalidate affected scope |
| Runner, dependency, or material environment changed | Invalidate prior execution evidence |
| Pure prose outside executable contracts changed | Preserve code evidence; verify prose separately |
| Identity is unknown or incomplete | Do not assume; rerun narrow proof |
| Failure, flake, timeout, or cleanup residual occurred | Supersede earlier pass and diagnose |

## FINAL Sensitivity

FINAL evidence is bound to the frozen candidate. Any executable, test, fixture,
runner, dependency, generated executable artifact, merge, or rebase change that
alters the candidate invalidates FINAL. During repair, run exact and affected proof;
run final once after the candidate freezes again.

