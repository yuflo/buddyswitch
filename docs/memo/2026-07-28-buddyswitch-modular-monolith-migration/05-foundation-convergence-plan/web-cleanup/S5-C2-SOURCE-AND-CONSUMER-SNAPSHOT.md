# S5 C2 Source and Consumer Snapshot

## 1. Identity

```text
executable base:       e687fa264408de0bf70f7f7411194e78d044dad9
branch:                fea-tool
base worktree:         clean
runtime activated_at:  2026-08-04T09:56:44.746545Z
runtime source:        8a0bbe8f7607cad0e574b6ce17a0aac4a68cab13d907b21eeb11999f15682a64
runtime distribution:  4f68eb5a09accb22003d5089ec33947f6419a2ade1181d830c20e286d918812a
runtime.verify:         ok=true
package version:       0.1.0
```

The executable base is the accepted and pushed C1 checkpoint. The later C2
preparation commit changes coordinating documents only; the independent
handoff names its exact clean `HEAD`.

Current preservation evidence is C1 replacement FINAL
`7841f5d5614141728a2db56a4612d8f4`:

```text
./buddyswitch-test full
Unit:        477 passed
JavaScript:  147 passed
Integration: 770 passed
Process:     260 passed
System:      22 passed
result:      PASS
cleanup:     run root and attributable resources absent
```

That FINAL is source-equivalent for every C2 executable and proof file. The
hub did not mechanically rerun the same source after C1 acceptance.

## 2. Current Web path

```text
Browser app.js
  -> GET /api/tracks | /api/tracks/{id}
    -> launcher.web_management.WebManagementService.handle_api
      -> concrete import buddyswitch.modules.track.public
        -> Track external-safe list/get projection

application.composition
  -> Communication ModuleAssembly.web_routes/web_workers
    -> application.build validation/flattening
      -> WebManagementService contributed prefix dispatch
```

The contribution mechanism is real and already owns Communication. The
remaining defect is narrow: generic `web_management.py` imports Track and
contains the Track list/detail branches and parser. Adding or removing that
product route still edits the host.

### Web owners and consumers

| Class | Current source/consumer | C2 disposition |
|---|---|---|
| host contract | `src/buddyswitch/launcher/web_contracts.py` | express passive exact and prefix matchers plus the route error contract |
| generic host | `src/buddyswitch/launcher/web_management.py` | remove Track import/branches/parser; dispatch only validated registrations |
| product owner | `src/buddyswitch/modules/track/private/adapters/web.py` | own existing Track list/detail HTTP projection |
| product assembly | `src/buddyswitch/modules/track/module.py` | contribute the Track route once |
| existing route owner | `src/buddyswitch/modules/communication/private/adapters/web/registration.py` | mechanically adopt the matcher contract; preserve IM behavior |
| composition | `src/buddyswitch/application/build.py`, `foundation/composition/__init__.py` | validate and carry the same passive route values |
| entrypoint | `application/entrypoints/web.py` | preserve; no semantic change expected |
| browser consumer | `launcher/assets/web-management/app.js` | preserve route strings and payload use |
| direct Web proofs | `tests/unit/web/**`, `tests/integration/web/**`, `tests/integration/im/test_external_projection.py` | prove matching, preparation/lifetime and exact product results |
| architecture proofs | `tests/unit/architecture/test_component_web_contributions.py` and component boundary tests | derive topology from assembly and forbid concrete imports |

The current public CLI already delegates product reads through typed command
registrations and imports neither Track nor Task product code. C2 re-proves
that fact; it does not manufacture a CLI rewrite.

## 3. Current cleanup path

```text
selected ModuleAssembly.cleanup contributions
  -> application.build
    -> application.entrypoints.cleanup
      -> runtime_support.env_cleanup plan
        -> preview JSON or guarded effect-time execution
          -> public data.cleanup JSON result
```

Discovery, attribution and product schema parsing already live in Demand,
Task, Track, Artifact and Communication adapters. Effect-time path/root
validation, actor-private deletion authority, deepest-first deletion and
truthful result filtering correctly remain generic host behavior.

