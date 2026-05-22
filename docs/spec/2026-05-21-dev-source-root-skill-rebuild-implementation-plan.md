# Dev Source Root And Skill Rebuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enforce the product source root as the only ordinary product-code write target, make profile/context semantics explicit, and rebuild Dev skills so Dev uses runtime source facts instead of AGENTS directory prose.

**Architecture:** Keep source root authority in launcher/env profile/runtime context, not in AGENTS and not in a new write tool. Rename ambiguous profile permission language so the contract says source root rather than project workspace. Use existing `context` as a read-only source facts surface, filesystem sandbox profiles for write enforcement, and focused Dev skills for workflow. Replace the catch-all Dev implementation skill with a small chain of skills that lock the runtime source root for the current turn, read implementation context, handle empty roots, implement, debug, verify, report, and prepare review.

**Tech Stack:** Python launcher/config generation, BuddySwitch env profiles, `context` env tool, Codex sandbox filesystem profile, TOML manifest, Markdown skills, `unittest`/`pytest`.

---

## Required Reading

- `docs/spec/2026-05-21-dev-source-root-skill-rebuild-scope.md`
- `docs/spec/2026-05-21-dev-source-root-skill-rebuild-test-plan.md`
- `docs/spec/2026-05-21-dev-source-root-skill-rebuild-addendum.md`
- `docs/bitter/2026-05-18-tool-skill-layering-principles.md`
- `docs/memo/2026-05-20-clean-runtime-environment-review-memo.md`
- `tmp/buddyswitch-real-startup-skill-inventory.html`
- `tools/launcher/codex_config.py`
- `tools/launcher/workspace.sh`
- `scripts/env_profiles.py`
- `framework/contracts/buddy-env-profile.json`
- `scripts/env/tools/context/tool.py`
- `scripts/env/tools/context/_impl.py`
- `scripts/env/tool_runtime/context.py`
- `buddyswitch/manifest.toml`
- `buddyswitch/skills/dev/implement-task/SKILL.md`
- `tools/launcher/assets/buddies/dev/AGENTS.md`
- `tests/test_buddy_env_sandbox.py`
- `tests/test_buddy_env_profiles.py`
- `tests/test_buddyswitch_launcher.py`
- `tests/test_context_binding_env_tool.py`
- `tests/test_runtime_skills.py`
- `tests/test_repo_consistency.py`

## Forward Rules

- Work only in `/Users/chen/Dev/buddyswitch/.worktrees/clean-runtime-env`.
- Do not switch to or edit `main`.
- Do not add `project`, `dev_env`, `source`, or source-write env tools.
- Do not route ordinary source writes through env tools.
- Do not use AGENTS as a source directory contract.
- Do not preserve `implement-task` as a parallel Dev implementation path.
- Do not create transition adapters or aliases for old Dev skill routing.
- Do not edit `buddyswitch/objects/**` or `buddyswitch/local/buddybox/**` directly.
- Do not over-constrain legitimate writes inside the locked source root: scoped scaffolds, tests, lockfiles, package files, and generated source artifacts are allowed when the task and local tooling justify them.
- Treat "lock source root" as a host-side turn discipline only. Do not add a persistent lock file, state object, or tool action.
- Do not guess source path/access from AGENTS, cwd, or literal path strings if profile/context resolution fails.

## Target Files

Expected modifications:

```text
tools/launcher/codex_config.py
tools/launcher/workspace.sh
scripts/env_profiles.py
framework/contracts/buddy-env-profile.json
buddyswitch/env-profiles/market.json
buddyswitch/env-profiles/pm.json
buddyswitch/env-profiles/design.json
buddyswitch/env-profiles/dev.json
buddyswitch/env-profiles/test.json
scripts/env/tools/context/tool.py
scripts/env/tools/context/_impl.py
tools/launcher/assets/buddies/market/AGENTS.md
tools/launcher/assets/buddies/pm/AGENTS.md
tools/launcher/assets/buddies/design/AGENTS.md
tools/launcher/assets/buddies/dev/AGENTS.md
tools/launcher/assets/buddies/test/AGENTS.md
buddyswitch/manifest.toml
buddyswitch/skills/dev/enter-dev-workspace/SKILL.md
buddyswitch/skills/dev/read-implementation-context/SKILL.md
buddyswitch/skills/dev/handle-empty-source-root/SKILL.md
buddyswitch/skills/dev/implement-scoped-change/SKILL.md
buddyswitch/skills/dev/debug-regression/SKILL.md
buddyswitch/skills/dev/select-local-verification/SKILL.md
buddyswitch/skills/dev/write-implementation-report/SKILL.md
buddyswitch/skills/dev/prepare-review-readiness/SKILL.md
tests/test_buddy_env_sandbox.py
tests/test_buddy_env_profiles.py
tests/test_buddyswitch_launcher.py
tests/test_context_binding_env_tool.py
tests/test_runtime_skills.py
tests/test_repo_consistency.py
```

