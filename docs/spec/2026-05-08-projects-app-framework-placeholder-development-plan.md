# Projects App Framework Placeholder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove concrete product residue from repo-tracked `projects/app` while preserving it as the launcher-managed shared project-source mount point.

**Architecture:** Keep the existing launcher worktree and runtime symlink contract unchanged. Replace repo-tracked product files under `projects/app` with one abstract placeholder, then move tests and docs from concrete sample-file expectations to mount-point/projection/boundary expectations.

**Tech Stack:** Git worktrees, Bash launcher scripts, Python `unittest`/`pytest`, Markdown framework docs, repo consistency guards.

---

## Working Directory

Run all implementation and verification from:

```bash
cd /Users/chen/Dev/buddyswitch/.worktrees/dev0210
```

Do not edit the main checkout at `/Users/chen/Dev/buddyswitch`. This plan intentionally targets the `dev0210` worktree.

## Memo Confirmation

The accepted consensus in `docs/memo/2026-05-08-projects-app-framework-placeholder-consensus-memo.md` is that `projects/app` is a BuddySwitch framework mount point, not a bundled product. The PM buddy treated DayFlow as current product context because the framework repo tracked DayFlow files under `projects/app`, and product-mode instances correctly projected that repo content into runtime workspaces.

The product boundary is now:

- Keep the path contract: runtime sessions use relative `projects/app`, projected from `${BUDDYSWITCH_SHARED_ROOT}/project/workspace/projects/app`.
- Remove concrete product source: no DayFlow, AI Scheduler, onboarding demo, or landing-page sample files are shipped by the framework repo.
- Allow one abstract placeholder if the directory must stay tracked.
- Verify path existence, projection, and access boundaries instead of verifying concrete HTML, JS, or CSS files.

## Current Bottleneck

The current blocker is repository state. Product-mode projection is doing the right thing, but the source tree contains product-specific content at a framework contract path, which biases buddy output and makes tests/docs encode a false framework UI surface.

The shortest validated cleanup is to remove the concrete files, add a placeholder README, and update tests/docs so the path contract stays covered without preserving DayFlow-shaped assumptions.

## Confirmed Facts

- `projects/app/index.html`, `projects/app/main.js`, and `projects/app/styles.css` are the only tracked files under `projects/app`.
- `projects/app/index.html` contains DayFlow product copy, metadata, navigation, pricing, FAQ, and signup UI.
- `tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_with_buddy_creates_shared_project_workspace` currently asserts `index.html`, `main.js`, and `styles.css` exist in the shared project workspace.
- `tests/test_repo_consistency.py::RepoConsistencyTests::test_browser_ui_does_not_import_runtime_internals` treats `projects/app/main.js` as a framework browser UI surface.
- `framework/docs/interface-spec.md` lists `projects/app/main.js` as a context panel UI surface.
- Root `AGENTS.md` calls `projects/app/` "Main app code", which implies bundled source rather than a runtime mount point.
- `tools/launcher/workspace.sh` creates `${BUDDYSWITCH_PROJECT_WORKSPACE_DIR}` as a detached worktree from the repo HEAD and symlinks runtime `projects/app` to `${BUDDYSWITCH_PROJECT_WORKSPACE_DIR}/projects/app`.
- No launcher code needs to seed sample product content for the current path contract to work.

## Open Assumptions And Invalidators

- Assumption: `projects/app/README.md` is the clearest tracked placeholder. Invalidator: a launcher or packaging check requires an empty directory marker such as `.gitkeep`; if found, use `.gitkeep` plus a nearby framework doc update instead.
- Assumption: deleting `index.html`, `main.js`, and `styles.css` is safe because they are historical sample product files. Invalidator: a non-test runtime flow opens these exact files as framework UI; if found, move that flow to `framework/console` or another framework-owned path rather than preserving product residue.
- Assumption: repo consistency should enforce a strict placeholder-only allowlist. Invalidator: a future real project source import intentionally lives under a separate user/project repository rather than this framework repo; do not weaken the framework guard for that case.
- Assumption: existing buddy access tests already cover Dev-write and non-Dev-read-only semantics. Invalidator: removing sample files exposes a missing path-existence assertion; add the smallest launcher/projection test rather than changing access policy.

