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
| R-COMM-001 | scattered Message/IM/service/Tool/inbound/session/channel/worker/tests | S4 Communication | one Communication root and worker contribution |
| R-SEARCH-001 | CLOSED — Search Tool and owning tests are physically aggregated, explicitly composed once, and the dynamic package plus generic host placeholder are absent | S4 Search | `04-independent-component-waves-plan/search/S4-SEARCH-ACCEPTANCE.md` |
| R-EVIDENCE-001 | CLOSED — Evidence Tool and stable broker-backed adapter have one stateless module root and one explicit assembly; retired technical roots and generic host placeholders are absent | S4 Evidence | `04-independent-component-waves-plan/evidence/S4-EVIDENCE-ACCEPTANCE.md` |
| R-CONTEXT-001 | Context projection reading private repos/domains from broad ToolContext | S4 Context | public read composition and one Context Tool |

## Foundation/composition residue

| ID | Current live surface | Owner | Closure proof |
|---|---|---|---|
| R-FND-001 | Demand, Task, Track and Artifact portions CLOSED; fine-grained imports for unmigrated products remain in host entrypoints | S2–S5 | S2/S3/Track–Artifact acceptance; later component registrations only and no product import |
| R-FND-002 | Demand, Task, Search, Track, Artifact and Evidence portions CLOSED through explicit fail-closed registration; global scanner remains for unmigrated Tools | S2–S5 | accepted component lanes; final explicit Tool registrations in S5 |
| R-FND-003 | Demand, Task, Search, Track, Artifact and Evidence private portions CLOSED; broad product-aware ToolContext remains for unmigrated products | S2–S5 | accepted component lanes; final host facts/injected Public capabilities in S5 |
| R-FND-004 | Task and Track Actor Console portions CLOSED through typed section contributions; other product routes/projections and retry coupling remain in Web implementation | S2–S5 | S3/Track–Artifact acceptance; WebHost plus remaining owner contributions |
| R-FND-005 | iMessage worker lifetime hidden in WebHost | S4 Communication | Communication lifecycle contribution |
| R-FND-006 | Demand, Task and Track portions CLOSED through owner CLI contributions; switches for unmigrated products remain | S2–S5 | S2/S3/Track–Artifact acceptance; remaining owner command contributions |
| R-FND-007 | Browser ownership fragmented across lifecycle/Daemon/Broker/proxy | S1/S5 | one Actor browser-runtime owner |
| R-FND-008 | Demand, Task, Track and Artifact portions CLOSED through typed cleanup contributions; attribution for unmigrated products remains | S2–S5 | accepted component lanes; remaining module cleanup contributions |
| R-FND-009 | Identity spread across product/daemon/Web/IM | S1/S5 | foundation Identity owner |
| R-FND-010 | Actor-private/source-reference primitives mixed into product ToolContext | S1/S5 | exact foundation value/capability boundaries |
| R-FND-011 | Demand, Task, Search, Track, Artifact and Evidence portions CLOSED with module-boundary proof; old technical-root enumeration remains for unmigrated components | S1–S5 | accepted component lanes; generic final dependency/topology proofs |
| R-FND-012 | Demand, Task, Search, Track, Artifact and Evidence obsolete paths CLOSED; empty/obsolete technical paths for unmigrated components remain | owning stage/S5 | accepted component lanes; later owner-stage absence proof |

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
| R-DOC-002 | Demand, Task, Search, Track, Artifact and Evidence paths CLOSED; other current component paths remain | S2–S4 | accepted component lanes; later owner cutovers |
| R-DOC-003 | Demand, Task and Track contribution wording CLOSED; remaining Daemon/Web/foundation composition wording awaits final host truth | S5 | accepted component lanes; S5 final host truth |
| R-DOC-004 | root stable Role/manifest paths | S6 | final RoleHost paths |
| R-DOC-005 | migration instructions presented as current policy after completion | S7 | historical-only state |

## Closure rule

Every new residue is registered before change, assigned once, and closed only
with source-bound consumer replacement plus absence proof. Historical memos and
negative absence guards may name retired terms; active code/guidance may not.