Expected removals:

```text
buddyswitch/skills/dev/implement-task/SKILL.md
buddyswitch/skills/dev/implement-task/assets/implementation-report-template.md
```

Only remove `implement-task` after the replacement skills and manifest routing tests are in place.

## Task 0: Baseline Confirmation

**Files:** none

- [ ] **Step 1: Confirm worktree**

Run:

```bash
pwd
git status --short --branch
```

Expected:

- `pwd` prints `/Users/chen/Dev/buddyswitch/.worktrees/clean-runtime-env`;
- branch is `clean-runtime-env`;
- no work is done in `main`.

- [ ] **Step 2: Run current focused baseline tests**

Run:

```bash
python3 -m pytest tests/test_buddy_env_sandbox.py tests/test_env_layer_boundaries.py -q
python3 -m pytest tests/test_context_binding_env_tool.py -q
python3 -m pytest tests/test_runtime_skills.py tests/test_repo_consistency.py -q
```

Expected:

- tests may pass or fail before implementation;
- record failures before editing so regressions can be distinguished from expected red tests.

## Task 1: Write AGENTS Guardrail Tests

**Files:**

- Modify: `tests/test_repo_consistency.py`

- [ ] **Step 1: Add a test that AGENTS does not own source path/access facts**

Add a test near existing AGENTS/runtime guidance tests:

```python
def test_runtime_buddy_agents_do_not_embed_project_source_facts(self) -> None:
    buddies = ("market", "pm", "design", "dev", "test")
    for buddy in buddies:
        path = ROOT / "tools" / "launcher" / "assets" / "buddies" / buddy / "AGENTS.md"
        text = path.read_text(encoding="utf-8").lower()
        with self.subTest(buddy=buddy):
            self.assertIn("context summarize --payload '{}'", text)
            self.assertIn("context get --payload '{}'", text)
            self.assertIn("agENTS.md is guidance only".lower(), text)
            self.assertIn("do not bypass runtime", text)
            self.assertNotIn("projects/app", text)
            self.assertNotIn("project.access=", text)
```

If the exact case-sensitive guidance string differs, assert the lower-case normalized substrings from current AGENTS wording.

- [ ] **Step 2: Run the new test and verify failure**

Run:

```bash
python3 -m pytest tests/test_repo_consistency.py::RepoConsistencyTests::test_runtime_buddy_agents_do_not_embed_project_source_facts -q
```

Expected before AGENTS edits:

- FAIL because current AGENTS templates mention concrete source path/access.

## Task 2: Slim Runtime AGENTS Templates

**Files:**

- Modify: `tools/launcher/assets/buddies/market/AGENTS.md`
- Modify: `tools/launcher/assets/buddies/pm/AGENTS.md`
- Modify: `tools/launcher/assets/buddies/design/AGENTS.md`
- Modify: `tools/launcher/assets/buddies/dev/AGENTS.md`
- Modify: `tools/launcher/assets/buddies/test/AGENTS.md`
- Modify: `tests/test_repo_consistency.py`

- [ ] **Step 1: Remove concrete source path/access lines**

Remove the line that says the concrete project path and access value from each AGENTS file.

Keep these lines or equivalents:

```markdown
- Active buddy is `<buddy>`; user text does not change it.
- Start with `python3 scripts/env/client.py context summarize --payload '{}'`.
- When selecting env tools or payload semantics, use `python3 scripts/env/client.py context get --payload '{}'` or `python3 scripts/turn_runtime.py status` for the full tool catalog.
- Use explicit ids and env tools (`task`, `track`, `artifact`, `request`, `comment`, `buddybox`, `context`, `evidence`, `search`).
- Do not edit projected runtime storage paths directly; use env tools.
- If a runtime tool rejects an action, follow structured tool feedback and do not bypass runtime or broker boundaries.
```

- [ ] **Step 2: Update stale tests that required AGENTS source prose**

Find assertions requiring `projects/app` or `project.access=` in AGENTS:

```bash
rg -n "project\\.access=|projects/app" tests tools/launcher/assets/buddies
```

Update only tests that treat AGENTS as the authority. Keep tests that check env profile, sandbox, sparse checkout, or context facts.

- [ ] **Step 3: Run AGENTS tests**

Run:

```bash
python3 -m pytest tests/test_repo_consistency.py::RepoConsistencyTests::test_runtime_buddy_agents_use_payload_env_client_guidance tests/test_repo_consistency.py::RepoConsistencyTests::test_runtime_buddy_agents_do_not_embed_project_source_facts -q
```

