# S5 C6A Boundary Design and Preflight

## Accepted topology

```text
application / modules / Actor host
                 |
                 v
foundation/app_server
  |-- protocol client and typed failures
  |-- thread / turn / Goal operations
  |-- socket selection and process lifecycle
  `-- co-located shell adapter
            |
            v
foundation/process_runtime

application entrypoint -> foundation App Server main
Launcher CLI/host shell -> co-located App Server shell adapter
```

The public process entrypoint remains stable. Consumers import the direct
Foundation owner module; the package root is inert and does not re-export a
compatibility surface.

## One-owner decisions

- App Server becomes one direct `foundation/app_server/**` owner.
- Its Python implementation and shell projection move atomically because the
  shell path is a live installed-package consumer of the same lifecycle.
- The shortest mapped implementation is an inert `__init__.py`, one runtime
  module and the co-located shell file. Equivalent private segmentation is
  executor-owned if it introduces no facade, alias or duplicate rule.
- `pyproject.toml` gives the co-located shell file its direct package-data
  owner; Launcher package data no longer carries that file.
- Application remains the stable process composition/activation boundary.
- Actor, Web, CLI, cleanup and remaining Launcher shell ownership do not move
  in C6A. They receive only necessary import or shell-path consumer edits.

## Positive preflight

`S5C6AP-20260811-01` parsed all 284 current production Python files and
simulated replacing `buddyswitch.launcher.app_server` with
`buddyswitch.foundation.app_server.runtime`.

Results:

- six direct production Python import sites were identified;
- the proposed owner depends only on
  `foundation.process_runtime.{event_log,process_identity}`;
- no Foundation-to-Launcher/application/module/Browser/Role/Broker edge is
  introduced;
- the current graph has two pre-existing Artifact-private SCCs and the
  simulated graph has the same two; C6A adds zero SCCs and removes none;
- the application entrypoint, current Actor/Daemon/module consumers and shell
  hosts remain independently runnable after only mechanical consumer changes.

Therefore C6A does not require later C6 work to run or prove its result.

## Negative preflight

The final candidate must prove:

- no old Launcher App Server Python or shell file, import, literal installed
  path, package projection, alias, fallback or package-root re-export;
- no App Server dependency on Launcher, application, product modules, Browser,
  Role, Runtime Broker or concrete host composition;
- no product/Role interpretation in App Server or its shell adapter;
- no protocol, state, permissions, environment, timeout or lifecycle change;
- no move/redesign of Actor, Web, CLI, cleanup or remaining shell owners;
- no plugin loader, DI container, service locator, event bus or generalized
  process framework;
- no architecture proof that grows a Python lexical/data-flow analyzer.

## C6 cut line

C6A is the first independently runnable owner split admitted under D-057.
After C6A acceptance, the hub refreshes the remaining C6 source and chooses
the next real owner boundary. Actor, Web and CLI are not authorized by this
packet, and their later navigation labels are not fixed implementation
contracts.

## Protected contracts

- App Server JSON-RPC/WebSocket methods, params, envelopes and typed failures;
- thread/turn/Goal/input/interrupt/compact behavior;
- socket fallback, process identity, readiness, status, logs and cleanup;
- shell function names, JSON output, environment propagation and exit effects;
- application entrypoint and root CLI observable behavior;
- accepted component, Daemon, Actor and Role behavior.

Internal import and package-asset paths are deliberately replaceable.
