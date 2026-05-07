# BuddySwitch Complete Residue Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the remaining P0-P2 historical residue that can pull BuddySwitch back toward old routing, authoring, launcher, browser, store, or documentation models.

**Architecture:** Keep one product path: launcher-managed locked buddy instances, broker-owned prepare/persist, compact buddy-run commits, instance-scoped skills, and supported debug/admin APIs only. Remove or rewrite stale surfaces instead of preserving compatibility wrappers. Keep explicit fail-closed guards for retired public commands and retired result shapes.

**Tech Stack:** Bash launcher scripts, Python runtime/store/debug scripts, `unittest`/`pytest`, JSON schemas, TOML manifest, Markdown docs and native skill assets.

---

## Working Scope

Worktree: `/Users/chen/Dev/buddyswitch/.worktrees/dev0210`

Do not touch the user-owned untracked file:

- `docs/memo/2026-05-07-buddy-instance-context-tool-feedback-direction-memo.md`

This plan intentionally includes all P0-P2 audit findings in one cleanup batch so execution does not fragment across several half-overlapping phases. The work is still broken into verification-sized tasks. Each task must leave the repo in a runnable state.

## Current Bottleneck

The prior cleanup commits already removed the largest runtime residues:

- switch-shaped request rejection in prepare;
- old result authoring keys from active schemas/contracts/skills;
- `runtime_store/repositories.py`;
- `_legacy_*` store implementation names.

The remaining bottleneck is active source confusion: current docs, native skill wording, launcher private paths, debug API flags, and stale plans still describe or preserve old models. This slows future iteration because agents can follow stale surfaces even though the runtime main path has moved on.

## Boundaries

Keep:

- Retired public CLI fail-closed behavior for `start`, `buddy`, `cleanup`, `reset`, `browser`, and `workspace`.
- Removed cleanup option fail-closed behavior for old destructive flags.
- Old Codex managed config block stripping, because it removes old wide permissions safely.
- Live legacy launcher marker blocking for open/delete/reset/cleanup safety.
- Persist rejection for top-level `skill_id`.
- Prepare rejection for retired markdown output paths such as `artifacts/*.md` and `runs/summaries/*.md`.
- Negative tests that prove retired schemas/contracts remain rejected.
- Market browser evidence and approved downgrade token policy.

Remove or rewrite:

- Active runtime docs that say command-shaped routing input is rejected.
- Active skill docs that imply skills directly write broker-owned state objects.
- Market templates that show copyable fake browser evidence tokens.
- Manifest artifact kinds with no active producer or explicit current purpose.
- Unreferenced Markdown framework templates that compete with native skill assets.
- Stale completed development/test plans that still teach old payloads.
- Private launcher paths for old workspace sync and no-buddy bootstrap.
- Non-instance shared browser/general MCP creation path, while keeping safe stale-marker cleanup.
- Unsupported debug/admin flags and unused store helpers.

## File Map

Runtime contract and guardrails:

- Modify `framework/docs/turn-runtime-spec.md`.
- Modify `tests/test_repo_consistency.py`.
- Read-only behavior reference: `tests/test_turn_runtime.py`.

Skills, templates, manifest, and buddy runtime instructions:

- Modify every `buddyswitch/skills/*/*/SKILL.md`.
- Modify every `buddyswitch/skills/market/*/assets/*.md` that contains `browser_cockpit_token`.
- Modify `tools/launcher/assets/buddies/design/AGENTS.md`.
- Modify `tools/launcher/assets/buddies/dev/AGENTS.md`.
- Modify `tools/launcher/assets/buddies/test/AGENTS.md`.
- Modify `buddyswitch/manifest.toml`.
- Modify `tests/test_runtime_skills.py`.
- Modify `tests/test_repo_consistency.py`.
- Modify runtime/integration fixtures that currently use `market-landing-page-brief`.

Obsolete templates and stale docs:

- Delete `framework/templates/prd.md`.
- Delete `framework/templates/impl-report.md`.
- Delete `framework/templates/research-report.md`.
- Delete `framework/templates/test-report.md`.
- Modify or delete stale completed plans under `docs/spec/`.
- Keep this plan and its companion test plan until the cleanup is executed and verified.

Launcher and browser:

- Modify `buddyswitch-codex`.
- Modify `tools/launcher/workspace.sh`.
- Modify `tools/launcher/browser_cockpit.sh`.
- Modify `tests/test_buddyswitch_launcher.py`.
- Modify `tests/test_browser_cockpit_launcher.py`.

Runtime debug/store:

- Modify `scripts/env_artifacts.py`.
- Modify `scripts/env_store.py`.
- Modify `scripts/env_cleanup.py` only if old backend cleanup scopes are confirmed unreachable and redundant.
- Modify `tests/test_debug_apis.py`.
- Modify `tests/test_env_store_v2.py`.
- Modify `tests/test_cleanup_system.py` if cleanup scopes are simplified.

## Execution Order

