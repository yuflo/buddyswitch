# Modular Monolith Migration Residue Register

Statuses:

- `OBSERVED`: present at the audit baseline;
- `CONFIRMED`: re-traced at stage source identity;
- `REMOVING`: owning stage active;
- `CLOSED`: consumer replacement and absence proved;
- `RECLASSIFIED`: accepted current interface, with decision reference.

## S1 package/runtime residue

| ID | Current live surface | Owner | Closure proof |
|---|---|---|---|
| R-PKG-001 | CLOSED — executable/product Python formerly under `scripts/**` | S1 | `S1-C2-C5-ACCEPTANCE.md`; package replacement and old executable tree absent |
| R-PKG-002 | CLOSED — executable Python/shell formerly under `tools/launcher/**` | S1 | `S1-C2-C5-ACCEPTANCE.md`; installed package entrypoints/hosts and old tree absent |
| R-PKG-003 | CLOSED — runtime assets formerly under `tools/launcher/assets/**` | S1 | `S1-C2-C5-ACCEPTANCE.md`; packaged current owner and old assets absent |
| R-PKG-004 | CLOSED physically — runtime manifest, profiles and Skills moved; S6 still owns semantic RoleHost replacement | S1 physical move; S6 semantic removal | `S1-C2-C5-ACCEPTANCE.md`; no runtime old root |
| R-PKG-005 | CLOSED physically — runtime contracts/config moved; owner stages still finalize semantics | S1 physical move; owner stages finalize | `S1-C2-C5-ACCEPTANCE.md`; package owner and old paths absent |
| R-PKG-006 | CLOSED — root launcher formerly sourced shell/file-path implementation | S1 | `S1-C2-C5-ACCEPTANCE.md`; thin installed-package delegation |
| R-PKG-007 | CLOSED — test runner repository `PYTHONPATH` surgery | S1 | `S1-C2-C5-ACCEPTANCE.md`; activated package test path and source PYTHONPATH absent |
| R-PKG-008 | CLOSED — `sys.path` mutation and parent-depth import bootstrap | S1 | `S1-C2-C5-ACCEPTANCE.md`; source scan absent |
| R-PKG-009 | CLOSED — Runtime Broker copied into Actor workspace | S1 | `S1-C2-C5-ACCEPTANCE.md`; code-free Actor allowlist |
| R-PKG-010 | CLOSED — Env MCP/host processes executing checkout code | S1 | `S1-C2-C5-ACCEPTANCE.md`; same installed runtime identity |
| R-PKG-011 | CLOSED — Broker dynamic checkout loading with `--repo-root` | S1 | `S1-C2-C5-ACCEPTANCE.md`; package import and source loader/argument absent |
| R-PKG-012 | CLOSED — copied legacy store facade | S1 | `S1-C2-C5-ACCEPTANCE.md`; file/import absent except negative guard |
| R-PKG-013 | CLOSED — Actor copied manifest/profile/contract/diagnostic implementation | S1 | `S1-C2-C5-ACCEPTANCE.md`; selected projection only |
| R-PKG-014 | CLOSED — source-layout runtime/state inference | S1 | `S1-C2-C5-ACCEPTANCE.md`; explicit locator use |
| R-PKG-015 | CLOSED — fixtures asserting executable old paths | S1 | `S1-C2-C5-ACCEPTANCE.md`; current proofs and old-path absence |
| R-PKG-016 | CLOSED — packaged and root/current guidance names current package owners | S1 C6 | `01-single-package-runtime-cutover-plan/S1-ACCEPTANCE.md` |
| R-PKG-017 | CLOSED — runtime Python formerly resolved without activation binding | S1 | `S1-C2-C5-ACCEPTANCE.md`; exact activation record, non-editable install and mismatch failure |
| R-PKG-018 | CLOSED — schema and test-only validator move-map omissions | S1 | `S1-C2-C5-ACCEPTANCE.md`; schemas packaged, validator in test support, old paths absent |
| R-PKG-019 | CLOSED — C1 runtime attribution formerly lacked one-to-one path/content correspondence between valid non-test source package inputs and the installed package | S1 C1 E2 | `S1-E2-ACCEPTANCE.md`; exact source/install manifest equality at activate/verify, full-tree symlink rejection, required runtime-asset attribution, co-located test/cache exclusion and complete C1/C2 preservation proof |