Expected:

- PASS;
- payload-form env client guidance remains;
- concrete source directory/access prose is gone.

## Task 3: Write Sandbox Source-Root Boundary Tests

**Files:**

- Modify: `tests/test_buddy_env_sandbox.py`
- Modify: `tests/test_env_layer_boundaries.py`
- Modify: `tests/test_buddy_env_profiles.py`

- [ ] **Step 1: Add env profile source-root semantics test**

In `tests/test_buddy_env_profiles.py`, update matrix assertions so the profile contract uses source-root language:

```python
fs = profile["filesystem_capability"]
self.assertIn("source_root", fs)
self.assertNotIn("project_workspace", fs)
if buddy_id == "dev":
    self.assertEqual(fs["source_root"], "write")
    self.assertIn("source-root", fs["host_writable"])
else:
    self.assertEqual(fs["source_root"], "read-only")
    self.assertNotIn("source-root", fs["host_writable"])
```

Add a corrupted-profile case that includes both `source_root` and `project_workspace`; validation must reject it.

- [ ] **Step 2: Add Dev source-root write scope test**

In `tests/test_buddy_env_sandbox.py`, add or change a test so Dev write access is asserted on the product source root, not the whole project workspace:

```python
product_source_root = project_workspace_dir / "projects" / "app"
self.assertIn(str(product_source_root.resolve(strict=False)), writable_paths)
self.assertNotIn(str(project_workspace_dir.resolve(strict=False)), writable_paths)
self.assertNotIn(str((project_workspace_dir / "tools").resolve(strict=False)), writable_paths)
self.assertNotIn(str((project_workspace_dir / "buddyswitch").resolve(strict=False)), writable_paths)
```

- [ ] **Step 3: Add Non-Dev read-only source-root test**

For `pm`, `design`, `market`, and `test`, assert:

```python
product_source_root = project_workspace_dir / "projects" / "app"
self.assertEqual(filesystem[str(product_source_root.resolve(strict=False))], "read")
self.assertNotIn(str(product_source_root.resolve(strict=False)), writable_paths)
self.assertNotIn(str(project_workspace_dir.resolve(strict=False)), writable_paths)
```

- [ ] **Step 4: Tighten temp-root boundary test**

Add temp roots under:

```python
project_workspace_dir / "projects" / "app" / "tmp"
project_workspace_dir / "tmp"
shared_root / "state" / "tmp"
instance_root / "tmp"
workspace_dir / "tmp"
```

Assert none become writable profile entries.

- [ ] **Step 5: Add true sandbox smoke test**

Add a conditional smoke test that runs only when the local Codex sandbox command is available. Keep it behavioral and avoid asserting exact error text:

- Dev can write under the product source root;
- Dev cannot write under project workspace outside source root, including sibling paths such as `tools/` or `docs/` when present;
- Dev cannot write runtime workspace or raw state;
- PM can read an existing source file;
- PM cannot write under product source root.

Document in the test name/comment that this is the real permission proof; fake-codex launcher tests only prove topology/projection.

- [ ] **Step 6: Run tests and verify red**

Run:

```bash
python3 -m pytest tests/test_buddy_env_profiles.py tests/test_buddy_env_sandbox.py tests/test_env_layer_boundaries.py -q
```

Expected before implementation:

- FAIL because current code grants write to project workspace root.

## Task 4: Enforce Product Source Root Write Boundary And Rename Profile Semantics

**Files:**

- Modify: `tools/launcher/codex_config.py`
- Modify: `scripts/env_profiles.py`
- Modify: `framework/contracts/buddy-env-profile.json`
- Modify: `buddyswitch/env-profiles/market.json`
- Modify: `buddyswitch/env-profiles/pm.json`
- Modify: `buddyswitch/env-profiles/design.json`
- Modify: `buddyswitch/env-profiles/dev.json`
- Modify: `buddyswitch/env-profiles/test.json`
- Modify: tests that name `project_workspace` when they now mean source root.

- [ ] **Step 1: Rename profile contract semantics**

In `framework/contracts/buddy-env-profile.json`:

- replace enum key `filesystem_capability.project_workspace` with `filesystem_capability.source_root`;
- keep enum values `["read-only", "write"]`;
- keep `project.path` as the relative product source path field;
- make sure `project.path` is documented in tests as the source-root relative path, not a model-configurable directory.

In all env profile JSON files:

- replace `"project-workspace"` in `filesystem_capability.host_writable` with `"source-root"` for Dev only;
- replace `"project_workspace": "<access>"` with `"source_root": "<access>"`.

- [ ] **Step 2: Update profile validation**

In `scripts/env_profiles.py`, validate the new field:

```python
source_root_access = _require_enum(
    enums=enums,
    key="filesystem_capability.source_root",
    value=fs_capability.get("source_root"),
    label="filesystem_capability.source_root",
)
if "project_workspace" in fs_capability:
    raise EnvProfileError("filesystem_capability.project_workspace is retired; use source_root")
expected_host_writable = ["home", "codex-home", "xdg-config", "scratch", "temp"]
if buddy_id == "dev":
    expected_host_writable = [*expected_host_writable, "source-root"]
```

Dev must have `source_root_access == "write"` and non-Dev buddies must have `source_root_access == "read-only"`.

- [ ] **Step 3: Add source-root path derivation**

In `tools/launcher/codex_config.py`, derive:

```python
project_profile_path = str(profile.get("project", {}).get("path", "")).strip()
project_source_root = canonical(str(project_workspace_dir / project_profile_path))
```

Reject if the profile path is empty or resolves outside `project_workspace_dir`.

- [ ] **Step 4: Grant profile access to source root instead of workspace root**

Change filesystem entry construction from project workspace root write/read to product source root write/read:

```python
filesystem_entries[str(project_source_root)] = (
    "write" if profile.get("filesystem_capability", {}).get("source_root") == "write" else "read"
)
```

Do not add a write entry for `project_workspace_dir`.

- [ ] **Step 5: Update temp forbidden boundaries**

Keep `project_workspace_dir` and `project_source_root` in forbidden temp roots so temp roots cannot reopen either boundary:

```python
forbidden_temp = [
    canonical_shared_root,
    project_root,
    project_workspace_dir,
    project_source_root,
    state_root,
    instance_root,
    workspace_dir,
]
```

- [ ] **Step 6: Run profile and sandbox tests**

Run:

```bash
python3 -m pytest tests/test_buddy_env_profiles.py tests/test_buddy_env_sandbox.py tests/test_env_layer_boundaries.py -q
```

Expected:

- PASS;
- Dev can write product source root;
- non-Dev cannot;
- broad project workspace root is not writable.

## Task 5: Write Context Source Facts Tests

**Files:**

- Modify: `tests/test_context_binding_env_tool.py`

- [ ] **Step 1: Add source facts tests**

Add tests for Dev and PM:

```python
def test_context_summarize_includes_source_workspace_facts_for_dev(self) -> None:
    instance_json = self._instance_json(buddy="dev")
    source_root = self._runtime_path("projects/app")
    source_root.mkdir(parents=True, exist_ok=True)
    (source_root / "README.md").write_text("# App\n", encoding="utf-8")

    payload = self._dispatch(instance_json=instance_json, tool="context", action="summarize", args={})
    self.assertTrue(payload.get("ok"), msg=payload)
    source = payload.get("source_workspace")
    self.assertIsInstance(source, dict, msg=payload)
    self.assertEqual(source.get("active_buddy"), "dev")
    self.assertEqual(source.get("path"), "projects/app")
    self.assertEqual(source.get("access"), "write")
    self.assertIs(source.get("can_write_source"), True)
    self.assertEqual(source.get("state"), "readme_only")
    self.assertEqual(source.get("top_level_entries"), ["README.md"])
    self.assertIs(source.get("top_level_entries_truncated"), False)
    self.assertIn("env_profile", source.get("source_of_truth", ""))
    self.assertIn("read-only", source.get("permission_boundary", "").lower())
    self.assertIn("does not configure", source.get("permission_boundary", "").lower())
    self.assertNotIn("# App", json.dumps(source, ensure_ascii=True))
```

Add the same shape for PM:

```python
self.assertEqual(source.get("access"), "read-only")
self.assertIs(source.get("can_write_source"), False)
self.assertIn("read-only", source.get("permission_boundary", "").lower())
```

- [ ] **Step 2: Add state classification test**

Create subcases for missing, empty, README-only, and source-like roots. Assert exact states:

```python
cases = [
    ("missing", None, "missing"),
    ("empty", [], "empty"),
    ("readme", ["README.md"], "readme_only"),
    ("package", ["package.json"], "has_source"),
    ("src", ["src/index.ts"], "has_source"),
]
```

- [ ] **Step 3: Add tool metadata and `list_sources` coverage**

Add assertions that:

- `context.get` action metadata names `source_workspace` in returned sections;
- `context.summarize` action metadata names `source_workspace` in returned sections;
- `context.list_sources` includes a `source_workspace` descriptor;
- descriptor/effect text says source facts are read-only orientation data;
- descriptor/effect text says context does not configure roots or grant write access.

- [ ] **Step 4: Add profile-source authority regression**

Seed an AGENTS template or runtime AGENTS content with a wrong path/access string in a temporary fixture, while the env profile still declares the source root as `projects/app`.

