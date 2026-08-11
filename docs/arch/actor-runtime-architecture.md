# Actor Runtime Architecture

## Owner

`src/buddyswitch/foundation/actor_runtime/` is the single direct owner for
Actor capability persistence and resolution, Codex runtime descriptors, parent
Actor Session input and attach, side-thread start and lifecycle, and
side-thread registry, lease, capability, purpose, and turn transitions. Its
direct modules are:

- `src/buddyswitch/foundation/actor_runtime/capability.py`;
- `src/buddyswitch/foundation/actor_runtime/codex_runtime.py`;
- `src/buddyswitch/foundation/actor_runtime/session.py`;
- `src/buddyswitch/foundation/actor_runtime/side_thread.py`;
- `src/buddyswitch/foundation/actor_runtime/side_thread_lifecycle.py`;
- `src/buddyswitch/foundation/actor_runtime/side_thread_registry.py`.

The package root is inert. Consumers import concrete modules directly; there
is no package-root re-export, Launcher compatibility path, fallback, or dual
runtime owner.

## Dependency direction

```text
application / Demand / current Launcher hosts
                     -> foundation Actor Runtime
foundation Actor Runtime -> foundation App Server
foundation Actor Runtime -> foundation Process Runtime
```

Foundation Actor Runtime imports only the standard library and direct
`foundation.app_server` and `foundation.process_runtime` owners. Application,
Demand, Host Control, CLI, and shell code are consumers. Role selection,
instance start/list, Actor workspace construction, Host Control lifecycle,
runtime locking, Web routing, public CLI dispatch, and host/global cleanup
orchestration remain outside this owner.

## Runtime contract

The owner preserves capability catalogs and config, the stable
`codex_runtime` instance-record field, executable/version validation, parent
input and attach resolution, App Server thread/turn/input behavior, side lease
and registry transitions, typed failures, environment propagation, permission
settings, interrupt behavior, and terminal cleanup effects.
