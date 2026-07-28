# S1 C2–C5 Atomic Installed-Runtime Cutover Acceptance

> Decision: ACCEPTED AT C5 RETURN GATE
> Packet: `BS-MM-S1-C2C5-20260728-01`
> Authority: coordinating hub
> Accepted checkpoints: S1 / C2, C3, C4 and C5
> S1 stage state after acceptance: IN_PROGRESS — C6 remains

## 1. Accepted outcome

The C2–C5 runtime candidate is one runnable truth:

```text
root public launcher
  -> activated non-editable BuddySwitch distribution
    -> verified package entrypoint and installed resources
      -> current product owner
        -> observable lifecycle result
```

The old 228-path implementation/resource set is absent. Current runtime code
and resources live below `src/buddyswitch/**`; public and supervised product
processes use the activated interpreter and installed package entrypoints;
Actor workspaces contain selected projections and no BuddySwitch
implementation.

This is checkpoint acceptance, not final S1 acceptance. C6 still owns current
root/architecture guidance, final residue classification and the frozen
repository-wide acceptance run.

## 2. Source and diff identity

The hub reproduced the executor's returned source exactly before changing
coordinating documents:

```text
worktree:
/Users/chen/Dev/buddyswitch/.worktrees/fea-tool

branch:
fea-tool

HEAD:
9e527141ef9c6ca705015fcecfa0b2a6fe1c3fc3

tracked patch:
8ca8725f7d8097e86fb45c46d88480fb08f0214f46ee1f2a44f8ad2dad3a6a41

index:
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855

untracked all:
327 paths
77c41b7c1044da9e34d4ce757baca90791d7fdafd64ec066d0668e7e5b55edd2
9b94e0da8ad8efcd57c5e1f6d868e5e17f5735e875403d6073d7f057f592d71e

untracked non-memo:
256 paths
f60eac80b0589b77c079d12225d025c7fc0cb546620da84290a3cef3b7f70047
0806676954a9db2e2e6f2178b10d4b5e4696dd0e776ac1dc9a39aab0662914a4

untracked memo:
71 paths
8ce8b850b909cfedc894f9b97a7851e6ece381a604fcc67686e696743f255f67
642fbdd31ffb1007b60248a265e1c879aebacf8dfd736aaa54a869d4f2dd61ad
```

The packet began from the exact frozen identity in
`S1-C2-C5-SOURCE-SNAPSHOT.md`. The index stayed empty, HEAD and branch did
not change, and the starting dirty `.gitignore`, `requirements-test.txt` and
coordinating memo scope were preserved.

## 3. Product and contract proof

| Claim | Consumer path | Evidence | Result |
|---|---|---|---|
| public CLI uses one activated installed runtime | `buddyswitch-codex -> package cli entrypoint -> current owner` | direct six-claim GREEN and complete Process proof | PASS |
| package contains every current runtime input | build -> wheel -> non-editable install -> activation | 253-file wheel manifest and exact source/install correspondence | PASS |
| product child services use package entrypoints | CLI/host -> Broker/App/Daemon/Browser entrypoint -> owner | Process/System proof and captured Broker command | PASS |
| Actor is code-free and attributable | instance start -> Actor builder -> selected projection/runtime identity | Actor `act-pm-dcbbc3e521a8`, thread `thread-act-pm-dcbbc3e521a8` | PASS |
| lifecycle semantics are preserved | roles/start/input/status/clear/resume/stop/delete -> current owners -> persisted and consumer-visible terminal state | complete Process/System groups plus isolated lifecycle capture | PASS |
| failure and cleanup agree | failed owner/process -> protocol/persisted status/error -> cleanup | affected-tier proof and external residue audit | PASS |

The representative Actor workspace contained exactly:

```text
.agents
AGENTS.md
private
projects
```

Start and status reported the accepted runtime identity. Stop removed owned
process state; resume preserved Actor/thread identity and required the current
runtime identity; delete removed the instance while preserving the shared
project workspace.

## 4. Architecture and replacement proof

The hub inspected the current candidate against the frozen consumer manifest:

- `pyproject.toml` is the sole build/package-data owner;
- `src/buddyswitch/**` contains 249 source/runtime files and all 15 accepted
  entrypoint modules;
- root wrappers select only the runtime directory, activation record and
  deterministic runtime Python;
- activation verifies exact source/distribution path-and-byte
  correspondence before owner execution;
- package initializers do not preserve retired top-level import aliases;
- production source has no checkout `.py` execution, `--repo-root` code
  loading, source `PYTHONPATH`, `spec_from_file_location`, `sys.path`
  mutation or dynamic source fallback;
- Actor publication has no `repo_root`, `RUNTIME_COPY_PATHS` or implementation
  copy surface;
- current canonical state paths and business contracts did not move.

The frozen 228-path classifier reproduced:

```text
223 MOVE
5 DELETE
223 unique targets
0 remaining old inputs
0 missing targets
0 collisions
0 unmatched
```

The five deleted inputs are:

```text
framework/agent-registry.md
scripts/env_legacy_store.py
scripts/env_store.py
scripts/runtime_store/__init__.py
tools/__init__.py
```