Assert context still returns the profile/projected source facts, not the AGENTS text. If the profile cannot be loaded or fails validation, assert the context action returns an explicit rejection or unavailable source block; it must not return `state = "missing"` for a profile-resolution failure.

- [ ] **Step 5: Run tests and verify red**

Run:

```bash
python3 -m pytest tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_context_summarize_includes_source_workspace_facts_for_dev -q
```

Expected before implementation:

- FAIL because context does not expose `source_workspace`.

## Task 6: Implement Context Source Facts

**Files:**

- Modify: `scripts/env/tools/context/tool.py`
- Modify: `scripts/env/tools/context/_impl.py`
- Modify: any local context schema/definition tests if metadata is centralized.

- [ ] **Step 1: Add return metadata**

In `scripts/env/tools/context/tool.py`:

- add `source_workspace` to `context.get` and `context.summarize` return metadata;
- update action descriptions/effect summaries so source facts are described as read-only orientation data;
- update `context.list_sources` so it describes `source_workspace` and says it does not configure or grant write access.

- [ ] **Step 2: Build source fact helper**

In `scripts/env/tools/context/_impl.py`, load the active buddy env profile through the same profile validation path used by launcher code. Do not derive source path or write access from AGENTS, cwd, literal strings, or unchecked manifest fields.

```python
def _repo_root_from_manifest_path(manifest_path: Path) -> Path:
    # manifest is <repo>/buddyswitch/manifest.toml in local/runtime layouts.
    return manifest_path.resolve(strict=False).parents[1]


def _load_active_env_profile(
    context: ContextServiceContext,
    active_buddy: str,
) -> dict[str, Any]:
    manifest_path = Path(str(context["manifest_path"]))
    repo_root = _repo_root_from_manifest_path(manifest_path)
    return env_profiles.require_env_profile(
        active_buddy,
        manifest_path=manifest_path,
        repo_root=repo_root,
    )
```

If profile loading fails, return the established tool-level rejection shape, or an explicit unavailable source block if that is the existing context-tool style. Do not encode profile validation/load failure as `state = "missing"`; `missing` is only for a resolved profile whose declared source path is absent.

Derive the source root from validated profile plus instance workspace projection:

```python
project_path = str(profile["project"]["path"]).strip()
workspace_dir = Path(str(instance_payload["workspace_dir"])).expanduser().resolve(strict=False)
source_root = (workspace_dir / project_path).resolve(strict=False)
if not _is_relative_to(source_root, workspace_dir):
    return _source_workspace_unavailable("profile project.path resolves outside workspace")
```

Add source root classification:

```python
def _classify_source_root(root: Path, *, limit: int = 20) -> tuple[str, list[str], bool]:
    if not root.exists():
        return "missing", [], False
    if not root.is_dir():
        return "missing", [], False
    all_entries = sorted(path.name for path in root.iterdir() if not path.name.startswith("."))
    entries = all_entries[:limit]
    truncated = len(all_entries) > limit
    if not entries:
        return "empty", [], truncated
    lower = {entry.lower() for entry in all_entries}
    if lower <= {"readme.md", "readme"}:
        return "readme_only", entries, truncated
    return "has_source", entries, truncated
```

- [ ] **Step 3: Add `source_workspace` to context sections**

Return:

```python
"source_workspace": {
    "active_buddy": active_buddy,
    "path": project_path,
    "access": source_root_access,
    "can_write_source": source_root_access == "write",
    "state": state,
    "top_level_entries": entries,
    "top_level_entries_truncated": truncated,
    "source_of_truth": "env_profile.project + workspace_projection",
    "permission_boundary": "context is read-only; filesystem writes are enforced by sandbox profile; context does not configure roots or grant write access",
}
```

Do not include file bodies. `context.get` may include a debug-oriented `resolved_path` if that is useful locally, but compact summaries should prefer the runtime-relative `path` and provenance instead of absolute paths.

- [ ] **Step 4: Include source facts in summarize/get**

Add `source_workspace` to both:

- `_current_context_sections`;
- `summary` in `summarize_context`.

`source_workspace.state` values:

- `missing`: profile-resolved source root path is absent or not a directory;
- `empty`: root exists with no visible top-level entries;
- `readme_only`: root exists and visible entries are README-only;
- `has_source`: root has non-README content available for inspection; this does not claim a runnable app/framework was verified.

- [ ] **Step 5: Run context tests**

Run:

```bash
python3 -m pytest tests/test_context_binding_env_tool.py -q
```

Expected:

- PASS.

## Task 7: Write Tool Non-Addition Guardrails

**Files:**

- Modify: `tests/test_repo_consistency.py`

- [ ] **Step 1: Add forbidden source tool scan**

Add:

