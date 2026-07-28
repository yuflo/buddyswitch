# Modular Monolith Readiness Finding Register

## 1. Status values

- OPEN — evidence supports the finding; target closure is not accepted.
- RESOLVING — an exact target decision and document change are under review.
- CLOSED — target decision, migration owner, and direct proof obligation are
  accepted for this architecture finding. It does not mean the runtime residue
  has already been removed; executable closure remains in the migration
  residue register.
- REJECTED — evidence disproved the finding; reason recorded.

## 2. Findings

| ID | Severity | Finding | Current evidence | Required closure | Stage impact | Status |
|---|---|---|---|---|---|---|
| F-001 | CRITICAL | `src/buddyswitch/**` was proposed without a complete final repository, packaging, entrypoint, configuration, runtime-data, and deletion topology | current implementation spans `scripts/**`, `tools/launcher/**`, `buddyswitch/**`, and `framework/**`; target memo shows only the core package tree | freeze one complete repository topology and old-root disposition | blocks D-002 and S0 | CLOSED |
| F-002 | CRITICAL | target architecture omitted the Actor runtime distribution copied into every Git-free workspace | `ActorEnvironmentBuilder.RUNTIME_COPY_PATHS` and workspace validation require exact old paths | define runtime distribution schema, provenance, package contents, workspace layout, startup, and cleanup | blocks S1 | CLOSED |
| F-003 | HIGH | Actor builder is coupled to product/repository physical paths rather than a stable runtime projection | `actor_environment.py:26-38,171-205,328-330,401-405` | builder consumes one exact runtime distribution plus one Role projection | S0/S1 redesign | CLOSED |
| F-004 | HIGH | current Actor runtime has split provenance: Runtime Broker executes copied workspace code while Env MCP executes repository code | `runtime_broker.sh:31-53`; `env.sh:54,225-296` | choose and prove one attributable deployment/runtime provenance model | blocks final runtime topology | CLOSED |
| F-005 | HIGH | copying the whole proposed source package would expose co-located tests and every Role's private code to each Actor | target places module tests and all Roles under `src/buddyswitch/**`; current workspace intentionally excludes tests and installs selected Role Skills | define filtered/build-time runtime artifact and selected Role projection; prohibit raw source-tree copy | blocks runtime distribution decision | CLOSED |
| F-006 | HIGH | public CLI, test runner, shell helpers, diagnostics, and process managers hard-code retired repository paths | root launchers and shell helpers reference `tools/launcher`, `scripts`, manifest, and framework paths | enumerate final entrypoints and replace every old path in owning stage | affects S1–S6 | CLOSED |
| F-007 | HIGH | existing migration stages do not yet assign complete ownership for Actor build/runtime projection cutover | S1 mentions packaging behavior but no accepted distribution/workspace decision exists | revise stage boundaries only after lifecycle and target-topology audits | blocks roadmap acceptance | CLOSED |
| F-008 | CRITICAL | the proposed `src/` layout has no accepted import, installation, build, or bootstrap model | the repository has no `pyproject.toml`, `setup.py`, or `setup.cfg`; current launchers mutate `PYTHONPATH` or `sys.path` and execute files by repository path | freeze one package/build model and prove every public and child-process entrypoint works without source-layout path surgery | blocks target topology and S1 | CLOSED |
| F-009 | HIGH | the proposed module inventory is incomplete and therefore cannot establish one semantic owner per current capability | current code owns Demand, Task, Track, Artifact, Message/IM, Identity, Actor-private files, Source refs, Search, Evidence, Context, Browser, Daemon, App Server, Runtime Broker, Web and cleanup behavior | classify every current capability as product module, foundation capability, RoleHost contribution, composition, or retired residue | blocks R0/R1 | CLOSED |
| F-010 | HIGH | Role packages and product-owned Skills have no accepted public/private boundary | Role manifests select product behavior Skills, while the target text places Skills privately inside product modules and also assigns Role Skills to RoleHost | define an exported module contribution contract and Role-owned selection/projection without cross-reading module-private files | blocks Role/plugin topology | CLOSED |
| F-011 | HIGH | the active `env_legacy_store.py` facade and other legacy adapters were omitted from the replacement residue inventory | the Actor builder copies `scripts/env_legacy_store.py`; current tests and runtime consumers import it; manifest and repository code also contain compatibility/rejection paths | classify each legacy surface as retired code to delete or an exact negative guard allowed after cutover, with source-bound residue checks | affects S1–S6 and replacement acceptance | CLOSED |
| F-012 | HIGH | test discovery and architecture tests are coupled to the old physical topology far beyond the current stage estimates | `pytest.ini` and `tests/runner.py` admit root `tests/**`; hundreds of test references name `scripts/**`, `tools/launcher/**`, `framework/contracts/**`, and the current manifest path | freeze final test placement/discovery rules and assign each topology-sensitive test to the stage that changes its owner | blocks proof topology | CLOSED |
| F-013 | HIGH | current guidance and Role contracts teach old physical paths and were not included in stage-local replacement scope | root `README.md`, `AGENTS.md`, `docs/arch/**`, Role `AGENTS.md`, Skills and framework contracts name current scripts, launchers, manifest, and runtime commands | inventory every active guidance consumer; replace it in the same stage as its owning behavior; leave history only in historical memos | affects all cutover stages | CLOSED |
| F-014 | HIGH | cleanup is a cross-product semantic owner but has no target boundary or stage-correct migration owner | `scripts/env_cleanup.py` validates Roles, interprets shared state, deletes role-attributable product records and Actor-private files, and handles legacy message paths | decompose cleanup into generic lifecycle cleanup plus module-owned deletion contributions, then assign cutover before affected state owners move | blocks safe product-module migration | CLOSED |
| F-015 | HIGH | Web management currently combines host lifecycle, product projections, IM delivery and an iMessage worker lifecycle, but the roadmap treats it as late generic foundation convergence | `web_management.py` imports HostControl, product repositories, identity, daemon and IM actors; Web process startup owns an iMessage channel worker; retry composes delete/recreate | define WebHost's interface-only contract, module route/projection contributions, and separate worker lifecycle before product modules move | blocks S2–S4 ordering | CLOSED |
| F-016 | HIGH | Browser was classified as a product module without repository evidence | browser state and CDP/proxy processes participate in instance start, stop, delete, daemon inbound handling, Runtime Broker dispatch and `instance.json` | decide whether Browser is a host capability or product aggregate using ownership/change evidence, then give it one lifecycle owner | blocks module inventory and stage order | CLOSED |
| F-017 | HIGH | Identity and runtime path/state location have no explicit target owners | Identity is consumed by central daemon, instance daemon, Web, IM, repositories and ToolContext; `runtime_files.py` infers repository/state roots by parent depth and environment fallbacks | establish foundation Identity and explicit state/runtime locator contracts; forbid parent-depth source-layout inference in the target | blocks foundation and runtime topology | CLOSED |
| F-018 | CRITICAL | one Actor request currently crosses multiple code provenances, and the target has not chosen one attributable runtime identity | CLI, HostControl, Web, daemons, App/Browser managers and Env MCP execute repository files; Runtime Broker executes workspace copies but dynamically loads selected repository handlers via `--repo-root` | make all BuddySwitch processes execute one immutable or source-identifiable runtime distribution; Actor workspace receives only selected Role/config/project/private projections | blocks deployment/runtime topology | CLOSED |
| F-019 | HIGH | the current migration pack does not preserve the complete Actor lifecycle and failure cleanup invariants stage by stage | start, clear, resume, stop, status, interrupt, compact, delete and Web retry coordinate Actor build, broker, App Server, daemon, Browser, thread identity, locks and cleanup | add a lifecycle transition matrix and require every stage to keep each transition runnable with exact rollback/cleanup proof | blocks migration topology | CLOSED |
| F-020 | HIGH | `projects/app` and BuddySwitch implementation source were not explicitly distinguished in the target tree | current builder seeds `projects/app` once into shared project state and symlinks it into each Actor workspace; it is product-under-development data, not framework implementation | preserve `projects/app` as a stable external product mount and define its projection independently from the BuddySwitch package/runtime artifact | blocks repository/workspace topology | CLOSED |
| F-021 | HIGH | explicit module assembly has no accepted staged coexistence rule with the current tool scanner and mixed migrated/unmigrated tools | Env MCP calls the broker; dispatcher uses a registry that scans `env.tools`; product handlers are also imported explicitly by daemon and dispatcher paths | define the single current assembly truth for every stage, with one owner per capability and no permanent scanner/assembly dual path | blocks S2–S5 | CLOSED |
| F-022 | HIGH | the first S1 move map omitted `framework/schemas/**` and misclassified the test-only output-schema validator | result schemas are consumed by `tests/unit/architecture/test_output_schema_boundaries.py`; `scripts/output_schema.py` has no runtime consumer | move schemas to the packaged current contract owner, move the validator to test support, and delete both old paths | blocks S1 source completeness | CLOSED |
| F-023 | HIGH | the first S1 plan still delegated architecture choices to the executor through conditional dispositions and an unspecified build backend | “move or delete”, “retain only if”, “selected backend” and conditional Actor contract projection appeared in the plan | freeze backend, every exceptional source disposition and exact Actor projection before handoff | blocks S0 admission | CLOSED |
| F-024 | HIGH | the S1 process plan promised full process cutover but named only six entrypoints | App Server, Actor build, Browser runtime/proxy, cleanup, diagnostics and command surfaces also execute Python | publish an exact executable-surface allowlist and stop on any newly discovered process | blocks S1 lifecycle proof | CLOSED |
| F-025 | CRITICAL | “one installed runtime” had no installation location, activation owner, interpreter-resolution rule or source-drift behavior | current root wrapper selects `PATH` Python; target previously named only an abstract installed distribution | use one non-editable checkout-local runtime plus atomic activation binding; fail closed on source/distribution/interpreter mismatch and never install during Actor start | blocks runtime provenance | CLOSED |
| F-026 | HIGH | the current Web interface architecture proof asserts retired exact prose after the accepted forward rewrite of `docs/arch/web-interface-call-architecture.md` | isolated run `dc292766c7344aa8b9e7c9811fb98b8a` fails seven stale string tokens; blame shows the test tokens predate document rewrite `f8c53b2` | align the architecture proof to the current single-track owner/consumer contract without restoring superseded wording | blocks S1 preservation baseline | CLOSED |
| F-027 | HIGH | the runless Context contract test still expects the unfiltered global Tool catalog even though parent Context deliberately removes side-only `demand_sys.resolve_inbound` | isolated run `3664a01b7c1a4cbca9ae0bf72c718245`; production filter and test divergence both trace to/around `4b9d297` | prove the parent-visible catalog exposes only parent-authorized Demand actions while the global registry retains the side-only action | blocks S1 preservation baseline | CLOSED |
| F-028 | CRITICAL | importing a Tool directly can enter a Runtime Kernel circular import after Demand ingress composition added a dispatcher import from `env.tool_runtime.context` | isolated run `fb3d4976cf654a00bd6111179729d52d`; `context -> daemon_client -> runtime_kernel.__init__ -> broker -> dispatcher -> context` | make the Runtime Kernel package initialization side-effect free and prove direct Tool imports/dispatch work without an eager Broker import | blocks S1 preservation baseline | CLOSED |
| F-029 | HIGH | S1.1 assigned actual wheel build/install proof to the process-free unit tier | `tests/unit/architecture/test_unit_runtime_policy.py` rejects all child-process creation; wheel build, venv and install necessarily spawn processes | keep static package topology in unit proof and move dynamic distribution/activation proof to `tests/process/package/**` | blocks formal S1 READY | CLOSED |
| F-030 | CRITICAL | the fail-closed installed runtime named no executable first-install owner, leaving launch unable to create the runtime it requires | target launchers reject PATH/source fallback and Actor start cannot install, while the S1 plan previously began only “after non-editable installation” | freeze explicit operator/developer PEP 517 build, venv, non-editable install and installed activation; keep all product launch paths non-installing | blocks formal S1 READY | CLOSED |
| F-031 | HIGH | the blanket ban on root wrappers executing `.py` conflicted with D-020 root ownership of `tests/runner.py` and the requirement that tests not ship in the runtime distribution | target keeps cross-component/process/system tests at root and excludes tests from the built runtime | allow the test-only root runner under the activated interpreter, clear source `PYTHONPATH`, prove package imports are installed, and keep production processes package-only | blocks formal S1 READY | CLOSED |
| F-032 | HIGH | the wrapper plan required reading a JSON-recorded interpreter before any trusted Python existed, which would force fragile shell JSON parsing or a PATH-Python fallback | root wrappers are Bash; target has a deterministic `<runtime-dir>/venv/bin/python` and forbids independent interpreter selection | let shell resolve only runtime dir plus deterministic venv interpreter; installed package alone parses/verifies the activation record | blocks formal S1 READY | CLOSED |
| F-033 | HIGH | two pre-move Tool contract tests still preserved retired direct Demand `create/revise/cancel` actions after `4b9d297` made `resolve_inbound` the only ingress mutation action | executor run `960b3959f7b64f86b29b95329f1d303a`; hub reproduction `c6e52cb80ffd4f33ba0b19caa83e5249`; current Tool definition, Demand architecture, schema and native-MCP proofs all expose `list/get/resolve_inbound/complete`; E1 GREEN `af024ab2e7874b01a658f88f4cbafe5e` proves 27 tests and 465 subtests without production change | update only the stale proof tables and idempotency expectation; production Demand behavior must not change; rerun the exact C2 pre-move baseline | C2 entry proof repaired and preserved by E2's complete unit/integration pre-move groups | CLOSED |
| F-034 | CRITICAL | C1 did not prove that the source package identity corresponded to the installed distribution it activated | E2 RED `ce3cebb704524413a54bc108b67739a5`, GREEN `84b9556aa9754168a7af46bec4179aa0`, C1 milestone `edc222ac236d4422a5bb9da00e19a26d`, complete C2 preservation runs `874221ab1d224e90b2258e771cd9b597` and `ffc941cb10b443598e8fcf9e2434404a`; hub diff/owner/runtime review in `S1-E2-ACCEPTANCE.md` | one source package manifest, one raw-RECORD/actual-tree installed manifest, exact relative-path/byte comparison at activate/verify, full-tree symlink rejection before exclusions, root `pyproject.toml` attribution and no retired independent scan | C1 accepted; fresh C2 packet preparation unblocked | CLOSED |
| F-035 | CRITICAL | the remaining S1 checkpoint order moved/deleted implementation in C2 before C3 cut public/child process consumers and before C4 removed Actor workspace implementation copies | root wrappers, child processes and `ActorEnvironmentBuilder.RUNTIME_COPY_PATHS` trace in `S1-C2-READY-PREFLIGHT.md`; maintainer accepted D-038; complete Unit/Integration/Process/System baseline and `C2C5P-d24c5a85fec6b34a` prove the combined replacement boundary and exact move topology | execute one C2–C5 atomic source-bound packet; no standalone C2/C3/C4 checkpoint, copy, alias or temporarily broken accepted path | resolved by D-038 and the C2–C5 READY pack; implementation remains unstarted | CLOSED |
| F-036 | HIGH | the complete process preservation group contained one stale cheap-action fixture that still selected retired `task_sys.close` | exact RED `284ed5522cf44a009fb1c2a7d5567891` showed the current registry correctly rejected `close`; exact GREEN `e14d3fb26b0e43c992889e2ecca2dd31` selects current read-only `task_sys.list`; complete process GREEN `6768ab5bf5284b3987f1022708caa792` and system GREEN `daa2d57225484b38943edd65da7020b4` | change only the process-test sample; do not restore or alias `close` | C2–C5 preservation baseline repaired | CLOSED |
| F-037 | HIGH | moving current launcher assets below the package exposes four extensionless `LICENSE*` files that the accepted explicit package-data allowlist does not include | first isolated direct-move build activated with `source_only` for DOMPurify `LICENSE`/`LICENSE-MPL`, Highlight.js `LICENSE` and markdown-it `LICENSE`; preflight `C2C5P-d24c5a85fec6b34a` passes after adding only `assets/**/LICENSE*`, with 228/228 dispositions, 238 wheel files and zero test/cache content | add `assets/**/LICENSE*` to `buddyswitch.launcher` package data and prove all four exact resources ship and participate in activation identity | owned by C2–C5 package/source move | OPEN |

