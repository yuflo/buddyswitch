# S5 C6E Web Runtime Implementation Plan

> **For agentic workers:** follow root `AGENTS.md`, `$buddyswitch-testing` and
> the independent-session workflow. This plan freezes outcome and boundaries;
> it does not transcribe a patch.

**Goal:** Give the generic Web runtime, its passive contracts and UI assets one
direct Foundation owner while preserving the complete public Web loop.

**Architecture:** Application explicitly configures one Foundation Web host.
The host consumes injected Host Control and passive component contributions.
The shared machine envelope has one sibling `cli_runtime` contract owner; the
CLI host itself remains for the next cutover.

**Tech stack:** Python 3.13, standard-library HTTP server, packaged HTML/CSS/JS,
installed PEP 517 runtime and the existing public BuddySwitch runner.

## Coherent execution blocks

### 1. Reproduce and rediscover

- Verify exact clean commit/runtime/resource identity.
- Rediscover every import, path, package projection, test/support reference and
  current-doc representation from repository facts.
- Treat path lists as minimum known representation classes, not a ceiling.

### 2. Establish behavior-preserving entry proof

- Reuse the three source-bound preparation runs while identities match.
- Select current exact assertions for ready success, bind rejection, route
  failure, HTTP success/error, worker cleanup and installed assets.
- Add only the smallest missing owner/replacement assertion; do not build a
  static-analysis framework or manufacture RED for the move.

### 3. Move direct owners atomically

- Create inert `foundation.web_runtime` and `foundation.cli_runtime` roots.
- Move—not copy—the Web contracts, Web runtime, machine CLI contract and Web
  static assets to the selected owners.
- Keep `web-management` protocol/state identifiers and all UI contents exact.
- Update the runtime's asset root to the owner-local installed location.

### 4. Cut over every consumer

- Update application composition/entrypoint, component adapters, generic CLI
  contract consumer, tests/support, package data and current architecture docs.
- Preserve one explicit application configuration path and injected Host
  Control; do not introduce a registry, locator, container or fallback import.

### 5. Replace every old representation

- Delete the three retired Launcher Python owners and Launcher Web asset tree.
- Prove old source/import/path and installed projections are absent.
- Leave the remaining Launcher CLI, Codex config, shell and Role assets intact;
  deleting or redesigning them belongs to later checkpoints.

### 6. Reprovision and verify

- After the coherent source mutation, build/install/activate/verify once before
  the next public test command.
- Run executor-discovered exact and affected proof, including package and the
  real Web System loop with attributable cleanup.
- Review all executable representations, freeze, then run one FINAL. If any
  executable change follows, use the bounded FIX_AFTER_FINAL cycle.

## Executor authority

The executor owns equivalent internal names, file splits, mechanical consumer
discovery, exact target selection and bounded owner-local repairs. It may
correct stale path hypotheses without asking the hub.

The executor may not change Web/CLI/product semantics, redesign CliHost or its
shell owners, move Codex config or Role assets, introduce compatibility or
generalized infrastructure, update migration master truth, commit, push or
start C7/S6.
