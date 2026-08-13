# BuddySwitch Forward Residue Cleanup Implementation Plan

> **For agentic workers:** execute this plan in order on the current `fea-tool`
> worktree. Use the repository `buddyswitch-testing` skill for target discovery,
> evidence identity and FINAL. Do not introduce a compatibility path, cleanup
> framework, alternate runner or second package owner.

**Goal:** remove the remaining retired repository roots, empty installed package
shells and test-only package contract while preserving the accepted installed
runtime behavior and every current product consumer.

**Architecture:** `src/buddyswitch/**` remains the only Python source root and the
installed wheel remains the only product execution source. Remove unconsumed
`config` and `launcher` packages outright; keep package-data only beside real
current owners. Treat ignored local output separately from tracked architecture
so local cleanup cannot rewrite product semantics.

**Tech stack:** Python 3.13, setuptools/PEP 517, pytest through
`./buddyswitch-test`, Bash launchers, Markdown architecture guidance.

---

## 1. Acceptance sentence

From a clean checkout and from the activated installed runtime, BuddySwitch has
one package/source topology: no root `artifacts`, `buddyswitch`, `framework`,
`scripts` or `tools` tree; no installed `buddyswitch.config` or
`buddyswitch.launcher` package; all current Role, module, Foundation,
Application, CLI, Web, Daemon, Broker and Tool behavior remains observable.

## 2. Findings and design decision

The 2026-08-13 read-only audit found no executable dual track. Root launchers use
the isolated installed package, clear source overrides and never import
`build/lib`. The remaining problem is narrower:

- `artifacts/.gitkeep` preserves a retired workspace artifact root;
- `src/buddyswitch/config/__init__.py` and
  `src/buddyswitch/launcher/__init__.py` install two packages with no production
  consumer or owned resource;
- `pyproject.toml`, package tests and current CLI architecture guidance protect
  those empty packages;
- the package fixture manufactures `launcher/assets/docs/help.md`, so a test-only
  resource keeps an otherwise unused package contract alive;
- deleted old roots remain as untracked empty physical directories;
- ignored build/output directories make the checkout noisy but are not product
  import paths.

Decision: perform one direct deletion cutover. Do not rename these roots, retain
an inert namespace, add an alias, or create a general residue scanner. Two exact
owner-local regressions are sufficient: repository topology and package topology.

## 3. Protected state

Do not alter or delete:

- `.buddyswitch-runtime/` until the replacement wheel is installed and activated;
- `docs/spec/` (97 MB of pre-existing ignored evidence);
- `docs/memo/2026-07-28-buddyswitch-modular-monolith-migration/**`, which is
  historical evidence and not current execution authority;
- `projects/app/`, `.agents/`, current `docs/arch/**`, Role packages, module-local
  tests or any product behavior unrelated to residue removal.

The ignored `output/`, `tmp/`, `build/`, `src/buddyswitch.egg-info/` and
`docs/.DS_Store` paths are regenerable local noise. Remove them only by explicit
validated target after all material content is classified. Never use a broad
recursive target or repository-wide clean command.

## 4. File matrix

### Delete tracked residue

- `artifacts/.gitkeep`
- `src/buddyswitch/config/__init__.py`
- `src/buddyswitch/launcher/__init__.py`

### Modify current owners and proofs

- `pyproject.toml` — remove package-data entries for the deleted packages.
- `tests/unit/architecture/test_repo_contracts.py` — assert the exact retired
  root set is absent.
- `tests/unit/architecture/test_package_contract.py` — assert the two retired
  installed package roots are absent and package-data names real owners only.
- `tests/support/package_runtime.py` — stop manufacturing a Launcher asset;
  retain only the package/test/cache correspondence probe.
- `tests/process/package/test_distribution_install.py` — prove the probe package
  ships while colocated tests/caches do not, without a fake Launcher resource.
- `tests/unit/architecture/test_cli_runtime_foundation_owner.py` — remove the
  assertion that protects Launcher package data.
- `tests/unit/architecture/test_web_runtime_foundation_owner.py` — remove the
  same obsolete assertion.
- `docs/arch/cli-runtime-architecture.md` — state that no Launcher package root
  remains rather than describing an inert root.