1. Update tests/guardrails first for active runtime and skill guidance.
2. Fix active docs/skills/templates/manifest.
3. Remove stale docs/templates that can mislead future execution.
4. Remove old launcher/browser paths.
5. Remove debug/store API residue.
6. Run focused then full verification.

Do not perform broad formatting, renames, or unrelated cleanup.

---

### Task 1: Fix Runtime Input Contract And Guardrail Gap

**Files:**

- Modify: `framework/docs/turn-runtime-spec.md`
- Modify: `tests/test_repo_consistency.py`
- Test: `tests/test_turn_runtime.py`

- [ ] **Step 1: Add an active-doc semantic guard before changing docs**

In `tests/test_repo_consistency.py`, extend `test_active_product_paths_exclude_legacy_switch_wire` with forbidden wording that represents the retired behavior without relying on one exact token.

Use this shape:

```python
forbidden_tokens = (
    "persist --skill-id",
    "persist-skill-result",
    "selected skill_id",
    "selected_" + "skill_packet",
    "prepare_context." + "skills",
    "instruction_path",
    "recommended" + "_switch",
    "reference_" + "switches",
    "switch " + "<buddy>:",
    "switch " + "pm:",
    "switch " + "market:",
    "switch " + "dev:",
    "Command-shaped routing input is rejected",
    "command-shaped routing input is rejected",
    "router-era guard",
)
```

- [ ] **Step 2: Run the guard and confirm it catches the stale active spec**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_active_product_paths_exclude_legacy_switch_wire \
  -q
```

Expected before doc fix: `FAILED` with a subtest pointing at `framework/docs/turn-runtime-spec.md`.

- [ ] **Step 3: Rewrite the product input contract**

In `framework/docs/turn-runtime-spec.md`, replace the stale bullet:

```markdown
- Command-shaped routing input is rejected before any task, artifact, run, or reservation writes.
```

with:

```markdown
- User text never routes or changes the active buddy. Text that resembles retired `switch <buddy>:` syntax is preserved as ordinary `request_text`.
- Retired top-level launcher commands still fail closed at the launcher boundary; that is separate from runtime request text handling.
```

- [ ] **Step 4: Verify runtime behavior and active-doc guard**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_turn_runtime.py::TurnRuntimeBuddyRunTests::test_prepare_accepts_switch_prefixed_text_as_ordinary_request \
  tests/test_turn_runtime.py::TurnRuntimeBuddyRunTests::test_prepare_uses_locked_buddy_for_switch_prefixed_text \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_active_product_paths_exclude_legacy_switch_wire \
  -q
```

Expected: all selected tests pass.

---

### Task 2: Align Skill Output Wording With Broker-Owned Persist

**Files:**

- Modify: every `buddyswitch/skills/*/*/SKILL.md`
- Modify: `tests/test_repo_consistency.py`
- Test: `tests/test_runtime_skills.py`

- [ ] **Step 1: Add a manifest-driven skill guidance guard**

Add a repo consistency test that loads skill paths from `buddyswitch/manifest.toml` and checks every active `SKILL.md`, instead of hardcoding a partial skill list.

Use this test body:

```python
def test_active_skill_outputs_do_not_claim_direct_state_writes(self) -> None:
    manifest = env_manifest.load_manifest(ROOT / "buddyswitch" / "manifest.toml")
    forbidden = (
        "A PM artifact object in `buddyswitch/objects/artifacts/`",
        "A run audit in `buddyswitch/content/runs/`",
        "A Market artifact object in `buddyswitch/objects/artifacts/`",
        "A Design artifact object in `buddyswitch/objects/artifacts/`",
        "A Dev artifact object in `buddyswitch/objects/artifacts/`",
        "A Test artifact object in `buddyswitch/objects/artifacts/`",
    )
    for skill in manifest.get("skills", []):
        assert isinstance(skill, dict)
        skill_md = ROOT / str(skill["path"]) / "SKILL.md"
        text = skill_md.read_text(encoding="utf-8")
        for token in forbidden:
            with self.subTest(skill=skill["id"], token=token):
                self.assertNotIn(token, text)
        self.assertIn("Contribute to one buddy-run commit", text)
        self.assertIn("Do not call persist from inside the skill", text)
```

- [ ] **Step 2: Run the new guard and confirm it fails on current wording**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_active_skill_outputs_do_not_claim_direct_state_writes \
  -q
```

Expected before skill edits: `FAILED` with at least one active skill path.

- [ ] **Step 3: Rewrite each `## Outputs` section**

For artifact-producing skills, use this pattern:

```markdown
## Outputs
- A contribution to the current compact buddy-run commit.
- When persisted by the locked buddy session, one authorized artifact entry under `artifacts[]`.
- Commit JSON aligned to the active buddy schema under `framework/schemas/`.
```

For PM track-manager, use this pattern:

```markdown
## Outputs
- A contribution to the current compact buddy-run commit.
- Optional `state_effects.track` for explicit PM track lifecycle changes.
- Optional `artifacts[]` only when a durable `track-note` or `pm-decision` is needed.
```