## 3. Accepted closure map

| Findings | Accepted closure authority | Executable owner |
|---|---|---|
| F-001, F-008, F-025 | target design §§4, 11; target-topology report §§2, 4–5; D-002–D-005, D-028–D-029 | S1 |
| F-002–F-005, F-018, F-020 | Actor/lifecycle report; target design §§11–13; S1 plan §§1.1, 1.3–1.6 | S1 |
| F-006, F-019, F-024 | S1 process allowlist and lifecycle matrix; R-PKG-006–R-PKG-018 | S1 |
| F-007, F-021 | stage-readiness report; revised S0–S7 roadmap and stage charters | S0, then S1–S5 |
| F-009, F-014–F-017 | component/foundation boundary report; D-012–D-015; stage ownership table | S1–S5 |
| F-010 | target Role/Skill model; D-016–D-017; S6 charter | S2–S6 |
| F-011 | S1 source map and R-PKG-012 | S1 |
| F-012 | target test topology; D-019–D-020; stage proof gates | S1–S7 |
| F-013 | roadmap stage-local guidance law and R-DOC-001–R-DOC-005 | S1–S7 |
| F-022–F-023 | D-029–D-030; S1 package/source/Actor plan | S1 |
| F-026–F-028 | S1 entry-baseline repair packet and source-bound focused RED/GREEN evidence | S1 READY prerequisite |
| F-029–F-031 | D-033–D-035; corrected S1 package/process plan and canonical target topology | S1 READY preparation |
| F-032 | D-036; deterministic wrapper bootstrap plus installed activation owner | S1 READY preparation |
| F-033 | `BS-MM-S1-E1-20260728-01`; GREEN `af024ab2e7874b01a658f88f4cbafe5e`; hub diff/owner review | S1 C2-entry prerequisite |
| F-034 | `BS-MM-S1-E2-20260728-01`; `S1-E2-ACCEPTANCE.md`; RED/GREEN, complete C1 milestone and complete C2 pre-move preservation evidence | S1 C1 checkpoint |