## Tools, Permissions, And Boundaries

- Use `git status --short` before and after edits to detect unrelated changes.
- Use `git ls-files -- projects/app` to verify tracked framework source under the mount point.
- Use `rg` for residue searches.
- Use `apply_patch` for manual file edits.
- Do not edit launcher-managed runtime instance workspaces under `${BUDDYSWITCH_SHARED_ROOT}/instances`.
- Do not add sample app fixtures under `projects/app`; fixture data must live under `tests/fixtures` if needed.

## Verification Stop Condition

Stop only when all of these are proven:

- `git ls-files -- projects/app` returns only `projects/app/README.md`.
- `rg -n "DayFlow|AI Scheduler|onboarding-demo" projects/app tests framework AGENTS.md README.md` returns no active source/test/doc residue outside accepted historical memos.
- Launcher tests verify the shared project workspace and runtime `projects/app` projection without asserting sample product files.
- Repo consistency tests fail if concrete tracked product files are reintroduced under `projects/app`.
- Framework docs describe `projects/app` as a shared product-source mount point, not framework UI or bundled app code.
- Focused tests pass, and `git diff --check` reports no whitespace errors.

## File Map

Modify:

- `projects/app/index.html`: delete concrete DayFlow page.
- `projects/app/main.js`: delete concrete DayFlow behavior.
- `projects/app/styles.css`: delete concrete DayFlow styling.
- `tests/test_buddyswitch_launcher.py`: replace shared workspace sample-file assertions with placeholder/projection assertions.
- `tests/test_repo_consistency.py`: remove `projects/app/main.js` from framework UI surfaces and add placeholder-only guard.
- `framework/docs/interface-spec.md`: remove `projects/app/main.js` from context panel UI surfaces and clarify product source is outside the context panel UI.
- `AGENTS.md`: replace "Main app code" wording with mount-point wording.

Create:

- `projects/app/README.md`: abstract placeholder explaining the runtime mount-point contract.

Do not modify:

- `tools/launcher/workspace.sh`: projection behavior is already path-based and should not seed product content.
- `buddyswitch/env-profiles/*.json`: project access policy remains unchanged.
- Runtime buddy AGENTS templates unless focused tests prove they contain concrete product residue.

## Task 1: Replace Concrete Product Source With Placeholder

**Files:**

- Delete: `projects/app/index.html`
- Delete: `projects/app/main.js`
- Delete: `projects/app/styles.css`
- Create: `projects/app/README.md`

- [ ] **Step 1: Inspect current tracked product files**

Run:

```bash
git ls-files -- projects/app
rg -n "DayFlow|AI Scheduler|onboarding-demo" projects/app
```

Expected result:

```text
projects/app/index.html
projects/app/main.js
projects/app/styles.css
```

The `rg` command should show DayFlow only in the current concrete files.

- [ ] **Step 2: Remove the concrete app files**

Apply a patch that deletes:

```text
projects/app/index.html
projects/app/main.js
projects/app/styles.css
```

- [ ] **Step 3: Add the placeholder README**

Create `projects/app/README.md` with this exact content:

```markdown
# Project Source Mount Point

`projects/app` is a BuddySwitch runtime mount point for shared product source.

The BuddySwitch framework repository intentionally does not ship a concrete
sample app here. Launcher-managed product-mode instances project this path from
`${BUDDYSWITCH_SHARED_ROOT}/project/workspace/projects/app` into each runtime
workspace as relative `projects/app`.

Real product source belongs in the launcher-managed project workspace or in a
separate project repository, not as framework-bundled sample content.
```

