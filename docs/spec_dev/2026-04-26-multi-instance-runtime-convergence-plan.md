# Multi-Instance Runtime Convergence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Converge the multi-instance BuddySwitch runtime into a simpler, clearer, merge-ready shape without redesigning the per-instance worktree model.

**Architecture:** Keep the core model: shared canonical BuddySwitch state, isolated execution per buddy-locked instance, one runtime lock, one canonical resolve/persist loop. Fix concrete lifecycle, cleanup, prompt, and documentation drift first; defer broad store rewrites and overlay workspace designs until real usage proves they are necessary.

**Tech Stack:** Bash launcher scripts, Python runtime and cleanup scripts, Markdown contracts/prompts, `unittest`/`pytest`, `rg`, `git diff --check`.

---

## Status

- Draft implementation plan.
- Work only in `/Users/chen/Dev/buddyswitch/.worktrees/multi-instance-buddy-runtime-architecture`.
- Do not edit `/Users/chen/Dev/buddyswitch` main checkout.
- Do not commit until the human confirms implementation and checkpoint scope.

## Preflight Gate

### Target Outcome And Current Bottleneck

The current bottleneck is convergence, not a new runtime architecture. The branch already implements the main shape, but merge readiness is blocked by drift and small correctness hazards:

1. Active docs still describe the old singleton `${BUDDYSWITCH_SHARED_ROOT}/workspace` product path.
2. Buddy prompt assets are thin overlays and do not carry the baseline runtime contract.
3. Cleanup and maintenance still have legacy assumptions around run attribution, dry-run mutation, and worktree deletion.
4. Context Panel snapshot locking and reservation cleanup still have fail-open or hidden-failure edges.
5. Browser/auth handling can be tightened without introducing new services or abstractions.

The target outcome is a verified checkpoint where the product-mode contract is clear:

```text
shared canonical state, isolated per-instance execution, one locked buddy per process
```

### Confirmed Facts

- `README.md` still says product mode uses `${BUDDYSWITCH_SHARED_ROOT}/workspace`.
- `AGENTS.md` still says `./buddyswitch-codex start` launches under `${BUDDYSWITCH_SHARED_ROOT}/workspace`.
- `tests/test_repo_consistency.py::test_readme_quick_start_distinguishes_development_and_launcher_modes` requires the old singleton workspace path.
- `scripts/env_cleanup.py::discover_run_content()` reads `switch.buddy`, while current run audits use `switch.buddy_id`.
- `scripts/cleanup_buddyswitch.sh` strips `.git/info/exclude` before checking whether cleanup is an executing cleanup or a dry-run.
- `buddyswitch-codex reset --yes` removes `${BUDDYSWITCH_SHARED_ROOT}` with `rm -rf` but does not explicitly deregister instance git worktrees first.
- `scripts/runtime_store/projections.py::runtime_snapshot_lock()` yields without a lock when `BUDDYSWITCH_SHARED_ROOT` is absent.
- `scripts/switch_runtime.py::_clear_run_reservation()` swallows `OSError`.
- `tools/launcher/assets/buddies/*/AGENTS.md` are short buddy overlays and omit important runtime baseline rules from `tools/launcher/assets/runtime-AGENTS.md`.
- `framework/contracts/market.md` and `framework/docs/browser-cockpit.md` still use stale shared-cockpit prose even though active metadata uses `instance-browser` and `instance-cockpit`.

### Open Assumptions

- Per-instance full git worktrees are acceptable for this checkpoint. Current repo size is small, and replacing them with overlay/symlink workspaces would add complexity before disk/startup cost is proven.
- Legacy no-buddy `start` and `${BUDDYSWITCH_SHARED_ROOT}/workspace` can remain as explicit compatibility/debug paths for now, but active docs must not present them as product mode.
- `switch.buddy` fallback in cleanup is kept only for existing historical run audits. Current-format cleanup authority is `switch.buddy_id`.
- Instance `auth.json` should not be a separate copied regular file in every instance. The first convergence target is shared auth reference plus per-instance config, not a credential vault.

### Non-Goals

- Do not redesign per-instance workspaces into overlay, symlink-only, bind mount, or FUSE workspaces.
- Do not remove all legacy no-buddy/shared-workspace compatibility in this batch.
- Do not flatten `runtime_store` / `env_store` in this batch.
- Do not introduce a browser supervisor daemon, credential vault, workflow engine, plugin layer, prompt generator, smart instance reuse system, or per-instance maintenance API.
- Do not make `parse_switch.py` accept plain text.
- Do not add aliases from `shared-browser` to `instance-browser`.
- Do not rewrite historical planning docs only because they mention old terms.

### Verification Plan

