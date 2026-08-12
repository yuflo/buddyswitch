# Foundation Architecture

## Current boundary

Foundation is the product-neutral execution, primitive, lifecycle and passive
composition layer. Product modules contribute typed values; Application selects
the concrete product and current Role facts; Foundation executes only the facts
it is given.

```text
product modules -> src/buddyswitch/foundation/composition/__init__.py
                -> passive ModuleAssembly / Skill / cleanup values

Application -> explicit current Role facts
            -> Foundation cleanup / diagnostics / Runtime Broker
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

`src/buddyswitch/application/entrypoints/cleanup.py` supplies cleanup
contributions, the current manifest path and the Application projection that
loads valid Role IDs. `src/buddyswitch/application/entrypoints/diagnostics.py`
supplies the current manifest path. The stable
`src/buddyswitch/application/entrypoints/runtime_broker.py` process entrypoint
supplies the current manifest loader to the Foundation Runtime Broker. These
inputs are required and have no Foundation default, fallback, discovery,
provider, registry or locator.

The remaining `src/buddyswitch/runtime_support/` files are only the current S6
Role inputs: manifest, profiles, authority and Skill materialization, plus an
inert package root. `src/buddyswitch/catalog/manifest.toml` and
`src/buddyswitch/launcher/assets/roles/` remain unchanged Role source/assets.

## Dependency rule

Python under `src/buddyswitch/foundation/` must not import Application,
Launcher, product modules, historical runtime-support or concrete Role
implementation. Embedded module/path strings, shell commands and packaged
files likewise contain no Launcher, product-module, runtime-support or Role
implementation path. Accepted stable Application process entrypoint module
strings remain explicit current lifecycle interfaces, not implementation
dependencies. Application may depend on both the concrete Role source and
Foundation to compose the running product. Retired generic runtime-support
owners are absent rather than aliased or re-exported.
