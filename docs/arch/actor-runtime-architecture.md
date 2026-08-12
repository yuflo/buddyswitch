# Actor Runtime Architecture

## Owner

`src/buddyswitch/foundation/actor_runtime/` is the single direct owner for
Actor capability persistence and resolution, Codex runtime descriptors, parent
Actor Session input and attach, side-thread start and lifecycle, and
side-thread registry, lease, capability, purpose, and turn transitions. It also
owns product-neutral Actor workspace validation, Git-free project seeding,
selected-bootstrap materialization, atomic publication, and failed-stage
cleanup. Its direct modules are:

- `src/buddyswitch/foundation/actor_runtime/capability.py`;
- `src/buddyswitch/foundation/actor_runtime/codex_runtime.py`;
- `src/buddyswitch/foundation/actor_runtime/environment.py`;
- `src/buddyswitch/foundation/actor_runtime/session.py`;
- `src/buddyswitch/foundation/actor_runtime/side_thread.py`;
- `src/buddyswitch/foundation/actor_runtime/side_thread_lifecycle.py`;
- `src/buddyswitch/foundation/actor_runtime/side_thread_registry.py`.

The package root is inert. Consumers import concrete modules directly; there
is no package-root re-export, Launcher compatibility path, fallback, or dual
runtime owner.

## Dependency direction

```text
application / Demand / Foundation Host Control / current Launcher adapters
                     -> foundation Actor Runtime
application Actor build -> resolved Role/Skill bootstrap -> Actor Runtime environment
foundation Actor Runtime -> foundation App Server
foundation Actor Runtime -> foundation Process Runtime
```

Foundation Actor Runtime imports only the standard library and direct
`foundation.app_server` and `foundation.process_runtime` owners. Application,
Demand, Foundation Host Control, CLI, and shell code are consumers. Role selection,
instance lifecycle, Process Runtime locking, Web routing,
public CLI dispatch, and host/global cleanup orchestration remain outside this
owner. Current central Role/Skill selection remains application-side until S6;
it supplies one explicit resolved bootstrap projection to the environment owner
through the application-selected Host Control start input and the stable
`buddyswitch.application.entrypoints.actor_build` boundary.

## Runtime contract

The owner preserves capability catalogs and config, the stable
`codex_runtime` instance-record field, executable/version validation, parent
input and attach resolution, App Server thread/turn/input behavior, side lease
and registry transitions, typed failures, environment propagation, permission
settings, interrupt behavior, and terminal cleanup effects.
Actor workspace publication preserves runtime-identity checks, exact
workspace/config/auth/Skill/project projections, path and symlink safety,
atomic no-overwrite publication, result/error behavior, and failed-stage
cleanup without importing Role, Launcher, application, modules, or
runtime-support policy.