No compatibility alias, fallback, dual source or copied Actor implementation
was added.

## 5. Distribution and runtime identity

The returned wheel was:

```text
buddyswitch-0.1.0-py3-none-any.whl
SHA-256:
70446bda253cdefdae688bef8fc85461461edef7dae77d9fe6ac73c6feaa68d6
files: 253
```

The wheel contained all required catalog, contract, Role, Skill, Web and four
`LICENSE*` resources, and contained no tests, cache path or bytecode.

The hub reran installed runtime verification against the unchanged executable
candidate:

```text
runtime.verify:
ok: true

activated_at:
2026-07-28T15:03:51.810665Z

source_digest:
0240a6d6897a96fc2538f8b883eee4a48f5830c2deb9928e4d9ccaf44809445f

distribution_digest:
02344c6d8e7edd0489cf02f69a28c991fc7364d833f1c1c72f04348a2505f0d7

package_version:
0.1.0

python:
/Users/chen/Dev/buddyswitch/.worktrees/fea-tool/.buddyswitch-runtime/venv/bin/python

package_root:
/Users/chen/Dev/buddyswitch/.worktrees/fea-tool/.buddyswitch-runtime/venv/lib/python3.13/site-packages/buddyswitch
```

## 6. Verification evidence

The final executable/non-memo identity reproduced exactly, so the hub reused
the executor's source-bound public-runner evidence. Reviewer independence
alone is not a reason to rerun unchanged broad suites.

```text
direct six-claim GREEN:
f4f7bf3cab9b4ba18a73d6cc6d1db94a
6 passed

accepted package group:
cb878724e5bc425d8c59a7d5df1a210c
13 passed in 22.78s

Unit:
d63166a0de0c4580998362227d8f332d
422 passed, 1125 subtests passed in 2.84s

Unit JavaScript:
1168172830794bf98760eaa0f3393c5b
147 passed in 0.18s

Integration:
5aed413f198e4bbc9586ff28a0096a12
757 passed, 438 subtests passed in 73.20s

Process:
7ba8e689b32a49c785bf98d7b42cf4ca
261 passed, 375 subtests passed in 86.08s

System:
aeec4cc8e03b4335a7a3e21b72cb5894
21 passed in 256.57s
```

The System group exposed one material operational defect: mailbox shutdown
left an externally visible Unix socket. The executor repaired
`DaemonMailboxServer.close()` at the resource owner and added a discriminating
regression:

```text
RED:
4f48b05bb7b74a8a9418f910c450e737

owner GREEN:
05d87e4167bd4cd8abe9a1fce180f688
1 passed

formerly leaking lifecycle:
6f8f2d0e46434de8afdeaefe6a6db167
1 passed in 202.95s
zero post-run socket/process/run-root residue
```

The complete affected tiers were rerun after the repair. `git diff --check`
passes and the index remains empty.

## 7. Operations and cleanup

At hub acceptance:

- `.buddyswitch-runtime` contains only `activation.json` and `venv`;
- installed BuddySwitch cache/bytecode count is zero;
- same-day packet-owned mailbox socket count is zero;
- supervised `bs-test` run-root count is zero;
- checkout-owned BuddySwitch process count is zero;
- no packet-owned PID, lock, instance or temporary build root remains.

Twenty-three ownerless mailbox sockets dated 2026-07-27 predate this packet.
They remain outside this fixed worktree's destructive scope and do not
invalidate packet cleanup.

## 8. Finding and residue decision

```text
F-037: CLOSED

R-PKG-001–R-PKG-015: CLOSED
R-PKG-017–R-PKG-018: CLOSED

R-PKG-016 packaged Role/Skill portion: CLOSED
R-PKG-016 root/current-guidance portion: OPEN, owned by C6

R-DOC-001: OPEN, owned by C6
```

The exact `assets/**/LICENSE*` package-data rule and built-wheel
correspondence close F-037. Current root `README.md`, root `AGENTS.md` and
`docs/arch/**` remain intentionally untouched by the executor; their
replacement is required before final S1 acceptance.

## 9. Omitted checks and residual risk

`./buddyswitch-test full` was intentionally omitted because the packet was
required to stop before C6. The complete Unit, JavaScript, Integration,
Process and System groups cover C2–C5, but only a frozen C6 candidate may run
and claim repository-wide final acceptance.

No known C2–C5 implementation or lifecycle defect remains. The remaining S1
risk is bounded to:

- current guidance may still teach retired paths until C6 replaces it;
- final residue classification has not run against updated current guidance;
- the frozen full-suite gate has not run;
- the large migration diff remains unstaged and uncommitted by design.

## 10. Transition decision

```text
BS-MM-S1-C2C5-20260728-01:
consumed; no longer executable

C2:
ACCEPTED

C3:
ACCEPTED

C4:
ACCEPTED

C5:
ACCEPTED

S1:
IN_PROGRESS

Next checkpoint:
C6 current-guidance replacement, final residue proof and frozen full-suite
acceptance

Runtime authorization:
none until the coordinating hub issues a source-bound C6 Goal Packet
```

This acceptance unlocks C6 preparation only. It does not accept S1 or
authorize S2.
