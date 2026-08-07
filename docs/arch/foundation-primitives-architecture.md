# Foundation Primitives Architecture

## Purpose

Foundation primitives provide small, product-neutral owners for identity,
runtime state, actor-private cleanup, and process-start identity. Product and
host modules import these owners directly; the package roots are inert.

## Owners

- `src/buddyswitch/foundation/identity/model.py` owns `IdentityRef`, Actor and
  external profile value models, validation, and stable payloads.
- `src/buddyswitch/foundation/identity/profiles.py` owns canonical profile paths
  plus guarded Actor and external profile persistence.
- `src/buddyswitch/foundation/state/runtime.py` owns environment-derived roots,
  runtime-workspace detection, write guards, identifiers, timestamps, and
  atomic JSON object storage.
- `src/buddyswitch/foundation/state/actor_private.py` owns only containment-safe
  deletion used by runtime cleanup.
- `src/buddyswitch/foundation/process_runtime/process_identity.py` owns exact
  process-start records and liveness checks used by lifecycle controllers.

## Dependency direction

```text
identity model <- identity profiles -> state runtime
product or host consumer -----------> direct Foundation owner
lifecycle controller ---------------> process identity
runtime cleanup --------------------> actor-private deletion
```

Foundation primitive owners do not import product modules, launchers, runtime
kernel modules, or runtime-support modules. Composition and consumer policy
remain outside Foundation.

## State and mutation

`state/runtime.py` derives `ROOT`, `STATE_ROOT`, `OBJECTS_ROOT`, and
`LOCAL_ROOT` from explicit environment inputs and refreshes them as one set.
Canonical object mutations pass the appropriate runtime or Central IM write
guard and replace a complete JSON object atomically. Identity profiles are
normalized before the guarded write, and reads reject malformed or non-object
payloads.

Actor-private cleanup receives an explicit root and logical name, rejects
existing paths that resolve outside that root, and deletes only regular files.
Process lifecycle controllers likewise act only on a PID whose recorded start
identity still matches the live process.