Do not remove the existing `BuddySwitch Commit Output` sections unless they duplicate these same lines verbatim.

- [ ] **Step 4: Verify all active skill guidance**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_active_skill_outputs_do_not_claim_direct_state_writes \
  tests/test_runtime_skills.py \
  -q
```

Expected: all selected tests pass.

---

### Task 3: Remove Fake Market Evidence Token Templates

**Files:**

- Modify: `buddyswitch/skills/market/research-scan/assets/research-report-template.md`
- Modify: `buddyswitch/skills/market/pmf-recon/assets/pmf-report-template.md`
- Modify: `buddyswitch/skills/market/customer-discovery/assets/interview-brief-template.md`
- Modify: `buddyswitch/skills/market/positioning-copy/assets/positioning-brief-template.md`
- Modify: `buddyswitch/skills/market/channel-discovery/assets/channel-plan-template.md`
- Modify: `buddyswitch/skills/market/launch-prep/assets/launch-prep-template.md`
- Modify: `tests/test_repo_consistency.py`
- Test: `tests/test_market_browser_evidence.py`

- [ ] **Step 1: Add a template guard against copyable fake evidence tokens**

Add this test to `tests/test_repo_consistency.py`:

```python
def test_market_templates_do_not_contain_copyable_fake_evidence_tokens(self) -> None:
    market_assets = ROOT / "buddyswitch" / "skills" / "market"
    forbidden_tokens = (
        "<broker-issued-token-from-current-run>",
        "\"browser_cockpit_token\": \"<",
        "browser_cockpit_token = \"<",
    )
    for path in market_assets.rglob("*"):
        if not path.is_file() or path.suffix not in {".md", ".json"}:
            continue
        text = path.read_text(encoding="utf-8")
        for token in forbidden_tokens:
            with self.subTest(path=str(path.relative_to(ROOT)), token=token):
                self.assertNotIn(token, text)
```

- [ ] **Step 2: Run the guard and confirm it fails on current templates**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_market_templates_do_not_contain_copyable_fake_evidence_tokens \
  -q
```

Expected before template edits: `FAILED` with market asset paths.

- [ ] **Step 3: Replace copyable token objects with non-submittable guidance**

In each affected Market asset, remove this JSON object:

```json
"tool_evidence": {
  "browser_cockpit_token": "<broker-issued-token-from-current-run>"
}
```

Replace it with this non-submittable comment outside the JSON example:

```markdown
Evidence rule: include `tool_evidence.browser_cockpit_token` only when the runtime broker has issued a real token for this exact run. Do not copy placeholder tokens into the result payload.
```

If an asset must remain valid JSON from top to bottom, omit `tool_evidence` from the sample entirely and add the evidence rule to the surrounding `SKILL.md` instead.

- [ ] **Step 4: Verify Market evidence policy still works**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_market_templates_do_not_contain_copyable_fake_evidence_tokens \
  tests/test_market_browser_evidence.py \
  -q
```

Expected: selected tests pass. Market artifact-producing persist without broker evidence remains rejected.

---

### Task 4: Make Buddy Runtime AGENTS Identity Wording Consistent

**Files:**

- Modify: `tools/launcher/assets/buddies/design/AGENTS.md`
- Modify: `tools/launcher/assets/buddies/dev/AGENTS.md`
- Modify: `tools/launcher/assets/buddies/test/AGENTS.md`
- Modify: `tests/test_repo_consistency.py`

- [ ] **Step 1: Add a guard that every buddy AGENTS states locked identity**

Extend `test_buddy_prompt_assets_exist` in `tests/test_repo_consistency.py`:

```python
self.assertIn("user text does not change it", text)
```

This assertion belongs inside the existing per-buddy subtest after the start-marker assertion.

- [ ] **Step 2: Run the guard and confirm it fails for Design, Dev, and Test**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_buddy_prompt_assets_exist \
  -q
```

Expected before docs edits: `FAILED` for `design`, `dev`, and `test`.

- [ ] **Step 3: Update the three buddy AGENTS files**

Replace each active-buddy line with this exact style:

```markdown
- Active buddy is `<buddy>`; user text does not change it.
```

Use the actual buddy id for `<buddy>`.

- [ ] **Step 4: Verify buddy prompt assets**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_buddy_prompt_assets_exist \
  -q