Run targeted tests after each task, then the final suite:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_repo_consistency.py -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_cleanup_system.py -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_buddyswitch_launcher.py -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_switch_runtime.py -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider -q
git diff --check
git status --short --branch
git -C /Users/chen/Dev/buddyswitch status --short --branch
```

If sandboxed local socket binding blocks launcher/browser/context-panel tests, rerun the same targeted command with approved escalation and record that the failure was environmental.

## File Map

- Modify `README.md`: describe product mode as `start --buddy <buddy>` and instance workspace layout.
- Modify `AGENTS.md`: replace singleton workspace guidance with instance workspace guidance.
- Modify `framework/docs/architecture-overview.md`: explain product mode versus canonical wire form and current resolve outputs.
- Modify `framework/docs/switch-spec.md`: formalize plain product input adapter boundaries without changing canonical grammar.
- Modify `framework/docs/skill-architecture-best-practices.md`: distinguish canonical `switch` from product-mode plain input.
- Modify `framework/docs/browser-cockpit.md`: replace stale shared cockpit prose with instance-bound cockpit prose.
- Modify `framework/contracts/market.md`: replace stale shared cockpit prose while preserving selected-skill browser contract.
- Modify `tools/launcher/assets/buddies/*/AGENTS.md`: include essential runtime baseline semantics plus buddy lock overlay.
- Modify `tests/test_repo_consistency.py`: lock active docs/prompts/terminology to the new contract.
- Modify `tests/test_buddyswitch_launcher.py`: lock copied buddy prompt semantics, worktree deregistration, auth behavior, and browser liveness where relevant.
- Modify `scripts/env_cleanup.py`: prefer `switch.buddy_id` for run audit attribution.
- Modify `scripts/cleanup_buddyswitch.sh`: make dry-run non-mutating and deregister instance worktrees before deleting runtime roots.
- Modify `tools/launcher/workspace.sh`: add reusable worktree deregistration helper.
- Modify `tools/launcher/env.sh`: avoid per-instance regular auth copies.
- Modify `tools/launcher/browser_cockpit.sh`: detect active instance browsers beyond pid markers.
- Modify `scripts/runtime_store/projections.py`: derive or fail closed for snapshot locks when projected state is present.
- Modify `scripts/switch_runtime.py`: make reservation deletion failure observable.
- Modify `tests/test_cleanup_system.py`: cover cleanup dry-run, current `switch.buddy_id`, and instance worktree cleanup.
- Modify `tests/test_switch_runtime.py`: cover snapshot lock derivation/fail-closed behavior and reservation clear failure.
- Modify `docs/spec_dev/2026-04-24-multi-instance-runtime-checkpoint-closeout-plan.md`: mark superseded by this convergence plan.

## Task 1: Lock Product Mode Docs To Instance Workspaces

**Files:**

- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `framework/docs/architecture-overview.md`
- Modify: `framework/docs/switch-spec.md`
- Modify: `framework/docs/skill-architecture-best-practices.md`
- Modify: `tests/test_repo_consistency.py`

- [ ] **Step 1: Write failing repo consistency checks**

In `tests/test_repo_consistency.py`, update `test_readme_quick_start_distinguishes_development_and_launcher_modes` to require instance product mode and reject singleton product-mode wording:

```python
    def test_readme_quick_start_distinguishes_development_and_launcher_modes(self) -> None:
        text = (ROOT / "README.md").read_text(encoding="utf-8").lower()

        self.assertIn("two modes exist", text)
        self.assertIn("develop buddyswitch", text)
        self.assertIn("./buddyswitch-codex start --buddy <buddy>", text)
        self.assertIn("${buddyswitch_shared_root}/instances/<instance-id>/workspace", text)
        self.assertIn("${buddyswitch_shared_root}/state", text)
        self.assertNotIn("product mode uses:\n\n- `${buddyswitch_shared_root}`", text)
        self.assertNotIn("${buddyswitch_shared_root}/workspace` for the execution worktree", text)
```

Add a focused active-doc guard:

```python
    def test_active_product_mode_docs_do_not_teach_singleton_workspace(self) -> None:
        active_docs = (
            ROOT / "README.md",
            ROOT / "AGENTS.md",
            ROOT / "framework" / "docs" / "architecture-overview.md",
            ROOT / "framework" / "docs" / "switch-spec.md",
            ROOT / "framework" / "docs" / "skill-architecture-best-practices.md",
        )
        forbidden = (
            "${buddyswitch_shared_root}/workspace for the execution worktree",
            "~/.codex-buddyswitch/workspace",
            "launcher-managed execution worktree under `${buddyswitch_shared_root}/workspace`",
        )
        required = (
            "${buddyswitch_shared_root}/instances/<instance-id>/workspace",
            "${buddyswitch_shared_root}/state",
        )
        for path in active_docs:
            with self.subTest(active_doc=str(path.relative_to(ROOT))):
                text = path.read_text(encoding="utf-8").lower()
                for token in forbidden:
                    self.assertNotIn(token, text)
        readme = (ROOT / "README.md").read_text(encoding="utf-8").lower()
        for token in required:
            self.assertIn(token, readme)
```

- [ ] **Step 2: Run the targeted failing tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_readme_quick_start_distinguishes_development_and_launcher_modes \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_active_product_mode_docs_do_not_teach_singleton_workspace \
  -q
```

Expected before docs are fixed: failure pointing at old `${BUDDYSWITCH_SHARED_ROOT}/workspace` wording.

- [ ] **Step 3: Update `README.md` quick start**

Replace the product-mode bullets near the top with this exact semantic content:

```markdown
The launcher-managed product mode uses:

- `${BUDDYSWITCH_SHARED_ROOT}` as the shared launcher root
- `${BUDDYSWITCH_SHARED_ROOT}/state` for canonical BuddySwitch task, track, artifact, and run state
- `${BUDDYSWITCH_SHARED_ROOT}/instances/<instance-id>/workspace` for each buddy-locked execution worktree
- `tools/launcher/assets/buddies/<buddy>/AGENTS.md` for the instance root prompt contract

Product-mode startup is:

```bash
./buddyswitch-codex start --buddy <buddy>
```
```

Replace later `./buddyswitch-codex start` examples with `./buddyswitch-codex start --buddy pm` or `./buddyswitch-codex start --buddy market` when product mode is intended. Reword `workspace sync` as legacy/debug compatibility only:

```markdown
`workspace sync` is retained only for the legacy singleton workspace path and is not the product-mode refresh path once `instances/` exists.
```

Replace cleanup wording that targets `~/.codex-buddyswitch/workspace` with:

```markdown
Cleanup targets shared state under `${BUDDYSWITCH_SHARED_ROOT}/state` and instance-local scratch under `${BUDDYSWITCH_SHARED_ROOT}/instances/*`.
```

- [ ] **Step 4: Update `AGENTS.md` repository notes**

Replace the old singleton line with:

```markdown
- `./buddyswitch-codex start --buddy <buddy>` does not run Codex from this checkout; it launches from a launcher-managed instance worktree under `${BUDDYSWITCH_SHARED_ROOT}/instances/<instance-id>/workspace`.
- Shared BuddySwitch state lives under `${BUDDYSWITCH_SHARED_ROOT}/state` and is projected into each instance workspace through the repo-relative runtime paths.
```

- [ ] **Step 5: Update framework docs for product mode versus canonical wire form**

In `framework/docs/switch-spec.md`, add a section immediately after the canonical syntax block:

```markdown
## Product-Mode Plain Input

The canonical wire grammar remains `switch <buddy>(<task-id>) -> <track-id>: <demand>`.
`parse_switch.py` stays strict and only parses canonical `switch ...` text.

In a launcher-managed product-mode session, `./buddyswitch-codex start --buddy <buddy>` binds the process to one active buddy. Plain user text inside that session is adapted by `scripts/switch_runtime.py resolve` before parse when all product-mode env vars are valid:

- `BUDDYSWITCH_ACTIVE_BUDDY`
- `BUDDYSWITCH_INSTANCE_ID`
- `BUDDYSWITCH_INSTANCE_JSON`

Same-buddy canonical switches are allowed. Cross-buddy canonical switches reject before parse/resolve mutation. Missing product-mode env keeps strict canonical behavior. Partial product-mode env rejects before mutation.
```

In `framework/docs/architecture-overview.md`, update the mental model to say:

```markdown
- Product mode selects the buddy at launcher startup.
- The canonical wire form remains `switch ...`.
- Plain product-mode text is adapted to the canonical wire form only inside a valid buddy-locked session.
```

In `framework/docs/skill-architecture-best-practices.md`, replace any absolute claim that the user always chooses the buddy with `switch <buddy>...` with:

```markdown
Canonical runtime input uses `switch <buddy>...: <demand>`. Product-mode sessions may accept plain text because the launcher has already selected one active buddy and the resolve adapter converts the text to canonical wire form.
```

- [ ] **Step 6: Run targeted docs tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_repo_consistency.py -q
```

Expected: all repo consistency tests pass.

## Task 2: Make Buddy Prompt Assets Carry Baseline Runtime Semantics

**Files:**

- Modify: `tools/launcher/assets/buddies/pm/AGENTS.md`
- Modify: `tools/launcher/assets/buddies/market/AGENTS.md`
- Modify: `tools/launcher/assets/buddies/design/AGENTS.md`
- Modify: `tools/launcher/assets/buddies/dev/AGENTS.md`
- Modify: `tools/launcher/assets/buddies/test/AGENTS.md`
- Modify: `tests/test_repo_consistency.py`
- Modify: `tests/test_buddyswitch_launcher.py`

- [ ] **Step 1: Strengthen buddy prompt tests**

Extend `test_buddy_prompt_assets_exist_for_every_manifest_buddy` with required baseline tokens:

```python
                required_runtime_tokens = (
                    "resolve_context",
                    "selected-skill preflight",
                    "host_execution",
                    "tool_scope",
                    "persist-skill-result",
                    "refreshed_context",
                    "receipt -> commands -> summary",
                    "runs/raw/",
                    "projects/app/.runtime/",
                )
                for token in required_runtime_tokens:
                    self.assertIn(token, lower)
```

In `test_start_with_buddy_wires_instance_env_and_lifecycle`, after asserting the copied prompt equals the source prompt, add:

```python
            copied_agents = (workspace_dir / "AGENTS.md").read_text(encoding="utf-8").lower()
            for token in (
                "selected-skill preflight",
                "host_execution",
                "tool_scope",
                "persist-skill-result",
                "refreshed_context",
                "receipt -> commands -> summary",
            ):
                self.assertIn(token, copied_agents)
```

- [ ] **Step 2: Run the failing prompt tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_buddy_prompt_assets_exist_for_every_manifest_buddy \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_with_buddy_wires_instance_env_and_lifecycle \
  -q
```

Expected before prompt assets are fixed: failure on missing baseline runtime tokens.

- [ ] **Step 3: Expand each buddy `AGENTS.md` concretely**

For each buddy asset, keep line 1 as:

```markdown
# BuddySwitch Runtime Workspace
```

Then include this shared baseline content, replacing `<buddy>` with the buddy id:

```markdown
This workspace is launcher-owned, runtime-only, and locked to the `<buddy>` buddy.

Inside this session, plain user requests belong to `<buddy>`. Do not ask the user to prefix normal product-mode requests with `switch <buddy>:`. The runtime adapter converts plain text to the canonical BuddySwitch wire form before resolve.

## Canonical Loop

1. Resolve with `scripts/switch_runtime.py resolve`.
2. Choose exactly one `skill_id` from `resolve_context.skills`.
3. Read and execute the selected BuddySwitch `SKILL.md`.
4. Persist with `scripts/switch_runtime.py persist`.
5. Continue from `refreshed_context` when it is valid.

## Selected-Skill Preflight

- Treat the selected skill's `host_execution` and `tool_scope` as binding preflight instructions.
- `required_tools` and `required_env` are advisory readiness metadata for the host session.
- If the selected skill declares `discovery_mode = browser-native`, begin discovery and evidence capture in the declared `browser_executor`.
- If `login_policy = mandatory-takeover` and a required login gate is encountered, pause for takeover before continuing.
- If fallback or downgrade is needed, request explicit user approval before widening tool scope.

## Buddy Lock

- The active buddy is `<buddy>`.
- Same-buddy canonical `switch <buddy>...:` commands are allowed.
- Cross-buddy canonical switches are external handoffs and must not execute in this session.
- Durable BuddySwitch state lives in the projected `buddyswitch/objects/**` and `buddyswitch/content/runs/**` paths.
- `runs/raw/` and `projects/app/.runtime/` are instance-local scratch.

## Persistence And Final Output

- Persisted outputs must go through `persist-skill-result` via `scripts/switch_runtime.py persist`.
- After persist, use `refreshed_context` when `refreshed_context.ok = true`; rerun resolve when refreshed context is unavailable.
- Final terminal output must use `Receipt -> Commands -> Summary`.
- Keep object paths as debug details, not the lead user-facing result.
```

Do not add a prompt generator in this task. The assets remain concrete files copied by the launcher.

- [ ] **Step 4: Run prompt tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_buddy_prompt_assets_exist_for_every_manifest_buddy \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_with_buddy_wires_instance_env_and_lifecycle \
  -q
```

Expected: tests pass. If the launcher test fails from local socket sandbox restrictions, rerun with approved escalation and record the environmental cause.

## Task 3: Remove Stale Shared Cockpit Wording From Active Contracts

**Files:**

- Modify: `framework/contracts/market.md`
- Modify: `framework/docs/browser-cockpit.md`
- Modify: `tests/test_repo_consistency.py`

- [ ] **Step 1: Replace stale shared-cockpit regression**

Replace `test_market_contract_describes_shared_cockpit_without_implying_multi_skill_runs` with:

```python
    def test_market_contract_describes_instance_bound_cockpit_without_implying_multi_skill_runs(self) -> None:
        contract_text = (ROOT / "framework" / "contracts" / "market.md").read_text(encoding="utf-8").lower()
        self.assertIn("run the selected market skill in the instance-bound headed cockpit", contract_text)
        self.assertIn("active buddy instance", contract_text)
        self.assertNotIn("run all six market skills", contract_text)
```

Extend the active browser docs guard:

```python
    def test_active_browser_docs_do_not_use_legacy_shared_cockpit_terms(self) -> None:
        active_docs = (
            ROOT / "framework" / "contracts" / "market.md",
            ROOT / "framework" / "docs" / "browser-cockpit.md",
        )
        forbidden = (
            "shared headed cockpit",
            "shared browser cockpit",
            "shared browser endpoint",
            "shared browser profile",
            "shared-browser",
            "shared-cockpit",
        )
        for path in active_docs:
            with self.subTest(active_doc=str(path.relative_to(ROOT))):
                text = path.read_text(encoding="utf-8").lower()
                for token in forbidden:
                    self.assertNotIn(token, text)
                self.assertIn("instance-browser", text)
                self.assertIn("instance-cockpit", text)
```

- [ ] **Step 2: Run failing browser wording tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_market_contract_describes_instance_bound_cockpit_without_implying_multi_skill_runs \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_active_browser_docs_do_not_use_legacy_shared_cockpit_terms \
  -q
```

Expected before docs are fixed: failure on active docs containing stale shared-cockpit prose.

- [ ] **Step 3: Update market contract prose**

In `framework/contracts/market.md`, replace:

```markdown
- Run the selected market skill in the shared headed cockpit defined in `framework/docs/browser-cockpit.md`; the same cockpit contract applies across all six market skills.
```

with:

```markdown
- Run the selected market skill in the instance-bound headed cockpit defined in `framework/docs/browser-cockpit.md`; the same cockpit contract applies across all six market skills inside the active Buddy instance.
```

Replace:

```markdown
- The six market skills above share one execution-time browser cockpit, not six isolated browser stacks.
```

with:

```markdown
- The six market skills above use one execution-time browser cockpit inside the active Buddy instance, not six browser stacks inside that instance.
```

Replace:

```markdown
- for critical sources, require mandatory takeover in the shared headed cockpit before continuing
```

with:

```markdown
- for critical sources, require mandatory takeover in the instance-bound headed cockpit before continuing
```

- [ ] **Step 4: Update browser cockpit docs**

In `framework/docs/browser-cockpit.md`, rename the runtime rule heading:

```markdown
1. Instance-bound headed cockpit
```

Replace product-mode bootstrap prose with:

```markdown
- Preferred product-mode path: run `./buddyswitch-codex start --buddy <buddy>`.
- Buddy-locked `start` bootstraps the active instance home, ensures the instance-bound headed cockpit endpoint, ensures `chrome-devtools-cockpit`, and then launches Codex.
- `./buddyswitch-codex browser status` and `./buddyswitch-codex browser ensure` are debug/compatibility commands outside the normal buddy-locked product-mode path.
```

- [ ] **Step 5: Run active browser docs tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_repo_consistency.py -q
```

Expected: repo consistency tests pass.

## Task 4: Make Cleanup Correct And Non-Mutating In Dry-Run

**Files:**

- Modify: `scripts/env_cleanup.py`
- Modify: `scripts/cleanup_buddyswitch.sh`
- Modify: `tests/test_cleanup_system.py`

- [ ] **Step 1: Add current run-audit cleanup fixture**

Add a cleanup backend or shell test that writes run audit content using current shape:

```json
{
  "run_id": "run-market-current",
  "switch": {
    "buddy_id": "market",
    "task_id": "task-market-current",
    "demand": "current market cleanup"
  }
}
```

The test must assert `--agent market --execute` deletes the market run audit and preserves a PM run audit.

- [ ] **Step 2: Add dry-run non-mutation shell test**

Add a shell integration test that:

1. Writes a marker line into source checkout `.git/info/exclude`.
2. Creates source checkout runtime files that `--all-storage --execute` would delete.
3. Runs `scripts/cleanup_buddyswitch.sh --all-storage --json` without `--execute`.
4. Asserts the source runtime files still exist and `.git/info/exclude` is byte-for-byte unchanged.

Use a test name:

```python
def test_shell_all_storage_dry_run_does_not_mutate_source_checkout_or_excludes(self) -> None:
```

- [ ] **Step 3: Run failing cleanup tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_cleanup_system.py::CleanupShellIntegrationTests::test_shell_all_storage_dry_run_does_not_mutate_source_checkout_or_excludes \
  tests/test_cleanup_system.py -q
```

Expected before implementation: dry-run test fails because `.git/info/exclude` changes, and current `switch.buddy_id` run attribution is not cleaned correctly.

- [ ] **Step 4: Update `discover_run_content()`**

Change `scripts/env_cleanup.py::discover_run_content()` so it resolves buddy like this:

```python
        buddy = switch.get("buddy_id")
        if not isinstance(buddy, str) or not buddy:
            buddy = switch.get("buddy")
        if not isinstance(buddy, str) or not buddy:
            invalid.append({"path": relative, "run_id": run_id, "reason": "run content is missing switch.buddy_id"})
            continue
```

This keeps legacy fallback but makes current `switch.buddy_id` primary.

- [ ] **Step 5: Move source checkout mutation behind execute**

In `scripts/cleanup_buddyswitch.sh`, move:

```bash
buddyswitch_cleanup_strip_legacy_runtime_excludes "${SOURCE_REPO_ROOT}"
```

inside an execute-only branch:

```bash
  if buddyswitch_cleanup_requests_execute "${BUDDYSWITCH_CLEANUP_COMMON_ARGS[@]}"; then
    buddyswitch_cleanup_strip_legacy_runtime_excludes "${SOURCE_REPO_ROOT}"
  fi
```

Keep source checkout `env_cleanup.py --all-storage --execute --force` guarded by both `--all-storage` and `--execute`.

- [ ] **Step 6: Run cleanup verification**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_cleanup_system.py -q
```

Expected: cleanup tests pass.

## Task 5: Deregister Instance Git Worktrees Before Deleting Runtime Roots

**Files:**

- Modify: `tools/launcher/workspace.sh`
- Modify: `buddyswitch-codex`
- Modify: `scripts/cleanup_buddyswitch.sh`
- Modify: `tests/test_buddyswitch_launcher.py`
- Modify: `tests/test_cleanup_system.py`

- [ ] **Step 1: Add reset worktree deregistration test**

In `tests/test_buddyswitch_launcher.py`, add a test that:

1. Starts a buddy instance with fake Codex and fake browser.
2. Captures the instance workspace path.
3. Runs `./buddyswitch-codex reset --yes`.
4. Runs `git worktree list --porcelain`.
5. Asserts the deleted instance workspace path is not listed.

Use this assertion shape:

```python
            worktrees = subprocess.run(
                ["git", "-C", str(ROOT), "worktree", "list", "--porcelain"],
                text=True,
                capture_output=True,
                check=True,
            ).stdout
            self.assertNotIn(str(workspace_dir), worktrees)
```

- [ ] **Step 2: Add all-storage worktree deregistration coverage**

In `tests/test_cleanup_system.py`, extend the instance all-storage cleanup test to register a real worktree under the temporary shared root and assert cleanup removes it from `git worktree list --porcelain`.

- [ ] **Step 3: Run failing lifecycle tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_reset_removes_registered_instance_worktrees \
  tests/test_cleanup_system.py::CleanupShellIntegrationTests::test_shell_all_storage_cleanup_handles_state_and_instances_without_legacy_workspace \
  -q
```

Expected before implementation: registered worktree metadata remains.

- [ ] **Step 4: Add workspace helper**

In `tools/launcher/workspace.sh`, add:

```bash
buddyswitch_workspace_remove_registered_worktrees_under() {
  local root="$1"
  local repo_root worktree_path

  repo_root="$(buddyswitch_workspace_repo_root)"
  if [[ -z "${root}" || ! -d "${root}" ]]; then
    return 0
  fi

  while IFS= read -r line; do
    case "${line}" in
      worktree\ *)
        worktree_path="${line#worktree }"
        case "${worktree_path}" in
          "${root}" | "${root}/"*)
            git -C "${repo_root}" worktree remove --force "${worktree_path}" >/dev/null 2>&1 || true
            ;;
        esac
        ;;
    esac
  done < <(git -C "${repo_root}" worktree list --porcelain)

  git -C "${repo_root}" worktree prune >/dev/null 2>&1 || true
}
```

- [ ] **Step 5: Call helper before destructive runtime root removal**

In `buddyswitch-codex::reset_shared_env_locked()`, before `rm -rf "${BUDDYSWITCH_SHARED_ROOT}"`, call:

```bash
buddyswitch_workspace_remove_registered_worktrees_under "${BUDDYSWITCH_SHARED_ROOT}"
```

In `scripts/cleanup_buddyswitch.sh`, before `rm -rf "${instance_root}"` for all-storage instance cleanup, call the same helper for the instance root or shared root.

- [ ] **Step 6: Run launcher and cleanup lifecycle tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_buddyswitch_launcher.py tests/test_cleanup_system.py -q
```

Expected: tests pass.

## Task 6: Fail Closed For Projected Snapshot Reads Without Explicit Shared Root

**Files:**

- Modify: `scripts/runtime_store/projections.py`
- Modify: `tests/test_switch_runtime.py`

- [ ] **Step 1: Add no-env projected-state snapshot test**

In `WorkspaceProjectionFacadeTests`, add a test that creates:

```text
<temp>/.codex-buddyswitch/state/buddyswitch/content/runs/
<temp>/.codex-buddyswitch/instances/inst-pm-a/workspace/buddyswitch/content/runs -> state path
```

Patch `workspace_projections.env_store.ROOT` to the instance workspace and remove `BUDDYSWITCH_SHARED_ROOT`.

Hold an exclusive lock on `<temp>/.codex-buddyswitch.lock`, then assert:

```python
with self.assertRaisesRegex(
    workspace_projections.RuntimeSnapshotLockError,
    "could not acquire runtime snapshot lock",
):
    workspace_projections.build_workspace_projection_snapshot()
```

- [ ] **Step 2: Run failing projection test**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_switch_runtime.py::WorkspaceProjectionFacadeTests::test_workspace_projection_snapshot_derives_lock_from_instance_workspace_without_shared_root \
  -q
```

Expected before implementation: snapshot reads without taking the lock.

- [ ] **Step 3: Derive lock path from workspace shape**

In `scripts/runtime_store/projections.py`, update `_runtime_lock_path()`:

1. Keep explicit `BUDDYSWITCH_SHARED_ROOT` behavior unchanged.
2. If `env_store.ROOT` path contains `.codex-buddyswitch/instances/<instance-id>/workspace`, derive shared root as the `.codex-buddyswitch` directory and return `<shared_root>.lock`.
3. If `env_store.ROOT` path contains `.codex-buddyswitch/workspace`, derive shared root as `.codex-buddyswitch` and return `<shared_root>.lock`.
4. If projected state symlinks exist but the shared root cannot be derived, raise `RuntimeSnapshotLockError` instead of yielding unlocked.

Use a small helper:

```python
def _shared_root_from_workspace_root(workspace_root: Path) -> Path | None:
    parts = workspace_root.resolve(strict=False).parts
    if ".codex-buddyswitch" not in parts:
        return None
    index = len(parts) - 1 - list(reversed(parts)).index(".codex-buddyswitch")
    return Path(*parts[: index + 1])
```

- [ ] **Step 4: Run projection and context panel tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_switch_runtime.py::WorkspaceProjectionFacadeTests \
  tests/test_switch_runtime.py::ContextPanelServerTests \
  -q
```

Expected: tests pass. If the context panel HTTP test is blocked by sandbox socket policy, rerun with approved escalation and record it.

## Task 7: Make Reservation Clear Failures Observable

**Files:**

- Modify: `scripts/switch_runtime.py`
- Modify: `tests/test_switch_runtime.py`

- [ ] **Step 1: Add failing reservation unlink test**

Add a test under product-mode persist coverage that patches `_reserved_run_path(run_id).unlink()` to raise `OSError("unlink failed")` during persist after canonical commit.

Expected response:

```json
{
  "ok": true,
  "receipt": {
    "warnings": [
      {
        "code": "W_RUN_RESERVATION_CLEAR_FAILED"
      }
    ]
  }
}
```

Also assert the warning includes `run_id` and `reservation_path`.

- [ ] **Step 2: Run failing persist test**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_switch_runtime.py::ResolveProductModeInputAdapterTests::test_cmd_persist_product_mode_reservation_clear_failure_returns_warning \
  -q
```

Expected before implementation: failure because `_clear_run_reservation()` swallows `OSError`.

- [ ] **Step 3: Return reservation clear result**

Replace `_clear_run_reservation(run_id) -> None` with a helper that returns warning data or raises before commit:

```python
def _clear_run_reservation(run_id: str) -> dict[str, Any] | None:
    path = _reserved_run_path(run_id)
    try:
        if path.exists():
            path.unlink()
    except OSError as exc:
        return {
            "code": "W_RUN_RESERVATION_CLEAR_FAILED",
            "message": f"run reservation could not be cleared: {exc}",
            "run_id": run_id,
            "reservation_path": str(path),
        }
    return None
```

In persist success paths after canonical commit, append the warning to `receipt.warnings[]` when returned. In resolve failure rollback paths where stale reservations would block correctness before commit, convert the warning into a `ValueError` so the failure is visible.

- [ ] **Step 4: Run product-mode runtime tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_switch_runtime.py::ResolveProductModeInputAdapterTests -q
```

Expected: product-mode tests pass.

## Task 8: Reduce Auth Copying While Keeping Instance Config Isolation

**Files:**

- Modify: `tools/launcher/env.sh`
- Modify: `tests/test_buddyswitch_launcher.py`

- [ ] **Step 1: Add auth non-duplication assertion**

In `test_start_with_buddy_wires_instance_env_and_lifecycle`, after resolving `instance_root`, add:

```python
            instance_auth = instance_root / "codex-home" / "auth.json"
            shared_auth = shared_root / "codex-home" / "auth.json"
            self.assertTrue(shared_auth.exists())
            self.assertTrue(instance_auth.exists())
            self.assertFalse(instance_auth.is_file() and not instance_auth.is_symlink())
            self.assertEqual(instance_auth.resolve(), shared_auth.resolve())
```

- [ ] **Step 2: Run failing launcher auth test**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_with_buddy_wires_instance_env_and_lifecycle \
  -q
```

Expected before implementation: instance auth is a copied regular file.

- [ ] **Step 3: Bootstrap shared auth source and symlink per instance**

In `tools/launcher/env.sh`, split auth handling:

1. Always create shared root auth at `${BUDDYSWITCH_SHARED_ROOT}/codex-home/auth.json` from `${BUDDYSWITCH_SOURCE_CODEX_HOME}/auth.json` when missing.
2. In instance mode, create `${BUDDYSWITCH_CODEX_HOME}/auth.json` as a symlink to the shared auth file.
3. Keep `${BUDDYSWITCH_CODEX_HOME}/config.toml` as an instance-local file.

Implementation sketch:

```bash
  local shared_codex_home="${BUDDYSWITCH_SHARED_ROOT}/codex-home"
  mkdir -p "${shared_codex_home}"
  if [[ ! -f "${shared_codex_home}/auth.json" && -f "${BUDDYSWITCH_SOURCE_CODEX_HOME}/auth.json" ]]; then
    cp "${BUDDYSWITCH_SOURCE_CODEX_HOME}/auth.json" "${shared_codex_home}/auth.json"
  fi
  if [[ "${BUDDYSWITCH_CODEX_HOME}" != "${shared_codex_home}" && -f "${shared_codex_home}/auth.json" ]]; then
    rm -f "${BUDDYSWITCH_CODEX_HOME}/auth.json"
    ln -s "${shared_codex_home}/auth.json" "${BUDDYSWITCH_CODEX_HOME}/auth.json"
  fi
```

- [ ] **Step 4: Run launcher auth tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_with_buddy_wires_instance_env_and_lifecycle -q
```

Expected: test passes.

## Task 9: Harden Browser Liveness Checks For Reset And Cleanup

**Files:**

- Modify: `tools/launcher/browser_cockpit.sh`
- Modify: `scripts/cleanup_buddyswitch.sh`
- Modify: `tests/test_buddyswitch_launcher.py`
- Modify: `tests/test_cleanup_system.py`

- [ ] **Step 1: Add reset test for live browser without pid marker**

Add a launcher test that writes `instances/inst-pm-live/instance.json` with `browser_port`, creates a fake endpoint responder or patches fake `curl` to return success for that port, omits `browser/chrome.pid`, then runs `reset --yes`.

Expected:

```python
self.assertEqual(completed.returncode, 3)
self.assertIn("active browser cockpit", completed.stderr)
self.assertTrue(shared_root.exists())
```

- [ ] **Step 2: Add cleanup test for stale pid with no endpoint**

Add cleanup coverage that creates stale `browser/chrome.pid`, no reachable endpoint, and asserts cleanup does not block only because of the stale marker.

- [ ] **Step 3: Run failing browser liveness tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_reset_blocks_live_instance_browser_without_pid_marker \
  tests/test_cleanup_system.py::CleanupShellIntegrationTests::test_shell_cleanup_ignores_stale_instance_browser_pid_without_endpoint \
  -q
```

Expected before implementation: reset misses live endpoint without pid marker.

- [ ] **Step 4: Implement instance browser endpoint scan**

In `tools/launcher/browser_cockpit.sh`, add a function that scans `instances/*/instance.json`, reads `browser_port`, and probes `http://127.0.0.1:<port>/json/version` using the existing browser URL check pattern.

