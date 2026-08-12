# S5 C6D Boundary Design and Preflight

## Selected boundary

```text
current application Role/start inputs
  -> one explicitly assembled private Host Control capability
  -> product-neutral Foundation Actor lifecycle coordination
  -> accepted Foundation service/runtime owners
  -> exact instance result, state and cleanup

application entrypoints
  -> generic CLI/Web adapters
  -> the same assembled Host Control capability
```

Foundation owns lifecycle sequencing, host facts, runtime validation, lock
semantics, terminal result/error interpretation and cleanup. It treats Role ID
as an opaque validated input and imports no current Role catalog, Role asset,
application, component, runtime-support or Launcher implementation.

Application composition owns the one current Role catalog/list/validation
input and any concrete application-selected start capability. This is direct
assembly, not a provider registry, service locator or early RoleHost. S6 may
replace that current Role input without changing Foundation lifecycle.

Web and CLI are not the lifecycle owner. Their current physical files may
receive only the mechanical constructor/contract changes needed to consume the
assembled capability. Their own physical convergence remains the next owner.

## Complete-owner rule

C6D is complete only if the actual lifecycle execution moves with the facade.
The retired `launcher/host_control.py`, `launcher/shell/host_control.sh` and
`launcher/runtime_lock.py` paths must be absent. A Foundation facade that still
executes a Launcher-owned Host Control script is rejected.

The executor may implement the owner in direct Python or retain narrowly
scoped shell projections under the receiving Foundation owner. If shell
remains, it must be packaged by that owner, contain no Role selection and
source no Launcher/application/module/runtime-support implementation. Existing
`env.sh`, Browser, cleanup, Web and CLI shell surfaces may remain only when
they are no longer part of Host Control ownership and are still required by a
later current consumer.

The shared runtime lock moves to direct Process Runtime ownership because it
is product-neutral and has current Host Control and CLI/cleanup consumers.

## Alternatives rejected

1. **Facade-only relocation — rejected.** The lifecycle owner and reverse
   dependency remain in Launcher.
2. **Move the current shell unchanged — rejected.** It imports mixed Role,
   config, Browser and Launcher policy into Foundation.
3. **Move all remaining Launcher code — rejected.** It combines independent
   Host Control, Web, CLI, cleanup, asset and RoleHost proof loops.
4. **Introduce a generic host/provider framework — rejected.** One exact
   application assembly and exact capabilities are sufficient.

## Topology preflight

`S5C6DP-20260812-01` parsed 286 current production Python modules and simulated
the Host Control/runtime-lock owner replacement plus application-side current
Role assembly.

- current non-trivial SCCs: one pre-existing Artifact Public/private pair;
- candidate non-trivial SCCs: the same one;
- new SCCs: zero;
- candidate adds no Foundation-to-Launcher/application/module/runtime-support
  edge;
- five pre-existing Foundation reverse edges remain for later C6/S6 owners;
- CLI/Web entrypoints can construct once and pass downward without lower-layer
  application imports.

This is a representative topology proof, not an implementation prescription.
The executor must re-prove the actual final graph.

## C6D / later cut line

C6D does not redesign:

- Role discovery, Role packages, profiles, authority or assets;
- generic Web routing, workers, DTOs, assets or lifecycle queue semantics;
- public CLI parsing, product command contributions, help or envelopes;
- generic cleanup semantics;
- Browser/App Server/Daemon/Broker protocols already accepted;
- final RoleHost or final Launcher-root deletion.

Necessary application assembly, direct consumers, package data, tests and
current Host Control/Actor architecture guidance are in scope.