The remaining defect is the projection shape inside the host:

- `new_plan` creates `artifact_*`, `message_*` and `comment_*` fields;
- `_actual_index_object_ids` enumerates those three object-ID fields;
- result construction writes those same three fields;
- `CATEGORY_ORDER` pre-enumerates `message_objects` even though selected
  contributions already supply every category.

The contribution already owns the desired field names through
`CleanupIndexProjection`. C2 therefore derives initialization, duplicate
validation, execution reconciliation and result projection from selected
contributions while preserving the exact current JSON field names.

### Cleanup owners and consumers

| Class | Current source/consumer | C2 disposition |
|---|---|---|
| generic host/contract | `src/buddyswitch/runtime_support/env_cleanup.py` | remove product field/category enumeration; derive from typed contributions |
| component contributors | `modules/{demand,task,track,artifact,communication}/private/adapters/cleanup.py` | preserve discovery and field declarations; mechanical contract edits only if required |
| composition | `application/build.py`, `foundation/composition/__init__.py` | preserve passive selection; validate new collision invariant at one owner |
| public bridge | `launcher/cli.py`, `launcher/shell/cleanup.sh`, `application/entrypoints/cleanup.py` | preserve command, confirmation, JSON and exit behavior |
| direct proofs | `tests/integration/env_tool/test_cleanup.py` | path safety, role/all-data, warning and result truth |
| process proofs | `tests/process/cli/test_cleanup_cli.py`, `tests/process/launcher/test_public_cli.py` | one-line JSON and public bridge behavior |
| architecture proofs | component boundary tests and `test_repo_contracts.py` | generic host derives topology and contains no product enumeration |

No production consumer other than the JSON bridge reads the three object-ID
fields. They nevertheless remain frozen in C2 because preserving observable
effect is cheaper and the current typed contributions can derive them without
host product knowledge.

## 4. Protected assertion inventory

The current suite contains direct assertions for:

- Track list rows, detail payload, archived/missing 404, invalid request
  mapping and absence of Track mutation/subpanel routes;
- query-preserving contributed dispatch, route preparation before readiness,
  invalid route rejection, duplicate rejection and worker fail-soft/reverse
  shutdown;
- Communication `/api/im/*` projection and no HostControl call;
- role-scoped and all-data cleanup, multi-owner Message selection, malformed
  warning behavior, required skeletons and exact current projection fields;
- effect-time root/parent revalidation, leaf-link handling, actor-private
  owner rejection, deepest-first deletion and truthful returned IDs;
- cleanup process JSON, public `data cleanup` bridge and confirmation/errors;
- generic CLI neutrality and current component assembly topology.

These assertions ran in FINAL `7841f5d5614141728a2db56a4612d8f4`.

## 5. Representations and residue

The refresh covered direct imports, literal routes, registration values,
application flattening, browser strings, process entrypoints, output fields,
tests and current architecture documents. It found no generated route table,
runtime package scanner, config-driven Web activation or second cleanup
registry.

C2-owned residue is therefore exactly:

1. the concrete Track import and branches in generic WebHost;
2. host-enumerated product cleanup categories/fields;
3. tests/docs that preserve those ownership defects rather than derive the
   current composition.

Physical relocation of Web/CLI/cleanup technical-history files is not C2
residue. C4 owns generic state/process primitives and C6 owns final interface
hosts after Browser and Broker/Daemon dependencies have moved.

## 6. Contrary signals

During hub refresh, the unsupported exploratory command
`./buddyswitch-codex runtime verify` returned `UNKNOWN_COMMAND`. It changed no
state and is non-evidence. The canonical installed entrypoint immediately
passed:

```text
BUDDYSWITCH_RUNTIME_DIR="$PWD/.buddyswitch-runtime" \
  .buddyswitch-runtime/venv/bin/python \
  -m buddyswitch.application.entrypoints.runtime_activation verify
```

The invalid spelling is recorded so it is not transmitted to the executor.
No test failure, timeout, flake or resource residue remains unresolved.