Keep the implementation local and deterministic:

```bash
buddyswitch_browser_any_recorded_instance_endpoint_is_active() {
  local instance_json browser_port
  for instance_json in "${BUDDYSWITCH_SHARED_ROOT}"/instances/*/instance.json; do
    if [[ ! -f "${instance_json}" ]]; then
      continue
    fi
    browser_port="$(python3 - "${instance_json}" <<'PY'
import json, sys
from pathlib import Path
try:
    payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
except Exception:
    raise SystemExit(0)
port = payload.get("browser_port")
if isinstance(port, int):
    print(port)
PY
)"
    if [[ -n "${browser_port}" ]] && curl --silent --show-error --fail "http://127.0.0.1:${browser_port}/json/version" >/dev/null 2>&1; then
      return 0
    fi
  done
  return 1
}
```

Call it from `buddyswitch_browser_is_active()` for shared reset/cleanup checks.

- [ ] **Step 5: Run browser launcher and cleanup tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_buddyswitch_launcher.py tests/test_cleanup_system.py -q
```

Expected: tests pass. If local socket policy blocks endpoint tests, rerun with approved escalation.

## Task 10: Supersede Stale Closeout Plan And Clean Active Resolve Docs

**Files:**

- Modify: `docs/spec_dev/2026-04-24-multi-instance-runtime-checkpoint-closeout-plan.md`
- Modify: `framework/docs/architecture-overview.md`
- Modify: `framework/docs/skill-architecture-best-practices.md`
- Modify: `tests/test_repo_consistency.py`

- [ ] **Step 1: Add stale active-plan guard**

Add a repo consistency test:

```python
    def test_old_multi_instance_closeout_plan_is_marked_superseded(self) -> None:
        text = (
            ROOT
            / "docs"
            / "spec_dev"
            / "2026-04-24-multi-instance-runtime-checkpoint-closeout-plan.md"
        ).read_text(encoding="utf-8").lower()
        self.assertIn("superseded", text)
        self.assertIn("2026-04-26-multi-instance-runtime-convergence-plan.md", text)