```python
def test_no_project_or_source_write_env_tool_is_shipped(self) -> None:
    forbidden_tools = {"project", "dev_env", "source", "filesystem", "workspace_write"}
    self.assertTrue(forbidden_tools.isdisjoint(tool_catalog.supported_tools()))

    tool_packages = {
        path.name
        for path in (ROOT / "scripts" / "env" / "tools").iterdir()
        if path.is_dir() and not path.name.startswith("_")
    }
    self.assertTrue(forbidden_tools.isdisjoint(tool_packages))

    forbidden_actions = {"apply_patch", "write_file", "delete_file", "configure_project"}
    for tool in tool_catalog.supported_tools():
        with self.subTest(tool=tool):
            self.assertTrue(forbidden_actions.isdisjoint(tool_catalog.supported_actions(tool)))
```

- [ ] **Step 2: Run guardrail**

Run:

```bash
python3 -m pytest tests/test_repo_consistency.py::RepoConsistencyTests::test_no_project_or_source_write_env_tool_is_shipped -q
```

Expected:

- PASS before and after implementation.

## Task 8: Write Dev Skill Routing Tests

**Files:**

- Modify: `tests/test_runtime_skills.py`

- [ ] **Step 1: Add expected Dev skill ids test**

Add:

```python
def test_dev_product_engineering_skill_chain_is_registered(self) -> None:
    skills_by_id = {row["id"]: row for row in self.manifest.get("skills", []) if isinstance(row, dict)}
    dev = next(row for row in self.manifest.get("buddies", []) if row.get("id") == "dev")
    dev_skills = set(dev.get("skills", []))
    expected = {
        "enter-dev-workspace",
        "read-implementation-context",
        "handle-empty-source-root",
        "implement-scoped-change",
        "debug-regression",
        "select-local-verification",
        "write-implementation-report",
        "prepare-review-readiness",
    }
    self.assertTrue(expected.issubset(dev_skills))
    self.assertIn("skill-creator-importer", dev_skills)
    self.assertNotIn("implement-task", dev_skills)
    for skill_id in expected:
        skill_file = ROOT / skills_by_id[skill_id]["path"] / "SKILL.md"
        self.assertTrue(skill_file.exists(), msg=skill_file)
```

- [ ] **Step 2: Add Dev skill content guardrails**

Add tests that validate each new Dev skill has complete operational sections, not just scattered keywords:

```python
required_headings = (
    "## Use when",
    "## Do not use when",
    "## Inputs",
    "## Steps",
    "## Outputs",
    "## Guardrails",
)
```

Each skill must also include either `## Verification` or `## Stop conditions`, depending on whether the skill ends in proof or handoff/blocking.

Forbidden content should target schema/tool coupling rather than small useful field references:

```python
forbidden = (
    "payload_fields",
    "operation_semantics",
    "**payload:**",
    "**returns:**",
    "## operations",
    "project.write_file",
    "project.apply_patch",
    "write_file",
    "delete_file",
)
```

Allow short field references such as `source_workspace.path` and `artifact_id`. Forbid full payload schemas, return schemas, and action catalogs copied into Dev skills.

Add scenario checks with section-local assertions:

- `enter-dev-workspace`: `context.summarize`, `locked source root`, `runtime`;
- `read-implementation-context`: artifact id present but artifact body unread;
- `handle-empty-source-root`: `missing`, `empty`, `readme_only`, `has_source`, explicit scaffold scope versus absent scope;
- `implement-scoped-change`: changed file outside locked root, test-first when practical, no silent scope change;
- `debug-regression`: reproduce before patch, root cause before fix;
- `select-local-verification`: no discovered project test command;
- `write-implementation-report`: changed files, verification evidence or blocked reason, risks, follow-ups;
- `prepare-review-readiness`: main path, blast radius, verification evidence, residual risk.

Add a chain-order assertion in the test fixture or comments so the expected workflow is:

```text
enter-dev-workspace
  -> read-implementation-context when task context is needed
  -> handle-empty-source-root when state is missing/empty/readme_only
  -> debug-regression for regression work
  -> implement-scoped-change for feature/refactor/source work
  -> select-local-verification
  -> write-implementation-report
  -> prepare-review-readiness
```

- [ ] **Step 3: Run tests and verify red**

Run:

```bash
python3 -m pytest tests/test_runtime_skills.py::RuntimeSkillsTests::test_dev_product_engineering_skill_chain_is_registered -q
```

Expected before skill creation:

- FAIL because new skills are not registered.

## Task 9: Create New Dev Skills

**Files:**

