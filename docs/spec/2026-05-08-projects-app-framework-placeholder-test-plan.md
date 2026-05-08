# Projects App Framework Placeholder Test Plan

**Goal:** Verify from functional requirements that BuddySwitch keeps `projects/app` as a shared product-source mount point without shipping concrete sample product content in the framework repository.

**Testing Principle:** Tests must start from observable product/framework requirements: tracked repo contents, launcher-created project worktrees, runtime projection, access boundary descriptions, and active docs. Do not build tests around a private helper branch or hard-code implementation details that would let product residue remain while the test passes.

---

## Functional Requirements Under Test

FR1. The BuddySwitch framework repo must not track concrete product source under `projects/app`.

FR2. The repo may track a minimal abstract placeholder under `projects/app` so the required directory is present.

FR3. Product-mode launcher startup must still create `${BUDDYSWITCH_SHARED_ROOT}/project/workspace` as a project worktree.

FR4. Runtime instance workspaces must still expose relative `projects/app`.

FR5. Runtime `projects/app` must resolve to `${BUDDYSWITCH_PROJECT_WORKSPACE_DIR}/projects/app`.

FR6. Launcher tests must not require sample product files such as `index.html`, `main.js`, or `styles.css`.

FR7. Framework docs must describe `projects/app` as shared product source or a mount point, not framework UI or bundled main app code.

FR8. Context panel browser UI boundary must remain framework-owned and must not treat `projects/app` as a context panel UI surface.

FR9. Active source, tests, and framework docs must not contain concrete product residue tokens such as DayFlow, AI Scheduler, onboarding-demo, or Personal Schedule Manager.

FR10. Existing buddy access policy must not change: Dev can write project source in product mode, and non-Dev buddies see it as read-only through runtime guidance and env profiles.

FR11. Runtime state and `.runtime` metadata must not be written under the shared product source target.

FR12. Future reintroduction of tracked product app files under `projects/app` must fail repo consistency checks.

## Coverage Matrix

| Requirement | Test Group | Observable Proof |
| --- | --- | --- |
| FR1, FR2, FR12 | TG-01 | `git ls-files -- projects/app` and repo consistency test allow only the placeholder |
| FR3, FR6 | TG-02 | Launcher startup creates shared project worktree and does not assert sample app files |
| FR4, FR5, FR11 | TG-03 | Runtime `projects_app_probe` resolves to shared project target and `.runtime` is absent |
| FR7, FR8 | TG-04 | Docs and UI boundary tests name only framework-owned UI surfaces |
| FR9 | TG-05 | Active residue search returns no product-specific tokens |
| FR10 | TG-06 | Existing env/profile/runtime tests still pass without sample product files |

## Test Data Rules

Use product-neutral labels in tests and docs:

- Placeholder file: `projects/app/README.md`
- Mount-point description: `BuddySwitch runtime mount point`
- Shared target: `${BUDDYSWITCH_PROJECT_WORKSPACE_DIR}/projects/app`
- Runtime path: `projects/app`
- Product-neutral sentinel names already present in launcher tests, such as `shared-product-sentinel.txt`

Do not introduce new DayFlow, AI Scheduler, onboarding demo, pricing-page, schedule-manager, or landing-page fixture files under `projects/app`.

If a test needs product-shaped changed-file metadata, keep it as a payload string in a runtime contract test or move real fixture files under `tests/fixtures`; never create tracked source under `projects/app` for fixture convenience.

## TG-01 Repo Placeholder-Only Guard

**Purpose:** Prove the framework repo tracks only an abstract placeholder under the product-source mount point.

**Functional risk covered:** A future cleanup or demo task may reintroduce a concrete app under `projects/app`, causing product-mode buddies to treat framework residue as real product context.

**Test location:**

```text
tests/test_repo_consistency.py::RepoConsistencyTests::test_projects_app_is_framework_placeholder_only
```

**Assertions:**

- `self._git_ls_files("projects/app")` returns exactly `["projects/app/README.md"]`.
- `projects/app/README.md` exists and says the path is a runtime mount point.
- `projects/app/README.md` says the framework repo does not ship a concrete sample app.
- No tracked `projects/app` file has one of these suffixes: `.html`, `.js`, `.css`, `.jsx`, `.tsx`, `.vue`, `.svelte`.
- No tracked `projects/app` file contains `DayFlow`, `AI Scheduler`, `onboarding-demo`, `sample landing page`, or `Personal Schedule Manager`.