- this memo — record evidence and final disposition after executable FINAL.

### Remove physical-only residue after tracked deletion

- `artifacts/`
- `buddyswitch/`
- `framework/`
- `scripts/`
- `tools/`
- `src/buddyswitch/config/`
- `src/buddyswitch/launcher/assets/`
- `src/buddyswitch/launcher/`

Use `rmdir` on these exact paths so any unexpected content fails closed.

## 5. Execution tasks

### Task 1 — Freeze entry identity and write exact RED

- [x] Record HEAD, upstream, tracked/index/non-ignored-untracked state and ignored
  local inventory.
- [x] Add `test_retired_repository_roots_are_absent` to
  `test_repo_contracts.py` with the exact root set from section 4.
- [x] Add `test_retired_empty_packages_are_absent` to
  `test_package_contract.py` for `config` and `launcher`.
- [x] Run only the two node IDs in one compatible focused command.
- [x] Accept RED only when it reports the currently present exact paths. An
  import/setup/runner failure is not valid RED.

Canonical command:

```bash
./buddyswitch-test focused \
  tests/unit/architecture/test_repo_contracts.py::test_retired_repository_roots_are_absent \
  tests/unit/architecture/test_package_contract.py::test_retired_empty_packages_are_absent
```

### Task 2 — Make the coherent deletion cutover

- [x] Delete the three tracked residue files.
- [x] Remove only `buddyswitch.config` and `buddyswitch.launcher` from package
  data and direct expected sets.
- [x] Remove the fake Launcher runtime asset from the isolated package fixture
  and its process assertion; preserve the real probe package and test/cache
  exclusion assertions.
- [x] Remove obsolete CLI/Web package-data assertions.
- [x] Update current CLI architecture guidance.
- [x] Use exact `rmdir` calls for physical-only empty paths. If any is non-empty,
  stop and classify it rather than deleting recursively.
- [x] Run static residue scans and `git diff --check`; do not run the public test
  runner after package source changes until reprovision completes.

### Task 3 — Reprovision exactly once before GREEN

- [x] Create one `/private/tmp/bs-forward-residue-cleanup.*` build root.
- [x] Copy only `pyproject.toml` and `src/` into its `source/` directory so PEP
  517 cannot recreate `build/` or `egg-info` in the checkout.
- [x] Build one wheel with the existing runtime Python using `pip wheel
  --no-deps --no-build-isolation`.
- [x] Force-reinstall `buddyswitch==0.1.0` from that wheel into the existing
  non-editable runtime.
- [x] Run installed `runtime_activation activate --source-root <repo>` and then
  `verify` with `python -I`.
- [x] Prove installed `buddyswitch/config` and `buddyswitch/launcher` are absent.
- [x] Move the exact temporary build root to a unique path under the user's
  Trash after success; do not use `rm -rf`.

### Task 4 — Efficient GREEN and IMPACT proof

- [x] Re-run the exact two-node command from Task 1. One run proves exact GREEN.
- [x] Run one compatible affected batch discovered from the actual final diff:

```bash
./buddyswitch-test focused \
  tests/unit/architecture/test_repo_contracts.py \
  tests/unit/architecture/test_package_contract.py \
  tests/unit/architecture/test_cli_runtime_foundation_owner.py \
  tests/unit/architecture/test_web_runtime_foundation_owner.py \
  tests/process/package/test_distribution_install.py \
  tests/process/package/test_runtime_activation.py
```

- [x] Do not rerun unchanged exact targets separately after the affected batch.
- [x] Treat no-collection, failure, flake, timeout or cleanup residue as new
  evidence; diagnose before any retry.

### Task 5 — Local checkout hygiene

- [x] Confirm ignored-path contents and dates again.
- [x] Preserve `.buddyswitch-runtime/` and `docs/spec/`.
- [x] Remove only classified regenerable checkout noise:
  `build/`, `src/buddyswitch.egg-info/`, `output/`, `tmp/` and
  `docs/.DS_Store`.
- [x] Prefer moving material directories to unique paths under
  `/Users/chen/.Trash`; do not overwrite an existing Trash target.
- [x] Confirm root topology, Git state and installed runtime identity remain
  exact after local cleanup.

### Task 6 — Review, freeze and FINAL once