- [ ] **Step 4: Verify tracked files under the mount point**

Run:

```bash
git ls-files -- projects/app
```

Expected result:

```text
projects/app/README.md
```

## Task 2: Update Launcher Shared Workspace Test

**Files:**

- Modify: `tests/test_buddyswitch_launcher.py`
- Test: `tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_with_buddy_creates_shared_project_workspace`

- [ ] **Step 1: Run the focused launcher test before the assertion change**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_with_buddy_creates_shared_project_workspace -q
```

Expected result before the test update: failure because the concrete app files no longer exist in the projected project worktree.

- [ ] **Step 2: Replace sample-file assertions with mount-point assertions**

In `test_start_with_buddy_creates_shared_project_workspace`, replace:

```python
self.assertTrue(project_workspace_dir.is_dir())
self.assertTrue((project_workspace_dir / "projects" / "app" / "index.html").is_file())
self.assertTrue((project_workspace_dir / "projects" / "app" / "main.js").is_file())
self.assertTrue((project_workspace_dir / "projects" / "app" / "styles.css").is_file())
```

with:

```python
self.assertTrue(project_workspace_dir.is_dir())
project_app_dir = project_workspace_dir / "projects" / "app"
placeholder_path = project_app_dir / "README.md"
self.assertTrue(project_app_dir.is_dir())
self.assertTrue(placeholder_path.is_file())
self.assertIn(
    "BuddySwitch runtime mount point",
    placeholder_path.read_text(encoding="utf-8"),
)
for sample_file in ("index.html", "main.js", "styles.css"):
    self.assertFalse((project_app_dir / sample_file).exists(), msg=sample_file)
```

- [ ] **Step 3: Keep the projection and runtime-noise assertions unchanged**

Keep these assertions in the same test:

```python
projects_app_probe = payload["projects_app_probe"]
self.assertTrue(projects_app_probe["exists"])
self.assertEqual(
    projects_app_probe["resolved"],
    str((project_workspace_dir / "projects" / "app").resolve()),
)
self.assertFalse((project_workspace_dir / "projects" / "app" / ".runtime").exists())
```

- [ ] **Step 4: Run the focused launcher test**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_with_buddy_creates_shared_project_workspace -q
```

Expected result after the update: one passing test.

## Task 3: Add Repo Consistency Guard For Placeholder-Only Source

**Files:**

- Modify: `tests/test_repo_consistency.py`
- Test: `tests/test_repo_consistency.py::RepoConsistencyTests::test_projects_app_is_framework_placeholder_only`
- Test: `tests/test_repo_consistency.py::RepoConsistencyTests::test_browser_ui_does_not_import_runtime_internals`

- [ ] **Step 1: Remove `projects/app/main.js` from framework UI surfaces**

In `test_browser_ui_does_not_import_runtime_internals`, change:

```python
ui_surfaces = (
    ROOT / "framework" / "console" / "app.js",
    ROOT / "projects" / "app" / "main.js",
)
```

to:

```python
ui_surfaces = (
    ROOT / "framework" / "console" / "app.js",
)
```

- [ ] **Step 2: Add a placeholder-only guard test**

Add this test method to `RepoConsistencyTests`:

```python
def test_projects_app_is_framework_placeholder_only(self) -> None:
    tracked = self._git_ls_files("projects/app")
    self.assertEqual(tracked, ["projects/app/README.md"])

    placeholder = ROOT / "projects" / "app" / "README.md"
    text = placeholder.read_text(encoding="utf-8")
    self.assertIn("runtime mount point", text)
    self.assertIn("does not ship a concrete", text)

    forbidden_suffixes = {".html", ".js", ".css", ".jsx", ".tsx", ".vue", ".svelte"}
    concrete_files = [path for path in tracked if Path(path).suffix in forbidden_suffixes]
    self.assertEqual(concrete_files, [])

    forbidden_product_tokens = (
        "DayFlow",
        "AI Scheduler",
        "onboarding-demo",
        "sample landing page",
        "Personal Schedule Manager",
    )
    for path in tracked:
        content = (ROOT / path).read_text(encoding="utf-8")
        for token in forbidden_product_tokens:
            with self.subTest(path=path, token=token):
                self.assertNotIn(token, content)
```