```

Add active resolve-doc guard:

```python
    def test_active_framework_docs_use_current_resolve_context_terms(self) -> None:
        active_docs = (
            ROOT / "framework" / "docs" / "architecture-overview.md",
            ROOT / "framework" / "docs" / "skill-architecture-best-practices.md",
        )
        forbidden = (
            "eligible_skills",
            "skill_cards",
            "required_output_schema_by_skill",
            "resolve writes nothing",
        )
        required = (
            "resolve_context.skills",
            "task_context",
            "track_context",
            "run_envelope",
        )
        for path in active_docs:
            with self.subTest(active_doc=str(path.relative_to(ROOT))):
                text = path.read_text(encoding="utf-8").lower()
                for token in forbidden:
                    self.assertNotIn(token, text)
                for token in required:
                    self.assertIn(token, text)
```

- [ ] **Step 2: Run failing stale-doc tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_old_multi_instance_closeout_plan_is_marked_superseded \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_active_framework_docs_use_current_resolve_context_terms \
  -q
```

Expected before docs are fixed: failure on stale closeout plan and old resolve terms.

- [ ] **Step 3: Mark old closeout plan superseded**

At the top of `docs/spec_dev/2026-04-24-multi-instance-runtime-checkpoint-closeout-plan.md`, add:

```markdown
> Superseded - do not execute. Replaced by `docs/spec_dev/2026-04-26-multi-instance-runtime-convergence-plan.md`.
```

Do not rewrite the historical body unless a test requires active wording removal. The superseded banner is enough to prevent execution drift.

- [ ] **Step 4: Update current resolve docs**

In `framework/docs/architecture-overview.md`, replace old resolve fields with:

```markdown
It returns fields such as:

- `skills`
- `task_context`
- `track_context`
- `inputs`
- `run_envelope`
- `warnings`
```

Replace `resolve writes nothing` with:

```markdown
`resolve` does not write final artifact output or run audit content. In create mode it may materialize a zero-run task and reserve the next run envelope so the host has a concrete task/run identity before execution.
```

In `framework/docs/skill-architecture-best-practices.md`, make the same current field-name and create-mode resolve semantics update.

- [ ] **Step 5: Run docs tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_repo_consistency.py -q
```

Expected: repo consistency tests pass.

## Task 11: Final Verification And Checkpoint Review

**Files:**

- Inspect all modified files.
- Do not commit until human confirmation.

- [ ] **Step 1: Run targeted suites**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_repo_consistency.py -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_cleanup_system.py -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_buddyswitch_launcher.py -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_switch_runtime.py -q
```

Expected: all targeted suites pass.

