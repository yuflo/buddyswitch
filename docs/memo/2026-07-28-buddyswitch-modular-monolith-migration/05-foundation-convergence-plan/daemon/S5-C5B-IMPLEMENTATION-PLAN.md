# S5 C5B Implementation Plan

## FRAME

Bottleneck: Daemon has one product-neutral semantic model but its service,
state, trigger, mailbox and host implementation remains physically divided
between Launcher and Foundation. That prevents Daemon from being an
independently iterable Foundation brick and leaves Foundation Browser/contracts
depending back on Launcher.

Acceptance sentence:

> Central and instance Daemon have one direct Foundation owner, application
> supplies all concrete registrations and App/Actor host behavior explicitly,
> every current consumer observes unchanged protocol, dispatch, recovery and
> lifecycle behavior, and the retired Launcher Daemon implementation is absent.

## TRACE

At entry, reproduce the handoff identity and rediscover:

- current Daemon owners and all direct/literal/generated/subprocess/package
  representations;
- application ordering and Browser/module registration sources;
- App/Actor calls required by the handler-facing runtime and notification loop;
- current state, protocol, process, cleanup and product-boundary proofs;
- current docs whose live path or dependency statements change.

Path examples in the snapshot are hypotheses. Representation completeness and
the shortest owner-correct local organization belong to the executor.

## PROVE

Reuse source-equivalent entry evidence. Select nearest direct proof for:

- central protocol/service and instance mailbox/trigger/state behavior;
- explicit registration validation and exact ordering;
- injected host capability parent activity/input behavior;
- process start/status/stop, stale identity and cleanup;
- module/Browser consumers and package installation;
- final owner/import/old-path absence.

Do not manufacture a behavioral RED for a behavior-preserving move. A small
stable architecture/replacement RED may establish the new owner boundary.

## BUILD / REPLACE

Build one coherent candidate:

1. establish the direct Foundation Daemon owner and its small public internal
   contracts;
2. inject the current App/Actor host capability from application wiring;
3. make application supply all concrete module and Browser registrations in
   unchanged order;
4. move the shared generic event-log primitive to Process Runtime;
5. update every classified consumer, test/support representation, installed
   package expectation and current architecture statement;
6. delete all retired Launcher Daemon/event-log implementations and imports.

The candidate must be runnable without C6. Do not leave old/new modules in
parallel and do not perform multiple partial reprovisions.

## VERIFY

After the coherent source mutation:

1. build/install/activate/verify the non-editable runtime before the next
   runner command;
2. dynamically discover valid exact and affected targets;
3. prove product, contract, architecture, replacement and operations claims;
4. review diff/proof complexity and resource state;
5. freeze the candidate and run one `./buddyswitch-test full`;
6. use only the bounded `$buddyswitch-testing` FIX_AFTER_FINAL rule for an
   attributable in-scope defect.

## ACCEPT

Return a result packet with exact source/runtime identities, physical topology,
changed files by semantic class, direct/affected/FINAL evidence, failure
disposition, old-path absence and cleanup. Do not update migration master
truth, commit, push or enter C6.