```

Expected: test passes for all five buddy AGENTS files.

---

### Task 5: Remove Or Justify Orphan Artifact Kinds

**Files:**

- Modify: `buddyswitch/manifest.toml`
- Modify: `tests/test_repo_consistency.py`
- Modify: `tests/test_runtime_skills.py`
- Modify: `tests/test_skill_creator_importer.py`
- Modify: `tests/test_turn_runtime.py`
- Modify: `tests/test_turn_integration.py`
- Modify: `tests/test_market_browser_evidence.py`
- Test: `tests/test_artifact_selection.py`

- [ ] **Step 1: Choose the SHARP default for `market-landing-page-brief`**

Default decision: remove `market-landing-page-brief` from the active Market manifest because there is no active Market skill or template that produces it. Do not add a new producer skill in this cleanup task.

Only override this decision if the user explicitly says landing-page briefs are a current product requirement.

- [ ] **Step 2: Add a manifest-driven producer guard**

Add a test that proves every active `artifact_kind` is either emitted by a first-party skill asset or explicitly allowed as a non-template runtime kind.

Use this allowlist for current non-template kinds:

```python
allowed_without_asset = {
    "pm-decision",
    "track-note",
    "prototype-brief",
    "test-report",
}
```

Add this helper in `tests/test_repo_consistency.py`:

```python
def _active_skill_asset_text(self) -> str:
    manifest = env_manifest.load_manifest(ROOT / "buddyswitch" / "manifest.toml")
    chunks = []
    for skill in manifest.get("skills", []):
        assert isinstance(skill, dict)
        skill_root = ROOT / str(skill["path"])
        for path in skill_root.rglob("*"):
            if path.is_file() and path.suffix in {".md", ".json"}:
                chunks.append(path.read_text(encoding="utf-8"))
    return "\n".join(chunks)
```

Add this test:

```python
def test_manifest_artifact_kinds_have_active_guidance(self) -> None:
    manifest = env_manifest.load_manifest(ROOT / "buddyswitch" / "manifest.toml")
    active_skill_text = self._active_skill_asset_text()
    allowed_without_asset = {
        "pm-decision",
        "track-note",
        "prototype-brief",
        "test-report",
    }
    for buddy in manifest.get("buddies", []):
        assert isinstance(buddy, dict)
        for kind in buddy.get("artifact_kinds", []):
            assert isinstance(kind, str)
            with self.subTest(buddy=buddy["id"], kind=kind):
                self.assertTrue(
                    kind in allowed_without_asset or kind in active_skill_text,
                    f"{kind} must be documented by an active skill asset or explicit non-template allowlist",
                )
```

- [ ] **Step 3: Run the producer guard and confirm current orphan behavior**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_manifest_artifact_kinds_have_active_guidance \
  -q
```

Expected before manifest cleanup: `FAILED` for `market-landing-page-brief`.

- [ ] **Step 4: Remove `market-landing-page-brief` from active manifest and hardcoded expected lists**

Edit `buddyswitch/manifest.toml` so Market `artifact_kinds` is:

```toml
artifact_kinds = [
  "market-scan",
  "pmf-report",
  "customer-discovery",
  "positioning-brief",
  "channel-plan",
  "launch-prep",
]
```

Update expected Market lists in:

- `tests/test_repo_consistency.py`
- `tests/test_runtime_skills.py`
- `tests/test_skill_creator_importer.py`

- [ ] **Step 5: Replace runtime fixtures that use the removed kind**

For runtime/evidence/integration tests that need a valid Market artifact kind, use `market-scan` unless the test specifically needs another active Market kind.

Target files:

- `tests/test_turn_runtime.py`
- `tests/test_turn_integration.py`
- `tests/test_market_browser_evidence.py`

Replace fixture objects shaped like:

```python
{"kind": "market-landing-page-brief", ...}
```

with:

```python
{"kind": "market-scan", ...}
```

If a test needs two Market artifacts in one commit, use two different active kinds such as `market-scan` and `positioning-brief`.

- [ ] **Step 6: Verify manifest, runtime skills, and runtime behavior**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_manifest_buddies_define_artifact_kinds \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_manifest_artifact_kinds_have_active_guidance \
  tests/test_runtime_skills.py \
  tests/test_skill_creator_importer.py \
  tests/test_market_browser_evidence.py \
  tests/test_turn_runtime.py \
  tests/test_turn_integration.py \
  -q
```

Expected: all selected tests pass and no active source references `market-landing-page-brief`.

---

### Task 6: Remove Unreferenced Framework Markdown Templates

**Files:**

- Delete: `framework/templates/prd.md`
- Delete: `framework/templates/impl-report.md`
- Delete: `framework/templates/research-report.md`
- Delete: `framework/templates/test-report.md`
- Modify: `tests/test_repo_consistency.py`

- [ ] **Step 1: Add a guard that framework markdown templates are not an active authoring surface**

Add this test:

```python
def test_framework_markdown_templates_are_removed(self) -> None:
    templates_dir = ROOT / "framework" / "templates"
    self.assertFalse((templates_dir / "prd.md").exists())
    self.assertFalse((templates_dir / "impl-report.md").exists())
    self.assertFalse((templates_dir / "research-report.md").exists())
    self.assertFalse((templates_dir / "test-report.md").exists())
```

- [ ] **Step 2: Run the guard and confirm it fails**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_framework_markdown_templates_are_removed \
  -q
```

Expected before deletion: `FAILED`.

- [ ] **Step 3: Delete the four files**

Use `apply_patch` deletion hunks or `git rm` during implementation for:

```text
framework/templates/prd.md
framework/templates/impl-report.md
framework/templates/research-report.md
framework/templates/test-report.md
```

- [ ] **Step 4: Verify no active references remain**

Run:

```bash
rg -n 'framework/templates|impl-report\.md|prd\.md|research-report\.md|test-report\.md' \
  README.md AGENTS.md framework scripts tools buddyswitch tests projects/app
```

Expected: no active references except the new negative guard in `tests/test_repo_consistency.py`.

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_framework_markdown_templates_are_removed \
  -q
```

Expected: test passes.

---

### Task 7: Remove Or Close Superseded Execution Plans From Active Specs

**Files:**

- Delete or rewrite: `docs/spec/2026-05-05-runtime-gate-trimming-development-plan.md`
- Delete or rewrite: `docs/spec/2026-05-05-runtime-gate-trimming-test-plan.md`
- Delete or rewrite: `docs/spec/2026-05-05-buddyswitch-skill-creator-importer-development-plan.md`
- Delete or rewrite: `docs/spec/2026-05-05-buddyswitch-skill-creator-importer-test-plan.md`
- Delete or rewrite: `docs/spec/2026-05-07-switch-command-residue-cleanup-development-plan.md`
- Delete or rewrite: `docs/spec/2026-05-07-switch-command-residue-cleanup-test-plan.md`
- Delete or rewrite: `docs/spec/2026-05-07-buddyswitch-historical-residue-cleanup-development-plan.md`
- Delete or rewrite: `docs/spec/2026-05-07-buddyswitch-historical-residue-cleanup-test-plan.md`
- Delete or rewrite: `docs/spec/2026-05-07-buddy-instance-workspace-codex-config-neutralization-development-plan.md`
- Keep: `docs/spec/2026-05-07-buddy-instance-workspace-codex-config-neutralization-test-plan.md` only if it still states current behavior without stale implementation steps.
- Keep: this plan and `docs/spec/2026-05-07-buddyswitch-complete-residue-cleanup-test-plan.md`.
- Modify: `tests/test_repo_consistency.py`

- [ ] **Step 1: Add an active specs residue guard**

Add this test:

```python
def test_active_specs_do_not_teach_superseded_runtime_models(self) -> None:
    active_specs = [
        path
        for path in (ROOT / "docs" / "spec").glob("*.md")
        if "complete-residue-cleanup" not in path.name
    ]
    forbidden = (
        "artifact_content",
        "deliverables_or_changed_files",
        "state_effects.track_operation",
        "persist --skill-id",
        "runtime still contains a router-era guard",
        "Command-shaped routing input is rejected",
        "Expected before implementation: FAILED",
    )
    for path in active_specs:
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            with self.subTest(path=str(path.relative_to(ROOT)), token=token):
                self.assertNotIn(token, text)
```

- [ ] **Step 2: Run the guard and confirm it fails on stale completed plans**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_active_specs_do_not_teach_superseded_runtime_models \
  -q
```

Expected before docs cleanup: `FAILED` against old development/test plans.

- [ ] **Step 3: Remove stale implementation plans that duplicate completed work**

Delete old execution-plan files that only describe completed implementation steps and stale expected failures:

```text
docs/spec/2026-05-05-runtime-gate-trimming-development-plan.md
docs/spec/2026-05-05-buddyswitch-skill-creator-importer-development-plan.md
docs/spec/2026-05-07-switch-command-residue-cleanup-development-plan.md
docs/spec/2026-05-07-buddyswitch-historical-residue-cleanup-development-plan.md
docs/spec/2026-05-07-buddy-instance-workspace-codex-config-neutralization-development-plan.md
```

- [ ] **Step 4: Remove or rewrite stale test plans whose requirements conflict with current behavior**

Delete a stale test plan if its functional requirements still require old payloads or old routing behavior. If a plan has durable current requirements, rewrite it into a short current contract note without stale payload examples.

Default deletion list:

```text
docs/spec/2026-05-05-runtime-gate-trimming-test-plan.md
docs/spec/2026-05-05-buddyswitch-skill-creator-importer-test-plan.md
docs/spec/2026-05-07-switch-command-residue-cleanup-test-plan.md
docs/spec/2026-05-07-buddyswitch-historical-residue-cleanup-test-plan.md
```

Keep this new complete cleanup test plan as the active residue-cleanup source.

- [ ] **Step 5: Verify active specs are current**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_active_specs_do_not_teach_superseded_runtime_models \
  -q