- [ ] **Step 2: Run full suite and diff checks**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider -q
git diff --check
git status --short --branch
git -C /Users/chen/Dev/buddyswitch status --short --branch
```

Expected:

- full suite passes
- `git diff --check` has no output
- worktree shows only intended tracked changes and the pre-existing untracked memo if still present
- main checkout remains `## main...origin/main`

- [ ] **Step 3: Self-review against SHARP**

Check the final diff against this rubric:

- The worktree model was not redesigned.
- Active docs no longer teach singleton workspace product mode.
- Buddy prompts include runtime baseline semantics.
- Cleanup dry-run is non-mutating.
- Current run audits with `switch.buddy_id` are cleaned correctly.
- Runtime root deletion deregisters instance worktrees.
- Projected state snapshot reads do not fail open.
- Reservation clear failures are observable.
- Auth is not duplicated into every instance as a regular file.
- Browser liveness checks do not rely only on pid markers.
- Store authority flattening remains deferred.

## Deferred Work

These items are explicitly not part of this convergence checkpoint:

- Replace full per-instance git worktrees with overlay/symlink workspaces.
- Remove all legacy no-buddy `start` and singleton workspace compatibility.
- Flatten `runtime_store` and `env_store` into one implementation module.
- Build a credential vault or browser supervisor.
- Add instance reuse/resume semantics.
- Add per-instance cleanup APIs.

## Execution Notes

- Prefer small commits by task if the human asks for commits.
- If a test requires local socket binding and fails with `PermissionError: [Errno 1] Operation not permitted`, rerun that exact command with approved escalation rather than changing the test.
- If any task reveals a larger architecture conflict, stop and update this plan instead of adding compatibility wrappers.