F-001–F-025 have an accepted target, stage owner and
direct proof obligation. Their runtime surfaces deliberately remain
`OBSERVED` in the residue register until the owning implementation stage
removes and proves them.

F-026–F-028 were discovered by the S1 source-refresh preservation run. Their
repair was accepted by the coordinating hub in
`01-single-package-runtime-cutover-plan/ENTRY-BASELINE-ACCEPTANCE.md` against
patch `7c861a672c53231aea422660f38ae3c2f0114837d67a4f5f84992da866c785ab`
and fresh run `e0b6718a11b2498da29d09309bb7766e`.

F-029–F-032 were plan-level contradictions found by the coordinating hub
during formal S1 READY review. Their closure changes no current executable
behavior; it removes executor ambiguity before runtime migration begins.

F-033–F-034 were discovered when the first formal S1 packet returned at C2.
E1 closed F-033 and exposed the broader provenance failure before widening
scope. E2 then closed F-034 through exact source/install correspondence and
complete affected preservation proof. The coordinating hub accepted C1 in
`S1-E2-ACCEPTANCE.md`; C2 still requires a new source-bound Goal Packet.

## 4. Finding format

New findings record:

```text
ID:
Severity:
Consumer-visible risk:
Current source evidence:
Contradicted or missing target claim:
Required target decision:
Migration stage/owner:
Direct proof:
Status:
```

No finding is closed by adding prose alone when an executable invariant can own
the final rule.