- [ ] **Step 3: Run focused consistency tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_repo_consistency.py::RepoConsistencyTests::test_projects_app_is_framework_placeholder_only tests/test_repo_consistency.py::RepoConsistencyTests::test_browser_ui_does_not_import_runtime_internals -q
```

Expected result: two passing tests.

## Task 4: Correct Framework Documentation Boundaries

**Files:**

- Modify: `framework/docs/interface-spec.md`
- Modify: `AGENTS.md`

- [ ] **Step 1: Update the context panel interface spec**

In `framework/docs/interface-spec.md`, replace:

```markdown
UI surfaces:

- `framework/console/app.js`
- `projects/app/main.js`
```

with:

```markdown
UI surface:

- `framework/console/app.js`

`projects/app` is shared product source projected into runtime workspaces. It is
not a framework context panel UI surface.
```

- [ ] **Step 2: Update root workspace guidance**

In `AGENTS.md`, replace:

```markdown
- Main app code: `projects/app/`
```

with:

```markdown
- Shared product-source mount point: `projects/app/`
```

- [ ] **Step 3: Search for remaining active boundary mistakes**

Run:

```bash
rg -n "projects/app/main\\.js|Main app code|DayFlow|AI Scheduler|onboarding-demo" AGENTS.md README.md framework tests projects/app
```

Expected result: no matches. Historical matches under `docs/memo` are acceptable and should not be edited for this task.

## Task 5: Run Focused And Final Verification

**Files:**

- Verify: `projects/app/README.md`
- Verify: `tests/test_buddyswitch_launcher.py`
- Verify: `tests/test_repo_consistency.py`
- Verify: `framework/docs/interface-spec.md`
- Verify: `AGENTS.md`

- [ ] **Step 1: Verify tracked placeholder state**

Run:

```bash
git ls-files -- projects/app
```

Expected result:

```text
projects/app/README.md
```

- [ ] **Step 2: Verify no concrete active residue remains**

Run:

```bash
rg -n "DayFlow|AI Scheduler|onboarding-demo|Personal Schedule Manager" projects/app tests framework AGENTS.md README.md
```

Expected result: no matches.

- [ ] **Step 3: Run focused regression tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_with_buddy_creates_shared_project_workspace \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_product_mode_projects_app_resolves_to_shared_project_app \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_projects_app_is_framework_placeholder_only \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_browser_ui_does_not_import_runtime_internals \
  -q
```

Expected result: all selected tests pass.

- [ ] **Step 4: Run broader relevant tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_buddyswitch_launcher.py \
  tests/test_repo_consistency.py \
  tests/test_prepare_runtime_context.py \
  -q
```

Expected result: all selected suites pass. If a pre-existing unrelated failure appears, record the failing test name, assertion, and why it is unrelated before stopping.

- [ ] **Step 5: Verify patch hygiene**

Run:

```bash
git diff --check
git status --short
```

Expected result: `git diff --check` prints no errors. `git status --short` shows only the planned file deletions, new placeholder README, docs, and test updates plus any pre-existing untracked memo files that were present before this plan.

## Self-Review Checklist

- The change fixes root cause by removing framework-shipped product content, not by telling buddies to ignore DayFlow.
- The runtime path contract remains intact: `projects/app` still exists and still projects to shared project source.
- Tests verify observable behavior through git-tracked source, launcher CLI behavior, and public runtime projection state.
- No compatibility wrapper, sample app substitute, or seeded demo product is added.
- Scope stays limited to `projects/app` placeholder cleanup, affected tests, and affected docs.
