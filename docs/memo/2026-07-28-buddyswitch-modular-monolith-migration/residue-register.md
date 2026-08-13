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
| R-FND-001 | CLOSED — every Foundation owner and executable representation is free of component, Application, Launcher and current Role implementation dependencies | S2–S5 | `05-foundation-convergence-plan/tool-host/S5-TOOL-HOST-ACCEPTANCE.md`; `05-foundation-convergence-plan/final-acceptance/S5-C7-ACCEPTANCE.md` |
| R-FND-002 | CLOSED — all eight current Tools are explicitly registered once; package scanner, dynamic loader, discovery APIs, old global Tool package root and discovery-shaped guidance are absent | S2–S5 | `05-foundation-convergence-plan/tool-host/S5-TOOL-HOST-ACCEPTANCE.md` |
| R-FND-003 | CLOSED — ToolContext contains only production-consumed host facts/capabilities and no repository/domain/Browser/private service-locator bag or unused alias/helper | S2–S5 | `05-foundation-convergence-plan/tool-host/S5-TOOL-HOST-ACCEPTANCE.md` |
| R-FND-004 | CLOSED — Track and Communication own their passive route adapters; generic WebHost imports no product module and contains no Track dispatch branch or parser | S2–S5 C2 | `05-foundation-convergence-plan/web-cleanup/S5-C2-ACCEPTANCE.md`; exact/prefix contribution proof and concrete-import/branch absence |
| R-FND-005 | CLOSED — iMessage worker lifetime is a passive Communication contribution run by generic WebHost lifecycle | S4 Communication | `04-independent-component-waves-plan/communication/S4-COMMUNICATION-ACCEPTANCE.md` |
| R-FND-006 | CLOSED — every current product CLI command enters through its passive module contribution; generic CLI Runtime contains no product command switch | S2–S5 | S2/S3/S4 component acceptance; `05-foundation-convergence-plan/cli-runtime/S5-C6F-ACCEPTANCE.md`; final S5 proof |
| R-FND-007 | CLOSED — Browser config, target transport, lifecycle, runtime, Daemon handlers, cockpit proxy and asset have one Actor-scoped `foundation/browser_runtime/**` owner; old `env`/`launcher` implementations and asset are absent | S5 C3 | `05-foundation-convergence-plan/browser-runtime/S5-C3-ACCEPTANCE.md`; exact/affected/frozen FINAL and old-path/import absence |
| R-FND-008 | CLOSED — cleanup category counts, plan/result fields and actual-ID reconciliation derive from selected typed contributions without product category/field enumeration | S2–S5 C2 | `05-foundation-convergence-plan/web-cleanup/S5-C2-ACCEPTANCE.md`; novel projection, truthful guarded-effect result and product-literal absence proof |
| R-FND-009 | CLOSED — Identity models/profile persistence, State primitives and process-start identity have direct Foundation owners; retired `env/**`, the old process-identity path and zero-consumer helper surfaces are absent | S1/S5 C4 | `05-foundation-convergence-plan/identity-state-process/S5-C4-ACCEPTANCE.md`; exact/affected/frozen FINAL and replacement proof |
| R-FND-010 | CLOSED — ToolContext exposes the exact resolved Actor-private root as a host fact; no repository bag owns that access | S1/S5 | `05-foundation-convergence-plan/tool-host/S5-TOOL-HOST-ACCEPTANCE.md` |
| R-FND-011 | CLOSED — every former technical root has one direct Foundation/Application/Role-stage owner; generic S5 owners no longer remain under historical roots | S1–S5 | C1–C7 acceptance; `05-foundation-convergence-plan/final-acceptance/S5-C7-ACCEPTANCE.md`; D-063/D-072 |
| R-FND-012 | CLOSED — old Tool/runtime/host technical roots, zero-consumer facades and the three generic runtime-support paths are absent from source and installed package | owning stage/S5 | `05-foundation-convergence-plan/tool-host/S5-TOOL-HOST-ACCEPTANCE.md`; `05-foundation-convergence-plan/final-acceptance/S5-C7-ACCEPTANCE.md` |
| R-FND-013 | CLOSED — Runtime Broker has one `foundation/runtime_broker/**` owner; shared service-neutral framing has one process-runtime owner; `runtime_kernel/**` and installed residue are absent | S5 C5A | `05-foundation-convergence-plan/runtime-broker/S5-C5A-ACCEPTANCE.md`; exact/affected/frozen FINAL and replacement proof |
| R-FND-014 | CLOSED — central and instance Daemon have one direct Foundation owner; application supplies App/Actor capability plus module/Browser registrations; the shared event log has one Process Runtime owner; retired Launcher owners and reverse dependencies are absent | S5 C5B | `05-foundation-convergence-plan/daemon/S5-C5B-ACCEPTANCE.md`; exact/affected/frozen FINAL, installed correspondence and replacement proof |
| R-FND-015 | CLOSED — App Server Python runtime and shell projection have one direct `foundation/app_server/**` owner; all consumers and package assets use it, and the retired Launcher Python/shell/import/path surfaces are absent | S5 C6A | `05-foundation-convergence-plan/app-server/S5-C6A-ACCEPTANCE.md`; exact/affected/frozen FINAL, installed correspondence and replacement proof |
| R-FND-016 | CLOSED — Actor capability, Codex runtime descriptor, parent Session and side-thread lifecycle/registry have one direct `foundation/actor_runtime/**` owner; application/Demand/Host/CLI consumers use it and all six retired Launcher paths are absent | S5 C6B | `05-foundation-convergence-plan/actor-runtime/S5-C6B-ACCEPTANCE.md`; exact/affected/System/frozen FINAL, installed correspondence and replacement proof |
| R-FND-017 | CLOSED — Actor workspace publication has one direct `foundation/actor_runtime/environment.py` owner; application supplies one resolved Role/Skill bootstrap and the retired Launcher owner is absent | S5 C6C | `05-foundation-convergence-plan/actor-environment/S5-C6C-ACCEPTANCE.md`; direct/affected/package/System/frozen FINAL, installed correspondence and replacement proof |
| R-FND-018 | CLOSED — Host Control lifecycle and shared runtime lock have direct Foundation owners; application supplies the exact Role and executable facts through one input; all Foundation Python/shell representations are free of upward implementation dependencies and retired Launcher owners are absent | S5 C6D | `05-foundation-convergence-plan/host-control/S5-C6D-ACCEPTANCE.md`; exact/affected/frozen FINAL, recursive shell proof and installed correspondence |
| R-FND-019 | CLOSED — generic Web runtime/contracts and Web UI assets have one `foundation/web_runtime/**` owner; the shared machine envelope has one `foundation/cli_runtime/contracts.py` owner; Application supplies the concrete attach module and retired Launcher owners are absent | S5 C6E | `05-foundation-convergence-plan/web-runtime/S5-C6E-ACCEPTANCE.md`; exact/affected/System/frozen FINAL, embedded-dependency and installed correspondence proof |
| R-FND-020 | CLOSED — public CLI host, Codex config and environment/cleanup/Browser shell adapters have one `foundation/cli_runtime/**` owner; Application supplies one required immutable input; Launcher contains only its inert root and unchanged S6 Role assets | S5 C6F | `05-foundation-convergence-plan/cli-runtime/S5-C6F-ACCEPTANCE.md`; exact/affected/System/frozen FINAL, recursive executable-root and installed correspondence proof |
| R-FND-021 | CLOSED — passive Skill/cleanup contracts, generic cleanup and diagnostics have direct Foundation owners; Runtime Broker and all Foundation representations have no current Role implementation edge; retired runtime-support files are absent from source and install | S5 C7 | `05-foundation-convergence-plan/final-acceptance/S5-C7-ACCEPTANCE.md`; architecture `c07abe8f…`; FINAL `364f7e924501414a9ca48b3404645307` |

