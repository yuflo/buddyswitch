# S5 C1 ToolHost Goal Packet

## Packet identity

- Packet ID: `BS-MM-S5-TOOLHOST-R1-20260804-01`
- Stage: S5 / C1 ToolHost
- Status: `READY — SINGLE EXECUTION AUTHORITY`
- Predecessor product checkpoint: `a61951fe63ecc4dd8cf03b8c0256fbfb11d12227`
- Required runtime source digest:
  `0f9c35e6a6431bd43974026ec41ea541babce6a63809e49fb78b108b1099af9b`

No earlier S5 packet exists. This packet is consumed after one accepted return
or any stop/replanning return; it is never resumed implicitly.

## Goal

Create the single current Foundation ToolHost: every current Tool is explicitly
selected once by application composition; the host owns only generic Tool
contracts, dispatch, feedback and narrow runtime facts; Role policy is injected,
dynamic discovery and broad context bags are gone, every consumer uses the final
owner, and observable Tool behavior is preserved.

If the session uses persistent goals, create exactly this objective and mark it
complete only after the return packet is fully assembled. Mark it blocked only
under the product's repeated-blocking rule, not merely on the first valid stop.

## Required reading

Read completely, in order:

1. root `AGENTS.md`;
2. `.agents/skills/buddyswitch-testing/SKILL.md` and its routed references;
3. `../README.md`;
4. `../S5-SOURCE-REFRESH-AND-CUTOVER-BLUEPRINT.md`;
5. `S5-TOOL-HOST-SOURCE-AND-CONSUMER-SNAPSHOT.md`;
6. `S5-TOOL-HOST-CONSUMER-MANIFEST.md`;
7. `S5-TOOL-HOST-IMPLEMENTATION-PLAN.md`;
8. `S5-TOOL-HOST-READY-REVIEW.md`.

Repository facts and the public test runner outrank illustrative memo text.

## Starting-state admission

Before editing:

1. inspect the current `fea-tool` worktree state supplied by the user; do not
   pull, reset, rebase or replace it;
2. record HEAD, tracked patch, index and untracked identities;
3. require no unreviewed non-memo source change from the predecessor product
   checkpoint;
4. verify installed runtime source digest equals the required digest;
5. regenerate ToolHost consumer representations named in the manifest;
6. prove no attributable test process/root is already live.

The hub preparation memos are expected changes after the predecessor product
commit. Do not revert, rewrite or stage them. If executable source differs or a
new consumer changes the owner/scope model, stop `REPLANNING REQUIRED`.

## Execution authority

Implement the coherent C1 blocks in
`S5-TOOL-HOST-IMPLEMENTATION-PLAN.md`. You own local implementation choices,
exact valid test-target discovery and owner-correct repair within the classified
write set. You do not need hub permission for a mechanically equivalent valid
runner target or a direct in-scope defect fix.

You do need to stop before:

- changing component domain/state/Public semantics;
- redesigning Web, cleanup, Browser, Daemon host, Runtime Broker host or RoleHost;
- changing canonical data/state paths;
- adding compatibility, fallback, discovery, DI or service-split machinery;
- touching master migration truth, commits, pushes or unrelated work;
- repairing an ambiguous or out-of-scope test failure.

## Required implementation outcome

At return, all of the following are true:

1. generic ToolHost lives only under `foundation/tool_runtime/**`;
2. generic Daemon client lives at `foundation/daemon/client.py`;
3. current Role policy lives at `runtime_support/role_auth.py` and is explicitly
   supplied to ToolHost by application composition;
4. registry is explicit-only and fail-fast for invalid/duplicate registration;
5. all eight current Tool IDs/actions come from application registrations;
6. ToolContext exposes no domain/repository/private-file/browser bag;
7. Artifact and Evidence use the two named narrow replacements;
8. all production, test, subprocess, generated, installed and guidance
   consumers use the final owner;
9. old ToolHost/package paths and dynamic discovery are absent;
10. native MCP, Broker, authorization, gate, result and cleanup behavior remain
    exact.

## Proof and runtime discipline

Use only:

```text
./buddyswitch-test focused <valid files/nodeids/runner tiers>
./buddyswitch-test full
```

Follow the candidate cycle in the implementation plan. Do not copy a test
directory target without validating it against the runner. Do not rerun an
unchanged failed full. Do not treat a changed/repaired/reprovisioned candidate
as the same frozen identity.

After each coherent source mutation, run the installed-runtime
activation/verification mechanism defined by the current repository before the
next public-runner command. Do not invent a launcher subcommand. Record source
and distribution digests.

Required evidence classes:

- final topology/architecture and replacement absence;
- direct ToolHost contract and context proof;
- affected component, native MCP, CLI, Broker and process proof;
- invalid/duplicate registration startup failure;
- real Broker-backed terminal result for representative read and mutation;
- installed-runtime identity and global resource cleanup;
- one frozen full for the final returned candidate.

## Return packet

Return one structured packet containing:

- Packet ID and proposed `ACCEPTED` or `REPLANNING REQUIRED` disposition;
- starting/final HEAD, tracked patch, index and untracked identities;
- exact changed/deleted files and diff-check result;
- regenerated consumer representation inventory and any classified delta;
- final Tool IDs, registration owner and ToolContext surface;
- exact proof commands, run IDs, results and source identity;
- activation time, source digest, distribution digest and runtime verify result;
- negative scanner/old-import/old-path proof;
- test-root/process/socket/lock cleanup proof;
- omitted checks and residual risk;
- proposed R-FND closure rows for hub review.

Do not edit the master ledger, decision log, residue register or acceptance
record. Do not commit or push. Stop after returning the packet and wait for the
coordinating hub/user.