## Component residue

| ID | Current semantic surface after S1 | Owner | Closure proof |
|---|---|---|---|
| R-DEMAND-001 | CLOSED — Demand domain/state/adapters/assets/Skills/tests physically aggregated under one Demand root and selected once by application composition | S2 | `02-demand-component-pilot-plan/S2-ACCEPTANCE.md`; one owner/Public/state path and retired Demand paths absent |
| R-TASK-001 | CLOSED — Task state, Tool, Goal adapters, CLI/Web/cleanup contributions and owning tests are physically aggregated under one Task root and selected once by application composition | S3 | `03-task-goal-boundary-cutover-plan/S3-ACCEPTANCE.md`; one owner/Public/state path, exact acyclic Demand collaboration and retired Task paths absent |
| R-TRACK-001 | CLOSED — Track state, domain, Tool, inbound, CLI/Web projections, Skills and owning tests have one module root and one explicit assembly | S4 Track | `04-independent-component-waves-plan/track-artifact/S4-TRACK-ARTIFACT-ACCEPTANCE.md` |
| R-ARTIFACT-001 | CLOSED — Artifact state, domain, Tool, selection assets, Skill and owning tests have one module root and one explicit assembly | S4 Artifact | `04-independent-component-waves-plan/track-artifact/S4-TRACK-ARTIFACT-ACCEPTANCE.md` |
| R-COMM-001 | CLOSED — Message/IM/service/Tool/inbound/session/channel/worker/tests have one Communication root and one explicit assembly | S4 Communication | `04-independent-component-waves-plan/communication/S4-COMMUNICATION-ACCEPTANCE.md` |
| R-SEARCH-001 | CLOSED — Search Tool and owning tests are physically aggregated, explicitly composed once, and the dynamic package plus generic host placeholder are absent | S4 Search | `04-independent-component-waves-plan/search/S4-SEARCH-ACCEPTANCE.md` |
| R-EVIDENCE-001 | CLOSED — Evidence Tool and stable broker-backed adapter have one stateless module root and one explicit assembly; retired technical roots and generic host placeholders are absent | S4 Evidence | `04-independent-component-waves-plan/evidence/S4-EVIDENCE-ACCEPTANCE.md` |
| R-CONTEXT-001 | CLOSED — Context is one last-selected read-only module over accepted Public reads; its old dynamic Tool package and Context-only shared ToolContext surfaces are absent | S4 Context | `04-independent-component-waves-plan/context/S4-CONTEXT-ACCEPTANCE.md` |

## Foundation/composition residue

