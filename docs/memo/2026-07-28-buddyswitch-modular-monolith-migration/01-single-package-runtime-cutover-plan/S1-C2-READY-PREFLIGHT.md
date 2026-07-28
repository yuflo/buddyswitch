# S1 C2 READY Preflight and Boundary Review

> Decision: ARCHITECTURE_REOPEN_REQUIRED
> Authority: coordinating hub
> Candidate checkpoint: S1 / C2 direct source and asset move
> Execution authorization: none
> Finding: F-035

## 1. Candidate claim

The existing C2 plan claims that all current implementation and runtime assets
can move directly into `src/buddyswitch/**`, old executable source can disappear,
and the repository can then proceed separately to C3 process cutover and C4
Actor projection.

That claim is false for the current consumer topology.

## 2. Current consumer contradiction

### Public wrappers

Current root product/test entrypoints still require files C2 deletes:

```text
buddyswitch-codex
  -> tools/launcher/env.sh
  -> tools/launcher/cli.py

buddyswitch-test
  -> tools/launcher/env.sh
  -> tests/runner.py with old source PYTHONPATH
```

C3, not C2, owns replacement of these paths with installed package
entrypoints. An exact C2 move therefore makes the public CLI and public test
runner unusable before C3 begins.

### Actor workspace

`tools/launcher/actor_environment.py` currently validates and copies:

```text
scripts/env
scripts/runtime_kernel
scripts/turn_runtime.py
scripts/env_store.py
scripts/env_legacy_store.py
scripts/env_manifest.py
scripts/env_profiles.py
scripts/browser_evidence.py
buddyswitch/manifest.toml
buddyswitch/env-profiles
framework/contracts
```

C2 moves or deletes every one of these implementation/catalog paths. C4, not
C2, removes `repo_root`, `RUNTIME_COPY_PATHS` and workspace implementation
copies. Exact C2 execution therefore makes Actor build/start unusable before
C4 begins.

### Runtime Broker and MCP

The current Broker/MCP path still uses repository-root/source arguments and
old runtime locations. C3 removes `--repo-root`, dynamic checkout loading and
checkout `.py` child commands. C2 cannot delete those source locations while
leaving the old process contract live.

## 3. Why existing C2 proof is insufficient

The frozen C2 verification group runs unit and integration tests only:

```text
tests/unit/architecture
tests/unit/env_tool
tests/unit/daemon
tests/unit/actor
tests/unit/launcher
tests/unit/runtime_protocol
tests/integration/env_tool
tests/integration/runtime
tests/integration/runtime_broker
tests/integration/daemon
tests/integration/app_server
```

It does not run the public process tier or system Actor lifecycle that observes
the broken root-wrapper, child-process and workspace-publication paths. A green
C2 group could therefore coexist with an unusable product path.

Stop conditions cannot repair this missing pre-READY proof.

## 4. Rejected alternatives

| Alternative | Why rejected |
|---|---|
| leave copies at old source paths until C3/C4 | duplicate live implementation and two current truths |
| add old-import aliases or source-path adapters | forbidden compatibility and path surgery |
| teach Actor builder to copy from a temporary second package surface | interim implementation-copy model created only to be deleted by C4 |
| move only files not currently executed | dependency/import graph still crosses old and installed provenance; does not satisfy the C2 claim |
| accept temporarily broken CLI/Actor paths | violates the shortest validated runnable loop and cannot be an accepted checkpoint |

## 5. Minimum coherent replacement boundary

The shortest source cutover that can remain runnable is:

```text
C2 direct source/resource move
  + C3 public and child-process entrypoint cutover
  + C4 code-free Actor projection
  + C5 complete lifecycle/consumer proof
```

These are not four independent deployment truths. They are four task groups
inside one source-bound replacement packet:

1. freeze exact move/consumer/entrypoint/workspace manifests;
2. write cross-boundary RED that observes public CLI, installed child command
   and Actor workspace behavior;
3. move implementation and resources once;
4. cut every live process consumer in the same candidate;
5. remove workspace implementation copy in the same candidate;
6. rebuild/reinstall/reactivate;
7. prove unit, integration, process and system lifecycle boundaries;
8. return before C6 current-guidance/residue/FINAL acceptance.

C6 remains a separate frozen-final checkpoint because it updates all current
guidance, performs repository-wide residue deletion/classification and owns
`./buddyswitch-test full`.

## 6. READY consequence

No standalone C2 Goal Packet may be issued from the current plan.

The hub must revise the remaining S1 checkpoint topology, produce a complete
move/consumer/write manifest and representative final-topology preflight, then
READY-review one coherent C2–C5 replacement packet. Because this changes the
size of the next independent execution unit, maintainer confirmation was
required before the new plan and Goal Packet became executable.

There is no compatibility bridge and no patch-on-patch successor to the
invalid standalone C2 plan.

## 7. Resolution

The maintainer accepted the minimum coherent boundary. D-038 and
`S1-C2-C5-READY-REVIEW.md` authorize one atomic C2–C5 packet,
`BS-MM-S1-C2C5-20260728-01`. F-035 is closed as a planning/READY defect.
Standalone C2 remains permanently rejected.
