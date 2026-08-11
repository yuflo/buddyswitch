# S5 C6B Source and Consumer Snapshot

## Source identity

```text
HEAD:                f441440d478d336a55599e49fdc554669d428da3
branch:              fea-tool
origin/fea-tool:     f441440d478d336a55599e49fdc554669d428da3
tracked/index patch: empty
untracked:           none
```

Activated runtime verification is clean:

```text
activated_at:        2026-08-11T08:50:39.546159Z
source_digest:       d7f838a2f2e2ea57936e99cc27ce83d0ddf722a6adbd6a27b7a1065aff5b5211
distribution_digest: 4a42c7328c768e3692d27e30c84ba64a3438c97c713a6f97d206fb25c6756e00
runtime.verify:      ok=true
```

## Current semantic owner cluster

Six Launcher files form one closed product-neutral Actor session/side-runtime
cluster:

| Current file | Lines | Responsibility | SHA-256 prefix |
|---|---:|---|---|
| `actor_capability.py` | 284 | parent/side capability state, validation and projection | `aa19693f` |
| `codex_runtime.py` | 108 | Codex executable/version descriptor and instance validation | `981fedab` |
| `actor_session.py` | 275 | parent input, attach and thread-resume resolution | `55c02c36` |
| `actor_side_thread.py` | 62 | capability-authorized side-thread start operation | `59691add` |
| `side_thread_lifecycle.py` | 444 | side start/send/interrupt/cleanup terminal effects | `7f9045e4` |
| `side_thread_registry.py` | 447 | side identity, lease, purpose and turn-state persistence | `e326ba78` |

Combined owner digest: `1e37b704358e4903014935d5c0edbdd989ea30f0711952ca70c7144f00997c42`.

The cluster's only external production dependencies are direct Foundation App
Server and Process Runtime operations plus the standard library. It imports no
product module, Role, Web, CLI, Host Control, application or runtime-support
owner.

## Live consumers and representations

Production consumers are:

- application Daemon host -> parent Actor Session input;
- Launcher CLI -> Actor Session and Codex runtime error/attach behavior;
- Launcher Host Control and its shell projection -> capabilities and Codex
  runtime validation;
- Demand private Daemon adapters -> side-thread start and registry operations;
- the six files' own internal imports.

Tests and support directly import, dynamically load, patch or name the current
files across Actor unit/integration, Host Control and CLI Process, Demand
integration, Daemon host, Web harness, Goal system and runtime-contract proof.
Package-distribution proof must gain the new Foundation modules and forbid the
retired Launcher files. Current Web-interface guidance must name the direct
Foundation Actor runtime after cutover.

The broad token inventory contains 39 paths:

```text
path-set SHA-256:        6c6637a860bf88f7d2d130b705c52743a1521fddb2f8c0113fa41021310a183a
path/content SHA-256:    3eefbcaf7c590dec67a57d77a5886e60ff86318d0e897a8982cb45c5db320d72
```

That inventory intentionally over-includes stable semantic fields such as the
instance-record key `codex_runtime` and prose describing side threads. Those
contracts are preserved, not renamed. Repository facts at execution time own
the final representation set; omitted mechanical consumers are in scope.

## Cut line

Not included in C6B:

- `host_control.py`, `runtime_lock.py` and lifecycle shell orchestration;
- `actor_environment.py`, `codex_config.py`, Role assets or Skill projection;
- WebHost, CliHost, cleanup, application composition or RoleHost redesign.

Host Control remains runnable by importing C6B's direct capability and Codex
runtime modules. Web and CLI remain current consumers. Role-bound start/list
and workspace construction stay for the later Host Control/Role boundary;
C6B introduces no provisional Role contract.

## Reusable preservation evidence

Direct refactor baseline:

```text
run:     d38fa5baa4a9407ea08119ba6965c3b7
targets: Actor capability/session/side-thread/registry/lifecycle plus Codex runtime
result:  56 passed, 25 subtests
```

Affected consumer baseline:

```text
run:     2f61b0ec789f4a28888c6176bf1a9b16
targets: Host Control, CLI, Daemon host, Demand side flow, Web consumer and runtime contract
result:  106 passed, 174 subtests
```

C6A frozen FINAL `2136e109979a470485151eb4b0c132e1` is executable-source
equivalent to this clean commit and passed every tier. Both new focused run
roots and attributable processes were absent after completion.
