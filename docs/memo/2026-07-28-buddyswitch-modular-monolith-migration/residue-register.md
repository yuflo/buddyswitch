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
| R-PKG-016 | REMOVING — packaged Role/Skill guidance is current; root README/AGENTS/docs remain | S1 C6 | `S1-C2-C5-ACCEPTANCE.md`; C6 current-guidance and final residue proof |
| R-PKG-017 | CLOSED — runtime Python formerly resolved without activation binding | S1 | `S1-C2-C5-ACCEPTANCE.md`; exact activation record, non-editable install and mismatch failure |
| R-PKG-018 | CLOSED — schema and test-only validator move-map omissions | S1 | `S1-C2-C5-ACCEPTANCE.md`; schemas packaged, validator in test support, old paths absent |
| R-PKG-019 | CLOSED — C1 runtime attribution formerly lacked one-to-one path/content correspondence between valid non-test source package inputs and the installed package | S1 C1 E2 | `S1-E2-ACCEPTANCE.md`; exact source/install manifest equality at activate/verify, full-tree symlink rejection, required runtime-asset attribution, co-located test/cache exclusion and complete C1/C2 preservation proof |

## Component residue

| ID | Current semantic surface after S1 | Owner | Closure proof |
|---|---|---|---|
| R-DEMAND-001 | scattered Demand domain/state/Tool/Daemon/Web/Skill/tests | S2 | one Demand root/assembly/state path |
| R-TASK-001 | scattered Task/Goal domain/state/Tool/Daemon/Web/tests | S3 | one Task root and exact Demand Public edge |
| R-TRACK-001 | scattered Track/comment/repo/Tool/inbound/Skill/tests | S4 Track | one Track root/assembly |
| R-ARTIFACT-001 | scattered Artifact/relation/visibility/config/Tool/Skill/tests | S4 Artifact | one Artifact root/assembly |
| R-COMM-001 | scattered Message/IM/service/Tool/inbound/session/channel/worker/tests | S4 Communication | one Communication root and worker contribution |
| R-SEARCH-001 | Search Tool/capability mixed into shared Tool context | S4 Search | one Search capability assembly |
| R-EVIDENCE-001 | Evidence Tool/capability mixed with Artifact/browser context | S4 Evidence | one capability plus Artifact Public |
| R-CONTEXT-001 | Context projection reading private repos/domains from broad ToolContext | S4 Context | public read composition and one Context Tool |

## Foundation/composition residue

| ID | Current live surface | Owner | Closure proof |
|---|---|---|---|
| R-FND-001 | fine-grained product imports in Daemon entrypoint | S2–S5 | component registrations only; no product import |
| R-FND-002 | global Tool package scanner and silent invalid omission | S2–S5 | explicit fail-closed Tool registrations |
| R-FND-003 | broad product-aware ToolContext | S2–S5 | host facts/injected Public capabilities only |
| R-FND-004 | product routes/projections and retry coupling in Web implementation | S2–S5 | WebHost plus owner contributions |
| R-FND-005 | iMessage worker lifetime hidden in WebHost | S4 Communication | Communication lifecycle contribution |
| R-FND-006 | product command switches in CLI/shared entrypoints | S2–S5 | owner command contributions |
| R-FND-007 | Browser ownership fragmented across lifecycle/Daemon/Broker/proxy | S1/S5 | one Actor browser-runtime owner |
| R-FND-008 | product schema/Role attribution inside generic cleanup | S2–S5 | module cleanup contributions |
| R-FND-009 | Identity spread across product/daemon/Web/IM | S1/S5 | foundation Identity owner |
| R-FND-010 | Actor-private/source-reference primitives mixed into product ToolContext | S1/S5 | exact foundation value/capability boundaries |
| R-FND-011 | architecture tests enumerating old technical roots | S1–S5 | generic final dependency/topology proofs |
| R-FND-012 | empty/obsolete in-package technical paths after component moves | owning stage/S5 | paths/imports absent |

## Role residue

| ID | Current live surface | Owner | Closure proof |
|---|---|---|---|
| R-ROLE-001 | central Role/Skill catalog | S6 | RoleHost + assembled Skill exports only |
| R-ROLE-002 | central Role profile/contract truth | S6 | Role package-owned descriptor/assets |
| R-ROLE-003 | Role bootstrap `AGENTS` outside Role package | S6 | Role package projection |
| R-ROLE-004 | shared product Skills consumed by path from central catalog | S2–S6 | typed module Skill exports and Role ID selection |
| R-ROLE-005 | Role authority/list/start/cleanup bound to central manifest | S6 | RoleHost contract |
| R-ROLE-006 | Actor projection able to see non-selected Role/Skills | S1/S6 | exact workspace allowlist |

## Documentation/migration residue

| ID | Current live surface | Owner | Closure proof |
|---|---|---|---|
| R-DOC-001 | current architecture paths changed by S1 | S1 | `docs/arch` matches package/runtime truth |
| R-DOC-002 | Demand/Task/current component paths | S2–S4 | updated with owner cutover |
| R-DOC-003 | Daemon/Web/foundation composition wording | S5 | final host truth |
| R-DOC-004 | root stable Role/manifest paths | S6 | final RoleHost paths |
| R-DOC-005 | migration instructions presented as current policy after completion | S7 | historical-only state |

## Closure rule

Every new residue is registered before change, assigned once, and closed only
with source-bound consumer replacement plus absence proof. Historical memos and
negative absence guards may name retired terms; active code/guidance may not.