- Create: `buddyswitch/skills/dev/enter-dev-workspace/SKILL.md`
- Create: `buddyswitch/skills/dev/read-implementation-context/SKILL.md`
- Create: `buddyswitch/skills/dev/handle-empty-source-root/SKILL.md`
- Create: `buddyswitch/skills/dev/implement-scoped-change/SKILL.md`
- Create: `buddyswitch/skills/dev/debug-regression/SKILL.md`
- Create: `buddyswitch/skills/dev/select-local-verification/SKILL.md`
- Create: `buddyswitch/skills/dev/write-implementation-report/SKILL.md`
- Create: `buddyswitch/skills/dev/prepare-review-readiness/SKILL.md`

- [ ] **Step 1: Use the shared skill shape**

Use the detailed content requirements in `docs/spec/2026-05-21-dev-source-root-skill-rebuild-addendum.md`.

Every new Dev skill must include:

- frontmatter with `name` and a trigger-only `description`;
- `## Use when`;
- `## Do not use when`;
- `## Inputs`;
- `## Steps`;
- `## Outputs`;
- `## Guardrails`;
- `## Verification` or `## Stop conditions`;
- at least one concrete scenario/counterexample for its main failure mode.

Keep skills decoupled:

- each skill solves one stable workflow problem;
- skills may say which next skill normally follows;
- skills must not copy full runtime payload schemas, return schemas, or action catalogs;
- skills may name small required fields such as `source_workspace.path`, `source_workspace.state`, `artifact_id`, changed files, and verification commands;
- exact tool payload/response details stay in tool metadata, runtime discovery, or shared tool skills.

- [ ] **Step 2: Create `enter-dev-workspace`**

Minimum required content, in addition to the shared headings from Step 1:

```markdown
---
name: enter-dev-workspace
description: Use when Dev starts source exploration, implementation, bug fixing, or refactoring in a BuddySwitch product runtime.
---

# Enter Dev Workspace

## Purpose
- Establish the runtime-provided source root for this turn before reading or editing product code.

## Inputs
- `context.summarize` / `context.get` source facts.
- `source_workspace.path`, `source_workspace.access`, `source_workspace.can_write_source`, `source_workspace.state`, and top-level entries.

## Steps
1. Run compact context discovery.
2. Read `source_workspace` from the runtime response.
3. Treat that runtime value as the locked source root for this turn.
4. Classify source state as `missing`, `empty`, `readme_only`, or `has_source`.
5. Use buddybox only for private notes and env tools for runtime objects.

## Guardrails
- Do not use AGENTS prose as source-root authority.
- Do not edit outside the locked source root.
- README-only means the root exists but app source is absent.
- Locking the source root is turn discipline only; do not write a lock file or mutate runtime state.
```

- [ ] **Step 3: Create `read-implementation-context`**

Include:

- use when implementation depends on track/task/request/artifact context;
- read full artifact body with artifact tool before claiming it was read;
- identify PM scope, design constraints, acceptance criteria, blockers;
- translate upstream product/design constraints into implementation constraints;
- flag architecture-impacting work before coding;
- avoid silently widening or changing product scope;
- stop if scope would require product decision.

- [ ] **Step 4: Create `handle-empty-source-root`**

Include exact state handling:

- `missing`: report runtime/source-root blocker;
- `empty`: scaffold only if the user directly requested app/source creation, or a PM/PRD/approved artifact clearly asks for it;
- `readme_only`: root exists, app source absent; scaffold only under the same explicit scope rule;
- `has_source`: proceed to implementation skill.

This skill should not over-restrict valid source-root work. If scaffold is allowed, normal source files, package metadata, lockfiles, generated app artifacts, tests, fixtures, and formatting/build outputs may be written under the locked root when the project/tooling justifies them.

- [ ] **Step 5: Create `implement-scoped-change`**

Include:

- requires locked source root;
- changed files must stay under locked source root;
- no product direction changes;
- no runtime report noise in source;
- localized refactors only when needed;
- start with a failing test when practical for new behavior or bug fixes;
- read existing project patterns before introducing new framework conventions;
- summarize changed files and any limitations before handoff.

- [ ] **Step 6: Create `debug-regression`**

Include:

- reproduce first;
- identify root cause;
- add focused regression test when practical;
- patch smallest cause;
- verify.

- [ ] **Step 7: Create `select-local-verification`**

Include:

- inspect project hints;
- select focused test/lint/typecheck/build/manual command;
- prefer project-owned verification commands over invented checks;
- distinguish topology/fake launcher tests from real sandbox/permission proof;
- report blocked verification with exact blocker.

- [ ] **Step 8: Create `write-implementation-report`**

Include:

- task summary;
- changed files;
- implementation notes;
- verification;
- risks;
- follow-ups;
- product-readable reports through artifact/request/track routes.

- [ ] **Step 9: Create `prepare-review-readiness`**

Include:

- main path;
- blast radius;
- changed files;
- verification evidence;
- known risks;
- suggested test focus.