- [x] Review the diff against Product, Contract, Architecture, Replacement and
  Operations proof classes.
- [x] Freeze HEAD/patch/index/untracked/runtime identities and confirm
  `git diff --check`.
- [x] Run exactly one `./buddyswitch-test full` on the frozen executable
  candidate.
- [x] If FINAL fails, preserve the signal. Do not blind-rerun. Any executable
  repair requires exact/affected proof, reprovision when package source changed,
  and one new FINAL after refreeze.
- [x] After a passing FINAL, update only this memo with run IDs, results,
  cleanup and residual risk; this prose-only update does not invalidate
  executable evidence.
- [x] Commit the coherent cleanup and memo, push `fea-tool`, and prove local
  HEAD equals `origin/fea-tool` with a clean tracked worktree.

## 6. Proof mapping

| Proof class | Required evidence |
|---|---|
| Product | existing frozen FINAL; no public behavior or consumer contract changes |
| Contract | package-data contains only real owners; wheel equals source package |
| Architecture | exact root/package absence tests and current CLI architecture doc |
| Replacement | old roots, installed empty packages and fake asset contract absent |
| Operations | non-editable activation verify, clean runner roots and preserved runtime |

## 7. Stop conditions

Stop and replan if:

- any deleted package has a production consumer;
- removing it requires a replacement namespace, alias or fallback;
- an exact empty directory contains unclassified data;
- `docs/spec/` or another pre-existing user artifact would be deleted;
- the activated installed package cannot exactly correspond to source;
- a focused or FINAL failure is outside this boundary and remains unexplained.

## 8. Evidence record

Status: `ACCEPTED — FORWARD SINGLE TRACK VERIFIED`

```text
Entry identity: 699704563a72bd940a0473f9a9aa26bf8584e7c0 matched
                origin/fea-tool with a clean tracked/index worktree; the plan
                was frozen separately in dbb6894a2fd4c64135b03968f410a51994b33966.
RED:            4cce6821a0e145548bcf38e42798ec87 — two exact expected
                failures for the present root and package shells.
Changed files:  three tracked residue files deleted; package data, isolated
                distribution fixture/proof, architecture proofs and current CLI
                architecture guidance moved to the one-root truth.
Runtime activation:
                activated_at 2026-08-13T10:12:49.820192Z
                source 1b448cb325b59287913d2e2c52efa4303fe277c9669f19a3c3a623e67cc23921
                distribution 85ff440cd64eeb8a895af655a7e9b2372856df8fa03741b0534f24bb9887ce7f
                package 0.1.0; final runtime.verify ok=true.
Exact GREEN:    5f4ac5271ba346b9890c70b1a54a8c89 — 2 passed.
Affected proof: 6b3a8999f0254cc8879c46705ddc96b0 — 34 passed and two
                stale inert-Launcher expectations found; repaired nodes passed
                in 57a10443343a4632ba13f51e7a4cc041.
First FINAL:    906ccc08275d4029b4aa9353f0c75b93 — stopped in Unit
                with two further stale tests reading the removed package root;
                no blind retry. The exact finding repair passed in
                214a9b5eb57740ed8dd47980d32845cd.
Replacement FINAL:
                b95c9d876152448fa6331228e6bb4ebd — Unit 530 + 861
                subtests, JavaScript 147, Contract 8, Integration 771 + 460
                subtests, Process 248 + 366 subtests, System 23, shell syntax
                and diff-check all passed.
Local cleanup:  exact empty retired roots removed with rmdir. Regenerable
                build, egg-info, output, tmp and .DS_Store moved to
                /Users/chen/.Trash/bs-forward-local-noise.CH1ysq; temporary
                build output moved beneath
                /Users/chen/.Trash/bs-forward-residue-cleanup.G5d5JK.
Commit/push:    this accepted change set is committed and pushed on fea-tool;
                local HEAD/origin equality is proved before handoff.
Residual risk:  none known inside this cleanup boundary. The ignored installed
                .buddyswitch-runtime and pre-existing docs/spec evidence remain
                intentionally preserved and are not alternate source roots.
Disposition:    ACCEPTED — no executable dual track, empty installed package,
                retired physical root, fake Launcher asset contract or runner
                residue remains.
```