## Role residue

| ID | Current live surface | Owner | Closure proof |
|---|---|---|---|
| R-ROLE-001 | CLOSED — central Role/Skill catalog is absent; Application combines reviewed Role packages with explicit component Skill exports | S6 | `06-role-host-cutover-plan/S6-ACCEPTANCE.md`; RoleHost/architecture/package/FINAL proof |
| R-ROLE-002 | CLOSED — each Role package owns its descriptor and result-schema asset; central profiles/contracts are absent | S6 | `S6-ACCEPTANCE.md`; Role-local unit/contract proof and retired-path absence |
| R-ROLE-003 | CLOSED — AGENTS exists only in each reviewed Role package and only the selected file reaches an Actor | S6 | real investor Actor `0245baaa9b20402e845d21a77a6dbda6`; FINAL |
| R-ROLE-004 | CLOSED — every shared product Skill enters through an explicit component `SkillExport`; Role-private Skills remain package-local | S2–S6 | S2–S4 module acceptance; S6 private-Skill GREEN `285538ef4b7e4c8091d306ab2ea59ab5` |
| R-ROLE-005 | CLOSED — authority/list/start/cleanup and Broker/CLI/ToolContext consume narrow Application/RoleHost projections with no manifest path | S6 | affected `af4886c1a3654524804bf5f1315561ca`; FINAL |
| R-ROLE-006 | CLOSED — Actor bootstrap resolves only the selected package AGENTS and selected local/public Skills | S1/S6 | RoleHost exact proof and real investor Actor proof |
| R-ROLE-007 | CLOSED — the single runner dynamically discovers Role-local approved tiers once and the wheel excludes all Role tests | S6 | runner/package `fd32828193b74698b17bf9d79c884065`; FINAL |

## Documentation/migration residue

| ID | Current live surface | Owner | Closure proof |
|---|---|---|---|
| R-DOC-001 | CLOSED — current architecture paths match accepted S1 installed-package truth | S1 | `01-single-package-runtime-cutover-plan/S1-ACCEPTANCE.md` |
| R-DOC-002 | CLOSED — every S2–S4 component path is current and its retired live guidance is absent | S2–S4 | accepted component lanes, including `S4-CONTEXT-ACCEPTANCE.md` |
| R-DOC-003 | CLOSED — current Foundation, Actor, App, Daemon, Broker, Web, CLI and cleanup guidance matches the sole accepted S5 owner topology | S5 | accepted component lanes; C5/C6 acceptance records; `05-foundation-convergence-plan/final-acceptance/S5-C7-ACCEPTANCE.md` |
| R-DOC-004 | CLOSED — root/current architecture guidance names RoleHost and physically aggregated Role packages, not manifest/profile paths | S6 | `docs/arch/role-host-architecture.md`; S6 package/current-doc proof |
| R-DOC-005 | CONFIRMED — migration instructions remain active only through S7; after final acceptance the hub must mark the pack historical and remove it from current execution authority | S7 | passing frozen S7 acceptance + coordinating historical-only promotion |

## Closure rule

Every new residue is registered before change, assigned once, and closed only
with source-bound consumer replacement plus absence proof. Historical memos and
negative absence guards may name retired terms; active code/guidance may not.
