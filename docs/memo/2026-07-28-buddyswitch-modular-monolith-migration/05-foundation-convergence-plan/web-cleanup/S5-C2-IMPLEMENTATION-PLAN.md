# S5 C2 Implementation Plan

## 1. Goal

Move Track HTTP meaning out of generic WebHost and remove product field
enumeration from generic cleanup, preserving every current route, payload,
error, deletion effect, output field and CLI behavior.

## 2. Authority model

The packet freezes outcome, semantic owners, matcher/projection contracts,
protected effects, evidence classes and dependency order. Paths below are the
current-source map, not a transcription contract. Within the classified C2
boundary, the executor owns the smallest owner-correct move/delete/rewrite and
current runner target discovery under root `AGENTS.md`, D-051, D-059 and
`$buddyswitch-testing`.

Do not preserve an unused surface because a test imports it. Do not widen C2
because a later physical move appears aesthetically adjacent.

## 3. Classified write boundary

| Class | Semantic authority | Current likely paths |
|---|---|---|
| OWNER | Track HTTP adapter and Track assembly contribution | `modules/track/private/adapters/web.py`, `modules/track/module.py` |
| HOST CONTRACT | typed Web matcher/error values; typed cleanup contribution/projection values | `launcher/web_contracts.py`, contract portion of `runtime_support/env_cleanup.py` |
| HOST | generic Web dispatch; generic cleanup planning/execution/result projection | `launcher/web_management.py`, `runtime_support/env_cleanup.py` |
| CONSUMER | Communication route matcher declaration and mechanically affected component adapters | `modules/communication/private/adapters/web/registration.py`, cleanup adapters only if the frozen contract requires it |
| COMPOSITION | passive validation/flattening and duplicate detection | `application/build.py`, `foundation/composition/__init__.py` |
| PROOF | direct Web/cleanup/CLI and generic architecture proofs | current root test tiers and true module-local owner tests |
| CURRENT DOC | current Web, Track and Communication architecture truth | `docs/arch/web-interface-call-architecture.md`, `track-capability-architecture.md`, `communication-capability-architecture.md` |
| SHARED | no other product meaning | any additional shared file must be demonstrated as a direct C2 consumer before edit |

Forbidden: Browser lifecycle, HostControl behavior, Actor lifecycle, Broker,
Daemon, identity/state/process relocation, RoleHost, static UI behavior,
Track/Communication Public semantics, persisted schemas/paths, test runner,
packaging policy, C3–C7 and unrelated cleanup.

## 4. Coherent block A — Web route ownership

1. Establish a behavior RED or identity-valid preservation baseline at the
   nearest generic matcher and Track HTTP boundary. Required detection:
   exact/prefix dispatch, false-neighbor rejection, passive validation and
   Track registration ownership.
2. Express the accepted exact/prefix contract and fail-closed validation.
3. Move existing Track list/detail translation and error mapping into the
   Track-owned adapter; contribute it once from Track assembly.
4. Remove the concrete Track import, branches and parser from generic WebHost.
5. Mechanically update Communication and all real consumers to the one current
   contract; add no alias or fallback.
6. Preserve route preparation, query forwarding, HTTP errors and worker
   lifecycle.

Block A is incomplete while WebHost can answer Track without the selected
Track contribution or while a false textual neighbor is captured.

## 5. Coherent block B — cleanup projection ownership

1. Add or refine a behavior proof using a novel projection field pair and
   duplicate/collision input. It must fail on host enumeration and detect
   dynamic plan plus effect-result behavior.
2. Validate contributions once before destructive discovery/effect.
3. Derive counts, plan projection lists, actual-ID reconciliation and result
   fields from selected contributions.
4. Remove every Artifact/Message/Comment field/category enumeration from the
   generic host while preserving those fields when their current contributors
   are selected.
5. Preserve D-055 effect-time guards and all warning/deletion truth.

Block B is incomplete if a new valid projection still requires a host edit or
if a failed deletion remains in returned IDs/paths/counts.

The executor may implement A and B in either local order, but both form one C2
candidate. They share one final composition contract and one runtime
reprovision boundary. Do not run a partial candidate as FINAL.

## 6. Runtime and proof order

1. Verify the clean handoff identity and current installed runtime with the
   canonical installed `runtime_activation verify` entrypoint.
2. Reuse the source-equivalent C1 FINAL as preservation evidence; run only a
   missing intent-appropriate RED discovered under `$buddyswitch-testing`.
3. Complete the coherent C2 source mutation.
4. Before any subsequent public-runner command, rebuild, non-editably install,
   activate and verify the declared checkout runtime.
5. Run direct GREEN for matcher/Track ownership and generic projection/effect
   truth.
6. Run affected Web, cleanup, application/composition, CLI/process/package and
   architecture proof at the narrowest sufficient current tiers.
7. Inspect source/import/residue absence and `git diff --check`; clean every
   attributable resource.
8. Freeze one candidate and run exactly one `./buddyswitch-test full`.

If the frozen FINAL exposes an attributable defect inside the authorized C2
boundary, follow `$buddyswitch-testing` FIX_AFTER_FINAL: repair the owner,
reprovision after package-source change, prove exact/affected, freeze a new
identity and run one replacement full. A neighboring or boundary-changing
failure is returned for hub review. A later pass never erases the first
signal.

## 7. Proof obligations

### Product/contract

- exact Track list/detail payloads and current 400/404 mapping;
- unowned/mutation/subpanel routes remain 404;
- Communication IM route and worker behavior unchanged;
- role/all-data cleanup and current JSON fields unchanged;
- public cleanup command, confirmation, JSON and exit behavior unchanged.

### Architecture/replacement

- generic WebHost imports no `buddyswitch.modules.*`;
- Track assembly contributes the route once;
- application validates exact/prefix duplicates without factory calls;
- cleanup host contains no product category or projection field literals;
- one application-selected contribution path; no scanner, alias, fallback or
  second registry;
- CLI remains product-neutral without source rewrite unless facts require it.

### Operations

- route preparation before ready and worker start/stop/close remain exact;
- cleanup effect-time root/parent/leaf/actor-private guards remain exact;
- result paths/counts/IDs reflect only actual effects;
- runtime identity is current and all test/process/temp resources are absent.

## 8. Return boundary

Return one result packet with source/diff identity, exact changed/deleted
paths, final route/contribution topology, projection derivation, all proof/run
identities, runtime identity, every contrary signal and disposition, cleanup,
residue proposal and `ACCEPTED`/`REJECTED` proposal. Do not edit master
decision/ledger/residue/acceptance truth, commit, push or begin C3.
