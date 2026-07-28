# S1 Source Snapshot 2026-07-28

> Snapshot state: HISTORICAL ENTRY SNAPSHOT; F-026–F-028 are accepted
> Worktree: `/Users/chen/Dev/buddyswitch/.worktrees/fea-tool`
> Branch: `fea-tool`
> HEAD: `9e527141ef9c6ca705015fcecfa0b2a6fe1c3fc3`

## 1. Source and dirty scope

```text
tracked patch SHA-256:
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855

index patch SHA-256:
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

There is no tracked or indexed executable/document patch. Non-ignored
untracked files are the coordinating session's architecture, audit and
migration documents under `docs/memo/**`. They are unrelated dirty work for an
execution session to preserve unless a Goal Packet explicitly authorizes one
of them.

The pre-refresh untracked path-set digest was
`c2b6dbe183471e6f63b5add7cef771aa24dc4b4ace905c366a4617f198beba79`.
The packet and this snapshot were added afterward, so an execution session must
record the current complete untracked identity at start rather than compare
only that earlier digest.

## 2. Runtime-root manifest

The refreshed tracked manifest still classifies all current runtime roots:

| Current class | Files |
|---|---:|
| `scripts/env/**` | 68 |
| `scripts/runtime_kernel/**` | 9 |
| `scripts/runtime_store/**` | 1 |
| top-level `scripts/*` | 10 |
| `tools/launcher/*.py` | 45 |
| `tools/launcher/*.sh` | 7 |
| `tools/launcher/assets/**` | 19 |
| `tools/__init__.py` | 1 |
| `buddyswitch/skills/**` | 47 |
| `buddyswitch/env-profiles/**` | 5 |
| `buddyswitch/manifest.toml` | 1 |
| `framework/contracts/**` | 7 |
| `framework/config/**` | 2 |
| `framework/schemas/**` | 5 |
| `framework/agent-registry.md` | 1 |
| **Total / unmatched** | **228 / 0** |

The sorted `disposition<TAB>source` manifest SHA-256 is
`0aee4958b9781324f3d14d37e5343328450c076076c6f8e345154f04177fc06d`.
The disposition rules remain exactly those in
`02-source-and-asset-move-map.md`.

## 3. Package dependency availability

The current public test environment resolves:

```text
Python: /Users/chen/miniconda3/bin/python
Python version: 3.13.5
setuptools: 78.1.1
wheel: 0.45.1
Node: v24.13.1
```

`setuptools` and `wheel` are available but are not declared in
`requirements-test.txt`. S1.1 already owns the declaration and isolated
build/install proof; this is not a prerequisite repair.

## 4. Process and state snapshot

`./buddyswitch-codex instance list` returned:

```json
{"ok":true,"kind":"instance.list","data":{"instances":[]}}
```

After the command exited:

- no persistent BuddySwitch process was found;
- no repository-local PID, socket or lock file was found;
- there is no checkout-local `.buddyswitch-runtime` yet.

Canonical persisted-data locations are preserved. No data migration is
authorized by S1 source refresh or the entry repair.

## 5. Preservation baseline

The selected direct-boundary run was:

```text
run id: 89cfc964e0924b80a681c44c346ac84d
result: 258 passed, 10 failed, 439 subtests passed
duration: 42.96s
cleanup: clean
```

The ten failures reduce to three reproducible defect families:

| Finding | Exact isolated run | Root cause |
|---|---|---|
| F-026 | `dc292766c7344aa8b9e7c9811fb98b8a` | the test still asserts pre-`f8c53b2` exact phrases after the current architecture document was rewritten |
| F-027 | `3664a01b7c1a4cbca9ae0bf72c718245` | parent Context intentionally filters side-only Demand action `resolve_inbound`, while the old test expects the global unfiltered catalog |
| F-028 | `fb3d4976cf654a00bd6111179729d52d` | `context -> daemon_client -> runtime_kernel.__init__ -> broker -> dispatcher -> context` after `4b9d297` |

The failures reproduce in isolated public-runner commands and therefore
supersede the otherwise passing baseline. They cannot be waived for a
behavior-preserving S1 refactor.

## 6. Invalidation

This snapshot must be refreshed before formal S1 READY after:

- any executable/test/current-doc repair;
- commit, merge, rebase or branch change;
- runner/dependency change;
- a new tracked runtime-root file;
- a new active Actor/process/resource;
- an overlap with unrelated dirty work.

The accepted entry repair invalidated this file as the formal S1 execution
identity. It remains the evidence that caused the prerequisite. The formal S1
snapshot is prepared separately against the repaired tracked patch.
