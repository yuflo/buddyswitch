# S5 C6E Web Runtime Source and Consumer Snapshot

> Source: `cfcbf387726359d766889114eb87688c211f0276`
> Worktree/index/untracked: clean / empty / none
> Captured: 2026-08-12

## Bottleneck

The accepted generic Web host remains physically under `launcher/**` even
though C2 removed product routing and worker meaning from it. Its typed route,
worker and Actor-console contracts, HTTP/runtime owner and static UI assets
change together. The Web host also uses the machine-first envelope currently
named `launcher.cli_contract`; leaving that dependency behind would create a
Foundation-to-Launcher edge after the move.

## Current owner set

```text
launcher/web_management.py
launcher/web_contracts.py
launcher/cli_contract.py
launcher/assets/web-management/**
```

Sixteen owner/asset files were captured. Ordered
`path + NUL + sha256(content) + LF` manifest:

```text
c2a8b7341115b2a1960b428cb2b922f7645f290918a6cb9c09154d8e2ff63d59
```

The host is already generic:

- application composition selects route/worker/console contributions;
- the host validates, prepares and dispatches them;
- Host Control is injected;
- component adapters own product DTO and operation meaning;
- Browser, App Server, Daemon and process owners are already Foundation
  capabilities.

## Live consumer classes

The complete mechanical consumer set is not frozen to a guessed filename list.
The executor must rediscover all of these representation classes from current
source:

- application build and Web entrypoint;
- `foundation/composition` type-only contracts;
- Track, Task and Communication Web adapters;
- Demand, Task and Track CLI adapters plus generic CLI host consumers of the
  shared machine envelope;
- Web/IM integration harnesses;
- Web, component-boundary, external-control and package tests;
- package-data declaration and installed-path assertions;
- current Web/Communication/Track/Task architecture guidance.

The preparation scan found 24 direct path/import representation files before
expanding the `cli_contract` multi-import form. Its ordered content manifest
was `980a621355e7f14906f6c956f0c1c8b440549750b0c4c21a6e4839ac6f73a8f8`.
That number is evidence for source refresh, not an executor path ceiling.

## Current protected paths

```text
./buddyswitch-codex web
  -> application.entrypoints.cli
    -> current generic CLI host
      -> application.entrypoints.web
        -> injected Host Control + configured Web contributions
          -> Web ready envelope, HTTP/API/UI and worker lifecycle
```

Protected observable behavior includes loopback-only binding, one-line
`web.ready` stdout, static content and content types, route/status/error DTOs,
asynchronous lifecycle operation truth, open-TUI safety, fail-soft worker
startup, reverse worker stop, server-close ordering and clean signal teardown.

## Neighbor boundary

CliHost is not part of this cutover. It still owns command parsing, public JSON
projection, Browser/cleanup/env shell orchestration and Web process launch.
Those dependencies form the next source refresh after C6E. Role assets and
Role selection remain S6-owned.
