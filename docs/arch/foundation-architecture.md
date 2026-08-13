# Foundation Architecture

## Current boundary

Foundation is the product-neutral execution, primitive, lifecycle and passive
composition layer. Product modules contribute typed values; Application selects
the concrete product and current Role facts; Foundation executes only the facts
it is given.

```text
product modules -> src/buddyswitch/foundation/composition/__init__.py
                -> passive ModuleAssembly / Skill / cleanup values

Application -> RoleHost + explicit current Role projections
            -> Foundation ToolHost / CLI / cleanup / Runtime Broker
            -> exact state, protocol, CLI and resource effects
```

The passive `SkillExport`, `CleanupContribution`, `CleanupIndexProjection` and
`OwnedStatePath` contracts live with `ModuleAssembly` at
`src/buddyswitch/foundation/composition/__init__.py`. Generic cleanup planning,
effect-time containment/ownership revalidation, deletion and result projection
live at `src/buddyswitch/foundation/state/cleanup.py`. Runless status and Tool
catalog diagnostics live at
`src/buddyswitch/foundation/cli_runtime/diagnostics.py`.

## Explicit Role inputs

Application constructs the one `RoleHost` from reviewed installed packages,
component `SkillExport` values and Artifact Public's template vocabulary before
publishing runtime capabilities. Foundation copies no Artifact product policy.
Application supplies immutable Role runtime projections to ToolHost and CLI
Runtime, valid Role IDs to cleanup, and selected AGENTS/Skills to the Actor
publisher. Runtime Broker carries no Role source path; Tool dispatch resolves
the active Role through the Application-configured capability. These inputs
have no fallback, translation layer, provider family, locator, or second
discovery path.

## Dependency rule

Python under `src/buddyswitch/foundation/` must not import Application,
Launcher, product modules, retired central Role support or concrete Role
implementation. Embedded module/path strings, shell commands and packaged
files likewise contain no Launcher, product-module, runtime-support or Role
implementation path. Accepted stable Application process entrypoint module
strings remain explicit current lifecycle interfaces, not implementation
dependencies. `RoleHost` imports only Foundation contracts and discovers exact
Role package entrypoints below its trusted installed root. Application depends
on product modules, RoleHost, and Foundation to compose the running product.
Retired central owners are absent rather than aliased or re-exported.
