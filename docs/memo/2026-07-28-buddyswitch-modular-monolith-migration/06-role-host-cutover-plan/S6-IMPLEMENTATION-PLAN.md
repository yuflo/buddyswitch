# S6 RoleHost Implementation Plan

> The independent executor owns exact files, signatures, local ordering and
> dynamic test target discovery. This plan freezes outcome, dependency direction
> and proof—not a hand-transcribed patch.

## Goal

Replace all central Role/Skill/profile/contract truth with physically aggregated
reviewed Role packages and one narrow RoleHost, preserving current behavior and
making directory-only Role addition real.

## Coherent block 1 — public Role contract and local packages

- Add the smallest exact Role descriptor and immutable projection contracts
  under `foundation/role_host/**`.
- Move each existing Role's AGENTS, private Skills and still-live Role assets
  into its package without retaining central copies or re-exports.
- Express only current consumer-required capabilities. Retire duplicated profile
  assertions that have no production consumer; do not recreate a central Role
  profile schema in another directory.
- Add the meaningful read-only `secondary-market-investor` Role package.
- Give Role-local tests physical ownership under the approved tiers.

## Coherent block 2 — RoleHost and Application composition

- Discover exact reviewed package entrypoints from one trusted installed root
  and fail closed before runtime/Actor publication.
- Validate explicit identity, duplicates, local paths/assets, containment and
  selected Skills. Combine Role-private Skill exports with the already explicit
  component Skill exports; reject unknown or duplicate IDs.
- Construct RoleHost from Application composition. Do not add a module list,
  generalized provider object, service locator or second registry.
- Configure Tool authority from validated Role IDs and the exact permissions in
  current Tool registrations, preserving known/unknown outcomes without a
  duplicate permission catalog.

## Coherent block 3 — every live consumer

- Actor build/start resolves bootstrap only through RoleHost and keeps the
  Foundation publisher code-free and atomic.
- Host Control, CLI Runtime, cleanup and diagnostics receive narrow RoleHost
  projections directly from Application.
- Runtime Broker/server/session/lifecycle and shells remove manifest path and
  `--manifest`; dispatch obtains the selected Role runtime projection from an
  explicit Application-supplied capability.
- ToolHost removes the manifest argument from authorization and dispatch context.
  `ToolContext` carries only the selected immutable Role runtime fact.
- Artifact, Search and Context consume that public fact. Remove unused manifest
  declarations from other tools/tests.
- Remove test-only manifest/profile entrypoints rather than preserving an
  otherwise unused interface.

Repository facts decide the smallest concrete call shape. A stale path or an
omitted mechanical consumer inside these classes is executor work, not a reason
to return to the hub.

## Coherent block 4 — package, runner, replacement and current truth

- Package every Role's required code/AGENTS/Skill/assets; exclude Role tests.
- Extend the one runner to Role-local approved tiers exactly once and prove
  focused target validation plus full discovery.
- Update root/cross-owner tests, fixtures, schemas and installed correspondence
  to the final topology; keep true Role-local tests with the Role.
- Delete central catalog/profile/Skill/Role-contract/Launcher Role paths and any
  inert roots left with no consumer.
- Remove legacy manifest translation, manifest CLI/path/environment arguments,
  patch targets and current guidance. Negative guards and historical memos may
  name them only to prove absence.
- Update root `AGENTS.md`, README and current architecture docs to the one Role
  package/RoleHost truth.

## Proof obligations

1. Existing five Roles have equivalent list/start/bootstrap/Skill/capability,
   Tool authority, Artifact template and source-access behavior.
2. The sixth Role is discovered and runnable without an Application, host or
   central-list edit.
3. Duplicate ID, malformed descriptor, missing asset, unknown/duplicate Skill,
   absolute/escape/symlink path and invalid capability fail before Actor
   publication, with no partial Actor root/record/service.
4. Actor output contains exactly selected AGENTS and Skills, no code, tests,
   descriptor, unselected Skill or other Role content.
5. CLI sandbox, Browser registration, Broker v2 success/failure, Tool dispatch,
   Context/Search/Artifact behavior, cleanup filtering, diagnostics and Host
   Control remain consumer-observable.
6. Foundation imports no concrete Role; RoleHost cannot activate modules; Role
   addition requires only one valid packaged directory.
7. Wheel/source correspondence includes required Role resources, excludes all
   tests, and contains none of the retired central paths.

## Verification sequence

1. Reproduce clean entry identity and partition any drift.
2. Use identity-valid preservation evidence; do not manufacture a refactor RED.
3. Implement the whole coherent source/test/package/current-doc candidate.
4. Provision, install, activate and verify the complete candidate before any
   public-runner command that imports changed source.
5. Discover and run exact RoleHost/package/Role-local unit and contract proof.
6. Run affected Application/Foundation/module/process/Actor real-boundary proof.
7. Review the complete diff and all executable, shell, installed and guidance
   representations; freeze once and run one `./buddyswitch-test full` FINAL.
8. Any executable edit after FINAL uses bounded FIX_AFTER_FINAL: diagnose one
   owner, exact proof, reprovision after source edits, affected proof and one
   replacement FINAL. Do not blind-rerun.

## Stop conditions

Stop only if current facts require a new product capability, product-module
Public redesign, protected external/data coexistence, arbitrary remote plugin
loading, an unavoidable compatibility path, or a canonical data move. Exact
file/signature/test-target correction and owner-correct fixes within the named
RoleHost/Application/consumer/package/proof boundary are executor-owned.
