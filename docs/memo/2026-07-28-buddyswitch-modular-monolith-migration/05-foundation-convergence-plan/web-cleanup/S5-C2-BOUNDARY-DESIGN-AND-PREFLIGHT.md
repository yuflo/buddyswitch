# S5 C2 Boundary Design and Preflight

## 1. Accepted outcome

> Existing Track and Communication HTTP behavior is selected through passive
> typed route contributions, generic WebHost imports no concrete product
> module, and cleanup derives every product projection field from selected
> cleanup contributions while preserving current user-visible effects.

This is a semantic host-boundary cutover, not the later C4 state/process or C6
interface-host physical convergence.

## 2. Web contribution contract

One route registration owns:

```text
name
factory(WebHostAccess) -> WebRoute
exact_paths: tuple[str, ...]
prefixes: tuple[str, ...]
```

Exact spelling may follow repository style. Required semantics are:

- at least one exact path or prefix;
- exact paths are query-free canonical `/api/...` paths;
- prefixes are query-free canonical `/api/.../` prefixes;
- duplicate/overlapping contributed matchers fail application build;
- a contributed matcher overlapping a reserved built-in host route fails
  before Web readiness;
- factories remain passive during application assembly;
- dispatch matches the URL path, not the raw query-bearing request;
- exact matching does not capture neighboring paths;
- prefix matching does not capture a mere textual neighbor such as
  `/api/imposter` or `/api/tracks-extra`.

Track contributes one route adapter covering exact `/api/tracks` and prefix
`/api/tracks/`. The adapter calls existing Track Public external reads and
preserves list/detail payloads and current `HttpError` behavior. The generic
route host contract owns the existing product-neutral HTTP error value
(`status`, `code`, `message`, optional `details`); Track and WebHost use that
one type. Keeping its current definition inside the WebManagement
implementation is not part of the accepted boundary.

Communication mechanically declares only prefix `/api/im/`. Its route,
identity, worker and Message behavior do not change.

Rejected alternatives:

- route-owned arbitrary `matches()` hides collisions and cannot fail closed
  during passive assembly;
- one registration per Track path creates duplicate route instances for one
  product adapter;
- a single broad textual prefix recreates the current false-neighbor defect;
- a global product route table or runtime discovery is a second registry.

## 3. Generic cleanup projection

`CleanupContribution` remains the sole selected unit. Its optional
`CleanupIndexProjection` continues declaring the plan/result ID field and
opaque record field. The host must:

1. validate all contributions and projection field names before discovery;
2. create category counts and projection lists from those contributions;
3. reject duplicate/colliding projection fields;
4. append opaque records during planning without product parsing;
5. reconcile actually deleted IDs from every contributed projection;
6. return the contributed object-ID fields dynamically.

Current Artifact, Message and Track Comment declarations therefore still
produce:

```text
artifact_object_ids / artifact_records
message_object_ids / message_records
comment_object_ids / comment_records
```

No JSON field rename, state move or compatibility layer is introduced. A
synthetic new contribution with different safe field names must work without
editing the host. Actor-private cleanup remains a Foundation-owned built-in
because it is workspace isolation, not product state.

Rejected alternatives:

- renaming output to a new universal `objects` schema changes observable CLI
  output without improving the current boundary;
- letting modules mutate the plan/result directly gives multiple write paths;
- retaining the three-field host list and adding future cases preserves the
  bottleneck;
- moving cleanup physically before C4/C6 mixes ownership and path-lifecycle
  risks.

## 4. Boundary matrix

| Claim | Positive proof | Negative/adversarial proof |
|---|---|---|
| passive composition | Track and Communication registrations validate without factory calls | duplicate name/exact/prefix and malformed matchers fail closed |
| exact route | `/api/tracks` reaches Track list | `/api/tracks-extra` is not captured |
| prefix route | Track detail and `/api/im/messages` reach their owners | `/api/imposter` and unowned nested/mutation routes remain 404 |
| product ownership | Track adapter calls Track Public and returns existing DTO/error | generic WebHost source has no `buddyswitch.modules` import or Track branch |
| worker lifetime | current Communication preparation/start/stop behavior remains | preparation failure blocks ready; failed worker is not stopped as started |
| projection derivation | all selected current fields appear unchanged | a novel valid projection needs no host edit; duplicate/collision fails |
| cleanup effects | role/all-data and returned IDs agree with actual deletion | unsafe/stale/symlinked/owner-rejected paths do not appear as deleted |
| CLI | current command and JSON bridge remain | no product import/switch or alternate output flag appears |
| correspondence | application-selected registrations/contributions equal host inputs | no discovery, fallback registration or second projection list exists |
| cleanup | test roots and attributable processes/resources are absent | no C2-created runtime process or state survives |

## 5. Representative final-topology preflight

Probe `S5C2P-20260804-02` ran from executable base `e687fa2...` through the
activated installed runtime. It instantiated the proposed exact/prefix
registration shape and actual selected cleanup contribution topology.

The command was an inline, read-only installed-Python probe defining one
passive registration value, validation and dispatch function; it then imported
`build_application`, `CleanupContribution` and `CleanupIndexProjection` and
asserted:

```text
Track exact /api/tracks                    -> selected
Track prefix /api/tracks/track-alpha      -> selected
Communication /api/im/messages?cursor=1   -> selected
/api/tracks-extra                         -> unselected
/api/imposter                             -> unselected
duplicate exact route                     -> rejected
overlapping contributed prefix            -> rejected
reserved host-route overlap               -> rejected
factories during validation               -> zero
current cleanup categories                -> 7 selected contributions
current projection fields                 -> derived Artifact/Comment/Message fields
novel probe_object_ids/probe_records       -> initialized without host enumeration
```

Result:

```text
S5C2P-20260804-02 PASS
web positive=3 neighbor_negative=2 collisions=4 passive_factory=true
cleanup current_contributions=demand_aggregates,task_records,artifact_objects,artifact_attachments,track_objects,comment_objects,message_objects
cleanup projection_fields=artifact_object_ids,comment_object_ids,message_object_ids
cleanup novel_projection=probe_object_ids/probe_records collisions=3
```

`S5-C2-PREFLIGHT-COMMAND.md` preserves the exact command and output. The
earlier narrower probe `S5C2P-20260804-01` is superseded non-evidence because
it did not exercise reserved-route and projection-field collisions.

The probe created no file, process, socket, lock or runtime state. It proves
the selected mechanism and current topology are coherent; it is not executor
RED/GREEN evidence.

## 6. Boundary completeness decision

No semantic or public decision remains for the executor:

- Track Public operations and DTOs are frozen;
- route matching semantics and collision behavior are fixed above;
- cleanup fields and destructive authority are frozen;
- the current physical host/state roots remain until their named C4/C6
  checkpoint;
- exact implementation layout inside the authorized boundary is private
  executor judgment.

C2 can leave one runnable product path without C3–C7 repair.