| ID | Current live surface | Owner | Closure proof |
|---|---|---|---|
| R-FND-001 | C1 TOOLHOST PORTION CLOSED — Foundation ToolHost imports no component or Role implementation; later S5 checkpoints own remaining concrete host imports | S2–S5 | `05-foundation-convergence-plan/tool-host/S5-TOOL-HOST-ACCEPTANCE.md`; final S5 foundation import proof |
| R-FND-002 | CLOSED — all eight current Tools are explicitly registered once; package scanner, dynamic loader, discovery APIs, old global Tool package root and discovery-shaped guidance are absent | S2–S5 | `05-foundation-convergence-plan/tool-host/S5-TOOL-HOST-ACCEPTANCE.md` |
| R-FND-003 | CLOSED — ToolContext contains only production-consumed host facts/capabilities and no repository/domain/Browser/private service-locator bag or unused alias/helper | S2–S5 | `05-foundation-convergence-plan/tool-host/S5-TOOL-HOST-ACCEPTANCE.md` |
| R-FND-004 | CLOSED — Track and Communication own their passive route adapters; generic WebHost imports no product module and contains no Track dispatch branch or parser | S2–S5 C2 | `05-foundation-convergence-plan/web-cleanup/S5-C2-ACCEPTANCE.md`; exact/prefix contribution proof and concrete-import/branch absence |
| R-FND-005 | CLOSED — iMessage worker lifetime is a passive Communication contribution run by generic WebHost lifecycle | S4 Communication | `04-independent-component-waves-plan/communication/S4-COMMUNICATION-ACCEPTANCE.md` |
| R-FND-006 | Demand, Task and Track portions CLOSED through owner CLI contributions; switches for unmigrated products remain | S2–S5 | S2/S3/Track–Artifact acceptance; remaining owner command contributions |
| R-FND-007 | CLOSED — Browser config, target transport, lifecycle, runtime, Daemon handlers, cockpit proxy and asset have one Actor-scoped `foundation/browser_runtime/**` owner; old `env`/`launcher` implementations and asset are absent | S5 C3 | `05-foundation-convergence-plan/browser-runtime/S5-C3-ACCEPTANCE.md`; exact/affected/frozen FINAL and old-path/import absence |
| R-FND-008 | CLOSED — cleanup category counts, plan/result fields and actual-ID reconciliation derive from selected typed contributions without product category/field enumeration | S2–S5 C2 | `05-foundation-convergence-plan/web-cleanup/S5-C2-ACCEPTANCE.md`; novel projection, truthful guarded-effect result and product-literal absence proof |
| R-FND-009 | Communication-owned IM identity portion CLOSED; remaining foundation identity is spread across lifecycle/daemon/Web | S1/S5 | Communication acceptance; final foundation Identity owner |
| R-FND-010 | CLOSED — ToolContext exposes the exact resolved Actor-private root as a host fact; no repository bag owns that access | S1/S5 | `05-foundation-convergence-plan/tool-host/S5-TOOL-HOST-ACCEPTANCE.md` |
| R-FND-011 | CONFIRMED — S5 refresh classified remaining technical roots into seven owner-bounded checkpoints | S1–S5 | C1–C7 acceptance and generic final dependency/topology proofs |
| R-FND-012 | C1 TOOLHOST PORTION CLOSED — old Tool runtime/package/client/MCP paths and the zero-consumer Broker facade are absent; later technical roots retain their checkpoint owners | owning stage/S5 | `05-foundation-convergence-plan/tool-host/S5-TOOL-HOST-ACCEPTANCE.md`; S5 final foundation absence proof |

## Role residue

| ID | Current live surface | Owner | Closure proof |
|---|---|---|---|
| R-ROLE-001 | central Role/Skill catalog | S6 | RoleHost + assembled Skill exports only |
| R-ROLE-002 | central Role profile/contract truth | S6 | Role package-owned descriptor/assets |
| R-ROLE-003 | Role bootstrap `AGENTS` outside Role package | S6 | Role package projection |
| R-ROLE-004 | Demand Skill path rows CLOSED through typed module exports; other shared product Skills and central Role selection remain | S2–S6 | S2 acceptance for Demand; remaining module exports and final RoleHost selection |
| R-ROLE-005 | Role authority/list/start/cleanup bound to central manifest | S6 | RoleHost contract |
| R-ROLE-006 | Actor projection able to see non-selected Role/Skills | S1/S6 | exact workspace allowlist |

## Documentation/migration residue

| ID | Current live surface | Owner | Closure proof |
|---|---|---|---|
| R-DOC-001 | CLOSED — current architecture paths match accepted S1 installed-package truth | S1 | `01-single-package-runtime-cutover-plan/S1-ACCEPTANCE.md` |
| R-DOC-002 | CLOSED — every S2–S4 component path is current and its retired live guidance is absent | S2–S4 | accepted component lanes, including `S4-CONTEXT-ACCEPTANCE.md` |
| R-DOC-003 | Demand, Task, Track and Communication contribution wording CLOSED; remaining Daemon/Web/foundation composition wording awaits final host truth | S5 | accepted component lanes; S5 final host truth |
| R-DOC-004 | root stable Role/manifest paths | S6 | final RoleHost paths |
| R-DOC-005 | migration instructions presented as current policy after completion | S7 | historical-only state |

## Closure rule

Every new residue is registered before change, assigned once, and closed only
with source-bound consumer replacement plus absence proof. Historical memos and
negative absence guards may name retired terms; active code/guidance may not.