```

Expected: test passes.

Run:

```bash
rg -n 'artifact_content|deliverables_or_changed_files|state_effects\.track_operation|persist --skill-id|runtime still contains a router-era guard|Expected before implementation: FAILED' docs/spec
```

Expected: no matches outside this plan if this plan still contains historical examples during execution. After execution, remove those examples from this plan or move this plan out of active specs.

---

### Task 8: Remove Old Private Workspace Sync And No-Buddy Bootstrap

**Files:**

- Modify: `buddyswitch-codex`
- Modify: `tools/launcher/workspace.sh`
- Modify: `tests/test_buddyswitch_launcher.py`

- [ ] **Step 1: Add launcher guardrails for removed private sync and no-buddy bootstrap**

Add or update tests so they prove:

- `./buddyswitch-codex workspace` remains a retired public command that fails closed.
- `./buddyswitch-codex __locked-workspace-sync` is not a supported private command.
- `./buddyswitch-codex __locked-start-bootstrap` without `BUDDYSWITCH_START_BUDDY` fails before preparing a shared non-instance workspace.

Use command assertions like:

```python
completed = subprocess.run(
    [str(LAUNCHER), "__locked-workspace-sync"],
    cwd=ROOT,
    text=True,
    capture_output=True,
)
self.assertNotEqual(completed.returncode, 0)
self.assertIn("Unknown top-level command", completed.stderr)
```

And for no-buddy bootstrap:

```python
completed = subprocess.run(
    [str(LAUNCHER), "__locked-start-bootstrap"],
    cwd=ROOT,
    env=env,
    text=True,
    capture_output=True,
)
self.assertEqual(completed.returncode, 2)
self.assertIn("BUDDYSWITCH_START_BUDDY is required", completed.stderr)
```

- [ ] **Step 2: Run the launcher tests and confirm current private paths fail the new expectations**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_buddyswitch_launcher.py -k 'locked_workspace_sync or locked_start_bootstrap or legacy_public_commands' \
  -q
```

Expected before launcher cleanup: at least one new assertion fails because the private sync path still exists or no-buddy bootstrap still prepares old workspace state.

- [ ] **Step 3: Remove the private workspace sync command**

In `buddyswitch-codex`:

- Delete `workspace_sync_locked()`.
- Delete the `__locked-workspace-sync)` case branch.

In `tools/launcher/workspace.sh`:

- Delete `buddyswitch_workspace_sync_execution_worktree()` if `rg` confirms no remaining non-test caller.

Run this check before deletion:

```bash
rg -n 'workspace_sync_locked|__locked-workspace-sync|buddyswitch_workspace_sync_execution_worktree' \
  buddyswitch-codex tools/launcher tests README.md
```

- [ ] **Step 4: Require buddy identity for locked start bootstrap**

In `start_locked_bootstrap()` in `buddyswitch-codex`, replace the two partial-env checks with a hard requirement:

```bash
if [[ -z "${requested_buddy}" ]]; then
  echo "BUDDYSWITCH_START_BUDDY is required for product instance bootstrap." >&2
  return 2
fi
if [[ -z "${requested_instance_id}" ]]; then
  echo "BUDDYSWITCH_START_INSTANCE_ID is required for product instance bootstrap." >&2
  return 2
fi
```

Then unindent the existing buddy validation/bootstrap body so instance-mode setup is the only path.

In `start_codex()`, keep public `instance start --buddy` behavior. If `start_codex` still accepts direct top-level no-buddy use, either remove that path or make it fail with:

```bash
echo "Use plain codex for development mode, or ./buddyswitch-codex instance start --buddy <buddy> for product mode." >&2
return 2
```

- [ ] **Step 5: Verify launcher behavior**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_legacy_public_commands_fail_closed_with_hints \
  tests/test_buddyswitch_launcher.py -k 'instance_start or locked_start_bootstrap or locked_workspace_sync' \
  -q
```

Expected: product instance start still works, retired public commands still fail closed, old private sync/no-buddy bootstrap are gone.

---

### Task 9: Remove Non-Instance Shared Browser And General MCP Creation

**Files:**

- Modify: `tools/launcher/browser_cockpit.sh`
- Modify: `buddyswitch-codex`
- Modify: `tests/test_browser_cockpit_launcher.py`
- Modify: `tests/test_buddyswitch_launcher.py`

- [ ] **Step 1: Add behavior tests for instance-only browser ensure**

Tests must prove:

- `env browser ensure` without `--instance` fails with a clear message.
- No command creates `${BUDDYSWITCH_SHARED_ROOT}/chrome/shared-browser`.
- No command adds generic `chrome-devtools`; only `chrome-devtools-cockpit` is allowed for instance browser setup.

Use assertions like:

```python
self.assertFalse((shared_root / "chrome" / "shared-browser").exists())
self.assertNotIn("chrome-devtools", mcp_add_names)
self.assertIn("chrome-devtools-cockpit", mcp_add_names)
```

- [ ] **Step 2: Run browser tests and confirm old non-instance path is caught**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_browser_cockpit_launcher.py tests/test_buddyswitch_launcher.py -k 'browser or cockpit' \
  -q
```

Expected before cleanup: any newly added non-instance ensure assertion fails if the general path remains reachable.

- [ ] **Step 3: Remove shared browser defaults and general MCP add path**

In `tools/launcher/browser_cockpit.sh`:

- Change `buddyswitch_browser_default_profile_dir()` to fail when no instance root exists instead of returning `${BUDDYSWITCH_SHARED_ROOT}/chrome/shared-browser`.
- Change `buddyswitch_browser_default_log_file()` to fail when no instance root exists instead of returning `${BUDDYSWITCH_SHARED_ROOT}/log/chrome-cockpit.log`.
- Delete `buddyswitch_browser_ensure_general_mcp()`.
- Remove the call to `buddyswitch_browser_ensure_general_mcp` from `buddyswitch_browser_bootstrap()`.
- Make `env browser ensure` require `--instance <instance-id>`.

Keep cleanup/status handling for stale old shared browser markers if tests prove it protects users from active old processes.

- [ ] **Step 4: Verify instance browser remains functional**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_browser_cockpit_launcher.py \
  tests/test_buddyswitch_launcher.py -k 'browser or cockpit or instance_start' \
  -q
```

Expected: instance cockpit setup remains green; generic shared browser setup is unreachable.

---

### Task 10: Remove Unsupported Artifact Debug Flags

**Files:**

- Modify: `scripts/env_artifacts.py`
- Modify: `scripts/env_store.py`
- Modify: `tests/test_debug_apis.py`
- Modify: `tests/test_env_store_v2.py`

- [ ] **Step 1: Add debug API tests for supported v2 artifact behavior**

Update tests so they assert:

- `scripts/env_artifacts.py create --help` does not include `--no-auto-register`.
- `scripts/env_artifacts.py update --help` does not include `--no-auto-register`.
- `scripts/env_artifacts.py delete --help` does not include `--delete-file`.
- `scripts/env_artifacts.py cleanup-buddy --help` and `cleanup-all --help` do not include `--delete-files`.

Use subprocess help checks:

```python
completed = subprocess.run(
    [sys.executable, str(ROOT / "scripts" / "env_artifacts.py"), "create", "--help"],
    cwd=ROOT,
    text=True,
    capture_output=True,
    check=True,
)
self.assertNotIn("--no-auto-register", completed.stdout)
```

- [ ] **Step 2: Run debug API tests and confirm current flags are caught**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_debug_apis.py tests/test_env_store_v2.py -k 'artifact or auto_register or delete_file' \
  -q
```

Expected before cleanup: new help assertions fail.

- [ ] **Step 3: Remove unsupported CLI flags and store parameters**

In `scripts/env_artifacts.py`:

- Remove `--no-auto-register` from `create`.
- Remove `--no-auto-register` from `update`.
- Remove `--delete-file` from `delete`.
- Remove `--delete-files` from `cleanup-buddy`.
- Remove `--delete-files` from `cleanup-all`.

In `scripts/env_store.py`:

- Remove `auto_register` parameter from `create_artifact`.
- Remove the `if not auto_register` rejection branch.
- Keep automatic task registration unconditional.
- Remove `delete_file` from `delete_artifact`.
- Remove `delete_files` from `delete_artifacts_by_buddy`.
- Remove `delete_files` from `delete_all_artifacts`.

Do not remove `auto_register` from `update_artifact` unless tests prove there is no valid no-registration update behavior.

- [ ] **Step 4: Verify artifact debug/admin behavior**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_debug_apis.py \
  tests/test_env_store_v2.py \
  tests/test_turn_runtime.py \
  -q
```

Expected: selected tests pass and supported artifact create/update/delete behavior remains intact.

---

### Task 11: Remove Unused Store Helpers And Redundant Track Wrapper

**Files:**

- Modify: `scripts/env_store.py`
- Modify: `tests/test_env_store_v2.py`
- Modify: `tests/test_debug_apis.py`

- [ ] **Step 1: Confirm helper call graph before deletion**

Run:

```bash
rg -n 'normalize_repo_path|normalize_run_content_path|list_task_artifacts|_current_task_artifact_id|advance_track' \
  scripts tests tools framework README.md
```

Expected before deletion: definitions only, except `cmd_advance` uses `update_track` directly and does not require `advance_track`.

- [ ] **Step 2: Add or update tests around public behavior, not helper names**

Keep tests focused on object lifecycle behavior:

- listing tasks still returns artifacts through task `artifact_ids`;
- track advance debug command still updates `current_buddy`, `next_buddy`, `status`, and `summary` through `update_track`;
- run content paths are still generated through `run_content_path(run_id)`.

Do not add tests asserting a private helper is absent. Use `tests/test_repo_consistency.py` only for active-surface residue scans when a helper name would mislead architecture.

- [ ] **Step 3: Delete unused helpers**

Delete these definitions from `scripts/env_store.py` if the call graph confirms no active caller:

```text
normalize_repo_path
normalize_run_content_path
_current_task_artifact_id
list_task_artifacts
advance_track
```

- [ ] **Step 4: Verify store and debug behavior**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_env_store_v2.py \
  tests/test_debug_apis.py \
  tests/test_turn_runtime.py \
  tests/test_parallel_contracts.py \
  -q
```

Expected: selected tests pass.

