# S5 C6D R2 READY Review

> Decision: `READY — R2 ONLY`
> Packet: `BS-MM-S5-HOST-CONTROL-R2-20260812-01`
> Entry: exact preserved R1 dirty candidate described below

## R2 acceptance sentence

> Every Foundation Host Control Python and shell representation is independent
> of Application, Launcher, product modules, runtime-support and concrete Role
> implementations; all application-owned executable capabilities needed by the
> preserved lifecycle enter through the one explicit application input, while
> R1 behavior, owner placement and replacement facts remain unchanged.

## Entry identity

```text
executable base:           e11ddccf9740268f327d215f4b6e11f3adae6283
entry HEAD/origin:         exact pushed R2 READY coordination commit from hub
non-memo patch SHA-256:    b2afa3e665b9e3d7957123ecfcd6ee5e740e44841b103bc92f2e4fab8d02afc3
index SHA-256:             e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
untracked count:           14
untracked manifest:        c32aa341cdae79b7725870b44a1281522596f7ce3603c110521e76fceed820f9
runtime source:            e963db28bf2b774ac55c64ce05b76cb8e55ea98ba2becfe656d625f38f78736e
runtime distribution:      edcacab07b6da016a0b98c08f5698875ff4000f688eb993ae047e390e01c2204
runtime verify:            ok=true
```

The independent executor must reproduce this exact preserved candidate. The
preparation-only memo changes that authorize R2 are coordinating-hub state and
must not be treated as candidate drift.

## Selected design

Extend the existing exact `HostControlApplicationInput`; do not introduce a
second configuration object or generic provider mechanism. Application owns
the concrete daemon and Runtime Broker process entrypoints. Foundation owns
when and with which lifecycle facts those capabilities are invoked.

The input may carry validated immutable command/module facts, or one exact
application start program may expose narrowly named service subcommands. The
executor owns that local choice. The required final properties are:

- no file under `foundation/host_control/**` contains a direct import, source,
  module invocation or embedded implementation path for Application, Launcher,
  modules, runtime-support or concrete Roles;
- Foundation still invokes the accepted Daemon and Runtime Broker lifecycle
  exactly once at the same phases with the same arguments and terminal effects;
- Application remains the one assembly point; there is no registry, locator,
  provider family, dynamic discovery, fallback or second execution path;
- the structure proof inspects every `foundation/host_control/shell/*.sh`, not
  only `host_control.sh`, and names only stable forbidden dependency roots;
- retired Launcher owner paths remain absent and R1 consumer/package topology
  remains intact.

## Authorized repair boundary

OWNER / INPUT / ASSEMBLY:

- the existing Host Control application-input contract and script runner;
- the application Host Control assembly/start entrypoint only as needed to
  supply current executable capabilities;
- owner-local Host Control shell helpers only where they consume that input.

PROOF / CURRENT DOC:

- the Host Control architecture test and nearest existing lifecycle/package
  tests affected by the input shape;
- current Host Control architecture prose if its dependency statement needs
  precision.

The executor may adjust mechanically affected tests or constructors inside
those classes after current-source discovery. A stale path list is not a stop
condition.

FORBIDDEN:

- lifecycle ordering, state schema/location, Role rows/IDs, Actor IDs, command
  arguments, public envelopes/status codes, destructive guards or cleanup;
- moving or redesigning Daemon, Runtime Broker, WebHost, CliHost, RoleHost,
  Actor Environment, Browser, App Server or generic cleanup;
- changing accepted Daemon or Runtime Broker process contracts;
- compatibility aliases, fallback paths, dual invocation, generalized command
  registries, DI containers, service locators or event buses;
- a general shell parser, lexical/data-flow analyzer or new test framework;
- master-truth updates, commit, push, C7 or S6.

## Proof and execution contract

1. Preserve the R1 candidate and reproduce its complete identity.
2. Add the smallest structural RED that fails because the helper shells contain
   the current application module invocations.
3. Implement the dependency inversion within the authorized boundary.
4. After the coherent executable mutation, build/install/activate/verify before
   the next public runner command.
5. Run the same structural target GREEN and discover only direct affected
   lifecycle/application/package targets from current references.
6. Reuse R1 evidence for unchanged claims; do not rerun broad proof merely for
   actor freshness.
7. Review the complete final diff and all Host Control executable
   representations. Freeze once.
8. Because executable state changes after R1 FINAL, run one new
   `./buddyswitch-test full` on the frozen R2 candidate.
9. Return complete source, runtime, contrary-signal and cleanup identities.

Any new in-scope executable repair after R2 FINAL follows bounded
`FIX_AFTER_FINAL`: exact regression, affected focused proof, freeze, then one
new FINAL. An unexplained failure or required owner expansion stops the packet.

## READY disposition

The escaped dependency and its proof boundary are fully known. R2 is a bounded
continuation over a coherent preserved candidate, not patch-on-patch design
experimentation. Only `BS-MM-S5-HOST-CONTROL-R2-20260812-01` may execute.