**Command:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_repo_consistency.py::RepoConsistencyTests::test_projects_app_is_framework_placeholder_only -q
```

**Expected result:** one passing test.

**Anti-cheat check:** The test must inspect git-tracked files, not only the working tree. A passing test must prove that concrete source cannot be committed under `projects/app` without failing consistency checks.

## TG-02 Launcher Shared Project Workspace

**Purpose:** Prove product-mode startup still materializes a shared project workspace after sample files are removed.

**Functional risk covered:** Removing `index.html`, `main.js`, and `styles.css` could accidentally break launcher product-mode startup if tests were depending on concrete files rather than the directory contract.

**Test location:**

```text
tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_with_buddy_creates_shared_project_workspace
```

**Flow:**

1. Start a PM instance through `./buddyswitch-codex instance start --buddy pm debug prompt-input "Draft the onboarding PRD"` using the existing fake Codex, fake curl, fake Chrome, and temporary home setup.
2. Load the fake Codex capture payload.
3. Resolve `shared_root`, `instance_root`, `runtime_workspace_dir`, and `project_workspace_dir`.

**Assertions:**

- Fake Codex `cwd` equals the runtime workspace, not the project workspace.
- Captured `project_workspace_dir` equals `${source_home}/.codex-buddyswitch/project/workspace`.
- `project_workspace_dir` exists.
- `project_workspace_dir / "projects" / "app"` is a directory.
- `project_workspace_dir / "projects" / "app" / "README.md"` is a file.
- Placeholder text contains `BuddySwitch runtime mount point`.
- `index.html`, `main.js`, and `styles.css` do not exist in the shared project app target.

**Command:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_with_buddy_creates_shared_project_workspace -q
```

**Expected result:** one passing test.

**Anti-cheat check:** Do not satisfy this test by generating empty `index.html`, `main.js`, or `styles.css`. The requirement is no concrete sample product files in the framework repo.

## TG-03 Runtime Projection Contract

**Purpose:** Prove runtime workspaces still expose `projects/app` as a projection to shared project source.

**Functional risk covered:** The cleanup must not turn `projects/app` into an absent path or a runtime-local scratch directory.

**Primary test location:**

```text
tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_with_buddy_creates_shared_project_workspace
```

**Additional existing regression:**

```text
tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_product_mode_projects_app_resolves_to_shared_project_app
```

**Assertions:**

- `payload["projects_app_probe"]["exists"]` is true.
- `payload["projects_app_probe"]["resolved"]` equals `str((project_workspace_dir / "projects" / "app").resolve())`.
- `(project_workspace_dir / "projects" / "app" / ".runtime").exists()` is false.
- Existing relative read/write sentinel behavior remains covered by `test_product_mode_projects_app_resolves_to_shared_project_app`.

**Command:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_with_buddy_creates_shared_project_workspace \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_product_mode_projects_app_resolves_to_shared_project_app \
  -q
```

**Expected result:** two passing tests.

**Anti-cheat check:** The proof must come from launcher-created runtime paths and captured fake Codex payloads, not from checking `projects/app` in the repo checkout alone.

## TG-04 Framework UI And Documentation Boundary

**Purpose:** Prove active docs and consistency checks no longer treat product source as framework UI.

**Functional risk covered:** Context panel and framework docs could keep teaching agents that `projects/app/main.js` is a framework-owned UI surface.

**Test location:**

```text
tests/test_repo_consistency.py::RepoConsistencyTests::test_browser_ui_does_not_import_runtime_internals
```

**Assertions:**

- UI surfaces checked for runtime internals include `framework/console/app.js`.
- UI surfaces do not include `projects/app/main.js`.
- `framework/console/app.js` still uses `/api/workspace`.
- `framework/docs/interface-spec.md` contains `framework/console/app.js`.
- `framework/docs/interface-spec.md` does not contain `projects/app/main.js`.
- Root `AGENTS.md` contains `Shared product-source mount point: `projects/app/``.
- Root `AGENTS.md` does not contain `Main app code: `projects/app/``.

**Command:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_repo_consistency.py::RepoConsistencyTests::test_browser_ui_does_not_import_runtime_internals -q
rg -n "projects/app/main\\.js|Main app code" framework/docs/interface-spec.md AGENTS.md
```