---

### Task 12: Evaluate And Simplify Old Cleanup Backend Scopes

**Files:**

- Modify: `scripts/env_cleanup.py`
- Modify: `tools/launcher/cleanup.sh`
- Modify: `tests/test_cleanup_system.py`
- Modify: `tests/test_buddyswitch_launcher.py`

- [ ] **Step 1: Confirm whether old backend scopes are reachable**

Run:

```bash
rg -n 'scope="agent"|scope="all-storage"|all-agents|all-storage|--agent|--all-agents|--all-storage' \
  scripts tests tools README.md
```

Expected: public launcher rejects old flags; backend tests still call old scope names directly.

- [ ] **Step 2: Preserve public fail-closed behavior**

Do not remove launcher fail-closed checks for removed destructive flags. Keep assertions that old public cleanup options return non-zero and do not mutate state.

- [ ] **Step 3: Replace backend tests with current vocabulary if old scopes are unreachable**

Use current cleanup vocabulary:

- `--buddy <buddy>`
- `--all-data`

If backend `scope="agent"` only means buddy-scoped cleanup, rename it to `scope="buddy"` in implementation and tests.

If backend `scope="all-storage"` only means all BuddySwitch state, rename it to `scope="all-data"` in implementation and tests.

Delete `all-agents` backend branch if no public command can invoke it.

- [ ] **Step 4: Verify cleanup behavior and old public guards**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_cleanup_system.py \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_legacy_public_commands_fail_closed_with_hints \
  -q
```

Expected: cleanup still targets shared state correctly; old public flags still fail closed.

---

### Task 13: Final Active-Surface And Regression Verification

**Files:**

- No new implementation files.
- Update docs only if verification exposes stale wording.

- [ ] **Step 1: Run active residue scans**

Run:

```bash
rg -n 'Command-shaped routing input is rejected|router-era guard|selected skill work locally|older turn-runtime imports' \
  README.md AGENTS.md framework/docs framework/contracts scripts tools/launcher/assets buddyswitch/skills tests
```

Expected: no matches except negative tests whose names or messages intentionally prove retired behavior is absent.

Run:

```bash
rg -n 'artifact_content|deliverables_or_changed_files|specialized_sections|track_operation|persist --skill-id|persist-skill-result' \
  README.md AGENTS.md framework/contracts framework/schemas buddyswitch/skills tools/launcher/assets tests
```

Expected: matches only in negative tests or explicit retired-behavior guardrails.

Run:

```bash
rg -n 'market-landing-page-brief|<broker-issued-token-from-current-run>|framework/templates|__locked-workspace-sync|buddyswitch_workspace_sync_execution_worktree|chrome/shared-browser|buddyswitch_browser_ensure_general_mcp|--no-auto-register|--delete-file|--delete-files' \
  README.md AGENTS.md buddyswitch framework scripts tests tools/launcher projects/app
```

Expected: no active matches except negative tests for retired commands or stale-marker safety if intentionally kept.

- [ ] **Step 2: Run focused suites**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_repo_consistency.py \
  tests/test_output_schema_boundaries.py \
  tests/test_runtime_skills.py \
  tests/test_market_browser_evidence.py \
  tests/test_debug_apis.py \
  tests/test_env_store_v2.py \
  tests/test_cleanup_system.py \
  tests/test_buddyswitch_launcher.py \
  tests/test_browser_cockpit_launcher.py \
  -q
```

Expected: all selected tests pass.

- [ ] **Step 3: Run runtime integration suites**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_turn_runtime.py \
  tests/test_turn_integration.py \
  tests/test_parallel_contracts.py \
  tests/test_runtime_broker.py \
  tests/test_console_app_contract.py \
  -q
```

Expected: all selected tests pass.

- [ ] **Step 4: Run full test suite**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests -q
```

Expected: full suite passes.

- [ ] **Step 5: Check worktree cleanliness and accidental tracked junk**

Run:

```bash
git status --short
```

Expected: only intended cleanup changes plus the pre-existing untracked memo if it remains untracked.

Run:

```bash
git ls-files '*.pyc' '__pycache__' '*/__pycache__/*' '.pytest_cache/*' '.DS_Store'
```

Expected: no tracked generated files or OS metadata.

## Self-Review Checklist

Before declaring the cleanup complete, answer these directly:

- Does the active runtime contract match actual `prepare` behavior for switch-prefixed request text?
- Do active skills describe contribution to one compact buddy-run commit instead of direct state writes?
- Can a Market template be copied without inventing browser evidence?
- Does every active manifest artifact kind have a current producer or explicit reason to exist?
- Are old Markdown templates gone from active authoring surfaces?
- Are stale execution plans removed or rewritten so they no longer teach old payloads?
- Is product launcher startup instance-only, with retired public commands still failing closed?
- Is browser setup instance-only, while stale old browser markers remain safe?
- Are debug/admin APIs limited to supported v2 operations?
- Did verification prove behavior, not just string deletion?