## Task 10: Update Manifest And Remove Catch-All Skill

**Files:**

- Modify: `buddyswitch/manifest.toml`
- Delete: `buddyswitch/skills/dev/implement-task/SKILL.md`
- Delete: `buddyswitch/skills/dev/implement-task/assets/implementation-report-template.md`

- [ ] **Step 1: Add new skill entries**

Add `[[skills]]` rows for all eight new Dev skills.

- [ ] **Step 2: Update Dev buddy skill list**

Replace `implement-task` in the Dev buddy `skills` array with:

```toml
"enter-dev-workspace",
"read-implementation-context",
"handle-empty-source-root",
"implement-scoped-change",
"debug-regression",
"select-local-verification",
"write-implementation-report",
"prepare-review-readiness",
```

Keep:

```toml
"skill-creator-importer"
```

and shared tool skills.

- [ ] **Step 3: Remove old catch-all skill files**

Delete `buddyswitch/skills/dev/implement-task`.

- [ ] **Step 4: Run manifest/skill tests**

Run:

```bash
python3 -m pytest tests/test_runtime_skills.py tests/test_skill_creator_importer.py -q
```

Expected:

- PASS.

## Task 11: Update Skill/AGENTS Consistency Tests

**Files:**

- Modify: `tests/test_runtime_skills.py`
- Modify: `tests/test_repo_consistency.py`

- [ ] **Step 1: Replace role skill file references**

Where tests list role skill files, replace `implement-task` with the new Dev skill set.

- [ ] **Step 2: Keep old guidance scans active**

Run:

```bash
python3 -m pytest tests/test_runtime_skills.py::RuntimeSkillsTests::test_active_skills_do_not_teach_old_env_client_flags tests/test_runtime_skills.py::RuntimeSkillsTests::test_role_skills_remove_optional_handoff_guidance -q
```

Expected:

- PASS.

## Task 12: Launcher Product Runtime Verification

**Files:**

- Modify: `tests/test_buddyswitch_launcher.py` if launcher expectations still refer to broad project workspace writes.

- [ ] **Step 1: Separate topology tests from permission tests**

Launcher tests that use fake Codex helpers must be treated as topology/projection tests only. They may prove sparse checkout shape, runtime path projection, environment wiring, and shared worktree reuse. They must not be used as proof that an OS sandbox allows or blocks writes, because fake Codex writes directly from the test process.

Update test names/comments where useful so a future reader does not mistake fake-codex file creation for permission enforcement. Real permission proof belongs in `tests/test_buddy_env_sandbox.py` profile inspection and the true sandbox smoke.

- [ ] **Step 2: Update expected source root projection**

In launcher tests that inspect `project_workspace_dir`, distinguish:

```python
project_workspace_dir = shared_root / "project" / "workspace"
product_source_root = project_workspace_dir / "projects" / "app"
```

Assert `product_source_root` is the runtime projection target. Do not assert that PM/design fake-codex writes prove source write permission.

- [ ] **Step 3: Keep sparse checkout checks**

Keep assertions that:

- sparse checkout list is the product source path;
- forbidden non-source root entries are absent;
- runtime projection points to product source root.

- [ ] **Step 4: Run launcher tests**

Run:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py -q
```

Expected:

- PASS.

## Task 13: Full Verification

**Files:** all modified files

- [ ] **Step 1: Run focused verification**

Run:

```bash
python3 -m pytest tests/test_buddy_env_profiles.py -q
python3 -m pytest tests/test_buddy_env_sandbox.py tests/test_env_layer_boundaries.py -q
python3 -m pytest tests/test_context_binding_env_tool.py -q
python3 -m pytest tests/test_runtime_skills.py tests/test_repo_consistency.py -q
python3 -m pytest tests/test_buddyswitch_launcher.py -q
```

Expected:

- all pass.

- [ ] **Step 2: Run full suite**

Run:

```bash
python3 -m pytest -q
```

Expected:

- PASS.

- [ ] **Step 3: Inspect final diff**

Run:

```bash
git diff --stat
git diff -- docs/spec/2026-05-21-dev-source-root-skill-rebuild-scope.md docs/spec/2026-05-21-dev-source-root-skill-rebuild-test-plan.md docs/spec/2026-05-21-dev-source-root-skill-rebuild-implementation-plan.md
git diff -- tools/launcher/codex_config.py scripts/env/tools/context/_impl.py buddyswitch/manifest.toml
```

Expected:

- no AGENTS source directory facts;
- no new source-write tool;
- Dev skill chain registered;
- source root write boundary enforced.

## Completion Report

Final report must state:

- changed runtime boundary files;
- changed Dev skill files;
- changed AGENTS files;
- changed tests;
- verification commands and results;
- any remaining risk.

Do not claim completion without verification output.
