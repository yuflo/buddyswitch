# S5 C3 Browser Runtime Implementation Plan

> Plan state: `READY`
> Execution unit: one atomic Browser owner cutover
> Product behavior: preservation

## 1. Goal

> Browser acquire, readiness, target, page-lease, Daemon cleanup and MCP proxy
> behavior are owned once under `foundation/browser_runtime/**`; Broker,
> Daemon, application and shell consumers call that owner without retired
> imports, private cross-module calls or compatibility paths.

## 2. FRAME and protected contracts

Bottleneck: Browser changes currently require coordinated edits across
historical `env`, `launcher`, Broker, Daemon and test paths, so one capability
has no physical owner.

Observable acceptance: the existing public Browser commands, Broker methods,
Daemon events and MCP proxy produce the same results and cleanup effects from
one new physical owner, and all retired implementation paths are absent.

Protected contracts are enumerated in the boundary design. Internal import
paths are not protected.

## 3. TRACE before editing

At packet entry, the executor must refresh—not assume—the following from the
current clean source:

- eight implementation modules and the proxy asset;
- direct imports and package-relative imports;
- string/literal/generated paths in harnesses and System tests;
- Broker and Daemon consumers;
- application/shell entrypoints;
- package-data and distribution assertions;
- Browser, adjacent Daemon/Broker/launcher and cleanup support tests;
- current architecture guidance and old-path residue assertions.

A newly discovered file is writable without hub return when it is clearly a
direct Browser owner/consumer/proof/current-doc representation inside the
classified scope. Record it in the return packet. Stop only when it changes a
semantic owner, protected behavior, persisted data or another checkpoint.

## 4. PROVE

Reuse source-equivalent FINAL `c1a3466da1b6455ead00dfcdca86bf46`
as the preservation baseline. Do not rerun it before implementation.

Select nearest current assertions for:

- config and target transport;
- page-idle state/locking/schedules;
- acquire/status/release plus stale/foreign/startup-failure behavior;
- Broker dispatch and exact errors;
- three Browser handler registrations and order;
- proxy protocol, lifecycle, page state, open/search and upstream cleanup;
- public Browser commands and System lazy release;
- wheel/package asset correspondence.

Add the smallest structural/behavioral regression needed to detect the new
architecture: one physical owner, no old paths/imports, side-effect-free
package root, host dependency direction, new asset owner and zero production
cross-submodule leading-underscore Browser calls. Do not manufacture tests for
unused helper names or a broad facade, and do not make private terminal helpers
public merely because an owner regression exercises them.

## 5. BUILD and REPLACE

Perform one coherent source block:

1. establish `foundation/browser_runtime/**` and move the owned asset;
2. move existing behavior without redesigning it;
3. expose only the actual cross-file operations already consumed;
4. change all Browser-owner and production-consumer imports;
5. change test/support/harness/path/package representations;
6. update current Browser and Daemon architecture guidance;
7. delete retired modules/asset and any dead source-relative constants.

The application entrypoints remain the public verified entrypoints. Broker
and Daemon retain their current host contracts. Root Browser tests remain
root-owned. No compatibility shim or package-root re-export is permitted.

## 6. Runtime gate

After any coherent `src/buddyswitch/**` or package declaration change:

```text
build/install non-editable runtime from declared inputs
  -> activate
    -> verify exact source/distribution correspondence
      -> public test runner
```

No GREEN may precede this gate. Use repository-owned provisioning mechanics;
do not copy old shell transcripts blindly and do not install undeclared
dependencies.

## 7. VERIFY

The executor owns valid focused-target discovery under
`$buddyswitch-testing`. Required breadth:

1. exact architecture/replacement and public-internal-operation proof;
2. complete Browser Unit and Integration owner behavior;
3. affected Broker, Daemon, launcher, process safety and cleanup behavior;
4. Browser Process and System lifecycle behavior;
5. package build/distribution/activation correspondence;
6. source and installed-distribution scans for retired modules/asset/imports;
7. `git diff --check`, process/socket/lock/root cleanup and one frozen FINAL.

Tests must observe real consumer results and parent-known process identity,
not only registration fields or child-authored markers.

## 8. Bounded FIX_AFTER_FINAL

Follow `$buddyswitch-testing`. An attributable in-scope defect may be repaired
inside the classified C3 boundary, followed by reprovision, exact proof,
affected proof and one replacement FINAL. An unexplained failure, another
checkpoint owner, protected-contract change or second owner-boundary
invalidation stops the packet for replanning.

## 9. ACCEPT and return

Audit the final diff against Product, Contract, Architecture, Replacement and
Operations proof. The return must include every contrary signal, not only the
last passing run, and exact residual resource state.

Do not update master migration truth, commit, push or begin C4.