**Expected result:** the pytest command passes. The `rg` command returns no matches.

**Anti-cheat check:** Do not keep `projects/app/main.js` as an empty file to satisfy UI-boundary checks. The framework UI boundary is `framework/console/app.js`.

## TG-05 Active Product Residue Search

**Purpose:** Prove active source, tests, and framework docs do not retain product-specific residue that can bias buddy behavior.

**Functional risk covered:** Even after file deletion, active docs or tests could continue to instruct agents around DayFlow or another sample product.

**Command:**

```bash
rg -n "DayFlow|AI Scheduler|onboarding-demo|Personal Schedule Manager" projects/app tests framework AGENTS.md README.md
```

**Expected result:** no matches.

**Allowed historical scope:** Matches inside `docs/memo` are allowed because memos intentionally record the cause and decision history. This command excludes `docs/memo` so active behavior remains clean.

**Anti-cheat check:** Do not hide residue by renaming DayFlow to a different concrete sample product. TG-01 also rejects common product app suffixes under `projects/app`.

## TG-06 Existing Access Boundary Regression

**Purpose:** Prove the cleanup does not change Dev/non-Dev access semantics for `projects/app`.

**Functional risk covered:** A placeholder cleanup should not weaken the environment-layer access boundary or change buddy capabilities.

**Existing coverage to run:**

```text
tests/test_prepare_runtime_context.py
tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_product_mode_projects_app_resolves_to_shared_project_app
```

**Assertions covered by existing tests:**

- Runtime context still reports `projects/app` as the project path.
- Dev remains the buddy with write access to project source.
- PM, Market, Design, and Test retain read-only project access.
- Runtime projection still points to shared project source.

**Command:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_prepare_runtime_context.py \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_product_mode_projects_app_resolves_to_shared_project_app \
  -q
```

**Expected result:** all selected tests pass.

**Anti-cheat check:** Do not adjust env profiles to make tests pass. This task is about framework source cleanup, not permission redesign.

## TG-07 Combined Focused Regression Suite

**Purpose:** Provide the shortest high-confidence verification loop for the full change set.

**Command:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_with_buddy_creates_shared_project_workspace \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_product_mode_projects_app_resolves_to_shared_project_app \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_projects_app_is_framework_placeholder_only \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_browser_ui_does_not_import_runtime_internals \
  tests/test_prepare_runtime_context.py \
  -q
```

**Expected result:** all selected tests pass.

**Failure handling:**

- If launcher startup fails, inspect stderr and the fake Codex capture before changing source.
- If projection fails, inspect whether `${BUDDYSWITCH_PROJECT_WORKSPACE_DIR}/projects/app` exists in the temporary shared root.
- If access tests fail, inspect env profiles and runtime context output but do not change access policy unless the failure proves this cleanup broke an existing contract.
- If repo consistency fails, inspect `git ls-files -- projects/app` first; the most likely root cause is a tracked product file.

## TG-08 Final Patch Hygiene

**Purpose:** Prove the patch is clean and limited to the intended task.

**Commands:**

```bash
git ls-files -- projects/app
rg -n "DayFlow|AI Scheduler|onboarding-demo|Personal Schedule Manager" projects/app tests framework AGENTS.md README.md
git diff --check
git status --short
```

**Expected results:**

- `git ls-files -- projects/app` prints only `projects/app/README.md`.
- The residue `rg` command prints no matches.
- `git diff --check` prints no whitespace errors.
- `git status --short` shows only planned deletions, the new placeholder README, test updates, doc updates, and pre-existing untracked memo/spec files.

## Manual Product-Mode Smoke Check

Run this only if the focused launcher tests pass but there is still doubt about real startup behavior:

```bash
tmp_home="$(mktemp -d)"
HOME="${tmp_home}" ./buddyswitch-codex instance start --buddy pm debug prompt-input "Confirm projects/app placeholder projection"
```

Observable proof:

- The command starts a launcher-managed PM instance.
- The runtime workspace contains `projects/app`.
- `projects/app` resolves to the shared project workspace target.
- The target contains `README.md` and no DayFlow files.

Clean up the temporary home after recording the result:

```bash
rm -rf "${tmp_home}"
```

Do not run this smoke check against a real shared root unless preserving its product workspace contents is intentional.
